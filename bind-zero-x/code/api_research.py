# -*- coding: utf-8 -*-
"""Research-only, authenticated FastAPI CV worker; NEVER public production API.

Requires OpenCV 5; no physical control, no persistent sessions, no S3/DynamoDB,
no trained visual segmentation, no Bedrock. Only manually attested ROIs.
Deploy behind TLS, private networking, IAM and an authenticated application proxy.
"""
from __future__ import annotations
import base64,binascii,hmac,os,hashlib,json
from typing import Any
import cv2
import numpy as np
from fastapi import FastAPI,HTTPException,Header,Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel,ConfigDict,Field
from research_pipeline import analyze,PipelineError
from measurement_contract import MeasurementError
from active_evidence_loop import start_research_loop,LoopError
from research_loop_store import SQLiteResearchLoops,StoreError
from measurement_contract import PlaneCalibration
from cv_evidence_gate import load_approved_gt_envelope,classify_visible_layer_displacement
from capture_archive import persist_capture,CaptureArchiveError
from capture_lifecycle import start_captured

app=FastAPI(title='BIND ZERO-X Research Vision Worker',version='4.9.0',docs_url=None,redoc_url=None,openapi_url=None)
MAX_REQUEST_BYTES=12_000_000
MAX_IMAGE_DECODED_BYTES=2_500_000
MAX_PIXELS=3_000_000

class ResearchRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    frame0_png_b64:str
    frame1_png_b64:str
    upper_mask_png_b64:str
    lower_mask_png_b64:str
    calibration:dict[str,Any]
    roi_manifest:dict[str,Any]
    observation_id:str=Field(min_length=1,max_length=128)

@app.middleware('http')
async def request_limit(request:Request,call_next):
    if request.url.path.startswith('/api/research/'):
        token=os.environ.get('BZX_RESEARCH_TOKEN','')
        if len(token)<32:
            return JSONResponse({'detail':'SERVER_TOKEN_NOT_CONFIGURED'},status_code=503)
        if not hmac.compare_digest(request.headers.get('authorization',''),'Bearer '+token):
            return JSONResponse({'detail':'UNAUTHORIZED'},status_code=401)
        try:length=int(request.headers.get('content-length','0'))
        except ValueError:
            return JSONResponse({'detail':'INVALID_CONTENT_LENGTH'},status_code=413)
        if length<=0 or length>MAX_REQUEST_BYTES:
            return JSONResponse({'detail':'BODY_SIZE_OUT_OF_RANGE'},status_code=413)
        raw=bytearray()
        async for chunk in request.stream():
            if len(raw)+len(chunk)>MAX_REQUEST_BYTES:
                return JSONResponse({'detail':'BODY_SIZE_OUT_OF_RANGE'},status_code=413)
            raw.extend(chunk)
        request._body=bytes(raw)
    return await call_next(request)

class LoopStartRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    session_id:str=Field(min_length=1,max_length=128)
    observation_id:str=Field(min_length=1,max_length=128)
    initial_image_sha256:str=Field(min_length=64,max_length=64)
    worlds:list[str]=Field(min_length=1,max_length=20)
    losses:dict[str,dict[str,float]]
    view_signatures:dict[str,dict[str,Any]]
    view_costs:dict[str,float]

class LoopCapturedStartRequest(ResearchRequest):
    session_id:str=Field(min_length=1,max_length=128)
    worlds:list[str]=Field(min_length=1,max_length=20)
    losses:dict[str,dict[str,float]]
    view_signatures:dict[str,dict[str,Any]]
    view_costs:dict[str,float]

class LoopFollowupRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    session_id:str=Field(min_length=1,max_length=128)
    expected_version:int=Field(ge=0)
    view:str=Field(min_length=1,max_length=32)
    signature:str=Field(min_length=1,max_length=128)
    capture_sha256:str=Field(min_length=64,max_length=64)
    source:str='HUMAN_REPORTED'

class LoopImageFollowupRequest(ResearchRequest):
    session_id:str=Field(min_length=1,max_length=128)
    expected_version:int=Field(ge=0)
    view:str=Field(min_length=1,max_length=32)

