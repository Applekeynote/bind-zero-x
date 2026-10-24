"""Bounded OpenCV 5 surface segmentation and reviewable shape hypotheses.

These are image regions, not calibrated object instances, dimensions or GT.
The packing guide is independent of the research physical-authorization gate.
"""
import base64
import hashlib
import struct
import cv2
import numpy as np
from packing_completion import complete_surface

PALETTE = ['#61dcb1','#79b7ff','#efb45f','#cb9ef5','#f38c99','#8bd3e1',
           '#c7d76e','#ec9cc7','#8fc4a2','#a8b7fa','#dbac8b','#b7dbed']
MAX_IMAGE_BYTES = 5_000_000


def decode_png(raw):
    if len(raw)>MAX_IMAGE_BYTES or len(raw)<33 or raw[:8]!=b'\x89PNG\r\n\x1a\n' or raw[12:16]!=b'IHDR':
        raise ValueError('PNG_REQUIRED_UP_TO_5_MB')
    width,height=struct.unpack('>II',raw[16:24])
    if not 32<=width<=4096 or not 32<=height<=4096 or width*height>3_000_000:
        raise ValueError('IMAGE_DIMENSIONS_OUT_OF_RANGE')
    image=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
    if image is None or image.shape[:2]!=(height,width):raise ValueError('INVALID_PNG')
    return image


