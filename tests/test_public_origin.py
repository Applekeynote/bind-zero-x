import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from starlette.testclient import TestClient
from public_origin import PublicOrigin,OutboundBudget
from auth_security import AuthStore,AuthError
from test_console import server


class PublicBoundary(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.auth=AuthStore(Path(self.temp.name)/'security',judge_only=True)
        self.password=self.auth.create_password_judge()
        self.auth_override=patch.object(server,'AUTH',self.auth);self.auth_override.start()
        self.mode=patch.object(server,'PUBLIC_MODE',True);self.mode.start()
        self.host='dpublicfixture123.cloudfront.net';self.secret='fixture-origin-token-'+'x'*48
        server.ALLOWED_HOSTS.append(self.host)
        server.app.middleware_stack=None
        self.client=TestClient(PublicOrigin(server.app,'https://'+self.host,self.secret),base_url='https://'+self.host)
        self.headers={'X-BZX-Origin':self.secret,'CloudFront-Forwarded-Proto':'https','CloudFront-Viewer-Address':'203.0.113.27:48000'}
    def tearDown(self):
        server.ALLOWED_HOSTS.remove(self.host);server.app.middleware_stack=None;self.mode.stop();self.auth_override.stop();self.temp.cleanup()
    def test_direct_origin_and_spoofed_forwarding_are_denied(self):
        self.assertEqual(self.client.get('/judge').status_code,404)
        self.assertEqual(self.client.get('/judge',headers={**self.headers,'X-BZX-Origin':'wrong'}).status_code,404)
        self.assertEqual(self.client.get('/judge',headers={**self.headers,'CloudFront-Forwarded-Proto':'http'}).status_code,404)
        self.assertEqual(self.client.get('/judge',headers={**self.headers,'CloudFront-Viewer-Address':'not-an-address'}).status_code,400)
    def test_judge_only_secure_cookie_csrf_and_no_operator_setup(self):
        self.client.headers.update(self.headers)
        state=self.client.get('/auth/session').json()
        self.assertTrue(state['configured']);self.assertFalse(state['setup_allowed'])
        self.client.headers.update({'Origin':'https://'+self.host,'X-CSRF-Token':state['csrf']})
        self.assertEqual(self.client.post('/auth/setup/begin',json={'password':self.password}).status_code,403)
        self.assertEqual(self.client.post('/auth/login',json={'username':'operator','password':self.password}).status_code,401)
        response=self.client.post('/auth/login',json={'username':'judge','password':self.password})
        self.assertEqual(response.status_code,200,response.text)
        self.assertIn('Secure',response.headers['set-cookie']);self.assertIn('HttpOnly',response.headers['set-cookie'])
        self.assertEqual(self.client.get('/api/console/runtime').json()['role'],'judge')
        self.assertEqual(self.client.get('/api/console/audit').status_code,403)
        self.assertEqual(self.client.post('/api/console/demo',json={},headers={'Origin':'https://evil.invalid'}).status_code,403)
        with self.assertRaises(AuthError):self.auth.issue_session(username='operator')
    def test_configuration_rejects_http_and_external_hosts(self):
        for url in ['http://dabc.cloudfront.net','https://evil.invalid','https://dabc.cloudfront.net/path']:
            with self.assertRaises(ValueError):PublicOrigin(server.app,url,self.secret)
    def test_egress_budget_is_durable_and_limits_response_bytes(self):
        path=Path(self.temp.name)/'budget.db';budget=OutboundBudget(path,daily=100,total=150)
        self.assertTrue(budget.reserve(80));self.assertFalse(budget.reserve(21))
        restarted=OutboundBudget(path,daily=100,total=150)
        self.assertFalse(restarted.reserve(21));self.assertTrue(restarted.reserve(20))
    def test_gateway_accepts_only_its_overwritten_edge_context(self):
        host='example123.execute-api.ap-northeast-1.amazonaws.com'
        async def simple(scope,receive,send):
            from starlette.responses import JSONResponse
            await JSONResponse({'client':scope['client'][0],'scheme':scope['scheme']})(scope,receive,send)
        client=TestClient(PublicOrigin(simple,'https://'+host,self.secret),base_url='https://'+host)
        response=client.get('/judge',headers={'X-BZX-Origin':self.secret,'X-BZX-Edge-Proto':'https','X-BZX-Viewer-IP':'203.0.113.28','X-Forwarded-For':'127.0.0.1'})
        self.assertEqual(response.json(),{'client':'203.0.113.28','scheme':'https'})

if __name__=='__main__':unittest.main()
