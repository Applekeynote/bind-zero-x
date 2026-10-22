# -*- coding: utf-8 -*-
"""v4.7 offline regression. Every CV5 version override and GT record in this
file is a MOCK / SYNTHETIC FIXTURE, NEVER a real OpenCV5 or physical GT test.
"""
import base64,hashlib,json,math,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import cv2,numpy as np
from fastapi.testclient import TestClient
from measurement_contract import PlaneCalibration,PixelMetric,px_to_mm,MeasurementError
from vision_motion_core import metric_from_pair
from witness_planner import recommend_witness,verify_witness_certificate
from test_synthetic_opencv import image_pair
from cv_evidence_gate import load_approved_gt_envelope,classify_visible_layer_displacement,CVEvidenceError
from api_research import app
from research_loop_store import SQLiteResearchLoops
from active_evidence_loop import start_research_loop,continue_research_loop,validate_loop,LoopError
from dataclasses import replace

class V47CalibrationAndGeometry(unittest.TestCase):
    def test_V47_001_string_false_rejected_verified(self):
        with self.assertRaisesRegex(MeasurementError,'BOOLEAN_TYPE'):
            PlaneCalibration(.2,'P','C','false')
    def test_V47_002_string_false_rejected_frozen(self):
        with self.assertRaisesRegex(MeasurementError,'BOOLEAN_TYPE'):
            PlaneCalibration(.2,'P','C',True,frozen='false')
    def test_V47_003_numeric_one_rejected_verified(self):
        with self.assertRaisesRegex(MeasurementError,'BOOLEAN_TYPE'):
            PlaneCalibration(.2,'P','C',1)
    def test_V47_004_strict_true_allows_research_px_to_mm(self):
        m=px_to_mm(PixelMetric(10,'IMAGE_T0','P','O'),PlaneCalibration(.2,'P','C',True))
        self.assertEqual(m.value_mm,2.)
    def test_V47_005_depth_range_invalid(self):
        with self.assertRaises(MeasurementError):
            PlaneCalibration(.2,'P','C',True,supported_depth_range_mm=(100,0))
    def test_V47_006_roi_max_lies_on_actual_roi(self):
        a,b,m=image_pair(theta=15)
        # Analytic SE(2) motion differs by point; verify max is exactly the
        # maximum over *actual foreground pixels*, not the box's false corners.
        # Use a custom rotated diamond mask but mocked transforms for deterministic test.
        import vision_motion_core as vc
        mask=np.zeros_like(a)
        poly=np.array([[80,110],[110,80],[140,110],[110,140]],np.int32)
        cv2.fillConvexPoly(mask,poly,255)
        masks={'upper':mask,'lower':np.zeros_like(a)}
        masks['lower'][10:40,10:40]=255
        theta=math.radians(15);c=math.cos(theta);s=math.sin(theta)
        upper=np.eye(3);upper[:2,:2]=[[c,-s],[s,c]]
        with patch.object(vc,'estimate_motion',side_effect=[(upper,{'p90_error_px':0.,'tracks':30}),(np.eye(3),{'p90_error_px':0.,'tracks':30})]):
            v,e=vc.metric_from_pair(a,a,masks)
        self.assertIsNone(e)
        yy,xx=np.nonzero(mask)
        q=np.vstack((xx,yy,np.ones(len(xx))))
        vals=np.linalg.norm((upper@q)[:2]-q[:2],axis=0)
        self.assertAlmostEqual(v['max_anchor_drift_px'],float(vals.max()),places=8)
        self.assertEqual(v['max_drift_domain'],'VISIBLE_T0_UPPER_MASK_PIXELS_NOT_HIDDEN_LAYER')
    def test_V47_007_missing_roi_fails_closed(self):
        a,b,m=image_pair(slip=(8,0));m['upper'][:]=0
        value,error=metric_from_pair(a,b,m)
        self.assertIsNone(value)
        self.assertIsNotNone(error)

