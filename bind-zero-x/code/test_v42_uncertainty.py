import unittest
from measurement_contract import MillimeterMetric,to_layer_observation
from cape_rule_core import choose_rule_action
class UncertaintyTests(unittest.TestCase):
 def test_B42_unc_01_interval_crosses_threshold(self):
  m=MillimeterMetric(5.2,.5,'C','P','O')
  obs=to_layer_observation(m,threshold_mm=5)
  self.assertNotEqual(obs.quality,'VALID')
  self.assertEqual(choose_rule_action(obs).action,'RECAPTURE')
 def test_B42_unc_02_far_above_threshold(self):
  m=MillimeterMetric(8.,.3,'C','P','O')
  self.assertEqual(to_layer_observation(m,threshold_mm=5).quality,'VALID')
 def test_B42_unc_03_bad_threshold(self):
  m=MillimeterMetric(8.,.3,'C','P','O')
  from measurement_contract import MeasurementError
  with self.assertRaises(MeasurementError):to_layer_observation(m,threshold_mm=0)
if __name__=='__main__':unittest.main()
