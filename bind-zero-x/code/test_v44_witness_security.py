# -*- coding: utf-8 -*-
"""v4.4 adversarial regressions: full witness integrity and conservative evidence gate."""
import unittest,hashlib,json
from dataclasses import replace
from witness_planner import (recommend_witness,restrict_worlds_after_view,
    WitnessError,verify_witness_certificate)
from decision_gateway import gate_rule_with_witness
from cape_rule_core import Decision
from failure_interaction_graph import (build_fig,FailureInteractionGraph,EvidenceNode,
    InteractionEdge,GraphError)
from measurement_contract import MillimeterMetric
from test_synthetic_opencv import image_pair
from research_pipeline import analyze

class WitnessSecurityV44(unittest.TestCase):
 def fixture(self):
  ws=['A','B'];losses={'REORDER':{'A':0,'B':5},'RE_TIE':{'A':5,'B':0}}
  sig={'SIDE':{'A':'layer','B':'rope'},'TOP':{'A':'same','B':'same'}}
  cost={'SIDE':1,'TOP':2}
  return ws,losses,sig,cost
 def plan(self):
  return recommend_witness(*self.fixture(),observation_id='OBS',calibration_id='CAL',
                           video_sha256='a'*64,model_version='m1')
 def test_W44_001_ambiguous_optimum_does_not_fabricate_pair(self):
  w=['A','B'];l={'REORDER':{'A':0,'B':1},'RE_TIE':{'A':0,'B':0}}
  o=recommend_witness(w,l,{},{});
  self.assertIsNone(o.counterexample_pair);self.assertIsNone(o.conflict_core)
  self.assertEqual(o.common_optimal_actions,('RE_TIE',))
  self.assertEqual(o.disposition,'DIRECT_ACTION')
 def test_W44_002_tiebreak_has_shared_optimum(self):
  w,l,s,c=self.fixture();l['RE_TIE']['A']=0
  o=recommend_witness(w,l,s,c)
  self.assertEqual(o.common_optimal_actions,('RE_TIE',))
  self.assertIsNone(o.counterexample_pair)
 def test_W44_003_three_way_without_pairwise_disjointness(self):
  w=['A','B','C'];l={'REORDER':{'A':0,'B':3,'C':0},
                     'RE_TIE':{'A':0,'B':0,'C':3},'KEEP':{'A':3,'B':0,'C':0}}
  o=recommend_witness(w,l,{'SIDE':{'A':'a','B':'b','C':'c'}},{'SIDE':.1})
  self.assertIsNone(o.counterexample_pair)
  self.assertEqual(o.conflict_core,('A','B','C'))
 def test_W44_004_pairwise_disjoint_witness(self):
  o=self.plan();self.assertEqual(o.counterexample_pair,('A','B'))
 def test_W44_005_unknown_wildcard_cannot_fake_information(self):
  w,l,s,c=self.fixture();s['SIDE']={'A':'?','B':'rope'}
  o=recommend_witness(w,l,{'SIDE':s['SIDE']},{'SIDE':0})
  self.assertEqual(o.disposition,'ABSTAIN')
 def test_W44_006_unknown_observation_never_shrinks(self):
  w,l,s,c=self.fixture();s['SIDE']={'A':'?','B':'rope'}
  self.assertEqual(restrict_worlds_after_view(w,'SIDE','rope',s),('A','B'))
  self.assertEqual(restrict_worlds_after_view(w,'SIDE','?',s),('A','B'))
 def test_W44_007_explicit_occlusion_is_not_mislabeled_unknown(self):
  w,l,s,c=self.fixture();s['SIDE']={'A':'UNOBSERVABLE','B':'rope'}
  self.assertEqual(restrict_worlds_after_view(w,'SIDE','UNOBSERVABLE',s),('A',))
 def test_W44_008_possible_outcome_set_overlaps_conservatively(self):
  w,l,s,c=self.fixture();s['SIDE']={'A':['rope','layer'],'B':['rope']}
  o=recommend_witness(w,l,{'SIDE':s['SIDE']},{'SIDE':0})
  self.assertEqual(o.disposition,'ABSTAIN')
  self.assertEqual(restrict_worlds_after_view(w,'SIDE','rope',s),('A','B'))
 def test_W44_009_model_falsification_is_explicit(self):
  w,l,s,c=self.fixture()
  with self.assertRaisesRegex(WitnessError,'MODEL_FALSIFIED'):
   restrict_worlds_after_view(w,'SIDE','never',s)
 def test_W44_010_full_hash_includes_unselected_view_cost(self):
  w,l,s,c=self.fixture();a=recommend_witness(w,l,s,c)
  c['TOP']=99
  b=recommend_witness(w,l,s,c)
  self.assertEqual(a.next_observation,b.next_observation)
  self.assertNotEqual(a.certificate_hash,b.certificate_hash)
 def test_W44_011_hash_changes_with_observation_id(self):
  w,l,s,c=self.fixture();a=recommend_witness(w,l,s,c,observation_id='O1');b=recommend_witness(w,l,s,c,observation_id='O2')
  self.assertNotEqual(a.certificate_hash,b.certificate_hash)
 def test_W44_012_hash_changes_with_model_version(self):
  w,l,s,c=self.fixture();a=recommend_witness(w,l,s,c,model_version='m1');b=recommend_witness(w,l,s,c,model_version='m2')
  self.assertNotEqual(a.certificate_hash,b.certificate_hash)
 def test_W44_013_hash_changes_with_video_sha(self):
  w,l,s,c=self.fixture();a=recommend_witness(w,l,s,c,video_sha256='a'*64);b=recommend_witness(w,l,s,c,video_sha256='b'*64)
  self.assertNotEqual(a.certificate_hash,b.certificate_hash)
 def test_W44_014_hash_changes_with_loss_nonopt(self):
  w,l,s,c=self.fixture();a=recommend_witness(w,l,s,c);l['RE_TIE']['A']=8
  self.assertNotEqual(a.certificate_hash,recommend_witness(w,l,s,c).certificate_hash)
 def test_W44_015_hash_can_be_verified(self):
  o=self.plan();self.assertTrue(verify_witness_certificate(o))
  self.assertFalse(verify_witness_certificate(replace(o,certificate_payload=o.certificate_payload+' ')))
 def test_W44_020_forged_field_with_original_hash_rejected(self):
  o=self.plan();fake=replace(o,disposition='DIRECT_ACTION',recommendation='REORDER')
  self.assertFalse(verify_witness_certificate(fake))
  g=gate_rule_with_witness(Decision('REORDER','M','O'),fake,roi_identity_attested=True)
  self.assertEqual(g.reason,'INVALID_WITNESS_CERTIFICATE')
 def test_W44_016_view_without_real_improvement_not_selected(self):
  w,l,s,c=self.fixture();s['SIDE']=dict(s['TOP']);c['SIDE']=0
  self.assertEqual(recommend_witness(w,l,s,c).disposition,'ABSTAIN')
 def test_W44_017_physical_auth_not_granted_by_witness(self):
  w,l,s,c=self.fixture()
  with self.assertRaisesRegex(WitnessError,'WITNESS_CANNOT_AUTHORIZE'):
   recommend_witness(w,l,s,c,physical_action_authorized=True)
 def test_W44_018_unbounded_loss_rejected(self):
  w,l,s,c=self.fixture();l['REORDER']['A']=float('nan')
  with self.assertRaisesRegex(WitnessError,'INVALID_LOSS'):recommend_witness(w,l,s,c)
 def test_W44_019_result_cost_nonnegative_and_finite(self):
  o=self.plan();self.assertEqual(o.risk_after_observation,1.)

