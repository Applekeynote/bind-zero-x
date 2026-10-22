# coding: utf-8
"""OpenCV motion estimator for expert-provided masks; NO automatic segmentation.
Pure CV core: motion is in pixel coordinates until explicitly calibrated.
"""
import math
import numpy as np
import cv2

def validate_distinct_layer_rois(frame0,masks):
    """Reject duplicated/overlapping expert ROIs. Non-overlap is necessary, never proof of true layer ID."""
    if not isinstance(masks,dict) or set(masks)!={'upper','lower'}:return 'LAYER_MASKS_REQUIRED'
    for name in ('upper','lower'):
        mask=masks[name]
        if not isinstance(mask,np.ndarray) or mask.shape!=frame0.shape:return 'INVALID_LAYER_ROI_SHAPE'
        if mask.dtype!=np.uint8:return 'INVALID_LAYER_ROI_DTYPE'
    a=masks['upper']>0;b=masks['lower']>0
    if not a.any() or not b.any():return None  # Preserve NO_FEATURES behavior at estimator
    if np.array_equal(a,b):return 'LAYER_ROI_NOT_INDEPENDENT'
    overlap=int(np.count_nonzero(a&b))
    if overlap>0 and overlap/min(np.count_nonzero(a),np.count_nonzero(b))>0.01:
        return 'LAYER_ROI_OVERLAP_AMBIGUOUS'
    return None

def estimate_motion(frame0,frame1,mask,min_inliers=12):
    try:
        points=cv2.goodFeaturesToTrack(frame0,maxCorners=120,qualityLevel=0.015,
                                       minDistance=5,mask=mask,blockSize=5)
    except cv2.error:
        return None,'FEATURE_OPENCV_ERROR'
    if points is None or len(points)<min_inliers:return None,'NO_FEATURES'
    try:
        nxt,status,_=cv2.calcOpticalFlowPyrLK(frame0,frame1,points,None,
                                                winSize=(19,19),maxLevel=3,
                                                criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,35,0.015))
        if nxt is None or status is None:return None,'FLOW_FAILED'
        if not isinstance(nxt,np.ndarray) or nxt.shape!=points.shape or not np.isfinite(nxt).all():
            return None,'FORWARD_FLOW_INVALID'
        back,back_status,_=cv2.calcOpticalFlowPyrLK(frame1,frame0,nxt,None,
                                                      winSize=(19,19),maxLevel=3)
    except cv2.error:
        return None,'FLOW_OPENCV_ERROR'
    # Both flow passes can fail independently; never dereference a missing
    # backward status or feed malformed tracks into RANSAC.
    n=len(points)
    if back is None or back_status is None:
        return None,'BACKWARD_FLOW_FAILED'
    if any(not isinstance(a,np.ndarray) or a.size!=n for a in (status,back_status)):
        return None,'FLOW_STATUS_INVALID'
    if any(not isinstance(a,np.ndarray) or a.shape!=(n,1,2) for a in (nxt,back)):
        return None,'FLOW_SHAPE_INVALID'
    if not np.isfinite(nxt).all() or not np.isfinite(back).all():
        return None,'NONFINITE_FLOW'
    keep=(status.ravel()==1)&(back_status.ravel()==1)
    fb=np.linalg.norm(points.reshape(-1,2)-back.reshape(-1,2),axis=1)
    keep &= fb<1.3
    p0=points.reshape(-1,2)[keep];p1=nxt.reshape(-1,2)[keep]
    if len(p0)<min_inliers:return None,'INSUFFICIENT_TRACKS'
    try:
        affine,inlier=cv2.estimateAffinePartial2D(p0,p1,method=cv2.RANSAC,
                                                   ransacReprojThreshold=1.5,
                                                   maxIters=2500,confidence=0.995)
    except cv2.error:
        return None,'AFFINE_OPENCV_ERROR'
    if affine is None:return None,'AFFINE_FAILED'
    scale=math.hypot(affine[0,0],affine[1,0])
    if abs(scale-1)>0.025:return None,'NONRIGID_SCALE'
    if inlier is None or int(np.sum(inlier))<min_inliers:return None,'INSUFFICIENT_INLIERS'
    theta=math.atan2(affine[1,0],affine[0,0]); c,s=math.cos(theta),math.sin(theta)
    r=np.array([[c,-s],[s,c]])
    q0=p0[inlier.ravel()==1].astype(np.float64)
    q1=p1[inlier.ravel()==1].astype(np.float64)
    t=np.median(q1-q0@r.T,axis=0)
    residual=np.linalg.norm(q1-(q0@r.T+t),axis=1)
    if np.quantile(residual,0.90)>1.5:return None,'HIGH_REPROJECTION_ERROR'
    h=np.eye(3);h[:2,:2]=r;h[:2,2]=t
    return h,{'tracks':len(q0),'p90_error_px':float(np.quantile(residual,.9)),
              'unconstrained_scale':scale}


def metric_from_pair(frame0,frame1,masks):
    invalid=validate_distinct_layer_rois(frame0,masks)
    if invalid is not None:return None,invalid
    transforms={}
    fit_quality={}
    for key,mask in masks.items():
        h,status=estimate_motion(frame0,frame1,mask)
        if h is None:return None,status
        transforms[key]=h
        fit_quality[key]=status
    # The initial local coordinate frames are indexed by image pixels at t0.
    # Common left multiplications cancel; relative transform is in lower-layer t0 frame.
    relative=np.linalg.inv(transforms['lower'])@transforms['upper']
    theta=math.degrees(math.atan2(relative[1,0],relative[0,0]))
    ys,xs=np.nonzero(masks['upper']>0)
    if len(xs)==0:return None,'NO_UPPER_MASK'
    cx,cy=float(np.mean(xs)),float(np.mean(ys))
    # For a rigid transform, ||T(x)-x|| is convex in x. Its maximum over a
    # finite ROI is attained at a vertex of its convex hull. The old code used
    # axis-aligned bounding-box corners, which could lie OUTSIDE a diamond ROI
    # and inflate the reported maximum by >40%. This uses only actual ROI
    # pixels for the support points, not an imaginary rectangular footprint.
    upper=(masks['upper']>0).astype(np.uint8)
    cv_points=cv2.findNonZero(upper)
    if cv_points is None:return None,'NO_UPPER_MASK'
    try:
        hull=cv2.convexHull(cv_points).reshape(-1,2).astype(float)
    except cv2.error:
        return None,'INVALID_ROI_CONVEX_HULL'
    if hull.shape[0]==0 or not np.isfinite(hull).all():
        return None,'INVALID_ROI_CONVEX_HULL'
    sample=np.vstack((np.array([[cx,cy]],float),hull))
    homogeneous=np.column_stack([sample,np.ones(len(sample))]).T
    pos=relative@homogeneous
    displacement=np.linalg.norm(pos[:2]-homogeneous[:2],axis=0)
    return {'max_anchor_drift_px':float(np.max(displacement)),
            'center_drift_px':float(displacement[0]),
            'relative_angle_deg':theta,'upper_footprint_anchor_count':int(sample.shape[1]),
            'roi_assignment':'EXPERT_ROI_UNVERIFIED_BY_CV',
            'max_drift_domain':'VISIBLE_T0_UPPER_MASK_PIXELS_NOT_HIDDEN_LAYER',
            'tracking_p90_error_px_by_layer':{k:v['p90_error_px'] for k,v in fit_quality.items()},
            'min_tracks_by_layer':{k:v['tracks'] for k,v in fit_quality.items()}},None

