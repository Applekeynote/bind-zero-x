# -*- coding: utf-8 -*-
"""Research image follow-up API. cv2 VERSION IS MOCKED; real installed OpenCV4.
No OpenCV5, AWS, real-box, empirical uncertainty, or safety claims result here.
"""
import base64,hashlib,os,tempfile,unittest
from unittest.mock import patch
import cv2
from fastapi.testclient import TestClient
from api_research import app
from test_synthetic_opencv import image_pair
from research_loop_store import SQLiteResearchLoops

class ResearchImageApiV46(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{'BZX_RESEARCH_TOKEN':'T'*48,
            'BZX_RESEARCH_LOOP_DB':self.temp.name+'/loops.db',
            'BZX_RESEARCH_INTEGRITY_KEY':'M'*64})
        self.env.start()
        self.client=TestClient(app)
        self.h={'Authorization':'Bearer '+'T'*48}
    def tearDown(self):self.env.stop();self.client.close();self.temp.cleanup()
    def start_body(self):
        return {'session_id':'S','observation_id':'O','initial_image_sha256':'a'*64,
            'worlds':['A','B'],'losses':{'REORDER':{'A':0,'B':6},'RE_TIE':{'A':6,'B':0},
            'ABSTAIN':{'A':2,'B':2}},'view_signatures':{'SIDE':{'A':'layer_moves','B':'layer_still'}},
            'view_costs':{'SIDE':.1}}
    def init_loop(self):
        response=self.client.post('/api/research/loop/start',json=self.start_body(),headers=self.h)
        self.assertEqual(response.status_code,200,response.text)
        return response
    def img_body(self,slip=5):
        a,b,m=image_pair(slip=(slip,0))
        def pack(img):return base64.b64encode(cv2.imencode('.png',img)[1].tobytes()).decode()
        manifest={'operator_verified':True,'frame0_sha256':hashlib.sha256(a.tobytes()).hexdigest(),
            'layers':{k:{'mask_sha256':hashlib.sha256(m[k].tobytes()).hexdigest(),
             'layer_label':k,'source_id':'SAMPLE_'+k} for k in m}}
        return dict(session_id='S',expected_version=0,view='SIDE',
            frame0_png_b64=pack(a),frame1_png_b64=pack(b),
            upper_mask_png_b64=pack(m['upper']),lower_mask_png_b64=pack(m['lower']),
            calibration=dict(scale_mm_per_px=.2,plane_id='P',calibration_id='SYNTH',verified=True),
            roi_manifest=manifest,observation_id='O')
    def test_V46_API_001_real_opencv4_runtime_rejected(self):
        self.init_loop()
        if cv2.__version__.split('.')[0]!='5':
            r=self.client.post('/api/research/loop/reobserve-image',json=self.img_body(),headers=self.h)
            self.assertEqual(r.status_code,503)
    def test_V46_API_002_unauthenticated_image_rejected(self):
        self.init_loop()
        self.assertEqual(self.client.post('/api/research/loop/reobserve-image',json=self.img_body()).status_code,401)
    def test_V46_API_003_extra_client_cv_attestation_rejected(self):
        self.init_loop();body=self.img_body();body['cv_result']={'EMPIRICALLY_CALIBRATED':True}
        r=self.client.post('/api/research/loop/reobserve-image',json=body,headers=self.h)
        self.assertEqual(r.status_code,422)
    def test_V46_API_004_synthetic_cv4_with_mocked_version_consumes_view_but_no_world_reduction(self):
        self.init_loop()
        with patch.object(cv2,'__version__','5.0.0-TEST_MOCK_NOT_ACTUAL_OPENCV5'):
            r=self.client.post('/api/research/loop/reobserve-image',json=self.img_body(),headers=self.h)
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['possible_worlds'],['A','B'])
        self.assertEqual(r.json()['disposition'],'ABSTAIN')
        self.assertFalse(r.json()['physical_action_authorized'])
        self.assertEqual(r.json()['cv_calibration_evidence'],'UNCALIBRATED_NO_WORLD_REDUCTION')
        self.assertLess(abs(r.json()['image_measurement_research_only']['max_footprint_drift_mm']-1.),.3)
        _,state=SQLiteResearchLoops(self.temp.name+'/loops.db').read('S')
        self.assertEqual(state.steps[0].source,'CV_UNCALIBRATED')
    def test_V46_API_005_replay_image_wrong_version_rejected(self):
        self.init_loop()
        with patch.object(cv2,'__version__','5.0.0-TEST_MOCK_NOT_ACTUAL_OPENCV5'):
            first=self.client.post('/api/research/loop/reobserve-image',json=self.img_body(),headers=self.h)
            self.assertEqual(first.status_code,200,first.text)
            replay=self.client.post('/api/research/loop/reobserve-image',json=self.img_body(),headers=self.h)
            self.assertEqual(replay.status_code,409)
    def test_V46_API_006_new_frame_roi_provenance_failure(self):
        self.init_loop();body=self.img_body();body['roi_manifest']['operator_verified']=False
        with patch.object(cv2,'__version__','5.0.0-TEST_MOCK_NOT_ACTUAL_OPENCV5'):
            r=self.client.post('/api/research/loop/reobserve-image',json=body,headers=self.h)
        self.assertEqual(r.status_code,422)
        self.assertEqual(SQLiteResearchLoops(self.temp.name+'/loops.db').read('S')[0],0)
    def test_V46_API_007_duplicate_layer_mask_error(self):
        self.init_loop();body=self.img_body()
        body['lower_mask_png_b64']=body['upper_mask_png_b64']
        # Manifest still refers to an independently created lower mask.
        with patch.object(cv2,'__version__','5.0.0-TEST_MOCK_NOT_ACTUAL_OPENCV5'):
            r=self.client.post('/api/research/loop/reobserve-image',json=body,headers=self.h)
        self.assertEqual(r.status_code,422)
    def test_V46_API_008_legacy_endpoint_rejects_client_cv_source(self):
        self.init_loop()
        body={'session_id':'S','expected_version':0,'view':'SIDE',
              'signature':'layer_moves','capture_sha256':'b'*64,'source':'CV_UNCALIBRATED'}
        r=self.client.post('/api/research/loop/reobserve',json=body,headers=self.h)
        self.assertEqual(r.status_code,422)

if __name__=='__main__':unittest.main()
