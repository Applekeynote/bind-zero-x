"""OpenCV DNN EfficientSAM proposals + hierarchy filtering + edge watershed.

Weights are the SHA-256-verified OpenCV Zoo Apache-2.0 EfficientSAM-Ti export.
This produces reviewable visible-instance proposals, never hidden-object GT.
"""
from pathlib import Path
import hashlib,json,os,threading
import cv2
import numpy as np

MODEL_SHA='4eb496e0a7259d435b49b66faf1754aa45a5c382a34558ddda9a8c6fe5915d77'
CUT='/image_encoder/neck/neck.3/Add_1_output_0'
LOCK=threading.Lock();NETWORKS=None


def model_directory():
    return Path(os.environ.get('BZX_SEGMENTATION_MODEL_DIR',Path(__file__).resolve().parents[1]/'runtime/models'))


def networks():
    global NETWORKS
    if NETWORKS is None:
        cv2.setNumThreads(2)
        directory=model_directory()
        try:
            manifest=json.loads((directory/'efficient-sam-manifest.json').read_text('utf-8'))
            if manifest['source_sha256']!=MODEL_SHA:raise ValueError()
            if set(manifest['files'])!={'efficient-sam-encoder.onnx','efficient-sam-decoder.onnx'}:raise ValueError()
            for name,wanted in manifest['files'].items():
                if name not in {'efficient-sam-encoder.onnx','efficient-sam-decoder.onnx'}:raise ValueError()
                if hashlib.sha256((directory/name).read_bytes()).hexdigest()!=wanted:raise ValueError()
            NETWORKS=tuple(cv2.dnn.readNetFromONNX(np.frombuffer((directory/name).read_bytes(),np.uint8)) for name in ['efficient-sam-encoder.onnx','efficient-sam-decoder.onnx'])
        except (OSError,KeyError,ValueError):raise RuntimeError('SEGMENTATION_MODEL_NOT_READY') from None
    return NETWORKS


