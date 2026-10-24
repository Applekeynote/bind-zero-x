import threading,unittest
from test_console import server,authenticated_client
from packing_jobs import PackingJobs
from fastapi.testclient import TestClient
from unittest.mock import patch

class PackingJobTests(unittest.TestCase):
    def test_owner_isolation_expiry_and_released_capacity(self):
        now=[100.];jobs=PackingJobs(clock=lambda:now[0]);finished=threading.Event()
        response=jobs.submit('judge',lambda:{'pixels':'private fixture'},finished.set)
        self.assertTrue(finished.wait(2));key=response['job_id']
        self.assertIsNone(jobs.read(key,'judge2'))
        self.assertEqual(jobs.read(key,'judge')['result']['pixels'],'private fixture')
        now[0]+=601;self.assertIsNone(jobs.read(key,'judge'))
    def test_worker_errors_never_return_internal_paths(self):
        jobs=PackingJobs();finished=threading.Event()
        def fail():raise ValueError('secret fixture path')
        response=jobs.submit('judge',fail,finished.set);self.assertTrue(finished.wait(2))
        self.assertEqual(jobs.read(response['job_id'],'judge')['error'],'SEGMENTATION_FAILED')
    def test_job_routes_require_session_and_submission_requires_csrf(self):
        anonymous=TestClient(server.app,base_url='http://localhost',client=('127.0.0.1',55000))
        self.assertEqual(anonymous.get('/api/console/segment/jobs/anything').status_code,401)
        client=authenticated_client()
        self.assertEqual(client.post('/api/console/segment',json={'demo_photo':'flat-primary','async_job':True},headers={'X-CSRF-Token':'bad'}).status_code,403)
        self.assertEqual(client.get('/api/console/segment/jobs/not-mine').status_code,404)
        with patch.object(server,'segment_cardboard',return_value={'regions':[]}):
            r=client.post('/api/console/segment',json={'demo_photo':'flat-primary','async_job':True})
        self.assertEqual(r.status_code,202);self.assertEqual(r.json()['status'],'PENDING')
