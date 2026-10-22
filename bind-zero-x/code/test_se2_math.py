# coding: utf-8
"""BIND ZERO-X v3.1: SE(2) mathematical regression tests.
Only tests ideal 2D rigid transforms; NOT physical calibration/OpenCV/AWS verification.
Run: python BIND_ZERO_X_v3.1_SE2相対運動_実行テスト.py
"""
import math
import unittest
from dataclasses import dataclass

@dataclass(frozen=True)
class SE2:
    """Pose: p_world = R(theta)*p_local + t; translation in mm, angle in radians."""
    theta: float
    tx: float
    ty: float

    def __post_init__(self):
        if not all(map(math.isfinite, (self.theta, self.tx, self.ty))):
            raise ValueError('NONFINITE_TRANSFORM')

    def apply(self, point):
        c,s=math.cos(self.theta),math.sin(self.theta)
        x,y=point
        return (c*x-s*y+self.tx, s*x+c*y+self.ty)

    def compose(self, other):
        """self @ other: left-to-right coordinate transform application."""
        x,y=self.apply((other.tx,other.ty))
        return SE2(self.theta+other.theta,x,y)

    def inverse(self):
        c,s=math.cos(self.theta),math.sin(self.theta)
        return SE2(-self.theta,-c*self.tx-s*self.ty, s*self.tx-c*self.ty)


def relative_pose(pose_i,pose_j):
    """Transform i-local points into j-local coordinates at the same instant."""
    return pose_j.inverse().compose(pose_i)


def drift_at_anchor(i0,j0,i1,j1,anchor_i=(0.0,0.0)):
    t0=relative_pose(i0,j0)
    t1=relative_pose(i1,j1)
    x0,y0=t0.apply(anchor_i)
    x1,y1=t1.apply(anchor_i)
    return math.hypot(x1-x0,y1-y0)


def relative_rotation_delta(i0,j0,i1,j1):
    a0=relative_pose(i0,j0).theta
    a1=relative_pose(i1,j1).theta
    return math.atan2(math.sin(a1-a0),math.cos(a1-a0))


def detect_relative_motion(i0,j0,i1,j1,anchors=((0,0),(20,0),(0,10)),tol=1e-9):
    if not anchors:
        raise ValueError('NO_ANCHORS')
    displacements=[drift_at_anchor(i0,j0,i1,j1,p) for p in anchors]
    angle=relative_rotation_delta(i0,j0,i1,j1)
    return {'max_anchor_drift_mm':max(displacements),
            'relative_angle_rad':angle,
            'no_relative_rigid_motion':max(displacements)<=tol and abs(angle)<=tol}

class TestSE2(unittest.TestCase):
    def setUp(self):
        self.i0=SE2(0,10,0)
        self.j0=SE2(0,0,0)

    def assertPoseNear(self,a,b,tol=1e-9):
        for q in ((0,0),(5,3),(-4,11)):
            p1=a.apply(q);p2=b.apply(q)
            self.assertLess(math.dist(p1,p2),tol)

    def test_MATH_016_common_90_degree_rotation(self):
        w=SE2(math.pi/2,0,0)
        i1=w.compose(self.i0);j1=w.compose(self.j0)
        out=detect_relative_motion(self.i0,self.j0,i1,j1)
        self.assertTrue(out['no_relative_rigid_motion'])
        self.assertLess(out['max_anchor_drift_mm'],1e-9)

    def test_MATH_017_common_translation_and_rotation(self):
        w=SE2(math.radians(37),24,-9)
        result=detect_relative_motion(self.i0,self.j0,w.compose(self.i0),w.compose(self.j0))
        self.assertTrue(result['no_relative_rigid_motion'])

    def test_MATH_018_only_top_layer_rotates(self):
        i1=self.i0.compose(SE2(math.radians(12),0,0))
        self.assertAlmostEqual(relative_rotation_delta(self.i0,self.j0,i1,self.j0),math.radians(12))

    def test_MATH_019_only_bottom_layer_rotates(self):
        j1=self.j0.compose(SE2(math.radians(-7),0,0))
        self.assertAlmostEqual(relative_rotation_delta(self.i0,self.j0,self.i0,j1),math.radians(7))

    def test_MATH_020_common_movement_plus_five_mm_slip(self):
        w=SE2(math.radians(25),13,-7)
        i1=w.compose(self.i0).compose(SE2(0,5,0))
        j1=w.compose(self.j0)
        self.assertAlmostEqual(drift_at_anchor(self.i0,self.j0,i1,j1),5.0)

    def test_MATH_021_zero_center_translation_still_sees_angle(self):
        origin=SE2(0,0,0)
        rotation=SE2(math.radians(30),0,0)
        self.assertAlmostEqual(drift_at_anchor(origin,origin,rotation,origin),0.0)
        self.assertAlmostEqual(relative_rotation_delta(origin,origin,rotation,origin),math.radians(30))

    def test_single_layer_translation(self):
        i1=self.i0.compose(SE2(0,5,0))
        self.assertAlmostEqual(drift_at_anchor(self.i0,self.j0,i1,self.j0),5)

    def test_common_translation(self):
        w=SE2(0,8,5)
        self.assertTrue(detect_relative_motion(self.i0,self.j0,w.compose(self.i0),w.compose(self.j0))['no_relative_rigid_motion'])

    def test_general_pose_inverse(self):
        p=SE2(math.radians(137),100,-48)
        self.assertPoseNear(p.inverse().compose(p),SE2(0,0,0))

    def test_no_anchor_rejected(self):
        with self.assertRaisesRegex(ValueError,'NO_ANCHORS'):
            detect_relative_motion(self.i0,self.j0,self.i0,self.j0,anchors=())

    def test_nonfinite_rejected(self):
        with self.assertRaisesRegex(ValueError,'NONFINITE'):
            SE2(float('nan'),0,0)

    def test_invariant_under_common_left_multiplication_randomized(self):
        # Deterministic exhaustive checks across 10 angle combinations x translations.
        for deg in [-170,-90,-45,0,15,45,90,125,179]:
            for tx,ty in [(-9,0),(0,0),(20,-11)]:
                w=SE2(math.radians(deg),tx,ty)
                self.assertTrue(detect_relative_motion(self.i0,self.j0,w.compose(self.i0),w.compose(self.j0))['no_relative_rigid_motion'])

    def test_se2_group_relative_equality_under_common_motion(self):
        w=SE2(math.radians(112),3,6)
        before=relative_pose(self.i0,self.j0)
        after=relative_pose(w.compose(self.i0),w.compose(self.j0))
        self.assertPoseNear(before,after)

if __name__=='__main__':
    unittest.main(verbosity=2)
