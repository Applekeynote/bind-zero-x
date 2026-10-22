# -*- coding: utf-8 -*-
import unittest, json, hashlib
from dataclasses import replace
from unittest.mock import patch
import numpy as np
from witness_planner import (recommend_witness,verify_witness_certificate,
    model_fingerprint_from_payload,WitnessError)
from cape_rule_core import Decision
from decision_gateway import gate_rule_with_witness
from vision_motion_core import estimate_motion
from active_evidence_loop import start_research_loop,continue_research_loop,LoopError,trace_dict

class SemanticProofV45(unittest.TestCase):
 def fixture(self):
  return (['A','B'], {'REORDER':{'A':0,'B':6},'RE_TIE':{'A':6,'B':0},
                    'ABSTAIN':{'A':2,'B':2}},
          {'SIDE':{'A':'left','B':'right'}},{'SIDE':.1})
 def case(self):return recommend_witness(*self.fixture(),observation_id='O',video_sha256='a'*64,calibration_id='C')
 def test_V45_001_semantic_proof_accept(self):self.assertTrue(verify_witness_certificate(self.case()))
 def test_V45_002_forged_direct_action_rejected_even_after_rehash(self):
  w=self.case();p=json.loads(w.certificate_payload)
  p['decision'].update(disposition='DIRECT_ACTION',next_observation=None,recommendation='REORDER')
  raw=json.dumps(p,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
  forged=replace(w,disposition='DIRECT_ACTION',next_observation=None,recommendation='REORDER',
                 certificate_hash=hashlib.sha256(raw.encode()).hexdigest(),certificate_payload=raw)
  self.assertFalse(verify_witness_certificate(forged))
  self.assertEqual(gate_rule_with_witness(Decision('REORDER','X','O'),forged,roi_identity_attested=True).action,'ABSTAIN')
 def test_V45_003_forged_minimax_regret_rejected(self):
  w=self.case();p=json.loads(w.certificate_payload);p['decision']['r0']=0.
  raw=json.dumps(p,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
  fake=replace(w,regret_no_observation=0,certificate_hash=hashlib.sha256(raw.encode()).hexdigest(),certificate_payload=raw)
  self.assertFalse(verify_witness_certificate(fake))
 def test_V45_004_toy_100_loss_direct_rejected(self):
  w=recommend_witness(['A','B'],{'KEEP':{'A':100,'B':100}}, {}, {})
  self.assertEqual(w.disposition,'ABSTAIN')
 def test_V45_005_small_single_world_still_direct_but_not_authorized(self):
  w=recommend_witness(['A'],{'REORDER':{'A':0}}, {}, {},observation_id='O',video_sha256='b'*64,calibration_id='C')
  self.assertEqual(w.disposition,'DIRECT_ACTION')
  g=gate_rule_with_witness(Decision('REORDER','X','O'),w,roi_identity_attested=True,
                           model_calibrated=True,independent_evidence_verified=True)
  self.assertEqual(g.reason,'TRUSTED_EVIDENCE_BINDING_REQUIRED')
 def test_V45_006_trusted_model_and_cv_can_propose_but_cannot_authorize(self):
  w=recommend_witness(['A'],{'REORDER':{'A':0}}, {}, {},observation_id='O',video_sha256='b'*64,calibration_id='C')
  g=gate_rule_with_witness(Decision('REORDER','X','O'),w,roi_identity_attested=True,
                           model_calibrated=True,independent_evidence_verified=True,
                           trusted_model_fingerprint=model_fingerprint_from_payload(w.certificate_payload),
                           expected_video_sha256='b'*64,expected_calibration_id='C')
  self.assertEqual(g.action,'REORDER');self.assertFalse(g.physical_action_authorized)
 def test_V45_007_untrusted_model_pin_mismatch_denied(self):
  w=recommend_witness(['A'],{'REORDER':{'A':0}}, {}, {},observation_id='O',video_sha256='b'*64,calibration_id='C')
  g=gate_rule_with_witness(Decision('REORDER','X','O'),w,roi_identity_attested=True,
                           model_calibrated=True,independent_evidence_verified=True,
                           trusted_model_fingerprint='0'*64,expected_video_sha256='b'*64,expected_calibration_id='C')
  self.assertEqual(g.reason,'TRUSTED_EVIDENCE_BINDING_MISMATCH')
 def test_V45_008_abs_ceiling_invalid_rejected(self):
  with self.assertRaisesRegex(WitnessError,'ABSOLUTE_LOSS_CEILING'):
   recommend_witness(['A'],{'KEEP':{'A':0}}, {}, {},max_acceptable_absolute_loss_units=float('nan'))
 def test_V45_009_inconsistent_model_hash_differs(self):
  w=self.case();p=json.loads(w.certificate_payload);p['losses']['REORDER']['A']=3
  raw=json.dumps(p,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
  self.assertNotEqual(model_fingerprint_from_payload(w.certificate_payload),model_fingerprint_from_payload(raw))

class FlowFailureV45(unittest.TestCase):
 def setUp(self):
  self.im=np.zeros((100,100),np.uint8)
  self.p=np.array([[[i*4.+5,j*4.+5]] for i in range(4) for j in range(4)],dtype=np.float32)
 def flow(self,second):
  with patch('cv2.goodFeaturesToTrack',return_value=self.p),patch('cv2.calcOpticalFlowPyrLK',side_effect=[(self.p.copy(),np.ones((16,1),np.uint8),None),second]):
   return estimate_motion(self.im,self.im,np.full_like(self.im,255))
 def test_V45_010_none_backward(self):self.assertEqual(self.flow((None,None,None))[1],'BACKWARD_FLOW_FAILED')
 def test_V45_011_none_status(self):self.assertEqual(self.flow((self.p.copy(),None,None))[1],'BACKWARD_FLOW_FAILED')
 def test_V45_012_wrong_backward_shape(self):self.assertEqual(self.flow((self.p.reshape(8,2,2),np.ones((16,1),np.uint8),None))[1],'FLOW_SHAPE_INVALID')
 def test_V45_013_nan_tracks(self):
  b=self.p.copy();b[0,0,0]=np.nan
  self.assertEqual(self.flow((b,np.ones((16,1),np.uint8),None))[1],'NONFINITE_FLOW')

class MultiTurnV45(unittest.TestCase):
 def fixture(self):
  return (['A','B'],{'REORDER':{'A':0,'B':6},'RE_TIE':{'A':6,'B':0},'ABSTAIN':{'A':2,'B':2}},
          {'SIDE':{'A':'left','B':'right'}},{'SIDE':.1})
 def start(self):return start_research_loop('S','O',*self.fixture(),initial_image_sha256='a'*64)
 def test_V45_014_start_requests_view(self):self.assertEqual(self.start().witness.next_observation,'SIDE')
 def test_V45_015_new_observation_restricts_hypotheses(self):
  s=continue_research_loop(self.start(),'SIDE','left','b'*64,source='HUMAN_REPORTED')
  self.assertEqual(s.worlds,('A',));self.assertEqual(s.disposition,'DIRECT_ACTION');self.assertFalse(s.approval_authorized)
 def test_V45_016_unknown_result_does_not_reduce_worlds(self):
  s=continue_research_loop(self.start(),'SIDE','?', 'b'*64,source='HUMAN_REPORTED')
  self.assertEqual(s.worlds,('A','B'));self.assertFalse(s.approval_authorized)
 def test_V45_017_wrong_view_rejected(self):
  with self.assertRaisesRegex(LoopError,'UNAUTHORIZED_OR_STALE_VIEW'):
   continue_research_loop(self.start(),'KNOT_CLOSEUP','left','b'*64,source='HUMAN_REPORTED')
 def test_V45_018_same_image_rejected(self):
  with self.assertRaisesRegex(LoopError,'REUSED_IMAGE'):
   continue_research_loop(self.start(),'SIDE','left','a'*64,source='HUMAN_REPORTED')
 def test_V45_019_cv_claim_without_calibration_rejected(self):
  with self.assertRaisesRegex(LoopError,'NOT_CALIBRATED'):
   continue_research_loop(self.start(),'SIDE','layer_moves','b'*64,source='CV_LAYER_ONLY',cv_result={'measurement':{'max_footprint_drift_mm':6}},trusted_cv_validator=lambda *_: True)
 def test_V45_020_cv_path_with_model_consistent_signature(self):
  ws=['A','B'];l={'REORDER':{'A':0,'B':6},'RE_TIE':{'A':6,'B':0},'ABSTAIN':{'A':2,'B':2}}
  s=start_research_loop('S','O',ws,l,{'SIDE':{'A':'layer_moves','B':'layer_still'}},{'SIDE':.1},'a'*64)
  m={'measurement':{'uncertainty_status':'EMPIRICALLY_CALIBRATED','capture_sha256':'b'*64,'max_footprint_drift_mm':7}}
  t=continue_research_loop(s,'SIDE','layer_moves','b'*64,source='CV_LAYER_ONLY',cv_result=m,trusted_cv_validator=lambda *_: True)
  self.assertEqual(t.worlds,('A',));self.assertFalse(trace_dict(t)['physical_action_authorized'])
 def test_V45_021_wrong_cv_signature_rejected(self):
  ws=['A','B'];l={'REORDER':{'A':0,'B':6},'RE_TIE':{'A':6,'B':0},'ABSTAIN':{'A':2,'B':2}}
  s=start_research_loop('S','O',ws,l,{'SIDE':{'A':'layer_moves','B':'layer_still'}},{'SIDE':.1},'a'*64)
  m={'measurement':{'uncertainty_status':'EMPIRICALLY_CALIBRATED','capture_sha256':'b'*64,'max_footprint_drift_mm':7}}
  with self.assertRaisesRegex(LoopError,'CV_SIGNATURE_MISMATCH'):
   continue_research_loop(s,'SIDE','layer_still','b'*64,source='CV_LAYER_ONLY',cv_result=m,trusted_cv_validator=lambda *_: True)
 def test_V45_022_toy_model_provenance_remains_visible(self):
  s=continue_research_loop(self.start(),'SIDE','left','b'*64,source='HUMAN_REPORTED')
  self.assertEqual(trace_dict(s)['scientific_status'],'HYPOTHETICAL_MODEL_NOT_EMPIRICALLY_VALIDATED')

class ExtraTrustBoundaryV45(unittest.TestCase):
 def test_V45_023_untrusted_cv_evidence_never_updates(self):
  ws=['A','B'];losses={'REORDER':{'A':0,'B':6},'RE_TIE':{'A':6,'B':0},'ABSTAIN':{'A':2,'B':2}}
  s=start_research_loop('S','O',ws,losses,{'SIDE':{'A':'layer_moves','B':'layer_still'}},{'SIDE':.1},'a'*64)
  fake={'measurement':{'uncertainty_status':'EMPIRICALLY_CALIBRATED','capture_sha256':'b'*64,'max_footprint_drift_mm':7}}
  with self.assertRaisesRegex(LoopError,'CV_WORKER_ATTESTATION_REQUIRED'):
   continue_research_loop(s,'SIDE','layer_moves','b'*64,source='CV_LAYER_ONLY',cv_result=fake)

class ExtraFlowRobustnessV45(unittest.TestCase):
 def test_V45_024_opencv_exception_becomes_quality_error(self):
  import cv2
  img=np.zeros((100,100),np.uint8)
  pts=np.array([[[i*4.+5,j*4.+5]] for i in range(4) for j in range(4)],np.float32)
  with patch('cv2.goodFeaturesToTrack',return_value=pts),patch('cv2.calcOpticalFlowPyrLK',side_effect=cv2.error('simulated flow error')):
   self.assertEqual(estimate_motion(img,img,np.full_like(img,255))[1],'FLOW_OPENCV_ERROR')
 def test_V45_025_malformed_forward_flow_rejected(self):
  img=np.zeros((100,100),np.uint8)
  pts=np.array([[[i*4.+5,j*4.+5]] for i in range(4) for j in range(4)],np.float32)
  with patch('cv2.goodFeaturesToTrack',return_value=pts),patch('cv2.calcOpticalFlowPyrLK',return_value=(pts[:8],np.ones((16,1),np.uint8),None)):
   self.assertEqual(estimate_motion(img,img,np.full_like(img,255))[1],'FORWARD_FLOW_INVALID')

class IndependentSemanticCheckerV45(unittest.TestCase):
 def test_V45_026_independent_checker_valid(self):
  from independent_witness_checker import check_semantics
  w=recommend_witness(['A','B'],{'REORDER':{'A':0,'B':6},'RE_TIE':{'A':6,'B':0},'ABSTAIN':{'A':2,'B':2}},
                      {'SIDE':{'A':'a','B':'b'}},{'SIDE':.2},observation_id='O')
  self.assertTrue(check_semantics(json.loads(w.certificate_payload)))
  self.assertTrue(verify_witness_certificate(w))
 def test_V45_027_independent_checker_catches_forged_optimal_actions(self):
  from independent_witness_checker import check_semantics
  w=recommend_witness(['A','B'],{'REORDER':{'A':0,'B':6},'RE_TIE':{'A':6,'B':0},'ABSTAIN':{'A':2,'B':2}},
                      {'SIDE':{'A':'a','B':'b'}},{'SIDE':.2},observation_id='O')
  p=json.loads(w.certificate_payload);p['optima']['A']=['ABSTAIN']
  self.assertFalse(check_semantics(p))