def shape_features(image,mask):
    """Return observable geometry, never a learned confidence probability."""
    contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    contour=max(contours,key=cv2.contourArea)
    x,y,w,h=cv2.boundingRect(contour)
    gray=cv2.cvtColor(image[y:y+h,x:x+w],cv2.COLOR_BGR2GRAY)
    edges=cv2.Canny(gray,55,140)
    inside=cv2.erode(mask[y:y+h,x:x+w],np.ones((7,7),np.uint8))
    edges=cv2.bitwise_and(edges,inside)
    lines=cv2.HoughLinesP(edges,1,np.pi/180,threshold=18,minLineLength=max(12,min(w,h)//4),maxLineGap=7)
    directions=set();vertical=0
    for line in ([] if lines is None else np.asarray(lines).reshape(-1,4)[:160]):
        x1,y1,x2,y2=map(int,line); angle=abs(np.degrees(np.arctan2(y2-y1,x2-x1)))%180
        directions.add(int(angle//30));vertical+=int(65<angle<115)
    compact=min(w,h)/max(w,h)
    (_, _),(rw,rh),angle=cv2.minAreaRect(contour)
    long_axis=(angle+(90 if rh>rw else 0))%180
    edge_fraction=float(np.count_nonzero(edges)/max(1,np.count_nonzero(inside)))
    # Several crease directions inside a compact face suggest retained volume.
    # A single view cannot prove the object is a box, so review remains explicit.
    score=min(1., .38*compact+.13*min(len(directions),4)+.1*min(vertical,2))
    if edge_fraction<.015:score*=.65
    hypothesis='OPEN_BOX_CANDIDATE' if score>=.72 and compact>.45 else 'SHAPE_UNCERTAIN'
    return (x,y,w,h),dict(compactness=round(compact,3),internal_line_directions=len(directions),
        vertical_crease_lines=vertical,edge_fraction=round(edge_fraction,4),geometry_score=round(score,3),
        image_long_axis_degrees=round(long_axis,1),image_long_edge_px=round(max(rw,rh),2),image_short_edge_px=round(min(rw,rh),2)),hypothesis


def segment_cardboard(raw):
    if cv2.__version__.split('.')[0]!='5':raise RuntimeError('OPENCV5_RUNTIME_REQUIRED')
    image=decode_png(raw)
    scale=min(1.,960/max(image.shape[:2]))
    image=cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA)
    h,w=image.shape[:2]
    hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV)
    # Chroma evidence includes colored/pastel sheets, not just brown surfaces.
    # This identifies visible color regions, not semantic cardboard instances.
    mask=cv2.inRange(hsv,np.array([0,30,30]),np.array([179,255,255]))
    lab=cv2.cvtColor(image,cv2.COLOR_BGR2LAB).astype(np.float32)
    border=np.concatenate((lab[:8].reshape(-1,3),lab[-8:].reshape(-1,3),
                           lab[:, :8].reshape(-1,3),lab[:, -8:].reshape(-1,3)))
    background_chroma=np.median(border[:,1:],axis=0)
    chroma_distance=np.linalg.norm(lab[:,:,1:]-background_chroma,axis=2)
    mask[chroma_distance<12]=0
    mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
    mask=cv2.morphologyEx(mask,cv2.MORPH_OPEN,np.ones((3,3),np.uint8))
    smooth=cv2.bilateralFilter(image,7,45,45)
    edges=cv2.Canny(smooth,45,110)
    edges=cv2.dilate(edges,np.ones((3,3),np.uint8))
    interiors=cv2.bitwise_and(mask,cv2.bitwise_not(edges))
    # Separate hue families before seeding so touching different colors survive.
    hue=hsv[:,:,0]
    histogram=np.bincount(hue[mask>0],minlength=180).astype(np.float32)
    circular=np.tile(histogram,3).reshape(1,-1)
    histogram=cv2.GaussianBlur(circular,(9,1),1.5).ravel()[180:360]
    peaks=[]
    for center in np.argsort(histogram)[::-1]:
        if histogram[center]<max(20,np.count_nonzero(mask)*.004):break
        if histogram[center]<histogram[(center-1)%180] or histogram[center]<histogram[(center+1)%180]:continue
        if all(min(abs(int(center)-p),180-abs(int(center)-p))>=8 for p in peaks):peaks.append(int(center))
        if len(peaks)>=8:break
    if peaks:
        hue_distance=np.abs(hue[:,:,None].astype(np.int16)-np.array(peaks))
        families=np.argmin(np.minimum(hue_distance,180-hue_distance),axis=2)
    else:families=np.zeros((h,w),np.uint8)
    diverse=len(peaks)>=3
    seed_masks=[]
    for family in (range(len(peaks)) if diverse else [None]):
        interior=((mask if diverse else interiors)>0).astype(np.uint8)
        if diverse:
            interior[ families!=family ]=0
            interior=cv2.morphologyEx(interior,cv2.MORPH_CLOSE,np.ones((9,9),np.uint8))
        distance=cv2.distanceTransform(interior,cv2.DIST_L2,5)
        peaks=(distance>max(4.,float(distance.max())*.10)).astype(np.uint8)
        count,labels,stats,_=cv2.connectedComponentsWithStats(peaks,8)
        for i in range(1,count):
            area=int(stats[i,cv2.CC_STAT_AREA])
            if area>max(25,w*h*.0004):seed_masks.append((area,labels==i))
    seeds=sorted(seed_masks,key=lambda item:item[0],reverse=True)[:36]
    markers=np.zeros((h,w),np.int32);markers[mask==0]=1
    for index,(_,seed) in enumerate(seeds,2):markers[seed]=index
    if seeds:cv2.watershed(smooth,markers)
    regions_to_review=[((markers==index)&(mask>0)).astype(np.uint8)*255 for index in range(2,len(seeds)+2)]
    algorithm='HSV_CHROMA_HUE_EDGE_MARKER_WATERSHED'
    inner_edges=cv2.bitwise_and(edges,cv2.erode(mask,np.ones((9,9),np.uint8)))
    if not diverse and np.count_nonzero(inner_edges)>max(60,w*h*.001):
        from packing_instances import instance_masks
        regions_to_review=instance_masks(image,mask)
        algorithm='OPENCV5_DNN_EFFICIENTSAM_INSTANCE_HIERARCHY_WATERSHED'
    candidates=[]
    for region in regions_to_review:
        area=int(np.count_nonzero(region))
        if area<w*h*.004:continue
        box,features,kind=shape_features(image,region)
        candidates.append((area,region,box,features,kind))
    candidates.sort(key=lambda item:item[0],reverse=True)
    all_regions=np.zeros((h,w),np.uint8)
    for _,region,*_ in candidates[:12]:all_regions[region>0]=255
    output=image.copy();regions=[];label_map=np.zeros((h,w),np.uint8)
    for number,(area,region,(x,y,rw,rh),features,kind) in enumerate(candidates[:12],1):
        color=PALETTE[number-1];rgb=tuple(int(color[i:i+2],16) for i in (1,3,5));bgr=np.array(rgb[::-1])
        selected=region>0
        output[selected]=(image[selected]*.46+bgr*.54).astype(np.uint8)
        label_map[selected]=number
        contours,_=cv2.findContours(region,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        contour=max(contours,key=cv2.contourArea)
        polygon=np.asarray(cv2.approxPolyDP(contour,max(.65,cv2.arcLength(contour,True)*.0012),True)).reshape(-1,2)
        if len(polygon)>256:polygon=polygon[np.linspace(0,len(polygon)-1,256,dtype=int)]
        all_contours,hierarchy=cv2.findContours(region,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
        holes=[]
        if hierarchy is not None:
            outer=max((i for i,hrow in enumerate(hierarchy.reshape(-1,4)) if hrow[3]<0),key=lambda i:cv2.contourArea(all_contours[i]))
            for i,hrow in enumerate(hierarchy.reshape(-1,4)):
                if hrow[3]!=outer or cv2.contourArea(all_contours[i])<8:continue
                hole=np.asarray(cv2.approxPolyDP(all_contours[i],1.2,True)).reshape(-1,2)[:80]
                holes.append([[round(float(px)/w,5),round(float(py)/h,5)] for px,py in hole])
                if len(holes)>=8:break
        cv2.drawContours(output,[contour],-1,rgb[::-1],2)
        center=cv2.moments(region)
        cx=int(center['m10']/center['m00']);cy=int(center['m01']/center['m00'])
        cv2.rectangle(output,(cx-17,cy-12),(cx+18,cy+9),(27,35,48),-1)
        cv2.putText(output,f'{number:02}',(cx-12,cy+4),cv2.FONT_HERSHEY_SIMPLEX,.45,(245,249,240),1,cv2.LINE_AA)
        regions.append(dict(id=number,color=color,pixel_area=area,area_fraction=round(area/(w*h),4),
            bbox=[round(v,5) for v in (x/w,y/h,rw/w,rh/h)],centroid=[cx/w,cy/h],
            polygon=[[round(float(px)/w,5),round(float(py)/h,5)] for px,py in polygon],
            holes=holes,completion=complete_surface(image,region,cv2.bitwise_and(all_regions,cv2.bitwise_not(region))),
            shape_hypothesis=kind,shape_evidence=features,review_required=True,
            instruction='Fold this box' if kind=='OPEN_BOX_CANDIDATE' else 'Check flat / open'))
    jpeg=cv2.imencode('.jpg',output,[cv2.IMWRITE_JPEG_QUALITY,88])[1].tobytes()
    png=cv2.imencode('.png',label_map)[1].tobytes()
    return dict(schema='BZX-PACKING-VISION-V1',opencv_version=cv2.__version__,
        source_sha256=hashlib.sha256(raw).hexdigest(),width=w,height=h,
        algorithm=algorithm,segmentation_scope='REVIEWABLE_VISIBLE_INSTANCE_PROPOSALS' if 'EFFICIENTSAM' in algorithm else 'VISIBLE_SURFACE_REGIONS_NOT_OBJECT_INSTANCES',
        shape_method='UNCALIBRATED_GEOMETRIC_HEURISTIC',regions=regions,
        overlay='data:image/jpeg;base64,'+base64.b64encode(jpeg).decode(),
        labels_png='data:image/png;base64,'+base64.b64encode(png).decode(),
        physical_action_authorized=False)
