"""Amodal hypotheses stay separate from observed segmentation labels."""
import base64
import cv2
import numpy as np


def complete_surface(image, observed, occluders):
    h,w=observed.shape
    contour=max(cv2.findContours(observed,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0],key=cv2.contourArea)
    rect=cv2.minAreaRect(contour);quad=cv2.boxPoints(rect)
    envelope=np.zeros_like(observed);cv2.fillConvexPoly(envelope,np.rint(quad).astype(np.int32),255)
    # Never fill empty background or turn a different region into observed pixels.
    missing=(envelope>0)&(observed==0)&(occluders>0)
    completed=observed.copy();completed[missing]=255
    exterior=max(cv2.findContours(completed,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0],key=cv2.contourArea)
    polygon=cv2.approxPolyDP(exterior,max(1.,cv2.arcLength(exterior,True)*.004),True).reshape(-1,2)[:96]
    angle=rect[2]+(90 if rect[1][1]>rect[1][0] else 0)
    c,s=np.cos(np.deg2rad(angle)),np.sin(np.deg2rad(angle))
    aligned=np.array([[x*c+y*s,-x*s+y*c] for x,y in quad]);lo=aligned.min(axis=0);hi=aligned.max(axis=0)
    # Find a broad, rectangular panel inside the completed outline. Small holes
    # are ignored for the fold target, but remain holes in the observed texture.
    matrix=np.array([[c,s,-lo[0]],[-s,c,-lo[1]]],np.float32)
    aw,ah=np.maximum(2,np.ceil(hi-lo).astype(int))
    mask=cv2.warpAffine(completed,matrix,(int(aw),int(ah)),flags=cv2.INTER_NEAREST)
    mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((7,7),np.uint8))
    small=cv2.resize(mask,(120,100),interpolation=cv2.INTER_NEAREST)>0
    heights=np.zeros(120,int);best=(0,0,0,120,100)
    for y,row in enumerate(small):
        heights=np.where(row,heights+1,0);stack=[]
        for x in range(121):
            height=int(heights[x]) if x<120 else 0;start=x
            while stack and stack[-1][1]>height:
                left,level=stack.pop();area=(x-left)*level
                if area>best[0]:best=(area,left,y-level+1,x,y+1)
                start=left
            if not stack or stack[-1][1]<height:stack.append((start,height))
    _,x0,y0,x1,y1=best
    # Slightly inset the inferred panel so source edge/slot pixels are not used
    # as load-bearing support. All these dimensions remain user-reviewable.
    x0=(x0+.7)/120*aw;x1=(x1-.7)/120*aw;y0=(y0+.7)/100*ah;y1=(y1-.7)/100*ah
    def inverse(x,y):
        x+=lo[0];y+=lo[1];return [round(float(x*c-y*s)/w,5),round(float(x*s+y*c)/h,5)]
    body=[inverse(x0,y0),inverse(x1,y0),inverse(x1,y1),inverse(x0,y1)]
    rgb=np.median(image[observed>0],axis=0)[::-1].astype(int).tolist()
    return dict(method='OCCLUDER_BOUNDED_ROTATED_ENVELOPE',inferred_pixels=int(missing.sum()),
        inferred_fraction=round(float(missing.sum()/max(1,np.count_nonzero(completed))),4),
        polygon=[[round(float(x)/w,5),round(float(y)/h,5)] for x,y in polygon],
        mask_png='data:image/png;base64,'+base64.b64encode(cv2.imencode('.png',completed)[1]).decode(),
        fill_rgb=rgb,review_required=True,verified=False,
        body_polygon=body,body_long_px=round(float(max(x1-x0,y1-y0)),2),
        body_short_px=round(float(min(x1-x0,y1-y0)),2),image_long_axis_degrees=round(float((angle+(90 if y1-y0>x1-x0 else 0))%180),2))
