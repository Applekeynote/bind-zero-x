# -*- coding: utf-8 -*-
"""v4.8 LOCAL ONLY synthetic regression suite.

OpenCV5 is mocked where marked; arbitrary video bytes are NOT real recordings.
No real independent GT, AWS, physical efficacy, or official scoring is claimed.
"""
from __future__ import annotations
import base64,csv,hashlib,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import cv2
from fastapi.testclient import TestClient
from api_research import app
from capture_archive import persist_capture,verify_capture,CaptureArchiveError
from active_evidence_loop import start_research_loop,validate_loop,LoopError
from research_loop_store import SQLiteResearchLoops
import test_v46_image_api as helper
ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0,str(ROOT/'experiments'))
from analyze_physical_comparison import analyze,read
from prepare_gt_envelope import build
from audit_gt_source_media import audit,AuditError
from cv_evidence_gate import load_approved_gt_envelope,_digest

class V48PairedStats(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.f=Path(self.temp.name)/'t.csv'
    def tearDown(self):self.temp.cleanup()
    def _row(self,case,pair,arm,n=10,carried=10,t=100,done=1,wrong=0):
        return dict(case_id=case,pair_id=pair,D0_D1_E1_E2_or_B=arm,
            original_sheet_count=str(n),carried_sheet_count=str(carried),
            elapsed_seconds=str(t),completed=str(done),wrong_intervention=str(wrong),
            abort_reason='' if done else 'OPERATOR_STOP',video_sha256=hashlib.sha256(case.encode()).hexdigest())
    def _run(self,rows):
        with self.f.open('w',encoding='utf-8',newline='') as fp:
            writer=csv.DictWriter(fp,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
        return analyze(self.f)
    def test_V48_001_aborted_one_second_not_reported_as_speed_gain(self):
        r=self._run([self._row('a','P','D1',t=120),self._row('b','P','E2',carried=0,t=1,done=0)])
        c=r['comparisons']['D1'];self.assertIsNone(c['completed_pair_only_E2_minus_control_elapsed_sec'])
        self.assertEqual(c['n_excluded_from_speed_because_incomplete'],1)
        self.assertEqual(c['E2_minus_control_completion_rate'],-1)
        self.assertEqual(c['E2_minus_control_success_without_wrong_intervention_rate'],-1)
        self.assertFalse(c['unconditional_speed_claim_permitted'])
    def test_V48_002_both_completed_allow_conditional_speed(self):
        r=self._run([self._row('a','P','D1',t=120),self._row('b','P','E2',t=80)])
        self.assertEqual(r['comparisons']['D1']['completed_pair_only_E2_minus_control_elapsed_sec'],-40)
        self.assertEqual(r['comparisons']['D1']['joint_completed_pairs'],1)
    def test_V48_003_both_abort_no_speed_data(self):
        r=self._run([self._row('a','P','D1',carried=1,t=1,done=0),self._row('b','P','E2',carried=2,t=2,done=0)])
        self.assertIsNone(r['comparisons']['D1']['completed_pair_only_E2_minus_control_elapsed_sec'])
        self.assertEqual(r['group_summaries']['E2']['completion_rate'],0)
    def test_V48_004_partial_completion_fraction_reported(self):
        r=self._run([self._row('a','P','D1',carried=10),self._row('b','P','E2',carried=4,done=0)])
        self.assertEqual(r['group_summaries']['E2']['sheet_completion_fraction'],.4)
    def test_V48_005_inconsistent_pair_sheet_count_rejected(self):
        with self.assertRaisesRegex(ValueError,'DIFFERENT_ORIGINAL'):
            self._run([self._row('a','P','D1',n=10),self._row('b','P','E2',n=8,carried=8)])
    def test_V48_006_malformed_time_rejected(self):
        with self.assertRaisesRegex(ValueError,'INVALID_PHYSICAL'):
            self._run([self._row('a','P','E2',t='nan')])
    def test_V48_007_incomplete_pairs_not_imputed(self):
        r=self._run([self._row('a','P','E2')]);self.assertEqual(r['comparisons']['D1']['status'],'NO_MATCHED_PAIRS')
    def test_V48_008_complete_n_without_completed_flag_still_counts_failure(self):
        r=self._run([self._row('a','P','D1'),self._row('b','P','E2',carried=10,done=0)])
        self.assertEqual(r['group_summaries']['E2']['completion_rate'],0)
        self.assertIsNone(r['comparisons']['D1']['completed_pair_only_E2_minus_control_elapsed_sec'])
    def test_V48_009_completion_bootstrap_for_two_pairs(self):
        r=self._run([self._row('a','P1','D1'),self._row('b','P1','E2',carried=0,done=0),
                     self._row('c','P2','D1'),self._row('d','P2','E2')])
        self.assertIsNotNone(r['comparisons']['D1']['completion_rate_difference_paired_bootstrap_95pct_CI'])
    def test_V48_010_missing_required_column_rejected(self):
        self.f.write_text('case_id,pair_id\na,b\n')
        with self.assertRaisesRegex(ValueError,'MISSING_REQUIRED_COLUMNS'):analyze(self.f)
    def test_V48_011_improper_completed_carried_rejected(self):
        with self.assertRaisesRegex(ValueError,'INCOMPLETE_SHEETS'):
            self._run([self._row('a','P','E2',carried=3,done=1)])
    def test_V48_012_zero_seconds_completed_is_data_not_auto_conclusion(self):
        r=self._run([self._row('a','P','D1',t=0),self._row('b','P','E2',t=0)])
        self.assertFalse(r['comparisons']['D1']['unconditional_speed_claim_permitted'])

class V48GroundTruthIndependence(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def rows(self,n=30,duplicate_bundle=False,duplicate_video=False):
        return [dict(trial_id=str(i),bundle_id=str(i if not duplicate_bundle else i%4),
            fault_mode='SLIP' if i%2 else 'STILL',gt_mm=str(i/10),cv_mm=str(i/10+.05),
            gt_rater='BLIND_RATER',video_sha256=f'{(i if not duplicate_video else i%4)+1:064x}')
            for i in range(n)]
    def test_V48_013_repeated_bundle_30_rows_not_30_independent_trials(self):
        with self.assertRaisesRegex(ValueError,'DIVERSITY'):
            build({},self.rows(duplicate_bundle=True),b'fixture',(100,100),1,.2)
    def test_V48_014_repeated_video_30_rows_rejected(self):
        with self.assertRaisesRegex(ValueError,'DIVERSITY'):
            build({},self.rows(duplicate_video=True),b'fixture',(100,100),1,.2)
    def test_V48_015_v2_envelope_draft_only(self):
        r=build({},self.rows(),b'fixture',(100,100),1,.2)
        self.assertEqual(r['schema'],'BZX-REAL-GT-ENVELOPE-V2')
        self.assertEqual(r['independent_bundle_n'],30)
        self.assertIsNone(r['external_audit_receipt_sha256'])
        self.assertFalse(r['approved'])
    def test_V48_016_unregistered_legacy_v1_claim_cannot_enable_cv_gate(self):
        cal={'a':1};rec={'schema':'BZX-REAL-GT-ENVELOPE-V1',
              'calibration_sha256':_digest(cal),'frame_shape':[100,100],
              'approved':True,'pre_registered':True,'independent_real_gt':True,'holdout_n':30}
        p=self.root/'env.json';p.write_text(json.dumps(rec));h=hashlib.sha256(p.read_bytes()).hexdigest()
        with patch.dict(os.environ,{'BZX_APPROVED_GT_ENVELOPE_PATH':str(p),'BZX_APPROVED_GT_ENVELOPE_SHA256':h}):
            self.assertIsNone(load_approved_gt_envelope(cal,(100,100)))
    def test_V48_017_v2_missing_external_receipt_denied(self):
        cal={'a':1};rec=build(cal,self.rows(),b'fixture',(100,100),1,.2)
        rec.update(approved=True,pre_registered=True,independent_real_gt=True)
        p=self.root/'env.json';p.write_text(json.dumps(rec));h=hashlib.sha256(p.read_bytes()).hexdigest()
        with patch.dict(os.environ,{'BZX_APPROVED_GT_ENVELOPE_PATH':str(p),'BZX_APPROVED_GT_ENVELOPE_SHA256':h}):
            self.assertIsNone(load_approved_gt_envelope(cal,(100,100)))
    def _media_fixture(self):
        rows=self.rows();media=self.root/'media';media.mkdir()
        for i,r in enumerate(rows):
            raw=('SYNTHETIC_BYTES_NOT_ACTUAL_VIDEO_'+str(i)).encode()
            r['video_sha256']=hashlib.sha256(raw).hexdigest()
            path=media/(str(i)+'.bin');path.write_bytes(raw);r['video_file']=path.name
        csv_path=self.root/'holdout.csv'
        with csv_path.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
        prereg=self.root/'prereg.json'
        prereg.write_text(json.dumps({'status':'FROZEN_BEFORE_GT_COLLECTION',
            'frozen_utc':'2026-10-12T00:00:00Z','primary_endpoint':'wrong_intervention_rate'}))
        return csv_path,media,prereg
    def test_V48_018_source_media_bytes_verified_but_not_approved(self):
        p,media,prereg=self._media_fixture();r=audit(p,media,prereg)
        self.assertEqual(r['n_unique_bundles'],30);self.assertFalse(r['real_world_ground_truth_approved'])
    def test_V48_019_media_tamper_detected(self):
        p,media,prereg=self._media_fixture();(media/'1.bin').write_bytes(b'tampered')
        with self.assertRaisesRegex(AuditError,'SHA256_MISMATCH'):audit(p,media,prereg)
    def test_V48_020_train_holdout_leak_detected(self):
        p,media,prereg=self._media_fixture();t=self.root/'training.txt';t.write_text('0\n')
        with self.assertRaisesRegex(AuditError,'LEAKAGE'):audit(p,media,prereg,t)
    def test_V48_021_no_prereg_freeze_rejected(self):
        p,media,prereg=self._media_fixture();prereg.write_text('{}')
        with self.assertRaisesRegex(AuditError,'NOT_FROZEN'):audit(p,media,prereg)
    def test_V48_022_video_path_escaping_root_denied(self):
        p,media,prereg=self._media_fixture()
        with p.open() as f:rows=list(csv.DictReader(f))
        rows[0]['video_file']='../outside.bin';outside=self.root/'outside.bin';outside.write_bytes(b'x')
        with p.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
        with self.assertRaises((AuditError,FileNotFoundError)):audit(p,media,prereg)

class V48CaptureArchive(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def imgs(self):return {name:b'\x89PNG\r\n\x1a\n'+name.encode() for name in ('frame0','frame1','upper_mask','lower_mask')}
    def test_V48_023_manifest_matches_all_four_images(self):
        h=persist_capture(self.root,'S','O',self.imgs(),{'a':1})
        self.assertTrue(verify_capture(self.root,h))
    def test_V48_024_image_tamper_detected(self):
        h=persist_capture(self.root,'S','O',self.imgs(),{'a':1});data=json.loads((self.root/(h+'.json')).read_text())
        (self.root/(data['images']['frame0']['sha256']+'.png')).write_bytes(b'changed')
        self.assertFalse(verify_capture(self.root,h))
    def test_V48_025_manifest_alteration_detected(self):
        h=persist_capture(self.root,'S','O',self.imgs(),{'a':1})
        (self.root/(h+'.json')).write_text('{}')
        self.assertFalse(verify_capture(self.root,h))
    def test_V48_026_immutable_archive_refuses_different_bytes_existing_name(self):
        h=persist_capture(self.root,'S','O',self.imgs(),{'a':1})
        payload=json.loads((self.root/(h+'.json')).read_text())
        (self.root/(payload['images']['frame0']['sha256']+'.png')).write_bytes(b'TAMPERED')
        with self.assertRaises(CaptureArchiveError):persist_capture(self.root,'S','O',self.imgs(),{'a':1})
    def test_V48_027_unknown_origin_session_rejected(self):
        m=helper.ResearchImageApiV46.start_body(None)
        from dataclasses import replace
        from active_evidence_loop import validate_loop
        s=start_research_loop('S','O',m['worlds'],m['losses'],m['view_signatures'],m['view_costs'],'a'*64)
        with self.assertRaisesRegex(LoopError,'UNKNOWN_INITIAL'):
            validate_loop(replace(s,initial_capture_origin='NOT_REAL'))
    def test_V48_028_archive_metadata_changes_receipt(self):
        a=persist_capture(self.root,'S','O',self.imgs(),{'k':'a'})
        b=persist_capture(self.root,'S','O',self.imgs(),{'k':'b'})
        self.assertNotEqual(a,b)

class V48CapturedStartAPI(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{'BZX_RESEARCH_TOKEN':'K'*48,
            'BZX_RESEARCH_LOOP_DB':self.temp.name+'/loops.db',
            'BZX_RESEARCH_INTEGRITY_KEY':'M'*64,
            'BZX_CAPTURE_ARCHIVE_DIR':self.temp.name+'/archive'})
        self.env.start();self.client=TestClient(app);self.headers={'Authorization':'Bearer '+'K'*48}
    def tearDown(self):self.client.close();self.env.stop();self.temp.cleanup()
    def body(self):
        b=helper.ResearchImageApiV46.img_body(None,slip=7)
        b.update(helper.ResearchImageApiV46.start_body(None));b.pop('initial_image_sha256')
        b.pop('view');b.pop('expected_version')
        return b
    def test_V48_029_cv4_runtime_rejected(self):
        if cv2.__version__.split('.')[0]!='5':
            r=self.client.post('/api/research/loop/start-captured',json=self.body(),headers=self.headers)
            self.assertEqual(r.status_code,503)
    def test_V48_030_mock_cv5_stores_real_received_png_bytes(self):
        with patch.object(cv2,'__version__','5.0.0-MOCK_NOT_REAL'):
            r=self.client.post('/api/research/loop/start-captured',json=self.body(),headers=self.headers)
        self.assertEqual(r.status_code,200,r.text)
        data=r.json();self.assertEqual(data['initial_capture_origin'],'SERVER_CAPTURED_PNG')
        self.assertTrue(verify_capture(self.temp.name+'/archive',data['initial_capture_receipt_sha256']))
        s=SQLiteResearchLoops(self.temp.name+'/loops.db').read('S')[1]
        self.assertEqual(s.initial_image_sha256,data['initial_capture_receipt_sha256'])
        self.assertEqual(s.initial_capture_origin,'SERVER_CAPTURED_PNG')
        self.assertFalse(data['physical_action_authorized'])
    def test_V48_031_uncaptured_legacy_route_labeled_unverified(self):
        b=helper.ResearchImageApiV46.start_body(None)
        r=self.client.post('/api/research/loop/start',json=b,headers=self.headers)
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['initial_capture_origin'],'CLIENT_CLAIM_ONLY')
        self.assertEqual(r.json()['initial_image_evidence'],'UNVERIFIED_CLIENT_HASH_NO_IMAGE')
    def test_V48_032_unauthorized_captured_route_rejected(self):
        self.assertEqual(self.client.post('/api/research/loop/start-captured',json=self.body()).status_code,401)
    def test_V48_033_missing_archive_prevents_captured_start(self):
        with patch.dict(os.environ,{'BZX_CAPTURE_ARCHIVE_DIR':''}):
            with patch.object(cv2,'__version__','5.0.0-MOCK_NOT_REAL'):
                r=self.client.post('/api/research/loop/start-captured',json=self.body(),headers=self.headers)
        self.assertEqual(r.status_code,503)
    def test_V48_034_duplicate_mask_fails_no_capture(self):
        b=self.body();b['lower_mask_png_b64']=b['upper_mask_png_b64']
        with patch.object(cv2,'__version__','5.0.0-MOCK_NOT_REAL'):
            r=self.client.post('/api/research/loop/start-captured',json=b,headers=self.headers)
        self.assertEqual(r.status_code,422)
        self.assertFalse((Path(self.temp.name)/'archive').exists())
    def test_V48_035_unverified_roi_fails_no_capture(self):
        b=self.body();b['roi_manifest']['operator_verified']=False
        with patch.object(cv2,'__version__','5.0.0-MOCK_NOT_REAL'):
            r=self.client.post('/api/research/loop/start-captured',json=b,headers=self.headers)
        self.assertEqual(r.status_code,422)
    def test_V48_036_server_capture_receipt_differs_from_claimed_hash(self):
        b=self.body();self.assertNotIn('initial_image_sha256',b)
        with patch.object(cv2,'__version__','5.0.0-MOCK_NOT_REAL'):
            r=self.client.post('/api/research/loop/start-captured',json=b,headers=self.headers)
        self.assertEqual(r.status_code,200,r.text)
        self.assertNotEqual(r.json()['initial_capture_receipt_sha256'],'a'*64)

if __name__=='__main__':unittest.main()
