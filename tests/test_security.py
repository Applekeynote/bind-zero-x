"""Authentication boundaries, replay, limits and source publication regressions."""
import base64
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_console import server, authenticated_client
from fastapi.testclient import TestClient
from auth_security import AuthStore, AuthError, totp, IDLE_SECONDS, SESSION_SECONDS
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from package_release import source_files, build

PASSWORD='fixture-only-password-1234'

class Authentication(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.now=[1800000000.0]
        self.store=AuthStore(Path(self.tmp.name),clock=lambda:self.now[0])
        self.override=patch.object(server,'AUTH',self.store)
        self.override.start()
        self.client=TestClient(server.app,base_url='http://localhost',client=('127.0.0.1',60000))
    def tearDown(self):
        self.override.stop(); self.tmp.cleanup()
    def challenge(self,client=None):
        client=client or self.client
        result=client.get('/auth/session')
        client.headers.update({'Origin':str(client.base_url).rstrip('/'),'X-CSRF-Token':result.json()['csrf']})
        return result.json()
    def enroll(self):
        self.challenge()
        result=self.client.post('/auth/setup/begin',json={'password':PASSWORD})
        self.assertEqual(result.status_code,200,result.text)
        self.secret=result.json()['secret']
        result=self.client.post('/auth/setup/finish',json={'code':totp(self.secret,int(self.now[0]//30))})
        self.assertEqual(result.status_code,200,result.text)
        return result
    def test_rfc6238_vectors(self):
        secret=base64.b32encode(b'12345678901234567890').decode().rstrip('=')
        for seconds,expected in ((59,'94287082'),(1111111109,'07081804'),(1111111111,'14050471'),(1234567890,'89005924'),(2000000000,'69279037'),(20000000000,'65353130')):
            self.assertEqual(totp(secret,seconds//30,digits=8),expected)
    def test_setup_login_replay_secure_cookie_and_logout(self):
        result=self.enroll()
        self.assertIn('HttpOnly',result.headers['set-cookie'])
        self.assertTrue(self.store.configured())
        self.assertEqual(self.client.get('/api/console/runtime').status_code,200)
        token=self.client.cookies.get(server.SESSION_COOKIE)
        with patch.object(server.app.state,'mobile_mode',True):
            phone=TestClient(server.app,base_url='https://localhost',client=('192.168.1.8',60001))
            self.challenge(phone)
            payload={'password':PASSWORD,'code':totp(self.secret,int(self.now[0]//30))}
            self.assertEqual(phone.post('/auth/login',json=payload).status_code,401)
            self.now[0]+=30
            payload['code']=totp(self.secret,int(self.now[0]//30))
            result=phone.post('/auth/login',json=payload)
            self.assertEqual(result.status_code,200,result.text)
            self.assertIn('Secure',result.headers['set-cookie'])
            self.assertNotEqual(token,phone.cookies.get(server.SESSION_COOKIE))
            self.challenge(phone)
            self.assertEqual(phone.post('/auth/revoke-others',json={}).status_code,200)
            self.assertEqual(self.client.get('/api/console/runtime').status_code,401)
            self.assertEqual(phone.post('/auth/logout',json={}).status_code,200)
            self.assertEqual(phone.get('/api/console/runtime').status_code,401)
    def test_wrong_factors_and_lockout(self):
        self.enroll();self.now[0]+=30
        for index in range(5):
            with self.assertRaisesRegex(AuthError,'INVALID_CREDENTIALS'):
                self.store.login('incorrect-password-1234',totp(self.secret,int(self.now[0]//30)),'attacker')
        with self.assertRaisesRegex(AuthError,'TRY_AGAIN_LATER'):
            self.store.login(PASSWORD,totp(self.secret,int(self.now[0]//30)),'attacker')
        self.now[0]+=901
        token=self.store.login(PASSWORD,totp(self.secret,int(self.now[0]//30)),'attacker')
        self.assertIsNotNone(self.store.session(token))
        with self.assertRaisesRegex(AuthError,'INVALID_CREDENTIALS'):
            self.store.login(PASSWORD,'000000','other')
    def test_expired_login_challenge_refresh_preserves_unused_totp(self):
        self.enroll()
        self.client.cookies.clear()
        self.challenge()
        self.now[0]+=601
        code=totp(self.secret,int(self.now[0]//30))
        payload={'password':PASSWORD,'code':code}
        stale=self.client.post('/auth/login',json=payload)
        self.assertEqual(stale.status_code,403)
        self.assertEqual(stale.json()['detail'],'INVALID_CSRF')
        self.challenge()
        fresh=self.client.post('/auth/login',json=payload)
        self.assertEqual(fresh.status_code,200,fresh.text)
        self.assertEqual(self.client.get('/api/console/runtime').status_code,200)
    def test_expiry_restart_and_secret_storage(self):
        self.enroll()
        token=self.client.cookies.get(server.SESSION_COOKIE)
        self.assertNotIn(self.secret.encode(),self.store.path.read_bytes())
        self.assertNotIn(PASSWORD.encode(),self.store.path.read_bytes())
        self.now[0]+=IDLE_SECONDS+1
        self.assertIsNone(self.store.session(token))
        token=self.store.issue_session()
        for _ in range(33):
            self.now[0]+=899
            self.store.session(token)
        self.assertIsNone(self.store.session(token))
        token=self.store.issue_session()
        restarted=AuthStore(self.tmp.name,clock=lambda:self.now[0])
        self.assertTrue(restarted.configured())
        self.assertIsNone(restarted.session(token))
    def test_local_setup_origin_csrf_body_and_proxy_boundaries(self):
        self.challenge()
        self.assertEqual(self.client.post('/auth/setup/begin',json={'password':PASSWORD},headers={'X-CSRF-Token':'wrong'}).status_code,403)
        self.assertEqual(self.client.post('/auth/setup/begin',json={'password':PASSWORD},headers={'Origin':'http://evil.invalid'}).status_code,403)
        self.assertEqual(self.client.post('/auth/setup/begin',content=b'x'*16385,headers={'Content-Type':'application/json'}).status_code,413)
        with patch.object(server.app.state,'mobile_mode',True):
            remote=TestClient(server.app,base_url='https://localhost',client=('192.168.1.5',60001))
            state=self.challenge(remote)
            self.assertFalse(state['setup_allowed'])
            self.assertEqual(remote.post('/auth/setup/begin',json={'password':PASSWORD},headers={'X-Forwarded-For':'127.0.0.1'}).status_code,403)
            plain=TestClient(server.app,base_url='http://localhost',client=('192.168.1.5',60001))
            self.assertEqual(plain.get('/',headers={'X-Forwarded-Proto':'https','X-Forwarded-For':'127.0.0.1'}).status_code,403)
    def test_signature_amplification_rejected_before_decode(self):
        self.enroll();self.challenge()
        payload=dict(session_id='LIMIT',observation_id='LIMIT',frame0_png_b64='',frame1_png_b64='',upper_mask_png_b64='',lower_mask_png_b64='',calibration={},roi_manifest={},worlds=['A','B'],losses={'ABSTAIN':{'A':0,'B':0}},view_signatures={'SIDE':{'A':['a']*17,'B':'b'}},view_costs={'SIDE':.1})
        with patch.object(server.research,'_decode',side_effect=AssertionError('decode reached')):
            result=self.client.post('/api/console/capture',json=payload)
        self.assertEqual(result.status_code,422,result.text)
        self.assertIn('SIGNATURE_LIMIT',result.text)

class Publication(unittest.TestCase):
    def test_allowlist_excludes_unlisted_env_and_runtime(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'scripts').mkdir();(root/'bind-zero-x/deploy').mkdir(parents=True)
            (root/'scripts/release-files.json').write_text(json.dumps(['README.md']))
            (root/'README.md').write_text('safe source')
            (root/'bind-zero-x/deploy/research.env').write_text('SENTINEL_SECRET')
            import zipfile
            with zipfile.ZipFile(build(root)) as package:
                self.assertEqual(sorted(package.namelist()),['README.md','RELEASE_SHA256.txt'])
                self.assertFalse(any(b'SENTINEL_SECRET' in package.read(n) for n in package.namelist()))
            (root/'scripts/release-files.json').write_text(json.dumps(['bind-zero-x/deploy/research.env']))
            with self.assertRaisesRegex(ValueError,'UNSAFE_RELEASE_FILE'): source_files(root)
            (root/'scripts/release-files.json').write_text(json.dumps(['../outside.py']))
            with self.assertRaisesRegex(ValueError,'UNSAFE_RELEASE_PATH'): source_files(root)
    def test_private_key_marker_in_renamed_text_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'scripts').mkdir()
            (root/'scripts/release-files.json').write_text(json.dumps(['README.md']))
            (root/'README.md').write_text('-----BEGIN '+'PRIVATE KEY-----')
            with self.assertRaisesRegex(ValueError,'SECRET_IN_RELEASE'): source_files(root)

if __name__=='__main__': unittest.main()
