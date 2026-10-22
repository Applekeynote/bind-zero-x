# coding: utf-8
import unittest, tempfile, os
from unittest.mock import patch
from fastapi.testclient import TestClient
from api_research import app
from active_evidence_loop import start_research_loop
from research_loop_store import SQLiteResearchLoops,StoreError

class ResearchLoopApiV45(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.env=patch.dict(os.environ,{'BZX_RESEARCH_TOKEN':'x'*32,
                                'BZX_RESEARCH_LOOP_DB':self.tmp.name+'/loop.db'})
  self.env.start()
  self.client=TestClient(app)
  self.headers={'Authorization':'Bearer '+'x'*32}
 def tearDown(self):self.env.stop();self.tmp.cleanup()
 def request(self):
  return {'session_id':'S','observation_id':'O','initial_image_sha256':'a'*64,
    'worlds':['A','B'],'losses':{'REORDER':{'A':0,'B':6},'RE_TIE':{'A':6,'B':0},'ABSTAIN':{'A':2,'B':2}},
    'view_signatures':{'SIDE':{'A':'left','B':'right'}},'view_costs':{'SIDE':.1}}
 def test_V45_API_001_auth_required_for_start(self):
  self.assertEqual(self.client.post('/api/research/loop/start',json=self.request()).status_code,401)
 def test_V45_API_002_multi_turn_persists_and_filters(self):
  first=self.client.post('/api/research/loop/start',json=self.request(),headers=self.headers)
  self.assertEqual(first.status_code,200,first.text)
  self.assertEqual(first.json()['next_view'],'SIDE')
  follow=self.client.post('/api/research/loop/reobserve',headers=self.headers,json={
    'session_id':'S','expected_version':0,'view':'SIDE','signature':'left',
    'capture_sha256':'b'*64,'source':'HUMAN_REPORTED'})
  self.assertEqual(follow.status_code,200,follow.text)
  self.assertEqual(follow.json()['possible_worlds'],['A'])
  self.assertFalse(follow.json()['physical_action_authorized'])
  self.assertEqual(SQLiteResearchLoops(self.tmp.name+'/loop.db').read('S')[0],1)
 def test_V45_API_003_stale_version_conflict(self):
  self.client.post('/api/research/loop/start',json=self.request(),headers=self.headers)
  body={'session_id':'S','expected_version':0,'view':'SIDE','signature':'left','capture_sha256':'b'*64}
  self.assertEqual(self.client.post('/api/research/loop/reobserve',json=body,headers=self.headers).status_code,200)
  self.assertEqual(self.client.post('/api/research/loop/reobserve',json=body,headers=self.headers).status_code,409)
 def test_V45_API_004_untrusted_cv_source_rejected(self):
  self.client.post('/api/research/loop/start',json=self.request(),headers=self.headers)
  body={'session_id':'S','expected_version':0,'view':'SIDE','signature':'left',
        'capture_sha256':'b'*64,'source':'CV_LAYER_ONLY'}
  r=self.client.post('/api/research/loop/reobserve',json=body,headers=self.headers)
  self.assertEqual(r.status_code,422);self.assertIn('SERVER_SIDE_CV_REQUIRED',r.text)
 def test_V45_API_005_duplicate_session_refused(self):
  self.assertEqual(self.client.post('/api/research/loop/start',json=self.request(),headers=self.headers).status_code,200)
  self.assertEqual(self.client.post('/api/research/loop/start',json=self.request(),headers=self.headers).status_code,422)
 def test_V45_API_006_rogue_extra_action_rejected(self):
  r=self.client.post('/api/research/loop/start',json={**self.request(),'force_N':100},headers=self.headers)
  self.assertEqual(r.status_code,422)
 def test_V45_API_007_auth_required_for_followup(self):
  self.assertEqual(self.client.post('/api/research/loop/reobserve',json={}).status_code,401)
