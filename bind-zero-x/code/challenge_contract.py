# coding: utf-8
"""Frozen experimental protocol, not an endorsed physical force or safety standard."""
import json, math, hashlib, copy
from datetime import datetime,timezone,timedelta
from evaluation_core import ProtocolError, _numeric

REQUIRED_FIELDS={
 'STATIC':frozenset({'input_force_N','duration_s'}),
 'QUASISTATIC':frozenset({'input_force_N','force_rate_N_per_s','duration_s'}),
 'LOW_ENERGY':frozenset({'input_amplitude_mm','input_frequency_Hz','duration_s'}),
 'NONCONTACT':frozenset({'duration_s'})
}

def freeze_profile(p):
    if not isinstance(p,dict):raise ProtocolError('INVALID_PROFILE')
    z=copy.deepcopy(p)
    kind=z.get('stimulus_type')
    if kind not in REQUIRED_FIELDS:raise ProtocolError('UNKNOWN_STIMULUS')
    if not z.get('challenge_id') or not z.get('revision') or not z.get('frozen_at_utc'):
        raise ProtocolError('MISSING_PROFILE_IDENTITY_OR_FREEZE')
    try:
        at=datetime.fromisoformat(z['frozen_at_utc'].replace('Z','+00:00'))
        if at.tzinfo is None or at.utcoffset()!=timedelta(0):raise ValueError('UTC timestamp required')
    except (TypeError,ValueError,AttributeError):raise ProtocolError('INVALID_FROZEN_TIMESTAMP')
    if z.get('preflight_approved') is not True:raise ProtocolError('PREFLIGHT_NOT_APPROVED')
    specs=z.get('input_targets')
    if not isinstance(specs,dict) or set(specs)!=REQUIRED_FIELDS[kind]:
        raise ProtocolError('REQUIRED_INPUT_TARGETS_MISSING_OR_EXTRA')
    for name,spec in specs.items():
        if not isinstance(spec,dict) or set(spec)!={'target','tolerance'}:
            raise ProtocolError('BAD_INPUT_SPEC_'+name)
        target=_numeric(spec['target'],name);tol=_numeric(spec['tolerance'],name)
        if target<0 or tol<0 or (name=='duration_s' and target<=0) or \
           (name in ('input_frequency_Hz','force_rate_N_per_s','input_amplitude_mm') and target<=0):
            raise ProtocolError('BAD_INPUT_RANGE_'+name)
        # Guard against meaningless profiles: tolerance at most 25% of the target
        # (conservative SOFTWARE quality gate, not a physical safety standard).
        if target>0 and tol>0.25*target:
            raise ProtocolError('UNREASONABLE_TARGET_TOLERANCE_'+name)
    if kind in ('STATIC','QUASISTATIC'):
        limit=_numeric(z.get('approved_force_limit_N'),'approved_force_limit_N')
        if limit<=0 or specs['input_force_N']['target']+specs['input_force_N']['tolerance']>limit:
            raise ProtocolError('FORCE_LIMIT_INCONSISTENT')
    z.pop('profile_hash',None)
    b=json.dumps(z,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
    z['profile_hash']=hashlib.sha256(b).hexdigest()
    return z


def assert_profile_frozen(p):
    if not isinstance(p,dict) or not p.get('profile_hash'):
        raise ProtocolError('MISSING_FROZEN_PROFILE_HASH')
    try:canonical=freeze_profile(p)
    except ProtocolError as exc:raise ProtocolError('PROFILE_TAMPERING') from exc
    if canonical['profile_hash']!=p['profile_hash']:
        raise ProtocolError('PROFILE_TAMPERING')
    return p
