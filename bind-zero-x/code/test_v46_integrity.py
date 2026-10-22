# -*- coding: utf-8 -*-
"""Additional adversarial checks for the v4.6 research chain."""
import hashlib,json,os,sqlite3,tempfile,unittest
from sqlite_scope import connect
from dataclasses import replace
from unittest.mock import patch
import cv2
import numpy as np
from active_evidence_loop import (start_research_loop,continue_research_loop,
    validate_loop,trace_dict,LoopError)
from research_loop_store import SQLiteResearchLoops,StoreError,encode,decode
from vision_motion_core import estimate_motion
from witness_planner import recommend_witness


def sample_inputs():
    return (['A','B'],
        {'REORDER':{'A':0,'B':6},'RE_TIE':{'A':6,'B':0},'ABSTAIN':{'A':2,'B':2}},
        {'SIDE':{'A':'left','B':'right'}},{'SIDE':0.1})

def sample_loop(budget=2):
    return start_research_loop('S','OBS',*sample_inputs(),'a'*64,view_budget=budget)

class ModelBindingV46(unittest.TestCase):
    def test_V46_001_client_loss_dict_mutation_does_not_change_loop(self):
        worlds,losses,views,costs=sample_inputs()
        s=start_research_loop('S','OBS',worlds,losses,views,costs,'a'*64)
        losses['REORDER']['A']=900
        self.assertEqual(s.losses['REORDER']['A'],0)
        self.assertTrue(validate_loop(s))
    def test_V46_002_client_view_prediction_mutation_detached(self):
        worlds,losses,views,costs=sample_inputs()
        s=start_research_loop('S','OBS',worlds,losses,views,costs,'a'*64)
        views['SIDE']['A']='right';costs['SIDE']=999
        self.assertEqual(s.view_signatures['SIDE']['A'],'left')
        self.assertEqual(s.view_costs['SIDE'],0.1)
    def test_V46_003_inplace_loss_tamper_refused(self):
        s=sample_loop();s.losses['REORDER']['A']=100
        with self.assertRaisesRegex(LoopError,'PINNED_MODEL_MISMATCH'):
            continue_research_loop(s,'SIDE','left','b'*64,source='HUMAN_REPORTED')
    def test_V46_004_inplace_view_signature_tamper_refused(self):
        s=sample_loop();s.view_signatures['SIDE']['A']='right'
        with self.assertRaisesRegex(LoopError,'PINNED_MODEL_MISMATCH'):validate_loop(s)
    def test_V46_005_forged_model_fingerprint_cannot_keep_old_proof(self):
        s=sample_loop();s.losses['REORDER']['A']=100
        from active_evidence_loop import _fingerprint
        s=replace(s,model_fingerprint=_fingerprint(s))
        with self.assertRaisesRegex(LoopError,'CURRENT_CERTIFICATE_MODEL_MISMATCH'):
            validate_loop(s)
    def test_V46_006_mismatched_worlds_rejected(self):
        s=sample_loop()
        with self.assertRaises(LoopError):validate_loop(replace(s,worlds=('A',)))
    def test_V46_007_mismatched_witness_rejected(self):
        s=sample_loop()
        w=recommend_witness(['A'],{'REORDER':{'A':0}}, {}, {})
        with self.assertRaises(LoopError):validate_loop(replace(s,witness=w))
    def test_V46_008_valid_advanced_history_reconstructed(self):
        s=continue_research_loop(sample_loop(),'SIDE','left','b'*64,source='HUMAN_REPORTED')
        self.assertTrue(validate_loop(s));self.assertEqual(s.worlds,('A',))
    def test_V46_009_forged_step_worlds_rejected(self):
        s=continue_research_loop(sample_loop(),'SIDE','left','b'*64,source='HUMAN_REPORTED')
        fake=replace(s.steps[0],worlds_after=('A','B'))
        with self.assertRaises(LoopError):validate_loop(replace(s,steps=(fake,)))
    def test_V46_010_forged_step_signature_rejected(self):
        s=continue_research_loop(sample_loop(),'SIDE','left','b'*64,source='HUMAN_REPORTED')
        fake=replace(s.steps[0],signature='right')
        with self.assertRaises(LoopError):validate_loop(replace(s,steps=(fake,)))
    def test_V46_011_hash_only_wrong_step_rejected(self):
        s=continue_research_loop(sample_loop(),'SIDE','left','b'*64,source='HUMAN_REPORTED')
        with self.assertRaises(LoopError):validate_loop(replace(s,steps=(replace(s.steps[0],after_certificate_hash='0'*64),)))
    def test_V46_012_zero_view_budget_no_false_request(self):
        s=sample_loop(0)
        self.assertEqual(s.disposition,'ABSTAIN');self.assertIsNone(trace_dict(s)['next_view'])
    def test_V46_013_zero_budget_followup_rejected(self):
        s=sample_loop(0)
        with self.assertRaisesRegex(LoopError,'BUDGET'):
            continue_research_loop(s,'SIDE','left','b'*64,source='HUMAN_REPORTED')
    def test_V46_014_direct_abstain_is_terminal(self):
        w=recommend_witness(['A'],{'ABSTAIN':{'A':0}}, {}, {})
        self.assertEqual(w.disposition,'ABSTAIN')
    def test_V46_015_trace_never_authorizes(self):
        s=sample_loop()
        self.assertFalse(trace_dict(s)['physical_action_authorized'])
    def test_V46_016_cv_unverified_rejected(self):
        s=sample_loop()
        with self.assertRaisesRegex(LoopError,'ATTESTATION'):
            continue_research_loop(s,'SIDE','?', 'b'*64,source='CV_UNCALIBRATED',cv_result={})
    def test_V46_017_uncalibrated_cv_does_not_shrink_worlds(self):
        s=sample_loop()
        m={'measurement':{'uncertainty_status':'NOT_CALIBRATED_UNCERTAINTY_NOT_ZERO'}}
        t=continue_research_loop(s,'SIDE','?', 'b'*64,source='CV_UNCALIBRATED',
            cv_result=m,trusted_cv_validator=lambda *_:True)
        self.assertEqual(t.worlds,('A','B'))
        self.assertFalse(t.approval_authorized)
    def test_V46_018_uncalibrated_cv_diagnostic_assertion_rejected(self):
        s=sample_loop()
        m={'measurement':{'uncertainty_status':'NOT_CALIBRATED_UNCERTAINTY_NOT_ZERO'}}
        with self.assertRaisesRegex(LoopError,'CANNOT_CLASSIFY'):
            continue_research_loop(s,'SIDE','left','b'*64,source='CV_UNCALIBRATED',
                cv_result=m,trusted_cv_validator=lambda *_:True)
    def test_V46_019_encode_decode_roundtrip(self):
        s=sample_loop()
        self.assertEqual(decode(encode(s)),s)
    def test_V46_020_decoded_bad_model_rejected(self):
        s=sample_loop();d=json.loads(encode(s));d['losses']['REORDER']['A']=999
        with self.assertRaises(StoreError):decode(json.dumps(d))
    def test_V46_021_history_replay_roundtrip(self):
        s=continue_research_loop(sample_loop(),'SIDE','left','b'*64,source='HUMAN_REPORTED')
        self.assertEqual(decode(encode(s)),s)

