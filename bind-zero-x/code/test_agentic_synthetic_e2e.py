# coding: utf-8
"""Synthetic-only vertical slice: cv2 optical flow -> SE(2) relative motion -> rule action -> human approval.
No OpenCV 5 runtime, no physical object, no AWS deployment; GT scale is SYNTHETIC.
"""
import unittest
from test_synthetic_opencv import image_pair,metric_from_pair
from cape_rule_core import Observation,choose_rule_action,Session,approval_event,confirm_human_execution,ActionError
from measurement_contract import PixelMetric,PlaneCalibration,px_to_mm,to_layer_observation,MeasurementError

class AgenticSyntheticE2ETests(unittest.TestCase):
 def scaled(self,m,oid='SCAN-X',scale=1.0):
  q=PixelMetric(m['center_drift_px'],'IMAGE_T0','SYNTHETIC_PLANE',oid)
  c=PlaneCalibration(scale,'SYNTHETIC_PLANE','SIMULATED-SCALE-NOT-GT',True)
  d=px_to_mm(q,c)
  return Observation(oid,'VALID',d.value_mm,0.,0.) # explicitly synthetic rope/knot GT=0; never real-world default
 def run_cv(self,**kwargs):
  a,b,m=image_pair(**kwargs)
  metrics,error=metric_from_pair(a,b,m)
  return metrics,error
 def test_E2E_001_common_motion_no_invasive_action(self):
  m,e=self.run_cv(theta=8,tx=9,ty=4)
  self.assertIsNone(e)
  d=choose_rule_action(self.scaled(m,'SCAN-A'),threshold_mm=3.0)
  self.assertEqual(d.action,'KEEP')
 def test_E2E_002_measured_slip_drives_reorder_and_approval(self):
  m,e=self.run_cv(theta=8,tx=9,ty=-7,slip=(6,0))
  self.assertIsNone(e)
  d=choose_rule_action(self.scaled(m,'SCAN-B'),threshold_mm=3.0)
  self.assertEqual(d.action,'REORDER')
  s=Session(session_id='S1',owner_sub='user-1',planned_action_id=d.action,
            planned_observation_id=d.source_observation_id,
            region_rules_verified=True,safety_preflight_ok=True)
  approved=approval_event(s,d.action,'idem-1',0,'SCAN-B','user-1')
  self.assertEqual(approved.state,'APPROVED')
  with self.assertRaisesRegex(ActionError,'NOT_AUTHORIZED'):
   confirm_human_execution(approved,d.action,'user-2',1)
  executed=confirm_human_execution(approved,d.action,'user-1',1)
  self.assertEqual(executed.state,'OUTCOME_PENDING')
  self.assertEqual(executed.probe_count,0)
 def test_E2E_005_units_4px_is_not_4mm(self):
  m,e=self.run_cv(slip=(4,0))
  self.assertIsNone(e)
  d=choose_rule_action(self.scaled(m,'SCALE-0.2',.2),threshold_mm=3.)
  self.assertNotEqual(d.action,'REORDER')
 def test_E2E_006_missing_calibration_rejected(self):
  with self.assertRaisesRegex(MeasurementError,'UNCALIBRATED'):
   px_to_mm(PixelMetric(4,'IMAGE_T0','P','S'),PlaneCalibration(.2,'P','MISSING',False))
 def test_E2E_003_occluded_image_cannot_authorize(self):
  m,e=self.run_cv(occlude=True)
  self.assertIsNone(m)
  d=choose_rule_action(Observation('SCAN-O','LOW',None,None,None))
  self.assertEqual(d.action,'RECAPTURE')
  self.assertFalse(d.human_approval_required)
 def test_E2E_004_wrong_observation_cannot_be_reused(self):
  m,e=self.run_cv(slip=(6,0))
  self.assertIsNone(e)
  d=choose_rule_action(self.scaled(m,'SCAN-1'),threshold_mm=3.)
  self.assertEqual(d.action,'REORDER')
  s=Session(planned_action_id=d.action,planned_observation_id='SCAN-1',
            region_rules_verified=True,safety_preflight_ok=True)
  with self.assertRaisesRegex(ActionError,'STALE_OR_UNISSUED_PLAN'):
   approval_event(s,d.action,'k',0,'SCAN-OLD','DEMO-OWNER')

if __name__=='__main__':unittest.main(verbosity=2)
