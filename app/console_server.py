"""UI adapter over the BIND ZERO-X v4.9 research core, with opt-in LAN access."""
from __future__ import annotations

import hashlib
import hmac
import base64
import binascii
import ipaddress
import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys
from dataclasses import asdict
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'bind-zero-x' / 'code'))

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, ConfigDict, Field

import api_research as research
from active_evidence_loop import start_research_loop, trace_dict, LoopError
from research_loop_store import SQLiteResearchLoops, StoreError
from research_pipeline import analyze
from operations_audit import inspect
from sqlite_scope import connect
from capture_archive import verify_capture
from auth_security import AuthStore, AuthError, SESSION_SECONDS
from packing_vision import segment_cardboard
import io
import threading
import qrcode
import qrcode.image.svg

DATA = Path(os.environ.get('BZX_DATA_DIR', ROOT / 'runtime'))
DATA.mkdir(parents=True, exist_ok=True)
os.environ.setdefault('BZX_RESEARCH_LOOP_DB', str(DATA / 'research.db'))
os.environ.setdefault('BZX_CAPTURE_ARCHIVE_DIR', str(DATA / 'captures'))
os.environ.setdefault('BZX_RESEARCH_TOKEN', secrets.token_urlsafe(48))
Path(os.environ['BZX_CAPTURE_ARCHIVE_DIR']).mkdir(parents=True, exist_ok=True)
AUTH = AuthStore(DATA / 'security')
SESSION_COOKIE = 'bzx_session'
BOOT_COOKIE = 'bzx_preauth'
ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
EXPENSIVE_GATE = threading.BoundedSemaphore(2)

