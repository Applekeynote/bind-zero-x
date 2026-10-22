import unittest
from research_pipeline import analyze,PipelineError
from test_synthetic_opencv import image_pair
class PipelineTests(unittest.TestCase):
 def calib(self):
  return dict(scale_mm_per_px=.2,plane_id='P',calibration_id='SYNTHETIC-CAL',verified=True)
 def test_PIPE_01_enforces_opencv5_runtime(self):
  a,b,m=image_pair()
  import cv2
  if cv2.__version__.split('.')[0]!='5':
   with self.assertRaisesRegex(PipelineError,'OPENCV5_RUNTIME_REQUIRED'):
    analyze(a,b,m,self.calib(),'O')
 def test_PIPE_02_unit_correct_even_with_slip(self):
  a,b,m=image_pair(slip=(5,0))
  r=analyze(a,b,m,self.calib(),'O',require_opencv5=False)
  self.assertLess(abs(r['measurement']['value_mm']-1.),.3)
  self.assertNotEqual(r['measurement']['value_mm'],5.)
 def test_PIPE_03_no_hidden_knot_assumption(self):
  a,b,m=image_pair()
  r=analyze(a,b,m,self.calib(),'O',require_opencv5=False)
  self.assertNotEqual(r['decision']['action'],'KEEP')
  self.assertIn('ROPE_AND_KNOT_NOT_MEASURED',r['limitations'])
 def test_PIPE_04_no_mask_is_failure(self):
  a,b,m=image_pair()
  with self.assertRaisesRegex(PipelineError,'LAYER_MASKS_REQUIRED'):
   analyze(a,b,{},self.calib(),'O',require_opencv5=False)
 def test_PIPE_05_wrong_calibration_refusal(self):
  a,b,m=image_pair()
  c=self.calib();c['verified']=False
  from measurement_contract import MeasurementError
  with self.assertRaisesRegex(MeasurementError,'UNCALIBRATED'):
   analyze(a,b,m,c,'O',require_opencv5=False)
if __name__=='__main__':unittest.main()
