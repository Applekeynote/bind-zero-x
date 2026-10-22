import unittest
from toy_cape_voi import choose_probe_finite,ModelError
class ToyVoITests(unittest.TestCase):
 def fixture(self):
  belief={'L':.5,'K':.5}
  loss={('REORDER','L'):0.,('REORDER','K'):10.,('RETIE','L'):10.,('RETIE','K'):0.}
  good={'VIEW':{'L':[('L','OBS_L',1.)],'K':[('K','OBS_K',1.)]}}
  return belief,loss,good
 def test_TVOI_01_informative_probe(self):
  a,b,c=self.fixture()
  out=choose_probe_finite(a,b,c,{'VIEW':.5},['VIEW'])
  self.assertEqual(out['chosen_probe'],'VIEW');self.assertAlmostEqual(out['baseline_risk'],5.)
 def test_TVOI_02_cost_exceeds_information(self):
  a,b,c=self.fixture()
  self.assertEqual(choose_probe_finite(a,b,c,{'VIEW':6},['VIEW'])['chosen_probe'],'NO_PROBE')
 def test_TVOI_03_physical_transition_can_reverse_benefit(self):
  a,b,c=self.fixture()
  # A probe changes both states to K and reports identical observation. Risk in this
  # contrived example becomes 0 with RETIE; this is *intervention* not information.
  c['VIEW']={'L':[('K','SAME',1.)],'K':[('K','SAME',1.)]}
  out=choose_probe_finite(a,b,c,{'VIEW':1},['VIEW'])
  self.assertEqual(out['chosen_probe'],'VIEW')
  self.assertTrue(out['simulation_only_not_calibrated'])
 def test_TVOI_04_invalid_prior(self):
  a,b,c=self.fixture();a['L']=.6
  with self.assertRaisesRegex(ModelError,'PROBABILITIES_NOT_NORMALIZED'):
   choose_probe_finite(a,b,c,{'VIEW':1},['VIEW'])
 def test_TVOI_05_invalid_transition(self):
  a,b,c=self.fixture();c['VIEW']['K']=[('K','X',.5)]
  with self.assertRaisesRegex(ModelError,'PROBABILITIES_NOT_NORMALIZED'):
   choose_probe_finite(a,b,c,{'VIEW':1},['VIEW'])
 def test_TVOI_06_dangerous_probe_filtered(self):
  a,b,c=self.fixture()
  self.assertEqual(choose_probe_finite(a,b,c,{},[])['chosen_probe'],'NO_PROBE')
 def test_TVOI_07_negative_cost(self):
  a,b,c=self.fixture()
  with self.assertRaisesRegex(ModelError,'INVALID_PROBE_COST'):
   choose_probe_finite(a,b,c,{'VIEW':-5},['VIEW'])
 def test_TVOI_08_unknown_next_state(self):
  a,b,c=self.fixture();c['VIEW']['L']=[('OUT_OF_SCOPE','Y',1.)]
  with self.assertRaisesRegex(ModelError,'UNKNOWN_NEXT_STATE'):
   choose_probe_finite(a,b,c,{'VIEW':.5},['VIEW'])
if __name__=='__main__':unittest.main()
