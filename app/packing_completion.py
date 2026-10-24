"""Occluder-limited outline and texture hypotheses, separate from observed labels."""
import base64
import cv2
import numpy as np


def png(array):
    return 'data:image/png;base64,'+base64.b64encode(cv2.imencode('.png',array)[1]).decode()


def sheet_axis(image, observed, contour):
    # Cross-shaped nets have diagonal minimum-area boxes. Vote with straight
    # creases instead so axes follow the cardboard, not the missing corner.
    edges=cv2.Canny(image,35,95)
    edges[cv2.erode(observed,np.ones((3,3),np.uint8))==0]=0
    x,y,w,h=cv2.boundingRect(contour)
    lines=cv2.HoughLinesP(edges,1,np.pi/180,threshold=18,
        minLineLength=max(15,int(max(w,h)*.13)),maxLineGap=12)
    histogram=np.zeros(90);segments=[]
    for a,b,c,d in ([] if lines is None else lines.reshape(-1,4)):
        length=float(np.hypot(c-a,d-b));angle=float(np.degrees(np.arctan2(d-b,c-a))%90)
        delta=np.abs(np.arange(90)-angle);delta=np.minimum(delta,90-delta)
        histogram+=length**1.5*np.exp(-delta*delta/18)
        segments.append((a,b,c,d,length))
    if histogram.max()>0:return float(np.argmax(histogram)),segments,'CREASE_EDGE_VOTE'
    return float(cv2.minAreaRect(contour)[2]%90),segments,'OUTLINE_FALLBACK'


def complete_surface(image, observed, occluders):
    h,w=observed.shape
    contour=max(cv2.findContours(observed,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0],key=cv2.contourArea)
    angle,segments,axis_method=sheet_axis(image,observed,contour)
    c,s=np.cos(np.deg2rad(angle)),np.sin(np.deg2rad(angle))
    xy=contour.reshape(-1,2).astype(float);aligned=xy@np.array([[c,-s],[s,c]])
    lo=np.floor(aligned.min(axis=0))-2;hi=np.ceil(aligned.max(axis=0))+3
    aw,ah=(hi-lo).astype(int)
    matrix=np.array([[c,s,-lo[0]],[-s,c,-lo[1]]],np.float32);inverse_matrix=cv2.invertAffineTransform(matrix)
    mask=cv2.warpAffine(observed,matrix,(aw,ah),flags=cv2.INTER_NEAREST)
    other=cv2.warpAffine(occluders,matrix,(aw,ah),flags=cv2.INTER_NEAREST)
    photo=cv2.warpAffine(image,matrix,(aw,ah))
    photo[mask==0]=np.median(image[observed>0],axis=0)
    yy,xx=np.nonzero(mask);cx=(xx.min()+xx.max())/2;cy=(yy.min()+yy.max())/2
    grid_y,grid_x=np.indices(mask.shape,dtype=np.float32);mirrored=[]
    for fx,fy in [(True,False),(False,True),(True,True)]:
        mx=(2*cx-grid_x if fx else grid_x).astype(np.float32);my=(2*cy-grid_y if fy else grid_y).astype(np.float32)
        reflected=cv2.remap(mask,mx,my,cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT)
        color=cv2.remap(photo,mx,my,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
        mirrored.append((reflected,color))
    complete=mask.copy();texture=photo.copy();votes=np.zeros(mask.shape,np.uint8)
    for reflected,_ in mirrored:votes+=(reflected>0).astype(np.uint8)
    covered=cv2.dilate(other,np.ones((5,5),np.uint8))>0
    missing=(mask==0)&covered&(votes>0);remaining=missing.copy()
    for reflected,color in mirrored:
        take=remaining&(reflected>0);texture[take]=color[take];remaining[take]=False
    complete[missing]=255
    completed=cv2.warpAffine(complete,inverse_matrix,(w,h),flags=cv2.INTER_NEAREST)
    completed[(observed==0)&(cv2.dilate(occluders,np.ones((5,5),np.uint8))==0)]=0
    completed[observed>0]=255;inferred=(completed>0)&(observed==0)
    texture=cv2.warpAffine(texture,inverse_matrix,(w,h));texture[observed>0]=image[observed>0]
    rgba=cv2.cvtColor(texture,cv2.COLOR_BGR2BGRA);rgba[:,:,3]=completed
    ys,xs=np.nonzero(completed)
    preview=rgba[ys.min():ys.max()+1,xs.min():xs.max()+1]
    exterior=max(cv2.findContours(completed,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0],key=cv2.contourArea)
    polygon=cv2.approxPolyDP(exterior,max(.65,cv2.arcLength(exterior,True)*.0012),True).reshape(-1,2)
    if len(polygon)>256:polygon=polygon[np.linspace(0,len(polygon)-1,256,dtype=int)]
    # Outline shoulders identify the central panel; nearby creases refine it.
    widths=np.count_nonzero(complete,axis=1);heights=np.count_nonzero(complete,axis=0)
    rows=np.flatnonzero(widths>=widths.max()*.78);cols=np.flatnonzero(heights>=heights.max()*.78)
    x0,x1=float(cols.min()),float(cols.max());y0,y1=float(rows.min()),float(rows.max())
    def refine(value,axis,extent):
        options=[]
        for a,b,d,e,length in segments:
            p=matrix@np.array([a,b,1]);q=matrix@np.array([d,e,1])
            if abs(p[axis]-q[axis])<length*.10:
                position=float((p[axis]+q[axis])/2)
                if abs(position-value)<extent*.10:options.append((abs(position-value),-length,position))
        return min(options)[2] if options else value
    x0=refine(x0,0,aw);x1=refine(x1,0,aw);y0=refine(y0,1,ah);y1=refine(y1,1,ah)
    if x1-x0<aw*.20 or y1-y0<ah*.20:x0,x1,y0,y1=xx.min(),xx.max(),yy.min(),yy.max()
    def inverse(x,y):
        px,py=inverse_matrix@np.array([x,y,1]);return [round(float(px)/w,5),round(float(py)/h,5)]
    body=[inverse(x0,y0),inverse(x1,y0),inverse(x1,y1),inverse(x0,y1)]
    return dict(method='CREASE_ALIGNED_OCCLUDER_SYMMETRY',axis_method=axis_method,
        inferred_pixels=int(inferred.sum()),inferred_fraction=round(float(inferred.sum()/max(1,np.count_nonzero(completed))),4),
        polygon=[[round(float(x)/w,5),round(float(y)/h,5)] for x,y in polygon],mask_png=png(completed),texture_png=png(rgba),preview_png=png(preview),
        fill_rgb=np.median(image[observed>0],axis=0)[::-1].astype(int).tolist(),review_required=True,verified=False,
        body_polygon=body,body_long_px=round(float(max(x1-x0,y1-y0)),2),body_short_px=round(float(min(x1-x0,y1-y0)),2),
        full_long_px=round(float(max(xx.max()-xx.min(),yy.max()-yy.min())),2),full_short_px=round(float(min(xx.max()-xx.min(),yy.max()-yy.min())),2),
        outline_axis_degrees=round(float((angle+(90 if yy.max()-yy.min()>xx.max()-xx.min() else 0))%180),2),
        image_long_axis_degrees=round(float((angle+(90 if y1-y0>x1-x0 else 0))%180),2),size_basis='SHARED_IMAGE_PIXELS_NOT_MM')
