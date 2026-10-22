"""API integration tests of the new UI boundary and persisted user journey."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TEMP = tempfile.TemporaryDirectory()
os.environ['BZX_DATA_DIR'] = TEMP.name
os.environ['BZX_RESEARCH_LOOP_DB'] = str(Path(TEMP.name) / 'loops.db')
os.environ['BZX_CAPTURE_ARCHIVE_DIR'] = str(Path(TEMP.name) / 'captures')
os.environ['BZX_RESEARCH_INTEGRITY_KEY'] = 'test-console-integrity-key-' + 'x' * 40
sys.path.insert(0, str(ROOT / 'app'))
from fastapi.testclient import TestClient
import console_server as server


def authenticated_client():
    client = TestClient(server.app, base_url='http://localhost', client=('127.0.0.1',50000))
    token = server.AUTH.issue_session('Test fixture')
    client.cookies.set(server.SESSION_COOKIE, token)
    client.headers.update({'Origin':'http://localhost','X-CSRF-Token':server.AUTH.session(token)['csrf']})
    return client


class ConsoleJourney(unittest.TestCase):
    def setUp(self):
        self.client = authenticated_client()

    def start(self):
        response = self.client.post('/api/console/demo', json={})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def follow(self, state, signature='rope_still'):
        return self.client.post(f"/api/console/sessions/{state['session_id']}/observe", json={
            'expected_version': state['version'], 'view': state['next_view'],
            'signature': signature, 'capture_sha256': hashlib.sha256(os.urandom(20)).hexdigest()})

    def test_cookie_and_same_origin_boundary(self):
        anonymous = TestClient(server.app, base_url='http://localhost', client=('127.0.0.1',50001))
        self.assertEqual(anonymous.get('/api/console/sessions').status_code, 401)
        self.assertEqual(self.client.post('/api/console/demo', json={},
                         headers={'Origin': 'https://untrusted.example'}).status_code, 403)
        self.assertEqual(self.client.get('/', headers={'Host': 'untrusted.example'}).status_code, 400)
        self.assertEqual(self.client.get('/research/api/research/loop/start').status_code, 404)

    def test_full_journey_persists_and_exports_without_authorization(self):
        start = self.start()
        self.assertEqual(start['next_view'], 'ROPE_PATH')
        self.assertEqual(start['mode'], 'SYNTHETIC')
        self.assertIsNotNone(start['measurement'])
        observed = self.follow(start).json()
        self.assertEqual(observed['possible_worlds'], ['LAYER_ONLY'])
        self.assertEqual(observed['modeled_recommendation'], 'REORDER')
        self.assertFalse(observed['physical_action_authorized'])
        self.assertEqual(observed['steps'][0]['source'], 'HUMAN_REPORTED')
        new_browser = authenticated_client()
        restored = new_browser.get(f"/api/console/sessions/{start['session_id']}").json()
        self.assertEqual(restored['witness']['certificate_hash'], observed['witness']['certificate_hash'])
        exported = self.client.get(f"/api/console/sessions/{start['session_id']}/export")
        self.assertIn('attachment', exported.headers['content-disposition'])
        self.assertFalse(exported.json()['physical_action_authorized'])

    def test_unknown_observation_does_not_manufacture_certainty(self):
        start = self.start()
        result = self.follow(start, '?')
        self.assertEqual(result.status_code, 200, result.text)
        result = result.json()
        self.assertEqual(result['possible_worlds'], start['possible_worlds'])
        self.assertEqual(result['disposition'], 'ABSTAIN')
        self.assertFalse(result['physical_action_authorized'])

    def test_conflicts_terminal_states_and_invalid_observations(self):
        start = self.start()
        self.assertEqual(self.follow(start, 'invented').status_code, 422)
        self.assertEqual(self.follow(start).status_code, 200)
        self.assertEqual(self.follow(start).status_code, 409)
        current = self.client.get(f"/api/console/sessions/{start['session_id']}").json()
        current['next_view'] = 'ROPE_PATH'
        self.assertEqual(self.follow(current).status_code, 422)

    def test_runtime_and_capture_fail_closed(self):
        runtime = self.client.get('/api/console/runtime').json()
        self.assertFalse(runtime['aws_verified'])
        self.assertFalse(runtime['gt_verified'])
        self.assertFalse(runtime['physical_action_authorized'])
        payload = dict(session_id='REAL', observation_id='REAL-OBS',
                       frame0_png_b64='', frame1_png_b64='', upper_mask_png_b64='', lower_mask_png_b64='',
                       calibration={}, roi_manifest={}, worlds=['A'], losses={'ABSTAIN': {'A': 0}},
                       view_signatures={}, view_costs={})
        if not runtime['opencv5']:
            response = self.client.post('/api/console/capture', json=payload)
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()['detail'], 'OPENCV5_RUNTIME_REQUIRED')

    def test_audit_and_absent_original(self):
        start = self.start()
        self.assertEqual(self.client.get(f"/api/console/sessions/{start['session_id']}/frame0").status_code, 404)
        report = self.client.get('/api/console/audit')
        self.assertEqual(report.status_code, 200)
        self.assertEqual(report.json()['status'], 'OK')
        self.assertEqual(report.json()['session_validation_failures'], [])

    def test_aws_record_requires_intact_archive_and_never_approves_deployment(self):
        from capture_archive import persist_capture
        with tempfile.TemporaryDirectory() as directory, patch.object(server, 'DATA', Path(directory)):
            self.assertIsNone(server.aws_execution_record())
            evidence = Path(directory) / 'evidence' / 'opencv5-aws'
            png = server.cv2.imencode('.png', server.np.zeros((4, 4), dtype='uint8'))[1].tobytes()
            receipt = persist_capture(evidence / 'captures', 'AWS-TEST', 'OBS-TEST',
                {name: png for name in ('frame0', 'frame1', 'upper_mask', 'lower_mask')}, {})
            report = dict(schema='BZX-GENUINE-OPENCV5-EXECUTION-V1',
                aws_execution_environment='AWS_CloudShell', aws_region='ap-northeast-1',
                input_tier='SYNTHETIC_OPENCV5_API_SMOKE_NOT_PHYSICAL_GT',
                opencv_version='5.0.0', receipt_sha256=receipt, executed_utc='2026-10-21T08:41:32Z')
            (evidence / 'execution.json').write_text(json.dumps(report))
            status = self.client.get('/api/console/runtime').json()
            self.assertTrue(status['aws_execution_record']['archive_reverified'])
            self.assertFalse(status['aws_verified'])
            self.assertFalse(status['aws_execution_record']['physical_gt_verified'])
            (evidence / 'captures' / (hashlib.sha256(png).hexdigest() + '.png')).write_bytes(b'corrupted')
            self.assertIsNone(server.aws_execution_record())
            (evidence / 'execution.json').write_text('[]')
            self.assertIsNone(server.aws_execution_record())

    def test_upload_limit_and_unknown_fields(self):
        self.assertEqual(self.client.post('/api/console/demo', json={'force_action': 'RE_TIE'}).status_code, 422)
        response = self.client.post('/api/console/demo', content=b'x' * (server.research.MAX_REQUEST_BYTES + 1), headers={'Content-Type':'application/json'})
        self.assertEqual(response.status_code, 413)

    def test_mobile_requires_https_and_mfa_without_join_bypass(self):
        with patch.object(server.app.state, 'mobile_mode', True):
            phone = TestClient(server.app, base_url='http://localhost', client=('192.168.0.88',55555))
            self.assertEqual(phone.get('/?access=anything').status_code,403)
            phone = TestClient(server.app, base_url='https://localhost', client=('192.168.0.88',55555))
            self.assertEqual(phone.get('/api/console/runtime').status_code,401)
            for alias in ('photos/','/photos/','PHOTOS/','photos%5c'):
                self.assertEqual(phone.get('/assets/'+alias+'flattened-cartons.png').status_code,401)
            self.assertFalse(phone.get('/auth/session').json()['setup_allowed'])
            token=server.AUTH.issue_session('Phone fixture')
            phone.cookies.set(server.SESSION_COOKIE,token)
            self.assertEqual(phone.get('/assets/photos/flattened-cartons.png').status_code,200)
            self.assertIsNone(phone.get('/api/console/runtime').json()['mobile_url'])

    def test_mobile_digest_fallback_hashes_exact_bytes_without_persisting(self):
        import base64
        raw = b'mobile capture\x00\xff'
        result = self.client.post('/api/console/digest', json={'bytes_b64': base64.b64encode(raw).decode()})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(self.client.post('/api/console/digest', json={'bytes_b64': '!!'}).status_code, 422)


if __name__ == '__main__':
    unittest.main()