class FIGV44(unittest.TestCase):
 def metric(self):return MillimeterMetric(9.,.4,'CAL','P','OBS')
 def graph(self):return build_fig(self.metric(),'OBS')
 def test_FIG44_001_layer_observed_rope_unknown_knot_unknown(self):
  f=self.graph();self.assertEqual(f.missing_channels(),('KNOT_END','ROPE_PATH'))
  self.assertEqual(len(f.edges),2)
 def test_FIG44_002_unknown_never_zero(self):
  f=self.graph();self.assertTrue(all(x.value_mm is None for x in f.nodes if x.state=='UNKNOWN'))
 def test_FIG44_003_hash_changes_on_evidence_update(self):
  f=self.graph();node=EvidenceNode('R01','ROPE_PATH','OBSERVED','OBS',value_mm=4.,plane_id='P',calibration_id='CAL',uncertainty_mm=.1)
  g=f.evolve(node);self.assertNotEqual(f.fingerprint(),g.fingerprint())
  self.assertEqual(g.missing_channels(),('KNOT_END',))
 def test_FIG44_004_rejects_other_obs(self):
  with self.assertRaisesRegex(GraphError,'OBSERVATION_MISMATCH'):
   build_fig(MillimeterMetric(2.,0,'CAL','P','NOT-OBS'),'OBS')
 def test_FIG44_005_uncertain_requires_reason(self):
  with self.assertRaisesRegex(GraphError,'UNAVAILABLE_REQUIRES_REASON'):
   EvidenceNode('L','LAYER_CONTACT','UNCERTAIN','O')
 def test_FIG44_006_reject_dangling_edge(self):
  with self.assertRaisesRegex(GraphError,'DANGLING_EDGE'):
   FailureInteractionGraph((EvidenceNode('L','LAYER_CONTACT','UNKNOWN','O',reason='X'),),
                           (InteractionEdge('L','R','CAN_COINCIDE_NOT_CAUSAL'),))
 def test_FIG44_007_reject_duplicate_node(self):
  a=EvidenceNode('L','LAYER_CONTACT','UNKNOWN','O',reason='X')
  with self.assertRaisesRegex(GraphError,'DUPLICATE_NODE'):
   FailureInteractionGraph((a,a),())

