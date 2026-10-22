# -*- coding: utf-8 -*-
import unittest
from witness_planner import recommend_witness,restrict_worlds_after_view,WitnessError

class BINDWitnessTests(unittest.TestCase):
 def example(self):
  worlds=['LAYER_SLIP','ROPE_SLIP']
  losses={'REORDER':{'LAYER_SLIP':0.,'ROPE_SLIP':5.},
          'REPOSITION_TWINE':{'LAYER_SLIP':5.,'ROPE_SLIP':0.}}
  signature={'SIDE':{'LAYER_SLIP':'layer_moves','ROPE_SLIP':'rope_moves'},
             'TOP':{'LAYER_SLIP':'same','ROPE_SLIP':'same'}}
  return worlds,losses,signature
 def test_WIT_001_conflicting_decisions_produce_witness(self):
  ws,l,s=self.example();r=recommend_witness(ws,l,s,{'SIDE':1.,'TOP':1.})
  self.assertEqual(r.disposition,'REQUEST_NONCONTACT_VIEW');self.assertEqual(r.next_observation,'SIDE')
  self.assertEqual(set(r.counterexample_pair),set(ws))
 def test_WIT_002_uninformative_view_not_requested(self):
  ws,l,s=self.example();r=recommend_witness(ws,l,{'TOP':s['TOP']},{'TOP':1.})
  self.assertEqual(r.disposition,'ABSTAIN')
 def test_WIT_003_costlier_than_regret_abstains(self):
  ws,l,s=self.example();r=recommend_witness(ws,l,s,{'SIDE':6.,'TOP':1.})
  self.assertEqual(r.disposition,'ABSTAIN')
 def test_WIT_004_one_world_direct_action(self):
  ws,l,s=self.example();l={a:{'LAYER_SLIP':v['LAYER_SLIP']} for a,v in l.items()}
  r=recommend_witness(['LAYER_SLIP'],l,{},{});self.assertEqual(r.disposition,'DIRECT_ACTION')
  self.assertEqual(r.recommendation,'REORDER')
 def test_WIT_005_same_good_action_no_view(self):
  ws,l,s=self.example();l['REORDER']['ROPE_SLIP']=0
  r=recommend_witness(ws,l,s,{'SIDE':0.1});self.assertEqual(r.disposition,'DIRECT_ACTION')
 def test_WIT_006_invalid_missing_loss_rejected(self):
  ws,l,s=self.example();del l['REORDER']['ROPE_SLIP']
  with self.assertRaisesRegex(WitnessError,'INCOMPLETE_LOSS_TABLE'):recommend_witness(ws,l,s,{'SIDE':1})
 def test_WIT_007_nan_cost_rejected(self):
  ws,l,s=self.example()
  with self.assertRaisesRegex(WitnessError,'INVALID_VIEW_COST'):recommend_witness(ws,l,s,{'SIDE':float('nan')})
 def test_WIT_008_evidence_update(self):
  ws,l,s=self.example()
  self.assertEqual(restrict_worlds_after_view(ws,'SIDE','layer_moves',s),('LAYER_SLIP',))
 def test_WIT_009_model_falsified_not_forced(self):
  ws,l,s=self.example()
  with self.assertRaisesRegex(WitnessError,'MODEL_FALSIFIED'):restrict_worlds_after_view(ws,'SIDE','knot_moves',s)
 def test_WIT_010_unknown_view_not_admitted(self):
  ws,l,s=self.example();s['DANGEROUS_SHAKE']={w:w for w in ws}
  r=recommend_witness(ws,l,s,{'SIDE':2.,'DANGEROUS_SHAKE':0})
  self.assertNotEqual(r.next_observation,'DANGEROUS_SHAKE')
 def test_WIT_011_view_cost_reduces_advantage(self):
  ws,l,s=self.example();r=recommend_witness(ws,l,s,{'SIDE':2.5})
  self.assertEqual(r.risk_after_observation,2.5)
 def test_WIT_012_repeatable_certificate(self):
  ws,l,s=self.example();a=recommend_witness(ws,l,s,{'SIDE':1});b=recommend_witness(ws[::-1],l,s,{'SIDE':1})
  self.assertEqual(a.certificate_hash,b.certificate_hash)
 def test_WIT_013_bad_signatures_rejected(self):
  ws,l,s=self.example();s['SIDE'].pop('ROPE_SLIP')
  with self.assertRaisesRegex(WitnessError,'INVALID_VIEW_SIGNATURE'):recommend_witness(ws,l,s,{'SIDE':1})
 def test_WIT_014_zero_information_stop(self):
  ws,l,s=self.example();s['SIDE']=dict(s['TOP'])
  self.assertEqual(recommend_witness(ws,l,s,{'SIDE':0.}).disposition,'ABSTAIN')
if __name__=='__main__':unittest.main()
