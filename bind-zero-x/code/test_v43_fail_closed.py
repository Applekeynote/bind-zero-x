# coding: utf-8
import hashlib,unittest
from research_pipeline import analyze
from test_synthetic_opencv import image_pair
class PipelineFailClosedTests(unittest.TestCase):
 def calib(self):return dict(scale_mm_per_px=1.,plane_id='P',calibration_id='SIMULATED_CAL',verified=True)
 def manifest(self,frame,masks):
  return dict(operator_verified=True,frame0_sha256=hashlib.sha256(frame.tobytes()).hexdigest(),
       layers={k:dict(mask_sha256=hashlib.sha256(m.tobytes()).hexdigest(),layer_label=k,source_id='LAB_'+k)
               for k,m in masks.items()})
 def test_SAFE_001_correct_motion_but_no_ROI_identity_means_no_action(self):
  a,b,m=image_pair(slip=(9,0))
  out=analyze(a,b,m,self.calib(),'O',require_opencv5=False)
  self.assertEqual(out['decision']['action'],'ABSTAIN')
  self.assertEqual(out['decision']['research_candidate_only'],'REORDER')
 def test_SAFE_002_operator_attested_roi_can_offer_human_approval(self):
  a,b,m=image_pair(slip=(9,0))
  out=analyze(a,b,m,self.calib(),'O',require_opencv5=False,roi_manifest=self.manifest(a,m))
  self.assertEqual(out['decision']['action'],'REQUEST_NONCONTACT_VIEW')
  self.assertEqual(out['decision']['research_candidate_only'],'REORDER')
  self.assertFalse(out['decision']['physical_action_authorized'])
 def test_SAFE_003_false_identity_no_unreviewed_physical_action(self):
  a,b,m=image_pair(slip=(9,0));m['lower']=m['upper'].copy()
  out=analyze(a,b,m,self.calib(),'O',require_opencv5=False)
  self.assertEqual(out['decision']['action'],'RECAPTURE')
if __name__=='__main__':unittest.main()
