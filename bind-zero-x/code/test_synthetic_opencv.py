# -*- coding: utf-8 -*-
"""BIND ZERO-X v4: OpenCV synthetic-image regression (not OpenCV5/physical validation).
Run: python code/test_synthetic_opencv.py
Fixed seed, deterministic geometric GT, no camera or human samples.
"""
import math
import unittest
import numpy as np
import cv2

SIZE=950
CENTERS={'upper':(425,295),'lower':(450,650)}


def tile(center,seed):
    rng=np.random.default_rng(seed)
    layer=np.zeros((SIZE,SIZE),dtype=np.uint8)
    mask=np.zeros_like(layer)
    cx,cy=center
    x0,y0=cx-112,cy-75
    x1,y1=cx+112,cy+75
    cv2.rectangle(mask,(x0,y0),(x1,y1),255,-1)
    cv2.rectangle(layer,(x0,y0),(x1,y1),80,-1)
    cv2.rectangle(layer,(x0+3,y0+3),(x1-3,y1-3),195,2)
    for _ in range(95):
        x=int(rng.integers(x0+10,x1-10)); y=int(rng.integers(y0+10,y1-10))
        v=int(rng.integers(160,255))
        cv2.circle(layer,(x,y),int(rng.integers(2,5)),v,-1)
    return layer,mask


def mat(theta_deg=0,tx=0,ty=0,center=(0,0)):
    m=cv2.getRotationMatrix2D(center,theta_deg,1.0).astype(np.float64)
    m[:,2]+=np.array([tx,ty])
    return m


def homogeneous(m):return np.vstack([m,[0.0,0.0,1.0]])


def image_pair(theta=0,tx=0,ty=0,slip=(0,0),local_rotation=0,occlude=False,scale_fault=1):
    frame0=np.full((SIZE,SIZE),25,np.uint8)
    frame1=np.full_like(frame0,25)
    masks=[]
    w=homogeneous(mat(theta,tx,ty,center=(SIZE/2,SIZE/2)))
    for idx,(name,center) in enumerate(CENTERS.items()):
        lay,mask=tile(center,100+idx)
        frame0[mask>0]=lay[mask>0]
        masks.append(mask)
        if name=='upper':
            s=homogeneous(mat(local_rotation,slip[0],slip[1],center=center))
            if scale_fault!=1:
                sc=cv2.getRotationMatrix2D(center,0,scale_fault)
                s=s@homogeneous(sc)
            h=w@s
        else:h=w
        warped=cv2.warpAffine(lay,h[:2],(SIZE,SIZE),flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_CONSTANT,borderValue=25)
        wm=cv2.warpAffine(mask,h[:2],(SIZE,SIZE),flags=cv2.INTER_NEAREST)
        frame1[wm>0]=warped[wm>0]
    if occlude:
        cv2.rectangle(frame1,(260,190),(610,405),25,-1)
    return frame0,frame1,dict(zip(CENTERS,masks))


from vision_motion_core import estimate_motion,metric_from_pair


class SyntheticVisionTests(unittest.TestCase):
    def require_meas(self,**kwargs):
        a,b,m=image_pair(**kwargs)
        result,err=metric_from_pair(a,b,m)
        self.assertIsNone(err,str(err));self.assertIsNotNone(result)
        return result
    def test_SCV_001_common_translation(self):
        r=self.require_meas(tx=17,ty=-8);self.assertLess(r['max_anchor_drift_px'],0.8)
    def test_SCV_002_common_rotation(self):
        r=self.require_meas(theta=12);self.assertLess(r['max_anchor_drift_px'],1.0)
    def test_SCV_003_common_rotation_translation(self):
        r=self.require_meas(theta=-9,tx=13,ty=7);self.assertLess(r['max_anchor_drift_px'],1.0)
    def test_SCV_004_true_five_pixel_slip(self):
        r=self.require_meas(slip=(5,0));self.assertLess(abs(r['center_drift_px']-5),1.0)
    def test_SCV_005_slip_under_camera_motion(self):
        r=self.require_meas(theta=8,tx=10,ty=-12,slip=(5,0));self.assertLess(abs(r['center_drift_px']-5),1.15)
    def test_SCV_006_ten_pixel_slip(self):
        r=self.require_meas(slip=(0,10));self.assertLess(abs(r['center_drift_px']-10),1.1)
    def test_SCV_007_relative_rotation(self):
        r=self.require_meas(local_rotation=8);self.assertLess(abs(r['relative_angle_deg']+8),1.0)
    def test_SCV_008_occlusion_abstention(self):
        a,b,m=image_pair(occlude=True);r,err=metric_from_pair(a,b,m)
        self.assertIsNone(r);self.assertIsNotNone(err)
    def test_SCV_009_scale_is_rejected(self):
        a,b,m=image_pair(scale_fault=1.12);r,err=metric_from_pair(a,b,m)
        self.assertIsNone(r);self.assertIsNotNone(err)
    def test_SCV_010_no_visible_features(self):
        a,b,m=image_pair();m['upper'][:]=0;r,err=metric_from_pair(a,b,m)
        self.assertIsNone(r);self.assertEqual(err,'NO_FEATURES')

if __name__=='__main__':
    print('Synthetic CV verification: local OpenCV',cv2.__version__,'(not OpenCV5 verified)')
    unittest.main(verbosity=2)
