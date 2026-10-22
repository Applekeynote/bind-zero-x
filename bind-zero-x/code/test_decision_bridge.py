# coding: utf-8
import unittest
from decision_bridge import illustrative_witness_for_layer_evidence
from test_synthetic_opencv import image_pair
from research_pipeline import analyze
class WitnessBridgeTests(unittest.TestCase):
 def test_BRIDGE_001_fault_drives_rope_path_view(self):
  r=illustrative_witness_for_layer_evidence(8.,0.)
  self.assertEqual(r['next_observation'],'ROPE_PATH')
  self.assertEqual(r['disposition'],'REQUEST_NONCONTACT_VIEW')
 def test_BRIDGE_002_no_detected_layer_fault_changes_next_view(self):
  a=illustrative_witness_for_layer_evidence(0,0)
  b=illustrative_witness_for_layer_evidence(8,0)
  self.assertNotEqual(a['next_observation'],b['next_observation'])
 def test_BRIDGE_003_relative_rotation_changes_view(self):
  r=illustrative_witness_for_layer_evidence(0.,8.)
  self.assertEqual(r['next_observation'],'ROPE_PATH')
 def test_BRIDGE_004_always_marks_uncalibrated(self):
  r=illustrative_witness_for_layer_evidence(0,0)
  self.assertFalse(r['physical_action_authorized'])
  self.assertIn('UNCALIBRATED',r['status'])
 def test_BRIDGE_005_from_CV_to_witness(self):
  def run(slip):
   a,b,m=image_pair(slip=slip)
   r=analyze(a,b,m,dict(scale_mm_per_px=1.,plane_id='P',calibration_id='SYNTHETIC',verified=True),
             'SYNTHETIC-O',require_opencv5=False,threshold_mm=5.)
   self.assertIsNotNone(r['measurement'])
   return r
  stable=run((0,0))
  shifted=run((9,0))
  self.assertNotEqual(stable['research_witness']['next_observation'],shifted['research_witness']['next_observation'])
  self.assertFalse(shifted['research_witness']['physical_action_authorized'])
if __name__=='__main__':unittest.main()