app = FastAPI(title='BIND ZERO-X Local Research Console', docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
app.state.mobile_mode = False
app.state.mobile_url = None


def store():
    return SQLiteResearchLoops(os.environ['BZX_RESEARCH_LOOP_DB'])


def metadata_db():
    db = connect(str(DATA / 'console.db'))
    db.row_factory = sqlite3.Row
    db.execute('CREATE TABLE IF NOT EXISTS metadata (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
    return db


def save_metadata(sid, label, mode, measurement=None):
    body = dict(label=label, mode=mode, created_at=datetime.now(timezone.utc).isoformat(),
                measurement=measurement)
    with metadata_db() as db:
        db.execute('INSERT INTO metadata VALUES (?,?)', (sid, json.dumps(body)))


def loopback(request):
    try:
        return ipaddress.ip_address(request.client.host).is_loopback
    except (ValueError, AttributeError):
        return False


def security_headers(response, request):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
    response.headers['Cross-Origin-Resource-Policy'] = 'same-origin'
    response.headers['Permissions-Policy'] = 'camera=(self), microphone=(), geolocation=()'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; "
        "style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
    response.headers['Cache-Control'] = 'no-store'
    if request.url.scheme == 'https':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000'
    return response


@app.middleware('http')
async def local_console_boundary(request: Request, call_next):
    def reject(code, status):
        return security_headers(JSONResponse({'detail': code}, status_code=status), request)
    if app.state.mobile_mode and request.url.scheme != 'https' and not loopback(request):
        return reject('HTTPS_REQUIRED', 403)
    if not app.state.mobile_mode and not loopback(request):
        return reject('LOCAL_ONLY', 403)
    request.state.session = AUTH.session(request.cookies.get(SESSION_COOKIE))
    path = request.url.path
    protected = path.startswith('/api/console/')
    if protected and request.state.session is None:
        return reject('MFA_SESSION_REQUIRED', 401)
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        if request.headers.get('origin') != str(request.base_url).rstrip('/'):
            return reject('SAME_ORIGIN_REQUIRED', 403)
        if request.headers.get('content-type', '').split(';')[0].strip() != 'application/json':
            return reject('JSON_REQUIRED', 415)
        if request.state.session is not None:
            if not hmac.compare_digest(request.state.session['csrf'], request.headers.get('x-csrf-token', '')):
                return reject('INVALID_CSRF', 403)
        else:
            try:
                AUTH.check_challenge(request.cookies.get(BOOT_COOKIE), request.headers.get('x-csrf-token'), request.client.host)
            except AuthError:
                return reject('INVALID_CSRF', 403)
        limit = research.MAX_REQUEST_BYTES if protected else 16_384
        raw = bytearray()
        async for chunk in request.stream():
            if len(raw) + len(chunk) > limit:
                return reject('BODY_SIZE_OUT_OF_RANGE', 413)
            raw.extend(chunk)
        request._body = bytes(raw)
    return security_headers(await call_next(request), request)


def session_cookie(response, request, token):
    response.set_cookie(SESSION_COOKIE, token, httponly=True, secure=request.url.scheme == 'https',
                        samesite='strict', max_age=SESSION_SECONDS, path='/')
    response.delete_cookie(BOOT_COOKIE, path='/')
    return response


@app.get('/auth/session')
def auth_status(request: Request):
    state = request.state.session
    if state:
        return dict(authenticated=True, configured=True, csrf=state['csrf'], expires=state['expires'])
    token, csrf = AUTH.challenge(request.cookies.get(BOOT_COOKIE), request.client.host)
    response = JSONResponse(dict(authenticated=False, configured=AUTH.configured(),
                                 setup_allowed=loopback(request) and not AUTH.configured(), csrf=csrf))
    response.set_cookie(BOOT_COOKIE, token, httponly=True, secure=request.url.scheme == 'https',
                        samesite='strict', max_age=600, path='/')
    return response


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    password: str = Field(min_length=14, max_length=128)
    code: str = Field(pattern=r'^[0-9]{6}$')


class SetupRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    password: str = Field(min_length=14, max_length=128)


class CodeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    code: str = Field(pattern=r'^[0-9]{6}$')


def auth_error(exc):
    status = 429 if str(exc) in ('TRY_AGAIN_LATER', 'LOGIN_BUSY') else 401
    raise HTTPException(status, str(exc))


@app.post('/auth/setup/begin')
def setup_begin(request: Request, data: SetupRequest):
    if not loopback(request) or AUTH.configured():
        raise HTTPException(403, 'LOCAL_INITIAL_SETUP_ONLY')
    secret = AUTH.begin_setup(request.cookies.get(BOOT_COOKIE, ''), data.password)
    image = qrcode.make(AUTH.provisioning_uri(secret), image_factory=qrcode.image.svg.SvgPathImage)
    buffer = io.BytesIO(); image.save(buffer)
    return dict(secret=secret, qr='data:image/svg+xml;base64,' + base64.b64encode(buffer.getvalue()).decode())


@app.post('/auth/setup/finish')
def setup_finish(request: Request, data: CodeRequest):
    if not loopback(request) or AUTH.configured():
        raise HTTPException(403, 'LOCAL_INITIAL_SETUP_ONLY')
    try:
        AUTH.finish_setup(request.cookies.get(BOOT_COOKIE, ''), data.code)
    except AuthError as exc:
        auth_error(exc)
    return session_cookie(JSONResponse({'authenticated': True}), request, AUTH.issue_session('Desktop'))


@app.post('/auth/login')
def login(request: Request, data: LoginRequest):
    try:
        token = AUTH.login(data.password, data.code, request.client.host)
    except AuthError as exc:
        auth_error(exc)
    return session_cookie(JSONResponse({'authenticated': True}), request, token)


@app.post('/auth/logout')
def logout(request: Request):
    if request.state.session:
        AUTH.logout(request.cookies.get(SESSION_COOKIE))
    response = JSONResponse({'authenticated': False})
    response.delete_cookie(SESSION_COOKIE, path='/')
    return response


@app.post('/auth/revoke-others')
def revoke_others(request: Request):
    if request.state.session is None:
        raise HTTPException(401, 'MFA_SESSION_REQUIRED')
    AUTH.logout(request.cookies.get(SESSION_COOKIE), others=True)
    return {'revoked': True}


@app.exception_handler(StoreError)
@app.exception_handler(LoopError)
async def model_error(request, exc):
    code = str(exc)
    status = 409 if code == 'VERSION_CONFLICT' else (404 if code == 'SESSION_NOT_FOUND' else 422)
    return JSONResponse({'detail': code}, status_code=status)


@app.get('/')
def index(request: Request):
    name = 'index.html' if request.state.session else 'login.html'
    return FileResponse(ROOT / 'app' / 'static' / name)


@app.get('/api/console/runtime')
def runtime(request: Request):
    cv5 = cv2.__version__.split('.')[0] == '5'
    return dict(version='4.9.0', opencv_version=cv2.__version__, opencv5=cv5,
                captured_analysis_ready=cv5, storage='LOCAL_SQLITE', aws_verified=False,
                aws_execution_record=aws_execution_record(),
                mobile_url=app.state.mobile_url if loopback(request) else None,
                gt_verified=False, physical_action_authorized=False, max_views=2)


def aws_execution_record():
    """Show a locally rechecked AWS run record, never deployment/physical approval."""
    evidence = DATA / 'evidence' / 'opencv5-aws'
    try:
        report = json.loads((evidence / 'execution.json').read_bytes())
        if (not isinstance(report, dict)
                or report.get('schema') != 'BZX-GENUINE-OPENCV5-EXECUTION-V1'
                or report.get('aws_execution_environment') != 'AWS_CloudShell'
                or report.get('aws_region') != 'ap-northeast-1'
                or report.get('input_tier') != 'SYNTHETIC_OPENCV5_API_SMOKE_NOT_PHYSICAL_GT'
                or report.get('opencv_version') != '5.0.0'
                or not verify_capture(evidence / 'captures', report.get('receipt_sha256'))):
            return None
        return dict(environment='TOKYO CLOUDSHELL', input_tier='SYNTHETIC',
                    executed_utc=report['executed_utc'], opencv_version=report['opencv_version'],
                    archive_reverified=True, trusted_cloud_attestation=False,
                    deployment_verified=False, physical_gt_verified=False)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def session_result(sid):
    version, state = store().read(sid)
    with metadata_db() as db:
        row = db.execute('SELECT body FROM metadata WHERE id=?', (sid,)).fetchone()
    info = json.loads(row['body']) if row else dict(label=sid, mode='RESEARCH', measurement=None)
    options = set()
    if state.disposition == 'REQUEST_NONCONTACT_VIEW':
        for world in state.worlds:
            value = state.view_signatures[state.witness.next_observation][world]
            options.update([value] if isinstance(value, str) else value)
        options.add('?')
    return dict(version=version, **trace_dict(state), **info,
                witness=asdict(state.witness), observation_options=sorted(options),
                view_budget=state.view_budget)


@app.get('/api/console/sessions')
def list_sessions():
    repository = store()
    with connect(repository.path) as db:
        ids = [r[0] for r in db.execute('SELECT session_id FROM research_loops ORDER BY rowid DESC LIMIT 100')]
    result = []
    for sid in ids:
        try:
            result.append(session_result(sid))
        except StoreError as exc:
            result.append(dict(session_id=sid, error=str(exc), label=sid))
    return result


@app.get('/api/console/sessions/{sid}')
def get_session(sid: str):
    return session_result(sid)


@app.get('/api/console/sessions/{sid}/export')
def export_session(sid: str):
    result = session_result(sid)
    result['export_scope'] = 'LOCAL_RESEARCH_NOT_PHYSICAL_AUTHORIZATION'
    return JSONResponse(result, headers={'Content-Disposition': 'attachment; filename="bind-zero-trace.json"'})


@app.get('/api/console/sessions/{sid}/frame0')
def original_frame(sid: str):
    _, state = store().read(sid)  # Verifies all original bytes before serving one.
    if state.initial_capture_origin != 'SERVER_CAPTURED_PNG':
        raise HTTPException(404, 'NO_CAPTURED_ORIGINAL')
    archive = Path(os.environ['BZX_CAPTURE_ARCHIVE_DIR'])
    manifest = json.loads((archive / (state.initial_image_sha256 + '.json')).read_bytes())
    digest = manifest['images']['frame0']['sha256']
    if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        raise HTTPException(422, 'INVALID_ARCHIVE_REFERENCE')
    return FileResponse(archive / (digest + '.png'), media_type='image/png')


class DemoRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    label: str = Field(default='Cardboard bundle / Demo', min_length=1, max_length=80)


class SegmentationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    demo_photo: str | None = Field(default=None,max_length=40)
    image_png_b64: str | None = Field(default=None,max_length=6_666_668)


@app.post('/api/console/segment')
def segment_photo(data: SegmentationRequest):
    if bool(data.demo_photo)==bool(data.image_png_b64):
        raise HTTPException(422,'CHOOSE_ONE_IMAGE_SOURCE')
    if not EXPENSIVE_GATE.acquire(blocking=False):raise HTTPException(429,'ANALYSIS_BUSY')
    try:
        if data.demo_photo:
            allowed={'flat-brown-pile', 'flat-primary', 'flat-brown-five', 'flat-pastel', 'flat-brown-three', 'open-boxes-group', 'open-boxes-trio', 'flat-jewel', 'flat-brown-spread'}
            if data.demo_photo not in allowed:raise HTTPException(422,'UNKNOWN_DEMO_PHOTO')
            raw=(ROOT/'app/static/photos'/(data.demo_photo+'.png')).read_bytes()
        else:
            raw=base64.b64decode(data.image_png_b64,validate=True)
        result=segment_cardboard(raw)
        result['input_tier']='USER_PROVIDED_DEMO_ONLY' if data.demo_photo else 'USER_IMAGE_UNVERIFIED'
        return result
    except (ValueError,binascii.Error) as exc:
        raise HTTPException(422,str(exc)[:100])
    except RuntimeError as exc:
        raise HTTPException(503,str(exc)[:100])
    finally:
        EXPENSIVE_GATE.release()


def bounded_metadata(value):
    pending = [(value, 0)]; count = 0
    while pending:
        item, depth = pending.pop(); count += 1
        if count > 4096 or depth > 12:
            raise HTTPException(422, 'METADATA_LIMIT_EXCEEDED')
        if isinstance(item, str) and len(item) > 1024:
            raise HTTPException(422, 'METADATA_LIMIT_EXCEEDED')
        if isinstance(item, dict):
            if len(item) > 128: raise HTTPException(422, 'METADATA_LIMIT_EXCEEDED')
            pending.extend((v,depth+1) for pair in item.items() for v in pair)
        elif isinstance(item, list):
            if len(item) > 128: raise HTTPException(422, 'METADATA_LIMIT_EXCEEDED')
            pending.extend((v,depth+1) for v in item)


class DigestRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    bytes_b64: str = Field(max_length=3_333_336)


@app.post('/api/console/digest')
def digest_bytes(data: DigestRequest):
    """Same-origin fallback for mobile browsers without secure-context WebCrypto."""
    try:
        raw = base64.b64decode(data.bytes_b64, validate=True)
    except (ValueError, binascii.Error):
        raise HTTPException(422, 'INVALID_BASE64')
    if len(raw) > 2_500_000:
        raise HTTPException(413, 'FILE_TOO_LARGE')
    return dict(sha256=hashlib.sha256(raw).hexdigest())


def synthetic_measurement():
    """Actual optical flow on reproducible synthetic texture; never physical GT."""
    rng = np.random.default_rng(49)
    a = rng.integers(0, 255, (320, 480), dtype=np.uint8)
    a = cv2.GaussianBlur(a, (3, 3), 0)
    b = a.copy()
    b[20:145, :] = np.roll(a[20:145, :], 7, axis=1)
    upper = np.zeros_like(a); upper[35:125, 35:440] = 255
    lower = np.zeros_like(a); lower[190:285, 35:440] = 255
    report = analyze(a, b, {'upper': upper, 'lower': lower},
                     dict(scale_mm_per_px=0.8, plane_id='SYNTHETIC', calibration_id='DEMO-ONLY', verified=True),
                     'SYNTHETIC-OBS', require_opencv5=False)
    measurement = report['measurement']
    if measurement is not None:
        measurement['opencv_version'] = cv2.__version__
    return measurement


@app.post('/api/console/demo')
def create_demo(data: DemoRequest):
    if not EXPENSIVE_GATE.acquire(blocking=False):
        raise HTTPException(429, 'ANALYSIS_BUSY')
    try:
        return _create_demo(data)
    finally:
        EXPENSIVE_GATE.release()


def _create_demo(data):
    sid = 'DEMO-' + secrets.token_hex(4).upper()
    worlds = ['LAYER_ONLY', 'LAYER_AND_ROPE']
    losses = {'REORDER': {'LAYER_ONLY': 0, 'LAYER_AND_ROPE': 6},
              'REPOSITION_TWINE': {'LAYER_ONLY': 5, 'LAYER_AND_ROPE': 2},
              'ABSTAIN': {'LAYER_ONLY': 2, 'LAYER_AND_ROPE': 2}}
    views = {'ROPE_PATH': {'LAYER_ONLY': 'rope_still', 'LAYER_AND_ROPE': 'rope_moved'}}
    image_hash = hashlib.sha256(('SYNTHETIC:' + sid).encode()).hexdigest()
    state = start_research_loop(sid, 'OBS-' + sid, worlds, losses, views, {'ROPE_PATH': .25}, image_hash)
    store().start(state)
    save_metadata(sid, data.label, 'SYNTHETIC', synthetic_measurement())
    return session_result(sid)


class ObservationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=0)
    view: str = Field(min_length=1, max_length=32)
    signature: str = Field(min_length=1, max_length=128)
    capture_sha256: str = Field(min_length=64, max_length=64)


@app.post('/api/console/sessions/{sid}/observe')
def observe(sid: str, data: ObservationRequest):
    # A manual report remains a manual report, including in synthetic sessions.
    store().advance(sid, data.expected_version, data.view, data.signature,
                    data.capture_sha256, source='HUMAN_REPORTED')
    return session_result(sid)


@app.post('/api/console/capture')
def captured(data: research.LoopCapturedStartRequest):
    if not EXPENSIVE_GATE.acquire(blocking=False):
        raise HTTPException(429, 'ANALYSIS_BUSY')
    try:
        return _captured(data)
    finally:
        EXPENSIVE_GATE.release()


def _captured(data):
    bounded_metadata(data.calibration)
    bounded_metadata(data.roi_manifest)
    report = research.research_loop_start_captured(data)
    measurement = report.get('image_measurement_research_only')
    if measurement is not None:
        measurement['opencv_version'] = cv2.__version__
    save_metadata(data.session_id, data.session_id, 'CAPTURED',
                  measurement)
    return session_result(data.session_id)


@app.post('/api/console/reobserve-image')
def image_followup(data: research.LoopImageFollowupRequest):
    if not EXPENSIVE_GATE.acquire(blocking=False):
        raise HTTPException(429, 'ANALYSIS_BUSY')
    try:
        return _image_followup(data)
    finally:
        EXPENSIVE_GATE.release()


def _image_followup(data):
    bounded_metadata(data.calibration)
    bounded_metadata(data.roi_manifest)
    report = research.research_loop_reobserve_image(data)
    if report.get('image_measurement_research_only') is not None:
        report['image_measurement_research_only']['opencv_version'] = cv2.__version__
    with metadata_db() as db:
        row = db.execute('SELECT body FROM metadata WHERE id=?', (data.session_id,)).fetchone()
        if row:
            info = json.loads(row['body'])
            info['measurement'] = report.get('image_measurement_research_only')
            db.execute('UPDATE metadata SET body=? WHERE id=?', (json.dumps(info), data.session_id))
    result = session_result(data.session_id)
    result['image_measurement_research_only'] = report.get('image_measurement_research_only')
    result['cv_calibration_evidence'] = report.get('cv_calibration_evidence')
    return result


@app.get('/api/console/audit')
def audit():
    return inspect(os.environ['BZX_RESEARCH_LOOP_DB'], os.environ['BZX_CAPTURE_ARCHIVE_DIR'])


class AuthenticatedAssets(StaticFiles):
    async def __call__(self, scope, receive, send):
        # The guard is inside the mount; it sees the same normalization as its consumer.
        public = {'auth.js', 'style.css', 'pixel.ttf', 'favicon.svg'}
        path = self.get_path(scope)
        request = Request(scope)
        if path not in public and AUTH.session(request.cookies.get(SESSION_COOKIE), touch=False) is None:
            return await JSONResponse({'detail': 'MFA_SESSION_REQUIRED'}, status_code=401)(scope, receive, send)
        return await super().__call__(scope, receive, send)


app.mount('/assets', AuthenticatedAssets(directory=ROOT / 'app' / 'static'), name='assets')


if __name__ == '__main__':
    import argparse
    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--mobile', action='store_true')
    parser.add_argument('--mobile-port', type=int, help='HTTPS port; defaults to desktop port + 1')
    parser.add_argument('--mobile-ip', help='Private IPv4 address of this PC')
    args = parser.parse_args()
    ssl_options = {}
    if args.mobile:
        import socket
        from tls_local import load_tls
        if not AUTH.configured():
            raise SystemExit('MFA_NOT_CONFIGURED: start desktop mode and complete Set up MFA first.')
        addresses = [args.mobile_ip] if args.mobile_ip else socket.gethostbyname_ex(socket.gethostname())[2]
        addresses = [str(ipaddress.IPv4Address(value)) for value in addresses
                     if ipaddress.IPv4Address(value).is_private and not ipaddress.IPv4Address(value).is_loopback
                     and not ipaddress.IPv4Address(value).is_link_local]
        if not addresses:
            raise SystemExit('No private IPv4 address found. Use --mobile-ip.')
        ssl_options = load_tls(DATA / 'tls', addresses[0])
        ALLOWED_HOSTS.extend(addresses)
        app.state.mobile_mode = True
        app.state.mobile_url = f'https://{addresses[0]}:{args.mobile_port or args.port+1}/'
        print('Mobile HTTPS ready:', app.state.mobile_url, flush=True)
        import time
        tls_server = uvicorn.Server(uvicorn.Config(app, host=addresses[0],port=args.mobile_port or args.port+1,
            proxy_headers=False,limit_concurrency=24,timeout_keep_alive=5,log_level='warning',**ssl_options))
        tls_thread = threading.Thread(target=tls_server.run,daemon=True)
        tls_thread.start()
        deadline = time.monotonic()+10
        while not tls_server.started and tls_thread.is_alive() and time.monotonic()<deadline:
            time.sleep(.05)
        if not tls_server.started:
            raise SystemExit('HTTPS_LISTENER_FAILED')
    try:
        uvicorn.run(app,host='127.0.0.1',port=args.port,proxy_headers=False,
                    limit_concurrency=24,timeout_keep_alive=5,log_level='warning')
    finally:
        if args.mobile:
            tls_server.should_exit=True
            tls_thread.join(timeout=10)
