"""Disposable fixtures for password-only judges and operator MFA isolation."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_console import server
from fastapi.testclient import TestClient
from auth_security import AuthStore,AuthError,totp

PASSWORD='fixture-judge-password-only-1234'

class JudgeAccounts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.now=[1800000000.]
        self.auth=AuthStore(Path(self.temp.name)/'security',clock=lambda:self.now[0])
        token,csrf=self.auth.challenge(None,'setup')
        secret=self.auth.begin_setup(token,PASSWORD)
        self.auth.finish_setup(token,totp(secret,int(self.now[0]//30)))
        self.owner_secret=secret
        self.override=patch.object(server,'AUTH',self.auth);self.override.start()
    def tearDown(self):self.override.stop();self.temp.cleanup()
    def client(self):return TestClient(server.app,base_url='http://localhost',client=('127.0.0.1',61000))
    def challenge(self,client):
        state=client.get('/auth/session').json()
        client.headers.update({'Origin':'http://localhost','X-CSRF-Token':state['csrf']})
    def owner(self):
        client=self.client();token=self.auth.issue_session('Owner fixture')
        client.cookies.set(server.SESSION_COOKIE,token);self.challenge(client);return client
    def enroll(self,name='judge'):
        password=self.auth.create_password_judge(name)
        client=self.client();self.challenge(client)
        finished=client.post('/auth/login',json={'username':name,'password':password})
        self.assertEqual(finished.status_code,200,finished.text)
        self.assertIn('Max-Age=3600',finished.headers['set-cookie'])
        self.challenge(client);return client,password,None
    def test_password_only_judge_and_unchanged_operator_mfa(self):
        client,password,_=self.enroll()
        self.assertEqual(client.get('/auth/session').json()['role'],'judge')
        self.assertGreaterEqual(len(password),32)
        outsider=self.client();self.challenge(outsider)
        self.assertEqual(outsider.post('/auth/login',json={'username':'operator','password':PASSWORD}).status_code,401)
        self.assertEqual(outsider.post('/auth/login',json={'username':'judge','password':'wrong-fixture-password'}).status_code,401)
        self.now[0]+=30
        response=outsider.post('/auth/login',json={'username':'operator','password':PASSWORD,'code':totp(self.owner_secret,int(self.now[0]//30))})
        self.assertEqual(response.status_code,200,response.text)
        token=outsider.cookies.get(server.SESSION_COOKIE)
        self.assertEqual(self.auth.session(token)['username'],'operator')
        self.assertNotIn(password.encode(),self.auth.path.read_bytes())
    def test_owner_and_other_judge_sessions_are_inaccessible(self):
        owner=self.owner();private=owner.post('/api/console/demo',json={}).json()['session_id']
        judge,_,_=self.enroll()
        mine=judge.post('/api/console/demo',json={}).json()['session_id']
        second,_,_=self.enroll('judge2')
        other=second.post('/api/console/demo',json={}).json()['session_id']
        listed={s['session_id'] for s in judge.get('/api/console/sessions').json()}
        self.assertIn(mine,listed);self.assertNotIn(private,listed);self.assertNotIn(other,listed)
        for sid in [private,other]:
            for suffix in ['', '/export','/frame0']:
                self.assertEqual(judge.get('/api/console/sessions/'+sid+suffix).status_code,404)
            self.assertEqual(judge.post('/api/console/sessions/'+sid+'/observe',json={'expected_version':1,'view':'ROPE_PATH','signature':'rope_still','capture_sha256':'a'*64}).status_code,404)
        for endpoint in ['audit','capture','reobserve-image']:
            response=judge.get('/api/console/'+endpoint) if endpoint=='audit' else judge.post('/api/console/'+endpoint,json={})
            self.assertEqual(response.status_code,403)
        self.assertEqual(judge.get('/api/console/sessions/'+mine).status_code,200)
    def test_judge_revoke_others_does_not_sign_out_owner(self):
        owner=self.owner();judge,_,_=self.enroll()
        self.assertEqual(judge.post('/auth/revoke-others',json={}).status_code,200)
        self.assertEqual(owner.get('/api/console/runtime').status_code,200)
        self.assertEqual(judge.get('/api/console/runtime').status_code,200)
    def test_expiration_and_revocation_invalidate_existing_session(self):
        judge,_,_=self.enroll()
        self.auth.revoke_judge('judge')
        self.assertEqual(judge.get('/api/console/runtime').status_code,401)
        active,_,_=self.enroll('judge2')
        self.now[0]+=30*86400-60
        token=self.auth.issue_session('Unexpired device session',username='judge2')
        self.now[0]+=61
        self.assertIsNone(self.auth.session(token))
    def test_existing_account_cannot_be_reset_and_password_failures_are_limited(self):
        client,password,_=self.enroll()
        with self.assertRaisesRegex(AuthError,'ACCOUNT_ALREADY_EXISTS'):
            self.auth.create_password_judge()
        for _ in range(5):
            with self.assertRaisesRegex(AuthError,'INVALID_CREDENTIALS'):
                self.auth.login('wrong-password-fixture',None,'judge-peer',username='judge')
        with self.assertRaisesRegex(AuthError,'TRY_AGAIN_LATER'):
            self.auth.login(password,None,'judge-peer',username='judge')
        self.assertEqual(client.get('/api/console/runtime').status_code,200)
    def test_login_requires_origin_csrf_and_session_has_one_hour_limit(self):
        client,password,_=self.enroll();outsider=self.client();self.challenge(outsider)
        payload={'username':'judge','password':password}
        self.assertEqual(outsider.post('/auth/login',json=payload,headers={'Origin':'https://evil.invalid'}).status_code,403)
        self.assertEqual(outsider.post('/auth/login',json=payload,headers={'X-CSRF-Token':'wrong'}).status_code,403)
        self.assertEqual(outsider.get('/judge').status_code,200)
        token=client.cookies.get(server.SESSION_COOKIE)
        for _ in range(7):
            self.now[0]+=500;self.assertIsNotNone(self.auth.session(token))
        self.now[0]+=101;self.assertIsNone(self.auth.session(token))

if __name__=='__main__':unittest.main()