def select_instances(proposals):
    candidates=[]
    for mask,score in proposals:
        m=mask.astype(np.uint8).copy()
        contours,_=cv2.findContours(m,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        if not contours:continue
        cv2.drawContours(m,contours,-1,1,-1)
        area=int(m.sum());yy,xx=np.nonzero(m)
        aspect=min(xx.max()-xx.min(),yy.max()-yy.min())/max(1,max(xx.max()-xx.min(),yy.max()-yy.min()))
        if not any(np.count_nonzero(m&o)/max(area,a)>.92 for o,_,a,_ in candidates):candidates.append((m,score,area,aspect))
    valid=[]
    for i,(m,s,a,_) in enumerate(candidates):
        children=[j for j,(o,sc,b,asp) in enumerate(candidates) if j!=i and .15*a<b<.85*a and b>m.size*.025 and sc>.72 and asp>.42 and np.count_nonzero(m&o)/b>.86]
        compound=any(np.count_nonzero(candidates[j][0]&candidates[k][0])/min(candidates[j][2],candidates[k][2])<.20 for ix,j in enumerate(children) for k in children[ix+1:])
        if not compound:valid.append(i)
    maximal=[]
    for i in valid:
        m,s,a,_=candidates[i]
        if any(candidates[j][2]>a*1.2 and candidates[j][1]>s-.35 and np.count_nonzero(m&candidates[j][0])/a>.85 for j in valid if j!=i):continue
        maximal.append(candidates[i])
    maximal.sort(key=lambda p:-(p[1]+.5*np.sqrt(p[2]/p[0].size)));selected=[]
    for p in maximal:
        if any(np.count_nonzero(p[0]&q[0])/min(p[2],q[2])>.65 for q in selected):continue
        selected.append(p)
    # A flap proposal partly overlaps a larger net; retain its pixels with that
    # net instead of advertising each crease as another cardboard object.
    fragments=[]
    for p in selected:
        if any(q is not p and q[2]>p[2]*2 and np.count_nonzero(cv2.dilate(p[0],np.ones((9,9),np.uint8))&q[0])/p[2]>.12 for q in selected):fragments.append(p)
    selected=[p for p in selected if all(p is not q for q in fragments)]
    return selected[:12]


def instance_masks(image,foreground):
    if not LOCK.acquire(blocking=False):raise RuntimeError('SEGMENTATION_BUSY')
    try:
        encoder,decoder=networks();h,w=image.shape[:2]
        rgb=cv2.cvtColor(cv2.resize(image,(1024,1024)),cv2.COLOR_BGR2RGB).astype(np.float32)/255
        encoder.setInput(cv2.dnn.blobFromImage(rgb));embedding=encoder.forward()
        def query(points,values):
            coords=np.zeros((1,1,6,2),np.float32);labels=np.full((1,1,6),-1,np.float32)
            for i,(x,y) in enumerate(points):coords[0,0,i]=[x*1024/w,y*1024/h];labels[0,0,i]=values[i]
            decoder.setInput(embedding,CUT);decoder.setInput(coords,'batched_point_coords');decoder.setInput(labels,'batched_point_labels')
            masks,scores=decoder.forward(['output_masks','iou_predictions'])
            return [(cv2.resize((mask>0).astype(np.uint8),(w,h),interpolation=cv2.INTER_NEAREST),float(sc)) for mask,sc in zip(masks[0,0],scores[0,0])]
        boxes=[]
        for y in np.linspace(h*.25,h*.80,4):
            for x in np.linspace(w*.18,w*.82,5):
                if not foreground[int(y),int(x)]:continue
                for mask,score in query([(x,y)],[1]):
                    area=int(mask.sum())
                    if not .012*w*h<area<.22*w*h or score<.45:continue
                    yy,xx=np.nonzero(mask);bw=xx.max()-xx.min();bh=yy.max()-yy.min();cx=(xx.max()+xx.min())/2;cy=(yy.max()+yy.min())/2
                    if min(bw,bh)/max(1,max(bw,bh))<.35:continue
                    for factor in [1.45,1.85]:
                        box=[max(0,int(cx-bw*factor/2)),max(0,int(cy-bh*factor/2)),min(w,int(cx+bw*factor/2)),min(h,int(cy+bh*factor/2))]
                        if any(max(0,min(box[2],b[2])-max(box[0],b[0]))*max(0,min(box[3],b[3])-max(box[1],b[1]))/max(1,(box[2]-box[0])*(box[3]-box[1]),(b[2]-b[0])*(b[3]-b[1]))>.83 for b in boxes):continue
                        boxes.append(box)
        # Additional overview boxes cover nets whose central panel is hidden.
        for scale in [.34,.48,.64,.80]:
            for fy in [.30,.5,.70]:
                for fx in [.25,.5,.75]:boxes.append([max(0,int((fx-scale/2)*w)),max(0,int((fy-scale/2)*h)),min(w,int((fx+scale/2)*w)),min(h,int((fy+scale/2)*h))])
        proposals=[]
        for x0,y0,x1,y1 in boxes[:90]:
            for mask,score in query([(x0,y0),(x1,y1)],[2,3]):
                area=int(mask.sum())
                if score<.65 or not .025*w*h<area<.38*w*h or np.count_nonzero((mask>0)&(foreground>0))/area<.92:continue
                proposals.append((mask,score))
        selected=select_instances(proposals)
        if not selected:raise RuntimeError('NO_RELIABLE_INSTANCE_PROPOSALS')
        # Re-prompt each proposed object with its own interior and neighbouring
        # object interiors as negatives. This recovers flaps that an initial
        # colour-ambiguous proposal assigned to the sheet underneath.
        centers=[]
        for mask,*_ in selected:
            distance=cv2.distanceTransform(mask,cv2.DIST_L2,5);_,_,_,point=cv2.minMaxLoc(distance);centers.append(point)
        refined=[]
        for index,(mask,score,area,aspect) in enumerate(selected):
            yy,xx=np.nonzero(mask);pad=max(5,int(max(xx.max()-xx.min(),yy.max()-yy.min())*.06))
            bounds=[(max(0,int(xx.min())-pad),max(0,int(yy.min())-pad)),(min(w-1,int(xx.max())+pad),min(h-1,int(yy.max())+pad))]
            point=centers[index];others=sorted([p for j,p in enumerate(centers) if j!=index],key=lambda p:(p[0]-point[0])**2+(p[1]-point[1])**2)[:3]
            options=[]
            for candidate,quality in query(bounds+[point]+others,[2,3,1]+[0]*len(others)):
                size=int(candidate.sum())
                if candidate[point[1],point[0]] and not any(candidate[y,x] for x,y in others) and .5*area<size<1.8*area:
                    options.append((quality+.2*min(1,size/area),candidate))
            if options:mask=np.maximum(mask,max(options,key=lambda p:p[0])[1])
            refined.append((mask,score,area,aspect))
        selected=refined
        # Assign overlapping proposals in image depth order, then grow only
        # within the material foreground. Creases no longer create new IDs.
        selected.sort(key=lambda p:np.nonzero(p[0])[0].mean())
        markers=np.zeros((h,w),np.int32);markers[foreground==0]=1
        for i,(mask,*_) in enumerate(selected,2):
            contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            clean=np.zeros_like(mask);cv2.drawContours(clean,[max(contours,key=cv2.contourArea)],-1,1,-1)
            markers[(cv2.erode(clean,np.ones((7,7),np.uint8))>0)&(foreground>0)]=i
        cv2.watershed(image,markers)
        unknown=(foreground>0)&(markers<=1)
        if unknown.any():
            distances=np.stack([cv2.distanceTransform((markers!=i).astype(np.uint8),cv2.DIST_L2,3) for i in range(2,len(selected)+2)])
            nearest=np.argmin(distances,axis=0)+2;markers[unknown]=nearest[unknown]
        return [((markers==i)&(foreground>0)).astype(np.uint8)*255 for i in range(2,len(selected)+2)]
    finally:LOCK.release()
