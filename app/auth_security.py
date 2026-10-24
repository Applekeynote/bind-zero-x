"""Password + RFC 6238 TOTP, expiring sessions, replay and attempt protection."""
from __future__ import annotations
import base64
import ctypes
import hashlib
import hmac
import os
from pathlib import Path
import re
import secrets
import struct
import threading
import time
from urllib.parse import quote
from cryptography.fernet import Fernet
from sqlite_scope import connect

SESSION_SECONDS = 8 * 60 * 60
IDLE_SECONDS = 15 * 60
CHALLENGE_SECONDS = 10 * 60

class AuthError(ValueError):
    pass


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def totp(secret, counter, digits=6, algorithm='sha1'):
    key = base64.b32decode(secret + '=' * (-len(secret) % 8), casefold=False)
    mac = hmac.new(key, struct.pack('>Q', counter), getattr(hashlib, algorithm)).digest()
    offset = mac[-1] & 15
    return str((int.from_bytes(mac[offset:offset+4], 'big') & 0x7fffffff) % (10 ** digits)).zfill(digits)


def password_key(password, salt):
    if not isinstance(password, str) or not 14 <= len(password) <= 128:
        raise AuthError('PASSWORD_LENGTH_14_TO_128')
    return hashlib.scrypt(password.encode(), salt=salt, n=2**17, r=8, p=1, dklen=32, maxmem=256*1024*1024)


class SecretBox:
    """DPAPI on Windows. On Unix, an exclusive 0600 local encryption key."""
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _dpapi(self, raw, decrypt=False):
        from ctypes import wintypes
        class Blob(ctypes.Structure):
            _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
        buffer = ctypes.create_string_buffer(raw)
        incoming = Blob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
        outgoing = Blob()
        crypt = ctypes.WinDLL('crypt32', use_last_error=True)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree.restype = ctypes.c_void_p
        func = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
        func.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
        func.restype = wintypes.BOOL
        if not func(ctypes.byref(incoming), None, None, None, None, 1, ctypes.byref(outgoing)):
            raise AuthError('OS_SECRET_PROTECTION_FAILED')
        try:
            return ctypes.string_at(outgoing.data, outgoing.size)
        finally:
            kernel.LocalFree(outgoing.data)

    def _fernet(self):
        path = self.directory / 'auth-local.key'
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            if path.is_symlink() or path.stat().st_mode & 0o077:
                raise AuthError('INSECURE_SECRET_KEY_FILE')
        else:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(Fernet.generate_key())
        return Fernet(path.read_bytes())

    def seal(self, raw):
        return b'DPAPI1:' + self._dpapi(raw) if os.name == 'nt' else b'FERNET1:' + self._fernet().encrypt(raw)

    def open(self, raw):
        if raw.startswith(b'DPAPI1:') and os.name == 'nt':
            return self._dpapi(raw[7:], decrypt=True)
        if raw.startswith(b'FERNET1:') and os.name != 'nt':
            return self._fernet().decrypt(raw[8:])
        raise AuthError('SECRET_PROTECTION_PLATFORM_MISMATCH')