class V47WitnessConstrainedViews(unittest.TestCase):
    def test_V47_008_absolute_risk_can_trigger_noncontact_view(self):
        w=recommend_witness(['A','B'],{
            'REORDER':{'A':0,'B':11},'RE_TIE':{'A':10,'B':0},'ABSTAIN':{'A':15,'B':15}},
            {'SIDE':{'A':'left','B':'right'}},{'SIDE':.1},
            regret_tolerance=10,max_acceptable_absolute_loss_units=5)
        self.assertEqual(w.disposition,'REQUEST_NONCONTACT_VIEW')
        self.assertEqual(w.next_observation,'SIDE')
        self.assertTrue(verify_witness_certificate(w))
    def test_V47_009_no_guaranteed_safe_view_abstains(self):
        w=recommend_witness(['A','B'],{'KEEP':{'A':100,'B':100},'ABSTAIN':{'A':90,'B':90}},
            {'SIDE':{'A':'?','B':'?'}},{'SIDE':.1},
            regret_tolerance=30,max_acceptable_absolute_loss_units=5)
        self.assertEqual(w.disposition,'ABSTAIN')
    def test_V47_010_zero_regret_high_loss_does_not_direct(self):
        w=recommend_witness(['A','B'],{'KEEP':{'A':100,'B':100}}, {}, {},
            max_acceptable_absolute_loss_units=5)
        self.assertEqual(w.disposition,'ABSTAIN')