def _research_loops():
    # Research-only single-token access; no multi-tenant user auth or AWS durability.
    return SQLiteResearchLoops(os.environ.get('BZX_RESEARCH_LOOP_DB','/tmp/bzx_research_loops.db'))

@app.post('/api/research/loop/start')
def research_loop_start(data:LoopStartRequest):
    try:
        loop=start_research_loop(data.session_id,data.observation_id,data.worlds,
             data.losses,data.view_signatures,data.view_costs,data.initial_image_sha256)
        result=_research_loops().start(loop)
        result['initial_image_evidence']='UNVERIFIED_CLIENT_HASH_NO_IMAGE'
        return result
    except (LoopError,StoreError,ValueError,TypeError) as e:
        raise HTTPException(422,str(e)[:120])

@app.post('/api/research/loop/start-captured')
def research_loop_start_captured(data:LoopCapturedStartRequest):
    """Server receives four ORIGINAL PNGs, validates CV/ROI and archives bytes.

    Source/camera timestamps and ROI attribution remain manually attested;
    this endpoint proves received bytes, not camera authenticity or real GT.
    """
    if cv2.__version__.split('.')[0]!='5':
        raise HTTPException(503,'OPENCV5_RUNTIME_REQUIRED')
    archive=os.environ.get('BZX_CAPTURE_ARCHIVE_DIR','')
    if not archive:raise HTTPException(503,'CAPTURE_ARCHIVE_NOT_CONFIGURED')
    try:
        start_research_loop(data.session_id,data.observation_id,data.worlds,data.losses,
            data.view_signatures,data.view_costs,'0'*64)
    except (LoopError,ValueError,TypeError) as e:
        raise HTTPException(422,str(e)[:120])
    a=_decode(data.frame0_png_b64);b=_decode(data.frame1_png_b64)
    u=_decode(data.upper_mask_png_b64);l=_decode(data.lower_mask_png_b64)
    if any(x.shape!=a.shape for x in (b,u,l)):
        raise HTTPException(422,'SHAPE_MISMATCH')
    try:
        report=analyze(a,b,{'upper':u,'lower':l},data.calibration,data.observation_id,
            require_opencv5=True,require_roi_provenance=True,roi_manifest=data.roi_manifest)
        if report.get('measurement') is None:
            raise HTTPException(422,'INITIAL_CV_NOT_MEASURABLE')
        raw={k:base64.b64decode(getattr(data,k+'_png_b64'),validate=True) for k in
             ('frame0','frame1','upper_mask','lower_mask')}
        metadata={'calibration':data.calibration,'roi_manifest':data.roi_manifest,
                  'frame_shape':list(a.shape),
                  'cv_measurement_sha256':hashlib.sha256(json.dumps(
                    report['measurement'],sort_keys=True,ensure_ascii=False,allow_nan=False
                  ).encode()).hexdigest()}
        result,receipt=start_captured(_research_loops(),archive,
            session_id=data.session_id,observation_id=data.observation_id,
            raw_images=raw,metadata=metadata,worlds=data.worlds,losses=data.losses,
            view_signatures=data.view_signatures,view_costs=data.view_costs)
        result.update(initial_capture_receipt_sha256=receipt,
            initial_image_evidence='SERVER_RECEIVED_PNG_BYTES_ARCHIVED_NOT_TRUSTED_CAMERA_ATTESTATION',
            image_measurement_research_only=report['measurement'])
        return result
    except (CaptureArchiveError,PipelineError,MeasurementError,LoopError,StoreError,
            ValueError,TypeError,KeyError) as e:
        raise HTTPException(422,str(e)[:120])

@app.post('/api/research/loop/reobserve')
def research_loop_reobserve(data:LoopFollowupRequest):
    try:
        return _research_loops().advance(data.session_id,data.expected_version,
            data.view,data.signature,data.capture_sha256,source=data.source)
    except StoreError as e:
        code=409 if str(e)=='VERSION_CONFLICT' else 422
        raise HTTPException(code,str(e)[:120])
    except (LoopError,ValueError,TypeError) as e:
        raise HTTPException(422,str(e)[:120])