class PersistentIntegrityV46(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=os.path.join(self.tmp.name,'sessions.db')
        self.store=SQLiteResearchLoops(self.path)
        self.store.start(sample_loop())
    def tearDown(self):self.tmp.cleanup()
    def change(self,sql,args=()):
        with connect(self.path) as db:db.execute(sql,args)
    def test_V46_022_valid_read(self):
        version,s=self.store.read('S')
        self.assertEqual(version,0);self.assertTrue(validate_loop(s))
    def test_V46_023_sql_loss_tamper_refused(self):
        with connect(self.path) as db:
            body=json.loads(db.execute("SELECT body FROM research_loops WHERE session_id='S'").fetchone()[0])
            body['losses']['REORDER']['A']=999
            db.execute('UPDATE research_loops SET body=? WHERE session_id=?',(json.dumps(body),'S'))
        with self.assertRaisesRegex(StoreError,'INTEGRITY_FAILED'):self.store.read('S')
    def test_V46_024_sql_version_tamper_refused(self):
        self.change('UPDATE research_loops SET version=99')
        with self.assertRaises(StoreError):self.store.read('S')
    def test_V46_025_sql_mac_tamper_refused(self):
        self.change('UPDATE research_loops SET record_mac=?',('0'*64,))
        with self.assertRaises(StoreError):self.store.read('S')
    def test_V46_026_same_path_uses_persistent_mac_key(self):
        self.assertEqual(SQLiteResearchLoops(self.path).read('S')[0],0)
    def test_V46_027_store_advances_atomically(self):
        t=self.store.advance('S',0,'SIDE','left','b'*64)
        self.assertEqual(t['version'],1)
        self.assertEqual(SQLiteResearchLoops(self.path).read('S')[0],1)
    def test_V46_028_stale_version_conflict(self):
        self.store.advance('S',0,'SIDE','left','b'*64)
        with self.assertRaisesRegex(StoreError,'VERSION_CONFLICT'):
            self.store.advance('S',0,'SIDE','right','c'*64)
    def test_V46_029_malformed_blob_rejected_even_if_mac_recomputed(self):
        body='not-json'
        self.change('UPDATE research_loops SET body=?,record_mac=?',
                    (body,self.store._mac('S',0,body)))
        with self.assertRaisesRegex(StoreError,'CORRUPTED'):self.store.read('S')
    def test_V46_030_model_changed_with_mac_recomputed_still_rejected(self):
        with connect(self.path) as db:
            d=json.loads(db.execute('SELECT body FROM research_loops').fetchone()[0]);d['losses']['REORDER']['A']=999
            body=json.dumps(d)
            db.execute('UPDATE research_loops SET body=?,record_mac=?',(body,self.store._mac('S',0,body)))
        with self.assertRaisesRegex(StoreError,'CORRUPTED'):self.store.read('S')
    def test_V46_031_untrusted_cv_source_refused_by_public_store_method(self):
        with self.assertRaisesRegex(StoreError,'SERVER_SIDE_CV_REQUIRED'):
            self.store.advance('S',0,'SIDE','?', 'b'*64,source='CV_UNCALIBRATED')
    def test_V46_032_server_cv_nondiagnostic_updates(self):
        m={'measurement':{'uncertainty_status':'NOT_CALIBRATED_UNCERTAINTY_NOT_ZERO'}}
        result=self.store.advance_cv_internal('S',0,'SIDE','b'*64,m,
            trusted_cv_validator=lambda *_:True)
        self.assertEqual(result['possible_worlds'],['A','B'])
        self.assertFalse(result['physical_action_authorized'])
    def test_V46_033_server_cv_fake_calibrated_rejected(self):
        m={'measurement':{'uncertainty_status':'EMPIRICALLY_CALIBRATED'}}
        with self.assertRaises(StoreError):self.store.advance_cv_internal('S',0,'SIDE','b'*64,m,
            trusted_cv_validator=lambda *_:True)
    def test_V46_034_wrong_external_integrity_key_cannot_read(self):
        with patch.dict(os.environ,{'BZX_RESEARCH_INTEGRITY_KEY':'Z'*64}):
            other=SQLiteResearchLoops(self.path)
            with self.assertRaises(StoreError):other.read('S')

class CvFailClosedV46(unittest.TestCase):
    def test_V46_035_feature_detector_cv2_error_yields_quality_error(self):
        im=np.zeros((64,64),np.uint8)
        with patch('cv2.goodFeaturesToTrack',side_effect=cv2.error('simulated')):
            result,quality=estimate_motion(im,im,np.full_like(im,255))
        self.assertIsNone(result);self.assertEqual(quality,'FEATURE_OPENCV_ERROR')
    def test_V46_036_no_feature_yields_unknown_not_zero(self):
        im=np.zeros((64,64),np.uint8)
        x,quality=estimate_motion(im,im,np.full_like(im,255))
        self.assertIsNone(x);self.assertEqual(quality,'NO_FEATURES')

if __name__=='__main__':unittest.main()
