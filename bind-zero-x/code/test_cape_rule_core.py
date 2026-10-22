# -*- coding: utf-8 -*-
import unittest
from cape_rule_core import (Observation,Session,ActionError,choose_rule_action,approval_event,
                            confirm_human_execution,mark_probe_completed)
class RuleTests(unittest.TestCase):
 def o(self,**kwargs):
  d={'observation_id':'O1','quality':'VALID','layer_slip_mm':0,'rope_shift_mm':0,'knot_slip_mm':0}
  d.update(kwargs);return Observation(**d)
 def session(self,action='REORDER',**kwargs):
  d=dict(planned_action_id=action,planned_observation_id='O1',region_rules_verified=True,
         safety_preflight_ok=True)
  d.update(kwargs);return Session(**d)
 def approve(self,s=None,action='REORDER',key='k1',version=0,oid='O1',owner='DEMO-OWNER'):
  return approval_event(s or self.session(action=action),action,key,version,oid,owner)
 def test_RULE_001_keep_observed(self):self.assertEqual(choose_rule_action(self.o()).action,'KEEP')
 def test_RULE_002_knot_slip_retie(self):self.assertEqual(choose_rule_action(self.o(knot_slip_mm=7)).action,'RE_TIE')
 def test_RULE_003_layer_slip_reorder(self):self.assertEqual(choose_rule_action(self.o(layer_slip_mm=7)).action,'REORDER')
 def test_RULE_004_all_unknown(self):self.assertEqual(choose_rule_action(self.o(layer_slip_mm=None,rope_shift_mm=None,knot_slip_mm=None)).action,'RECAPTURE')
 def test_RULE_005_recapture_limit(self):self.assertEqual(choose_rule_action(self.o(quality='LOW'),1).action,'ABSTAIN')
 def test_RULE_006_rope_knot_unknown(self):self.assertEqual(choose_rule_action(self.o(rope_shift_mm=7,knot_slip_mm=None)).action,'PROBE_KNOT')
 def test_RULE_007_only_keep_not_allowed(self):self.assertEqual(choose_rule_action(self.o(layer_slip_mm=9),allowed={'KEEP'}).action,'ABSTAIN')
 def test_RULE_008_nonfinite(self):
  for v in (float('nan'),float('inf'),float('-inf'),-1):
   with self.assertRaisesRegex(ActionError,'INVALID_METRIC'):choose_rule_action(self.o(layer_slip_mm=v))
 def test_RULE_009_approval_not_execution(self):
  a=self.approve();self.assertEqual(a.state,'APPROVED')
  with self.assertRaisesRegex(ActionError,'UNAPPROVED_ACTION'):confirm_human_execution(a,'RE_TIE','DEMO-OWNER',1)
  self.assertEqual(confirm_human_execution(a,'REORDER','DEMO-OWNER',1).state,'OUTCOME_PENDING')
 def test_RULE_010_idempotent_same_payload(self):
  a=self.approve();self.assertEqual(approval_event(a,'REORDER','k1',0,'O1','DEMO-OWNER'),a)
 def test_RULE_011_stale_version(self):
  a=self.approve()
  with self.assertRaisesRegex(ActionError,'VERSION_CONFLICT'):self.approve(a,'RE_TIE','k2',0)
 def test_RULE_012_probe_limit(self):
  s=self.session(action='PROBE_KNOT',state='OUTCOME_PENDING',approved_action_id='PROBE_KNOT',probe_count=2,version=2,accepted_observation_ids=frozenset({'O2'}))
  with self.assertRaisesRegex(ActionError,'PROBE_LIMIT'):mark_probe_completed(s,'O2','DEMO-OWNER',2)
 def test_BLOCKER_01_rope_only_never_keep(self):
  r=choose_rule_action(self.o(rope_shift_mm=7,knot_slip_mm=0));self.assertEqual(r.action,'REPOSITION_TWINE')
 def test_BLOCKER_01B_rope_disallowed_abstains(self):
  r=choose_rule_action(self.o(rope_shift_mm=7,knot_slip_mm=0),allowed={'KEEP'});self.assertEqual(r.action,'ABSTAIN')
 def test_BLOCKER_01C_multi_mode_not_blind(self):
  self.assertEqual(choose_rule_action(self.o(layer_slip_mm=9,rope_shift_mm=7)).action,'ABSTAIN')
 def test_BLOCKER_01D_partial_unknown_not_keep(self):
  self.assertNotEqual(choose_rule_action(self.o(knot_slip_mm=None)).action,'KEEP')
 def test_BLOCKER_02_arbitrary_unissued_action(self):
  with self.assertRaisesRegex(ActionError,'ACTION_NOT_ALLOWLISTED'):
   self.approve(action='UNSAFE_UNLISTED_ACTION')
 def test_BLOCKER_02B_allowed_but_not_issued(self):
  with self.assertRaisesRegex(ActionError,'STALE_OR_UNISSUED_PLAN'):
   self.approve(self.session(action='REORDER'),action='RE_TIE')
 def test_BLOCKER_02C_wrong_observation(self):
  with self.assertRaisesRegex(ActionError,'STALE_OR_UNISSUED_PLAN'):self.approve(oid='O2')
 def test_BLOCKER_02D_other_owner(self):
  with self.assertRaisesRegex(ActionError,'NOT_AUTHORIZED'):self.approve(owner='OTHER')
 def test_BLOCKER_02E_constraints_unverified(self):
  with self.assertRaisesRegex(ActionError,'UNVERIFIED_CONSTRAINTS'):self.approve(s=self.session(safety_preflight_ok=False))
 def test_BLOCKER_03_reused_key_other_body(self):
  a=self.approve()
  with self.assertRaisesRegex(ActionError,'IDEMPOTENCY_KEY_REUSE_CONFLICT'):
   self.approve(a,action='RE_TIE',key='k1')
 def test_BLOCKER_03B_reused_key_wrong_owner(self):
  a=self.approve()
  with self.assertRaisesRegex(ActionError,'NOT_AUTHORIZED'):
   self.approve(a,key='k1',owner='OTHER')
 def test_BLOCKER_03C_replay_after_advance(self):
  a=self.approve();e=confirm_human_execution(a,'REORDER','DEMO-OWNER',1)
  with self.assertRaisesRegex(ActionError,'REPLAY_RESULT_FROM_IDEMPOTENCY_STORE'):
   self.approve(e,key='k1')
 def test_RULE_024_terminal_action_denied(self):
  with self.assertRaisesRegex(ActionError,'TERMINAL_STATE'):
   self.approve(self.session(state='ABORTED'))
 def test_RULE_025_no_forged_execution(self):
  with self.assertRaisesRegex(ActionError,'UNAPPROVED_ACTION'):
   confirm_human_execution(self.session(),'REORDER','DEMO-OWNER',0)
 def test_RULE_026_no_probe_w_o_evidence(self):
  s=self.session(action='PROBE_KNOT',state='OUTCOME_PENDING',approved_action_id='PROBE_KNOT',version=2,accepted_observation_ids=frozenset({'O2'}))
  with self.assertRaisesRegex(ActionError,'MISSING_OUTCOME_OBSERVATION'):mark_probe_completed(s,None,'DEMO-OWNER',2)
 def test_RULE_027_completed_probe_unique(self):
  s=self.session(action='PROBE_KNOT',state='OUTCOME_PENDING',approved_action_id='PROBE_KNOT',version=2,accepted_observation_ids=frozenset({'O2'}))
  t=mark_probe_completed(s,'O2','DEMO-OWNER',2)
  self.assertEqual((t.probe_count,t.state),(1,'PLAN_READY'))
  with self.assertRaisesRegex(ActionError,'INVALID_STATE'):mark_probe_completed(t,'O2','DEMO-OWNER',3)
 def test_RULE_029_probe_limit_selects_abstain(self):
  d=choose_rule_action(self.o(rope_shift_mm=7,knot_slip_mm=None),probe_count=2)
  self.assertEqual(d.action,'ABSTAIN')
 def test_RULE_030_unverified_probe_evidence(self):
  s=self.session(action='PROBE_KNOT',state='OUTCOME_PENDING',approved_action_id='PROBE_KNOT',version=2)
  with self.assertRaisesRegex(ActionError,'UNVERIFIED_OUTCOME_OBSERVATION'):
   mark_probe_completed(s,'O2','DEMO-OWNER',2)
 def test_RULE_028_retie_cannot_increment_probe(self):
  s=self.session(action='RE_TIE',state='OUTCOME_PENDING',approved_action_id='RE_TIE',version=2)
  with self.assertRaisesRegex(ActionError,'NOT_A_DIAGNOSTIC_PROBE'):mark_probe_completed(s,'O2','DEMO-OWNER',2)
if __name__=='__main__':unittest.main(verbosity=2)