class V47GTGate(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.cal=dict(scale_mm_per_px=.2,plane_id='P',calibration_id='SYNTH',verified=True)
        self.shape=(256,256)
    def tearDown(self):self.tmp.cleanup()
    def _record(self):
        from cv_evidence_gate import _digest
        return {'schema':'BZX-REAL-GT-ENVELOPE-V2',
            'channel':'LAYER_VISIBLE_MAX_MM','calibration_sha256':_digest(self.cal),
            'frame_shape':list(self.shape),'approved':True,
            'pre_registered':True,'independent_real_gt':True,'holdout_n':40,
            'holdout_manifest_sha256':'a'*64,'independence_unit':'UNIQUE_PHYSICAL_BUNDLE_ID_NOT_ROWS',
            'independent_bundle_n':40,'independent_video_n':40,
            'fault_mode_counts':{'SLIP':20,'STILL':20},
            'external_audit_receipt_sha256':'e'*64,'threshold_mm':1.,
            'p95_absolute_error_mm':.1,'max_allowed_p95_mm':.2}
    def _env(self,record):
        path=Path(self.tmp.name)/'registry.json'
        path.write_text(json.dumps(record,sort_keys=True),encoding='utf-8')
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        return patch.dict(os.environ,{'BZX_APPROVED_GT_ENVELOPE_PATH':str(path),
            'BZX_APPROVED_GT_ENVELOPE_SHA256':digest})
    def test_V47_011_no_registry_no_world_reduction(self):
        with patch.dict(os.environ,{'BZX_APPROVED_GT_ENVELOPE_PATH':'',
            'BZX_APPROVED_GT_ENVELOPE_SHA256':''}):
            self.assertIsNone(load_approved_gt_envelope(self.cal,self.shape))
    def test_V47_012_modified_record_mismatched_digest_rejected(self):
        rec=self._record()
        with self._env(rec):
            p=Path(os.environ['BZX_APPROVED_GT_ENVELOPE_PATH']);p.write_text('{}')
            self.assertIsNone(load_approved_gt_envelope(self.cal,self.shape))
    def test_V47_013_research_fixture_only_registry_parses(self):
        with self._env(self._record()):
            self.assertIsNotNone(load_approved_gt_envelope(self.cal,self.shape))
    def test_V47_014_unapproved_registry_rejected(self):
        r=self._record();r['approved']=False
        with self._env(r):self.assertIsNone(load_approved_gt_envelope(self.cal,self.shape))
    def test_V47_015_low_holdout_rejected(self):
        r=self._record();r['holdout_n']=2
        with self._env(r):self.assertIsNone(load_approved_gt_envelope(self.cal,self.shape))
    def test_V47_016_mismatched_scale_fingerprint_rejected(self):
        with self._env(self._record()):
            self.assertIsNone(load_approved_gt_envelope({**self.cal,'scale_mm_per_px':.9},self.shape))
    def test_V47_017_mismatched_image_shape_rejected(self):
        with self._env(self._record()):
            self.assertIsNone(load_approved_gt_envelope(self.cal,(200,200)))
    def test_V47_018_classifies_outside_uncertainty(self):
        r=self._record()
        for x,expect in ((0,'layer_still'),(.95,'?'),(2,'layer_moves')):
            self.assertEqual(classify_visible_layer_displacement({'max_footprint_drift_mm':x,
                'uncertainty_status':'NOT_CALIBRATED_UNCERTAINTY_NOT_ZERO'},r),expect)
    def test_V47_019_nan_rejected(self):
        with self.assertRaises(CVEvidenceError):
            classify_visible_layer_displacement({'max_footprint_drift_mm':float('nan'),
                'uncertainty_status':'NOT_CALIBRATED_UNCERTAINTY_NOT_ZERO'},self._record())
    def test_V47_020_unexpected_uncertainty_claim_rejected(self):
        with self.assertRaises(CVEvidenceError):
            classify_visible_layer_displacement({'max_footprint_drift_mm':0.,
                'uncertainty_status':'EMPIRICALLY_CALIBRATED'},self._record())

class V47ImageApiBindings(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{'BZX_RESEARCH_TOKEN':'T'*48,
            'BZX_RESEARCH_LOOP_DB':self.tmp.name+'/loops.db',
            'BZX_RESEARCH_INTEGRITY_KEY':'M'*64,
            'BZX_APPROVED_GT_ENVELOPE_PATH':'',
            'BZX_APPROVED_GT_ENVELOPE_SHA256':''})
        self.env.start();self.client=TestClient(app);self.headers={'Authorization':'Bearer '+'T'*48}
        self.cal=dict(scale_mm_per_px=.2,plane_id='P',calibration_id='SYNTH',verified=True)
    def tearDown(self):self.client.close();self.env.stop();self.tmp.cleanup()
    def _start(self):
        b={'session_id':'S','observation_id':'O','initial_image_sha256':'a'*64,
            'worlds':['A','B'],'losses':{'REORDER':{'A':0,'B':6},'RE_TIE':{'A':6,'B':0},'ABSTAIN':{'A':2,'B':2}},
            'view_signatures':{'SIDE':{'A':'layer_moves','B':'layer_still'}},'view_costs':{'SIDE':.1}}
        r=self.client.post('/api/research/loop/start',json=b,headers=self.headers)
        self.assertEqual(r.status_code,200,r.text)
    def _body(self,slip=0):
        a,b,m=image_pair(slip=(slip,0))
        def enc(im):return base64.b64encode(cv2.imencode('.png',im)[1].tobytes()).decode()
        manifest={'operator_verified':True,'frame0_sha256':hashlib.sha256(a.tobytes()).hexdigest(),
            'layers':{k:{'mask_sha256':hashlib.sha256(m[k].tobytes()).hexdigest(),
                'layer_label':k,'source_id':k} for k in m}}
        return {'session_id':'S','observation_id':'O','expected_version':0,'view':'SIDE',
            'frame0_png_b64':enc(a),'frame1_png_b64':enc(b),
            'upper_mask_png_b64':enc(m['upper']),'lower_mask_png_b64':enc(m['lower']),
            'calibration':dict(self.cal),'roi_manifest':manifest}
    def _post(self,b):
        with patch.object(cv2,'__version__','5.0.0-MOCK_V47_NOT_ACTUAL'):
            return self.client.post('/api/research/loop/reobserve-image',json=b,headers=self.headers)
    def test_V47_021_parent_observation_mismatch_rejected(self):
        self._start();b=self._body();b['observation_id']='UNRELATED'
        r=self._post(b);self.assertEqual(r.status_code,422,r.text)
        self.assertEqual(SQLiteResearchLoops(self.tmp.name+'/loops.db').read('S')[0],0)
    def test_V47_022_false_string_calibration_rejected_before_cv(self):
        self._start();b=self._body();b['calibration']['verified']='false'
        r=self._post(b);self.assertEqual(r.status_code,422,r.text)
        self.assertEqual(SQLiteResearchLoops(self.tmp.name+'/loops.db').read('S')[0],0)
    def test_V47_023_false_string_frozen_rejected(self):
        self._start();b=self._body();b['calibration']['frozen']='false'
        self.assertEqual(self._post(b).status_code,422)
    def test_V47_024_mock_cv_reobservation_binds_parent_child(self):
        self._start();r=self._post(self._body(slip=10))
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['parent_observation_id'],'O')
        self.assertEqual(r.json()['child_observation_id'],'O:view1')
        self.assertEqual(r.json()['cv_observation_token'],'?')
        self.assertEqual(r.json()['possible_worlds'],['A','B'])
        state=SQLiteResearchLoops(self.tmp.name+'/loops.db').read('S')[1]
        self.assertEqual(state.steps[0].child_observation_id,'O:view1')
        self.assertEqual(state.steps[0].parent_observation_id,'O')
    def test_V47_025_malformed_history_child_binding_rejected(self):
        self._start();self._post(self._body())
        state=SQLiteResearchLoops(self.tmp.name+'/loops.db').read('S')[1]
        bad=replace(state.steps[0],child_observation_id='O:view999')
        with self.assertRaisesRegex(LoopError,'PARENT_CHILD_MISMATCH'):
            validate_loop(replace(state,steps=(bad,)))
    def test_V47_026_mock_gt_metadata_cv_really_changes_worlds_but_is_not_physical_proof(self):
        self._start()
        from cv_evidence_gate import _digest
        b=self._body(slip=10)
        a=cv2.imdecode(np.frombuffer(base64.b64decode(b['frame0_png_b64']),np.uint8),cv2.IMREAD_GRAYSCALE)
        synthetic_claim={'schema':'BZX-REAL-GT-ENVELOPE-V2','channel':'LAYER_VISIBLE_MAX_MM',
            'calibration_sha256':_digest(self.cal),'frame_shape':list(a.shape),
            'approved':True,'pre_registered':True,'independent_real_gt':True,'holdout_n':40,
            'holdout_manifest_sha256':'b'*64,'independence_unit':'UNIQUE_PHYSICAL_BUNDLE_ID_NOT_ROWS',
            'independent_bundle_n':40,'independent_video_n':40,
            'fault_mode_counts':{'SLIP':20,'STILL':20},
            'external_audit_receipt_sha256':'e'*64,'threshold_mm':1.,
            'p95_absolute_error_mm':.1,'max_allowed_p95_mm':.2}
        # The *claims* above are fabricated test metadata. They test code wiring,
        # not real-world calibration or integrity of ground-truth collection.
        path=Path(self.tmp.name)/'mock_gt.json';path.write_text(json.dumps(synthetic_claim))
        env={'BZX_APPROVED_GT_ENVELOPE_PATH':str(path),
            'BZX_APPROVED_GT_ENVELOPE_SHA256':hashlib.sha256(path.read_bytes()).hexdigest()}
        with patch.dict(os.environ,env):r=self._post(b)
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['cv_observation_token'],'layer_moves')
        self.assertEqual(r.json()['possible_worlds'],['A'])
        self.assertEqual(r.json()['disposition'],'DIRECT_ACTION')
        self.assertFalse(r.json()['physical_action_authorized'])
        self.assertEqual(SQLiteResearchLoops(self.tmp.name+'/loops.db').read('S')[1].steps[0].source,'CV_LAYER_ONLY')
    def test_V47_027_mock_gt_static_image_changes_to_other_world(self):
        self._start()
        from cv_evidence_gate import _digest
        b=self._body(slip=0)
        frame=cv2.imdecode(np.frombuffer(base64.b64decode(b['frame0_png_b64']),np.uint8),cv2.IMREAD_GRAYSCALE)
        fixture={'schema':'BZX-REAL-GT-ENVELOPE-V2','channel':'LAYER_VISIBLE_MAX_MM',
            'calibration_sha256':_digest(self.cal),'frame_shape':list(frame.shape),
            'approved':True,'pre_registered':True,'independent_real_gt':True,'holdout_n':40,
            'holdout_manifest_sha256':'b'*64,'independence_unit':'UNIQUE_PHYSICAL_BUNDLE_ID_NOT_ROWS',
            'independent_bundle_n':40,'independent_video_n':40,
            'fault_mode_counts':{'SLIP':20,'STILL':20},
            'external_audit_receipt_sha256':'e'*64,'threshold_mm':1.,
            'p95_absolute_error_mm':.1,'max_allowed_p95_mm':.2}
        p=Path(self.tmp.name)/'sim_gt.json';p.write_text(json.dumps(fixture))
        with patch.dict(os.environ,{'BZX_APPROVED_GT_ENVELOPE_PATH':str(p),
            'BZX_APPROVED_GT_ENVELOPE_SHA256':hashlib.sha256(p.read_bytes()).hexdigest()}):r=self._post(b)
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['cv_observation_token'],'layer_still')
        self.assertEqual(r.json()['possible_worlds'],['B'])
        self.assertFalse(r.json()['physical_action_authorized'])

if __name__=='__main__':unittest.main()