@app.get('/health')
def health():
    return {'service':'BIND_ZERO_X_RESEARCH_ONLY','opencv_version':cv2.__version__,
            'opencv5':cv2.__version__.split('.')[0]=='5','physical_authorization':False}

@app.get('/ready')
def ready():
    token=os.environ.get('BZX_RESEARCH_TOKEN','')
    if len(token)<32 or cv2.__version__.split('.')[0]!='5':
        raise HTTPException(503,'OPENCV5_OR_AUTH_NOT_READY')
    return {'ready':True,'opencv_version':cv2.__version__}

def _decode(value:str):
    if len(value)>((MAX_IMAGE_DECODED_BYTES+2)//3)*4+4:raise HTTPException(413,'IMAGE_TOO_LARGE')
    try:raw=base64.b64decode(value,validate=True)
    except (ValueError,binascii.Error):raise HTTPException(400,'BAD_BASE64')
    if len(raw)>MAX_IMAGE_DECODED_BYTES or not raw.startswith(b'\x89PNG\r\n\x1a\n'):
        raise HTTPException(415,'PNG_REQUIRED_OR_TOO_LARGE')
    if len(raw)<24:
        raise HTTPException(422,'MALFORMED_PNG_HEADER')
    w,h=int.from_bytes(raw[16:20],'big'),int.from_bytes(raw[20:24],'big')
    if w<=0 or h<=0 or w*h>MAX_PIXELS or w>MAX_PIXELS or h>MAX_PIXELS:
        raise HTTPException(413,'DECODED_IMAGE_PIXEL_LIMIT')
    try:
        img=cv2.imdecode(np.frombuffer(raw,dtype=np.uint8),cv2.IMREAD_GRAYSCALE)
    except cv2.error:
        raise HTTPException(422,'PNG_DECODING_ERROR')
    if img is None or img.size>MAX_PIXELS:raise HTTPException(422,'INVALID_OR_TOO_LARGE_IMAGE')
    return img

@app.post('/api/research/loop/reobserve-image')
def research_loop_reobserve_image(data:LoopImageFollowupRequest):
    """Process NEW frame pair on the server; UNCALIBRATED result cannot collapse worlds.

    Server derives the capture digest from decoded frame/masks/calibration/ROI.
    Client cannot claim the image was empirically calibrated or authorize repairs.
    Runtime requires genuine cv2 major version 5; no compatibility bypass.
    """
    if cv2.__version__.split('.')[0]!='5':
        raise HTTPException(503,'OPENCV5_RUNTIME_REQUIRED')
    # Check the active request against the pinned session before image decode.
    # The observation ID here denotes the parent inspection; child evidence
    # identity is assigned by the server and bound to the step below.
    try:
        current_version,current=_research_loops().read(data.session_id)
        if current_version!=data.expected_version:
            raise HTTPException(409,'VERSION_CONFLICT')
        if data.observation_id!=current.observation_id:
            raise HTTPException(422,'PARENT_OBSERVATION_ID_MISMATCH')
        if current.disposition!='REQUEST_NONCONTACT_VIEW' or data.view!=current.witness.next_observation:
            raise HTTPException(422,'UNEXPECTED_OR_STALE_VIEW')
        PlaneCalibration(**data.calibration)
    except StoreError as e:
        raise HTTPException(422,str(e)[:120])
    except (MeasurementError,TypeError,KeyError,ValueError) as e:
        raise HTTPException(422,str(e)[:120])
    a=_decode(data.frame0_png_b64);b=_decode(data.frame1_png_b64)
    u=_decode(data.upper_mask_png_b64);l=_decode(data.lower_mask_png_b64)
    if any(x.shape!=a.shape for x in (b,u,l)):
        raise HTTPException(422,'SHAPE_MISMATCH')
    masks={'upper':u,'lower':l}
    serialized=json.dumps({'calibration':data.calibration,'roi_manifest':data.roi_manifest},
                         ensure_ascii=False,sort_keys=True,allow_nan=False).encode()
    capture_hash=hashlib.sha256(b''.join(x.tobytes() for x in (a,b,u,l))+serialized).hexdigest()
    child_observation_id=f'{current.observation_id}:view{len(current.steps)+1}'
    try:
        result=analyze(a,b,masks,data.calibration,data.observation_id,
           require_opencv5=True,require_roi_provenance=True,roi_manifest=data.roi_manifest)
        # No independent physical ground truth exists. Preserve the world's
        # uncertainty and consume the requested observation, even if CV returns
        # a nominal displacement. Never manufacture an EMPIRICALLY_CALIBRATED flag.
        if result.get('measurement') is None:
            raise LoopError('NEW_IMAGE_NOT_MEASURABLE')
        envelope=load_approved_gt_envelope(data.calibration,a.shape)
        token=classify_visible_layer_displacement(result['measurement'],envelope) if envelope else '?'
        # Only a trusted, server-installed, separately approved GT envelope can
        # authorize world reduction. A positive JSON boolean from the client
        # must NEVER confer independent GT evidence.
        if envelope and token!='?':
            result['measurement']['uncertainty_status']='EMPIRICALLY_CALIBRATED'
            result['measurement']['capture_sha256']=capture_hash
            result['measurement']['independent_gt_manifest_sha256']=envelope['holdout_manifest_sha256']
            result['measurement']['p95_absolute_error_mm']=envelope['p95_absolute_error_mm']
        output=_research_loops().advance_cv_internal(
            data.session_id,data.expected_version,data.view,capture_hash,result,
            qualified_signature=token,cv_threshold_mm=envelope['threshold_mm'] if envelope else 5.0,
            trusted_cv_validator=lambda v,r,d: (v==data.view and r is result and d==capture_hash))
        output['image_measurement_research_only']=result['measurement']
        output['cv_calibration_evidence']=('GT_ENVELOPE_P95_RESEARCH_ONLY' if token!='?' else
            ('GT_ENVELOPE_AMBIGUOUS_NO_WORLD_REDUCTION' if envelope else 'UNCALIBRATED_NO_WORLD_REDUCTION'))
        output['cv_observation_token']=token
        output['parent_observation_id']=current.observation_id
        output['child_observation_id']=child_observation_id
        output['capture_sha256']=capture_hash
        return output
    except StoreError as e:
        raise HTTPException(409 if str(e)=='VERSION_CONFLICT' else 422,str(e)[:120])
    except (PipelineError,MeasurementError,LoopError,ValueError,TypeError,KeyError) as e:
        raise HTTPException(422,str(e)[:120])

@app.post('/api/research/analyze')
def research_analyze(data:ResearchRequest,authorization:str|None=Header(default=None)):
    token=os.environ.get('BZX_RESEARCH_TOKEN','')
    if len(token)<32:raise HTTPException(503,'SERVER_TOKEN_NOT_CONFIGURED')
    if not authorization or not hmac.compare_digest(authorization,'Bearer '+token):
        raise HTTPException(401,'UNAUTHORIZED')
    if cv2.__version__.split('.')[0]!='5':
        raise HTTPException(503,'OPENCV5_RUNTIME_REQUIRED')
    a=_decode(data.frame0_png_b64);b=_decode(data.frame1_png_b64)
    u=_decode(data.upper_mask_png_b64);l=_decode(data.lower_mask_png_b64)
    if a.shape!=b.shape or u.shape!=a.shape or l.shape!=a.shape:
        raise HTTPException(422,'SHAPE_MISMATCH')
    try:
        result=analyze(a,b,{'upper':u,'lower':l},data.calibration,data.observation_id,
                       require_opencv5=True,require_roi_provenance=True,roi_manifest=data.roi_manifest)
    except (PipelineError,MeasurementError,TypeError,KeyError,ValueError) as exc:
        # error type/code only; never include supplied images, headers, or sensitive values.
        raise HTTPException(422,str(exc)[:120])
    return result
