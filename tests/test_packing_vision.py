"""Real OpenCV 5 segmentation, bounded inputs and protected route contracts."""
import base64
import struct
import unittest
from pathlib import Path
from unittest.mock import patch
from test_console import server,authenticated_client
from fastapi.testclient import TestClient
import cv2
import numpy as np
from packing_vision import segment_cardboard,decode_png,shape_features
from packing_completion import complete_surface

class PackingVision(unittest.TestCase):
    def png(self,image):return cv2.imencode('.png',image)[1].tobytes()
    def test_occlusion_is_completed_without_relabelling_observed_pixels(self):
        image=np.full((200,240,3),170,np.uint8)
        visible=np.zeros((200,240),np.uint8);visible[30:170,30:200]=255;visible[95:170,30:105]=0
        other=np.zeros_like(visible);other[95:170,30:105]=255
        image[visible>0]=(210,80,20);image[other>0]=(20,160,60)
        result=complete_surface(image,visible,other)
        completed=cv2.imdecode(np.frombuffer(base64.b64decode(result['mask_png'].split(',')[1]),np.uint8),cv2.IMREAD_GRAYSCALE)
        self.assertGreater(result['inferred_pixels'],4000)
        self.assertEqual(completed[130,60],255)
        self.assertEqual(visible[130,60],0)
        self.assertEqual(completed[10,10],0)
        self.assertFalse(result['verified']);self.assertTrue(result['review_required'])
        self.assertEqual(result['fill_rgb'],[20,80,210])
    def test_an_actual_background_notch_is_not_filled(self):
        visible=np.zeros((180,220),np.uint8);visible[20:160,20:200]=255;visible[100:160,20:70]=0
        result=complete_surface(np.full((180,220,3),120,np.uint8),visible,np.zeros_like(visible))
        self.assertEqual(result['inferred_pixels'],0)
    def test_non_cardboard_background_has_no_invented_regions(self):
        image=np.full((200,300,3),170,np.uint8)
        result=segment_cardboard(self.png(image))
        self.assertEqual(result['regions'],[])
        self.assertFalse(result['physical_action_authorized'])
    def test_separated_tan_sheets_have_disjoint_colored_labels(self):
        image=np.full((300,500,3),220,np.uint8)
        cv2.rectangle(image,(30,30),(220,270),(95,150,190),-1)
        cv2.rectangle(image,(300,80),(470,230),(100,160,200),-1)
        result=segment_cardboard(self.png(image))
        self.assertEqual(len(result['regions']),2)
        labels=cv2.imdecode(np.frombuffer(base64.b64decode(result['labels_png'].split(',')[1]),np.uint8),cv2.IMREAD_GRAYSCALE)
        self.assertEqual(set(np.unique(labels)),{0,1,2})
        self.assertNotEqual(result['regions'][0]['color'],result['regions'][1]['color'])
        self.assertTrue(all(r['review_required'] for r in result['regions']))
    def test_blue_red_and_pastel_surfaces_are_included(self):
        image=np.full((300,600,3),170,np.uint8)
        for x,color in [(20,(190,80,20)),(215,(40,40,210)),(410,(185,210,180))]:
            cv2.rectangle(image,(x,40),(x+160,260),color,-1)
        result=segment_cardboard(self.png(image))
        self.assertEqual(len(result['regions']),3)
        self.assertTrue(all('image_long_axis_degrees' in r['shape_evidence'] for r in result['regions']))
    def test_crease_geometry_is_a_reviewable_fold_candidate(self):
        image=np.full((220,220,3),(100,160,200),np.uint8)
        for a,b in [((50,25),(50,195)),((30,50),(185,50)),((30,35),(185,190)),((35,185),(185,35))]:
            cv2.line(image,a,b,(25,40,55),3)
        mask=np.full((220,220),255,np.uint8)
        _,features,kind=shape_features(image,mask)
        self.assertEqual(kind,'OPEN_BOX_CANDIDATE')
        self.assertGreaterEqual(features['internal_line_directions'],3)
    def test_all_demo_photos_are_computed_and_remain_demo_only(self):
        root=Path(__file__).resolve().parents[1]
        for p in (root/'app/static/photos').glob('*.png'):
            result=segment_cardboard(p.read_bytes())
            self.assertGreater(len(result['regions']),0,p.name)
            self.assertLessEqual(len(result['regions']),12)
            self.assertLessEqual(max(result['width'],result['height']),960)
            self.assertFalse(result['physical_action_authorized'])
    def test_bad_headers_and_pixel_bombs_rejected_before_decode(self):
        raw=self.png(np.zeros((40,40,3),np.uint8))
        with self.assertRaises(ValueError):decode_png(b'not PNG')
        bad=raw[:16]+struct.pack('>II',100000,100000)+raw[24:]
        with patch('packing_vision.cv2.imdecode',side_effect=AssertionError('decoder reached')):
            with self.assertRaisesRegex(ValueError,'DIMENSIONS'):decode_png(bad)
    def test_api_requires_auth_csrf_and_allowlisted_sources(self):
        anonymous=TestClient(server.app,base_url='http://localhost',client=('127.0.0.1',54000))
        self.assertEqual(anonymous.post('/api/console/segment',json={'demo_photo':'open-boxes-group'}).status_code,401)
        client=authenticated_client()
        self.assertEqual(client.post('/api/console/segment',json={'demo_photo':'../../runtime/security/auth.db'}).status_code,422)
        self.assertEqual(client.post('/api/console/segment',json={'demo_photo':'open-boxes-group','image_png_b64':'bad'}).status_code,422)
        self.assertEqual(client.post('/api/console/segment',json={'image_png_b64':'!bad'}).status_code,422)
        self.assertEqual(client.post('/api/console/segment',json={'demo_photo':'open-boxes-group'},headers={'X-CSRF-Token':'bad'}).status_code,403)
        response=client.post('/api/console/segment',json={'demo_photo':'open-boxes-group'})
        self.assertEqual(response.status_code,200,response.text[:300])
        self.assertEqual(response.json()['input_tier'],'USER_PROVIDED_DEMO_ONLY')
        self.assertEqual(response.json()['opencv_version'].split('.')[0],'5')
        self.assertFalse(response.json()['physical_action_authorized'])
    def test_analysis_gate_returns_busy_without_decoding(self):
        client=authenticated_client()
        with patch.object(server,'EXPENSIVE_GATE') as gate:
            gate.acquire.return_value=False
            response=client.post('/api/console/segment',json={'demo_photo':'open-boxes-group'})
        self.assertEqual(response.status_code,429)
    def test_uploaded_png_uses_the_same_pipeline_without_demo_provenance(self):
        image=np.full((160,240,3),220,np.uint8)
        cv2.rectangle(image,(20,20),(180,140),(95,150,190),-1)
        response=authenticated_client().post('/api/console/segment',json={'image_png_b64':base64.b64encode(self.png(image)).decode()})
        self.assertEqual(response.status_code,200,response.text[:100])
        self.assertEqual(response.json()['input_tier'],'USER_IMAGE_UNVERIFIED')
        self.assertGreater(len(response.json()['regions']),0)

if __name__=='__main__':unittest.main()
