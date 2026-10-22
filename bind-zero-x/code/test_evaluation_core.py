# -*- coding: utf-8 -*-
import unittest
from challenge_contract import freeze_profile
from evaluation_core import (ProtocolError,selective_metrics,validate_challenge,
                             paired_effect,utility_gate,summarize_all_attempts)
PROFILE=freeze_profile({'challenge_id':'Q-001','stimulus_type':'STATIC','revision':'Q-r1',
 'frozen_at_utc':'2026-10-12T00:00:00Z','preflight_approved':True,
 'approved_force_limit_N':5.0,'input_targets':{
 'input_force_N':{'target':2.0,'tolerance':0.2},
 'duration_s':{'target':6.0,'tolerance':0.5}}})

def item(config,method,force=2.0,duration=6.0,outcome=20.0,status='COMPLETED',sheets=7,trial=None):
 return {'configuration_id':config,'trial_id':trial or config+'-'+method,'method':method,'challenge_id':'Q-001',
         'challenge_profile_revision':'Q-r1','challenge_profile_hash':PROFILE['profile_hash'],'material_batch':'T1','fixture_revision':'r1','stimulus_type':'STATIC',
         'input_force_N':force,'duration_s':duration,'job_status':status,
         'original_sheet_count':7,'evaluated_sheet_count':sheets,'total_time_s':outcome}

class EvaluationUnitTests(unittest.TestCase):
 def test_MET_001_unknown_only_not_success(self):
  r=selective_metrics([{'LAYER'},{'ROPE'}],[None,None]);self.assertEqual(r['coverage'],0)
  self.assertIsNone(r['selective_exact_accuracy']);self.assertEqual(r['per_mode']['LAYER']['recall'],0)
 def test_MET_002_micro_coverage(self):
  r=selective_metrics([{'LAYER'},{'KNOT'},set()],[{'LAYER'},None,set()]);self.assertAlmostEqual(r['coverage'],2/3)
  self.assertEqual(r['per_mode']['KNOT']['fn'],1)
 def test_MET_003_false_positive(self):
  r=selective_metrics([set(),{'LAYER'}],[{'LAYER'},{'LAYER'}]);self.assertEqual(r['per_mode']['LAYER']['precision'],.5)
 def test_MET_004_multilabel(self):
  self.assertEqual(selective_metrics([{'LAYER','ROPE'}],[{'LAYER','ROPE'}])['selective_exact_accuracy'],1)
 def test_MET_005_arms_mismatch(self):
  with self.assertRaises(ProtocolError):validate_challenge(item('C1','B'),item('C1','E',force=2.3),PROFILE)
 def test_MET_006_profile_match(self):self.assertTrue(validate_challenge(item('C1','B'),item('C1','E'),PROFILE))
 def test_MET_007_censored_not_silent(self):
  with self.assertRaisesRegex(ProtocolError,'CENSORED'):
   paired_effect([item('C1','B'),item('C1','E',status='ABORTED')],'B','E','total_time_s',PROFILE)
 def test_MET_008_partial_not_complete(self):
  with self.assertRaisesRegex(ProtocolError,'FALSE_COMPLETE_SHEETS'):
   paired_effect([item('C1','B'),item('C1','E',sheets=4)],'B','E','total_time_s',PROFILE)
 def test_MET_009_pair_difference(self):
  r=paired_effect([item('C1','B',outcome=70),item('C1','E',outcome=50)],'B','E','total_time_s',PROFILE)
  self.assertEqual(r['paired_deltas'][0]['delta_treatment_minus_control'],-20)
 def test_MET_010_small_sample_inconclusive(self):
  r=paired_effect([item('C1','B',outcome=70),item('C1','E',outcome=50)],'B','E','total_time_s',PROFILE)
  self.assertTrue(utility_gate(r).startswith('INCONCLUSIVE'))
 def test_MET_011_duplicate_arm(self):
  with self.assertRaisesRegex(ProtocolError,'DUPLICATE_ARM'):
   paired_effect([item('C1','B'),item('C1','B'),item('C1','E')],'B','E','total_time_s',PROFILE)
 def test_MET_012_nan_outcome(self):
  with self.assertRaisesRegex(ProtocolError,'NONFINITE'):
   paired_effect([item('C1','B'),item('C1','E',outcome=float('nan'))],'B','E','total_time_s',PROFILE)
 def test_BLOCKER_04_both_100N_rejected(self):
  with self.assertRaisesRegex(ProtocolError,'TARGET_DEVIATION'):
   validate_challenge(item('C1','B',force=100),item('C1','E',force=100),PROFILE)
 def test_BLOCKER_04B_empty_profile_rejected(self):
  with self.assertRaisesRegex(ProtocolError,'MISSING_FROZEN_PROFILE_HASH'):
   validate_challenge(item('C1','B'),item('C1','E'),{})
 def test_BLOCKER_04C_comparable_wrong_duration(self):
  with self.assertRaisesRegex(ProtocolError,'TARGET_DEVIATION'):
   validate_challenge(item('C1','B',duration=60),item('C1','E',duration=60),PROFILE)
 def test_BLOCKER_04D_missing_target_spec(self):
  with self.assertRaisesRegex(ProtocolError,'MISSING_FROZEN_PROFILE_HASH'):
   validate_challenge(item('C1','B'),item('C1','E'),{'challenge_id':'Q-001','input_targets':{'input_force_N':0.2}})
 def test_MET_017_abort_counted(self):
  r=summarize_all_attempts([item('C1','B'),item('C1','E',status='ABORTED')]);self.assertEqual(r['E']['aborted'],1)
  self.assertEqual(r['E']['completion_rate'],0)
 def test_MET_018_noncompleted_time_not_imputed(self):
  r=summarize_all_attempts([item('C1','E',status='ABORTED',outcome=None)])
  self.assertEqual(r['E']['observed_completed_times_s'],[])
 def test_MET_019_false_complete_rejected(self):
  with self.assertRaisesRegex(ProtocolError,'FALSE_COMPLETE_SHEETS'):
   summarize_all_attempts([item('C1','E',sheets=3)])
if __name__=='__main__':unittest.main(verbosity=2)