class AuthStore:
    def __init__(self, directory, clock=time.time, judge_only=False):
        self.directory = Path(directory)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path = self.directory / 'auth.db'
        self.box = SecretBox(self.directory)
        self.clock = clock
        self.judge_only=judge_only
        self.login_gate = threading.BoundedSemaphore(2)
        with connect(self.path) as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS credentials(id INTEGER PRIMARY KEY CHECK(id=1),salt BLOB NOT NULL,password_hash BLOB NOT NULL,secret BLOB NOT NULL,last_counter INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,csrf TEXT NOT NULL,created REAL NOT NULL,seen REAL NOT NULL,expires REAL NOT NULL,label TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS challenges(token_hash TEXT PRIMARY KEY,csrf TEXT NOT NULL,peer TEXT NOT NULL,expires REAL NOT NULL,pending BLOB,salt BLOB,password_hash BLOB);
                CREATE TABLE IF NOT EXISTS attempts(peer TEXT PRIMARY KEY,failures INTEGER NOT NULL,until REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS accounts(username TEXT PRIMARY KEY,role TEXT NOT NULL CHECK(role='judge'),status TEXT NOT NULL,salt BLOB,password_hash BLOB,secret BLOB,last_counter INTEGER NOT NULL DEFAULT -1,expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS invitations(token_hash TEXT PRIMARY KEY,username TEXT NOT NULL,expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS enrollment_accounts(challenge_hash TEXT PRIMARY KEY,invite_hash TEXT NOT NULL,username TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS session_principals(token_hash TEXT PRIMARY KEY,username TEXT NOT NULL);
            ''')
        if os.name != 'nt':
            self.path.chmod(0o600)
        # A restart invalidates sessions and pre-auth challenges; TOTP replay state persists.
        with connect(self.path) as db:
            db.execute('DELETE FROM sessions')
            db.execute('DELETE FROM challenges')
            db.execute('DELETE FROM enrollment_accounts')
            db.execute('DELETE FROM session_principals')

    def configured(self):
        with connect(self.path) as db:
            if self.judge_only:return db.execute("SELECT 1 FROM accounts WHERE status='ACTIVE' AND expires>?",(self.clock(),)).fetchone() is not None
            return db.execute('SELECT 1 FROM credentials WHERE id=1').fetchone() is not None

    def challenge(self, token, peer):
        with connect(self.path) as db:
            row = db.execute('SELECT csrf,expires FROM challenges WHERE token_hash=? AND peer=?', (digest(token), peer)).fetchone() if token else None
            if row and row[1] > self.clock():
                return token, row[0]
            db.execute('DELETE FROM challenges WHERE expires<=?', (self.clock(),))
            if db.execute('SELECT COUNT(*) FROM challenges').fetchone()[0] >= 256:
                db.execute('DELETE FROM challenges WHERE token_hash IN (SELECT token_hash FROM challenges ORDER BY expires LIMIT 32)')
            token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            db.execute('INSERT INTO challenges VALUES(?,?,?,?,NULL,NULL,NULL)', (digest(token), csrf, peer, self.clock()+CHALLENGE_SECONDS))
            return token, csrf

    def check_challenge(self, token, csrf, peer):
        with connect(self.path) as db:
            row = db.execute('SELECT csrf,expires FROM challenges WHERE token_hash=? AND peer=?', (digest(token or ''), peer)).fetchone()
        if not row or row[1] <= self.clock() or not hmac.compare_digest(row[0], csrf or ''):
            raise AuthError('INVALID_CSRF')

    def _attempt_allowed(self, peer):
        with connect(self.path) as db:
            db.execute('DELETE FROM attempts WHERE until<=?', (self.clock(),))
            per = db.execute('SELECT failures FROM attempts WHERE peer=?', (peer,)).fetchone()
            glob = db.execute("SELECT failures FROM attempts WHERE peer='*'").fetchone()
            if (per and per[0] >= 5) or (glob and glob[0] >= 30):
                raise AuthError('TRY_AGAIN_LATER')

    def _failure(self, peer):
        with connect(self.path) as db:
            for key in (peer, '*'):
                db.execute('INSERT INTO attempts VALUES(?,1,?) ON CONFLICT(peer) DO UPDATE SET failures=failures+1', (key, self.clock()+15*60))
            if db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0] > 512:
                db.execute("DELETE FROM attempts WHERE peer!='*' AND peer NOT IN (SELECT peer FROM attempts ORDER BY until DESC LIMIT 256)")

    def _match(self, secret, code, previous):
        if not isinstance(code, str) or not re.fullmatch(r'[0-9]{6}', code):
            return None
        now = int(self.clock() // 30)
        matches = [step for step in (now-1, now, now+1) if step >= 0 and hmac.compare_digest(totp(secret, step), code)]
        return next((step for step in matches if step > previous), None)

    def begin_setup(self, token, password):
        if self.configured():
            raise AuthError('MFA_ALREADY_CONFIGURED')
        salt = secrets.token_bytes(16)
        key = password_key(password, salt)
        secret = base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')
        with connect(self.path) as db:
            db.execute('UPDATE challenges SET pending=?,salt=?,password_hash=? WHERE token_hash=? AND expires>?',
                       (self.box.seal(secret.encode()), salt, key, digest(token), self.clock()))
        return secret

    def finish_setup(self, token, code):
        self._attempt_allowed('setup')
        with connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT pending,salt,password_hash FROM challenges WHERE token_hash=? AND expires>?', (digest(token), self.clock())).fetchone()
            if db.execute('SELECT 1 FROM credentials WHERE id=1').fetchone():
                raise AuthError('MFA_ALREADY_CONFIGURED')
            step = self._match(self.box.open(row[0]).decode(), code, -1) if row and row[0] else None
            if step is None:
                failed = True
            else:
                db.execute('INSERT INTO credentials VALUES(1,?,?,?,?)', (row[1],row[2],row[0],step))
                db.execute('DELETE FROM challenges')
                failed = False
        if failed:
            self._failure('setup'); raise AuthError('INVALID_CREDENTIALS')

    def login(self, password, code, peer, username='operator'):
        self._attempt_allowed(peer)
        if self.judge_only and username=='operator':
            self._failure(peer);raise AuthError('INVALID_CREDENTIALS')
        if not self.login_gate.acquire(blocking=False):
            raise AuthError('LOGIN_BUSY')
        try:
            with connect(self.path) as db:
                if username=='operator':
                    row = db.execute('SELECT salt,password_hash,secret,last_counter FROM credentials WHERE id=1').fetchone()
                else:
                    row = db.execute("SELECT salt,password_hash,secret,last_counter FROM accounts WHERE username=? AND status='ACTIVE' AND expires>?",(username,self.clock())).fetchone()
            valid = False
            if row:
                try:
                    valid = hmac.compare_digest(password_key(password, row[0]), row[1])
                except AuthError:
                    pass
            else:
                # Unknown/invited identities incur the same bounded password work.
                try: password_key(password,b'BZX-DUMMY-SALT-01')
                except AuthError: pass
            password_only=bool(username!='operator' and row and row[2] is None)
            step = self._match(self.box.open(row[2]).decode(), code, row[3]) if valid and not password_only else None
            if not valid or (not password_only and step is None):
                self._failure(peer); raise AuthError('INVALID_CREDENTIALS')
            with connect(self.path) as db:
                db.execute('BEGIN IMMEDIATE')
                if username=='operator':
                    updated = db.execute('UPDATE credentials SET last_counter=? WHERE id=1 AND last_counter<?', (step,step)).rowcount
                elif password_only:
                    updated=int(db.execute("SELECT 1 FROM accounts WHERE username=? AND status='ACTIVE' AND secret IS NULL AND expires>?",(username,self.clock())).fetchone() is not None)
                else:
                    updated = db.execute("UPDATE accounts SET last_counter=? WHERE username=? AND status='ACTIVE' AND expires>? AND last_counter<?",(step,username,self.clock(),step)).rowcount
                if updated != 1:
                    raise AuthError('INVALID_CREDENTIALS')
                db.execute('DELETE FROM attempts WHERE peer=?', (peer,))
            return self.issue_session(peer,username=username)
        finally:
            self.login_gate.release()

    def issue_session(self, label='Device', username='operator'):
        if self.judge_only and username=='operator':raise AuthError('INVALID_CREDENTIALS')
        token, csrf, now = secrets.token_urlsafe(48), secrets.token_urlsafe(32), self.clock()
        with connect(self.path) as db:
            if username!='operator' and not db.execute("SELECT 1 FROM accounts WHERE username=? AND status='ACTIVE' AND expires>?",(username,now)).fetchone():
                raise AuthError('INVALID_CREDENTIALS')
            db.execute('DELETE FROM sessions WHERE expires<=? OR seen<=?', (now,now-IDLE_SECONDS))
            if db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0] >= 32:
                db.execute('DELETE FROM sessions WHERE token_hash IN (SELECT token_hash FROM sessions ORDER BY seen LIMIT 1)')
            db.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?)', (digest(token),csrf,now,now,now+(SESSION_SECONDS if username=='operator' else 3600),label[:80]))
            db.execute('INSERT INTO session_principals VALUES(?,?)',(digest(token),username))
            db.execute('DELETE FROM session_principals WHERE token_hash NOT IN (SELECT token_hash FROM sessions)')
        return token

    def session(self, token, touch=True):
        if not token or len(token)>128:
            return None
        now = self.clock()
        with connect(self.path) as db:
            row = db.execute('SELECT csrf,created,seen,expires,label FROM sessions WHERE token_hash=?', (digest(token),)).fetchone()
            principal=db.execute('SELECT username FROM session_principals WHERE token_hash=?',(digest(token),)).fetchone()
            if not principal:return None
            username=principal[0]
            if username!='operator' and not db.execute("SELECT 1 FROM accounts WHERE username=? AND status='ACTIVE' AND expires>?",(username,now)).fetchone():
                db.execute('DELETE FROM sessions WHERE token_hash=?',(digest(token),));return None
            if not row or row[3] <= now or row[2] <= now-IDLE_SECONDS:
                if row: db.execute('DELETE FROM sessions WHERE token_hash=?', (digest(token),))
                return None
            if touch: db.execute('UPDATE sessions SET seen=? WHERE token_hash=?', (now,digest(token)))
        return dict(csrf=row[0],created=row[1],seen=row[2],expires=row[3],label=row[4],username=username,role='operator' if username=='operator' else 'judge')

    def logout(self, token, others=False):
        with connect(self.path) as db:
            if others:
                principal=db.execute('SELECT username FROM session_principals WHERE token_hash=?',(digest(token),)).fetchone()
                username=principal[0] if principal else 'operator'
                db.execute('DELETE FROM sessions WHERE token_hash!=? AND token_hash IN (SELECT token_hash FROM session_principals WHERE username=?)',(digest(token),username))
            else:db.execute('DELETE FROM sessions WHERE token_hash=?',(digest(token),))
            db.execute('DELETE FROM session_principals WHERE token_hash NOT IN (SELECT token_hash FROM sessions)')

    def provisioning_uri(self, secret, username='Operator'):
        return f'otpauth://totp/{quote("BIND ZERO-X:"+username)}?secret={secret}&issuer=BIND%20ZERO-X&algorithm=SHA1&digits=6&period=30'

    def create_password_judge(self,username='judge',days=30):
        if not self.configured() and not self.judge_only:raise AuthError('OWNER_MFA_REQUIRED')
        if not re.fullmatch(r'[a-z][a-z0-9_-]{2,31}',username) or username=='operator':raise AuthError('INVALID_USERNAME')
        if not 1<=days<=90:raise AuthError('INVALID_ACCOUNT_LIFETIME')
        password=secrets.token_urlsafe(24);salt=secrets.token_bytes(16);key=password_key(password,salt)
        with connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT status FROM accounts WHERE username=?',(username,)).fetchone()
            if row and row[0]!='INVITED':raise AuthError('ACCOUNT_ALREADY_EXISTS')
            if row:
                db.execute("UPDATE accounts SET status='ACTIVE',salt=?,password_hash=?,secret=NULL,last_counter=-1 WHERE username=?",(salt,key,username))
            else:
                db.execute("INSERT INTO accounts(username,role,status,salt,password_hash,secret,last_counter,expires) VALUES(?,'judge','ACTIVE',?,?,NULL,-1,?)",(username,salt,key,self.clock()+days*86400))
            db.execute('DELETE FROM invitations WHERE username=?',(username,))
            db.execute('DELETE FROM challenges WHERE token_hash IN (SELECT challenge_hash FROM enrollment_accounts WHERE username=?)',(username,))
            db.execute('DELETE FROM enrollment_accounts WHERE username=?',(username,))
        return password

    def revoke_judge(self,username):
        with connect(self.path) as db:
            if db.execute("UPDATE accounts SET status='REVOKED' WHERE username=?",(username,)).rowcount!=1:raise AuthError('ACCOUNT_NOT_FOUND')
            db.execute('DELETE FROM invitations WHERE username=?',(username,))
            db.execute('DELETE FROM sessions WHERE token_hash IN (SELECT token_hash FROM session_principals WHERE username=?)',(username,))
            db.execute('DELETE FROM session_principals WHERE username=?',(username,))
            db.execute('DELETE FROM challenges WHERE token_hash IN (SELECT challenge_hash FROM enrollment_accounts WHERE username=?)',(username,))
            db.execute('DELETE FROM enrollment_accounts WHERE username=?',(username,))

    def judge_status(self,username):
        with connect(self.path) as db:row=db.execute('SELECT role,status,expires FROM accounts WHERE username=?',(username,)).fetchone()
        if not row:raise AuthError('ACCOUNT_NOT_FOUND')
        return dict(username=username,role=row[0],status=row[1],expires=row[2])