class UnifiedGateV44(unittest.TestCase):
 def request(self):return recommend_witness(*WitnessSecurityV44().fixture())
 def test_GATE44_001_witness_request_blocks_rule_reorder(self):
  g=gate_rule_with_witness(Decision('REORDER','MEASURED','O'),self.request(),roi_identity_attested=True)
  self.assertEqual(g.action,'REQUEST_NONCONTACT_VIEW');self.assertFalse(g.physical_action_authorized)
 def test_GATE44_002_unverified_roi_abstains(self):
  g=gate_rule_with_witness(Decision('REORDER','MEASURED','O'),self.request(),roi_identity_attested=False)
  self.assertEqual(g.action,'ABSTAIN')
 def test_GATE44_003_toy_model_always_blocks_physical(self):
  w=['A'];l={'REORDER':{'A':0}}
  o=recommend_witness(w,l,{},{});
  g=gate_rule_with_witness(Decision('REORDER','M','O'),o,roi_identity_attested=True)
  self.assertEqual(g.action,'ABSTAIN');self.assertEqual(g.reason,'UNCALIBRATED_MODEL')
 def test_GATE44_004_even_calibrated_agreement_not_physical_exec(self):
  o=recommend_witness(['A'],{'REORDER':{'A':0}},{},{},observation_id='O')
  g=gate_rule_with_witness(Decision('REORDER','M','O'),o,roi_identity_attested=True,
                           model_calibrated=True,independent_evidence_verified=True)
  self.assertEqual(g.action,'ABSTAIN');self.assertEqual(g.reason,'TRUSTED_EVIDENCE_BINDING_REQUIRED')
 def test_GATE44_005_disagreement_abstains(self):
  o=recommend_witness(['A'],{'RE_TIE':{'A':0}},{},{},observation_id='O')
  g=gate_rule_with_witness(Decision('REORDER','M','O'),o,roi_identity_attested=True,
                           model_calibrated=True,independent_evidence_verified=True)
  self.assertEqual(g.reason,'TRUSTED_EVIDENCE_BINDING_REQUIRED')
 def test_GATE44_006_tampered_certificate_abstains(self):
  o=self.request();o=replace(o,certificate_hash='0'*64)
  g=gate_rule_with_witness(Decision('REORDER','M','O'),o,roi_identity_attested=True)
  self.assertEqual(g.reason,'INVALID_WITNESS_CERTIFICATE')
 def test_GATE44_007_main_pipeline_respects_witness(self):
  import hashlib
  a,b,m=image_pair(slip=(9,0))
  manifest=dict(operator_verified=True,frame0_sha256=hashlib.sha256(a.tobytes()).hexdigest(),
     layers={key:dict(mask_sha256=hashlib.sha256(mask.tobytes()).hexdigest(),layer_label=key,source_id=key)
             for key,mask in m.items()})
  result=analyze(a,b,m,dict(scale_mm_per_px=1.,plane_id='P',calibration_id='SIM',verified=True),
                 'OBS',require_opencv5=False,roi_manifest=manifest)
  self.assertEqual(result['decision']['action'],'REQUEST_NONCONTACT_VIEW')
  self.assertEqual(result['decision']['research_candidate_only'],'REORDER')
  self.assertFalse(result['decision']['physical_action_authorized'])
  self.assertIn('ROPE_PATH',result['fig_missing_channels'])
  from witness_planner import verify_witness_certificate
  self.assertEqual(hashlib.sha256(result['research_witness']['certificate_payload'].encode()).hexdigest(),
                   result['research_witness']['certificate_hash'])
 def test_GATE44_009_stale_witness_different_observation_abstains(self):
  o=recommend_witness(['A'],{'REORDER':{'A':0}},{},{},observation_id='OLD')
  g=gate_rule_with_witness(Decision('REORDER','M','NEW'),o,roi_identity_attested=True,
                           model_calibrated=True,independent_evidence_verified=True)
  self.assertEqual(g.reason,'STALE_WITNESS_OBSERVATION')
 def test_GATE44_010_unbound_evidence_cannot_authorize(self):
  o=recommend_witness(['A'],{'REORDER':{'A':0}},{},{})
  g=gate_rule_with_witness(Decision('REORDER','M','O'),o,roi_identity_attested=True,
                           model_calibrated=True,independent_evidence_verified=True)
  self.assertEqual(g.reason,'UNBOUND_WITNESS_CANNOT_APPROVE')
 def test_GATE44_011_image_content_binds_certificate(self):
  a,b,m=image_pair(slip=(3,0));x=analyze(a,b,m,dict(scale_mm_per_px=1.,plane_id='P',calibration_id='SIM',verified=True),'O',require_opencv5=False)
  a,b,m=image_pair(slip=(4,0));y=analyze(a,b,m,dict(scale_mm_per_px=1.,plane_id='P',calibration_id='SIM',verified=True),'O',require_opencv5=False)
  self.assertNotEqual(x['research_witness']['certificate_hash'],y['research_witness']['certificate_hash'])
 def test_GATE44_008_tracking_sigma_not_falsely_calibrated(self):
  a,b,m=image_pair(slip=(9,0))
  result=analyze(a,b,m,dict(scale_mm_per_px=1.,plane_id='P',calibration_id='SIM',verified=True),
                 'OBS',require_opencv5=False)
  self.assertIsNone(result['measurement']['sigma_mm'])
  self.assertIn('NOT_CALIBRATED',result['measurement']['uncertainty_status'])
  self.assertIn('upper',result['measurement']['tracking_p90_error_px_by_layer'])

if __name__=='__main__':unittest.main(verbosity=2)
