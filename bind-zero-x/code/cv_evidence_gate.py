# -*- coding: utf-8 -*-
"""Research measurement -> world-token gate; fails closed without independently
collected, pre-registered real-image GT evidence. Server trust roots are NOT
exposed through request bodies. Registry hashes establish integrity, NOT truth.

This module is an IMPLEMENTATION OF A FUTURE GATE, not a claim that any real GT
certificate exists. The default runtime has no registry and cannot update worlds
based on a pixel/mm estimate.
"""
import hashlib, json, math, os
from pathlib import Path

class CVEvidenceError(ValueError):pass

def _canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def _digest(x):return hashlib.sha256(_canonical(x).encode()).hexdigest()
def _hex64(x):return isinstance(x,str) and len(x)==64 and all(c in '0123456789abcdef' for c in x)
def _number(x):return type(x) in (int,float) and math.isfinite(x)

def load_approved_gt_envelope(calibration,shape):
    """Read from server-controlled allowlisted file only. No user-supplied paths.
    File SHA256 must match separately deployed allowlisted digest.
    """
    path=os.getenv('BZX_APPROVED_GT_ENVELOPE_PATH','')
    expected=os.getenv('BZX_APPROVED_GT_ENVELOPE_SHA256','')
    if not path or not _hex64(expected):return None
    try:
        raw=Path(path).read_bytes()
        if len(raw)>16_384 or hashlib.sha256(raw).hexdigest()!=expected:return None
        p=json.loads(raw)
        if not isinstance(p,dict) or p.get('schema')!='BZX-REAL-GT-ENVELOPE-V2':return None
        if (p.get('calibration_sha256')!=_digest(calibration) or
            p.get('frame_shape')!=list(shape) or
            p.get('channel')!='LAYER_VISIBLE_MAX_MM'):
            return None
        if p.get('approved') is not True or p.get('pre_registered') is not True or p.get('independent_real_gt') is not True:
            return None
        if type(p.get('holdout_n')) is not int or p['holdout_n']<30:return None
        if p.get('independence_unit')!='UNIQUE_PHYSICAL_BUNDLE_ID_NOT_ROWS':return None
        for key in ('independent_bundle_n','independent_video_n'):
            if type(p.get(key)) is not int or p[key]<30 or p[key]>p['holdout_n']:
                return None
        counts=p.get('fault_mode_counts')
        if (not isinstance(counts,dict) or len(counts)<2 or
            any(type(v) is not int or v<5 for v in counts.values()) or
            sum(counts.values())!=p['holdout_n']):return None
        if not _hex64(p.get('external_audit_receipt_sha256')):return None
        if not _hex64(p.get('holdout_manifest_sha256')):return None
        for k in ('threshold_mm','p95_absolute_error_mm','max_allowed_p95_mm'):
            if not _number(p.get(k)) or p[k]<=0:return None
        if p['p95_absolute_error_mm']>p['max_allowed_p95_mm']:return None
        # A custom claim is not automatically endorsed. Validation is limited
        # to metadata and trusted registry digest. Audit holdout independently.
        return p
    except (OSError,ValueError,TypeError,OverflowError):return None

def classify_visible_layer_displacement(measurement, envelope):
    """Return conservative token for registered 95th-percentile error range.
    P95 is probabilistic and NOT a worst-case safety guarantee.
    """
    if not isinstance(measurement,dict) or not isinstance(envelope,dict):
        raise CVEvidenceError('INVALID_CV_EVIDENCE')
    x=measurement.get('max_footprint_drift_mm')
    e=envelope.get('p95_absolute_error_mm')
    t=envelope.get('threshold_mm')
    if not all(_number(q) and q>=0 for q in (x,e,t)) or t<=0:
        raise CVEvidenceError('INVALID_MEASUREMENT_ENVELOPE')
    if measurement.get('uncertainty_status')!='NOT_CALIBRATED_UNCERTAINTY_NOT_ZERO':
        raise CVEvidenceError('UNEXPECTED_MEASUREMENT_CLAIM')
    if x-e>=t:return 'layer_moves'
    if x+e<t:return 'layer_still'
    return '?'  # Uncertain: must not collapse possible worlds.
