# -*- coding: utf-8 -*-
import unittest,os,base64
from unittest.mock import patch
from fastapi.testclient import TestClient
from api_research import app,_decode
from test_synthetic_opencv import image_pair
import cv2

class ApiV44(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.client=TestClient(app)
 def test_API44_001_health_does_not_claim_opencv5(self):
  r=self.client.get('/health');self.assertEqual(r.status_code,200)
  self.assertEqual(r.json()['opencv5'],cv2.__version__.split('.')[0]=='5')
  self.assertFalse(r.json()['physical_authorization'])
 def test_API44_002_ready_denied_without_token(self):
  with patch.dict(os.environ,{},clear=True):
   self.assertEqual(self.client.get('/ready').status_code,503)
 def test_API44_003_missing_token_denied(self):
  with patch.dict(os.environ,{},clear=True):
   r=self.client.post('/api/research/analyze',json={})
   self.assertIn(r.status_code,(413,422,503))
 def test_API44_004_invalid_token_denied(self):
  with patch.dict(os.environ,{'BZX_RESEARCH_TOKEN':'x'*32}):
   r=self.client.post('/api/research/analyze',json=dict(
        frame0_png_b64='a',frame1_png_b64='a',upper_mask_png_b64='a',lower_mask_png_b64='a',
        calibration={},roi_manifest={},observation_id='o'),headers={'Authorization':'Bearer wrong'})
   self.assertEqual(r.status_code,401)
 def test_API44_005_extra_fields_disallowed(self):
  with patch.dict(os.environ,{'BZX_RESEARCH_TOKEN':'x'*32}):
   base=dict(frame0_png_b64='a',frame1_png_b64='a',upper_mask_png_b64='a',lower_mask_png_b64='a',
        calibration={},roi_manifest={},observation_id='o')
   r=self.client.post('/api/research/analyze',json={**base,'unsafe_force':100},headers={'Authorization':'Bearer '+'x'*32})
   self.assertEqual(r.status_code,422)
 def test_API44_006_bad_image_decode_rejected(self):
  from fastapi import HTTPException
  with self.assertRaises(HTTPException):_decode('not valid base64')
 def test_API44_007_non_png_rejected(self):
  from fastapi import HTTPException
  with self.assertRaises(HTTPException):_decode(base64.b64encode(b'JPEG').decode())
 def test_API44_008_no_opencv4_bypass_in_api(self):
  if cv2.__version__.split('.')[0]=='5':self.skipTest('Run on v5 separately')
  with patch.dict(os.environ,{'BZX_RESEARCH_TOKEN':'x'*32}):
   base=dict(frame0_png_b64='a',frame1_png_b64='a',upper_mask_png_b64='a',lower_mask_png_b64='a',
        calibration={},roi_manifest={},observation_id='o')
   r=self.client.post('/api/research/analyze',json=base,headers={'Authorization':'Bearer '+'x'*32})
   self.assertEqual(r.status_code,503)
 def test_API44_009_large_png_data_rejected(self):
  from fastapi import HTTPException
  with self.assertRaises(HTTPException):_decode('a'*4_000_000)

if __name__=='__main__':unittest.main()
