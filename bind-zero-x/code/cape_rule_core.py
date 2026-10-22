# coding: utf-8
"""BIND ZERO-X v4.1 deterministic reference planner and security-aware session core.
Pure Python development model only. Real API MUST repeat authorization, validators and
atomic idempotency in DynamoDB; Python in-memory dataclasses are NOT a cloud security layer.
NO calibrated EVSI, physical certification, or automatic execution is claimed.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
from hashlib import sha256
import json, math

POLICY_VERSION='RULE-4.2'
PHYSICAL_ACTIONS=frozenset({'REORDER','RE_TIE','REPOSITION_TWINE','SPLIT_2','PROBE_KNOT','PROBE_LAYER'})
NONPHYSICAL_ACTIONS=frozenset({'KEEP','RECAPTURE','ABSTAIN'})
ALLOWED=PHYSICAL_ACTIONS|NONPHYSICAL_ACTIONS
PROBE_ACTIONS=frozenset({'PROBE_KNOT','PROBE_LAYER'})

class ActionError(ValueError): pass

@dataclass(frozen=True)
class Observation:
    observation_id: str
    quality: str
    layer_slip_mm: float|None
    rope_shift_mm: float|None
    knot_slip_mm: float|None
    layer_max_drift_mm: float|None=None
    relative_angle_deg: float|None=None

@dataclass(frozen=True)
class Decision:
    action: str
    reason: str
    source_observation_id: str
    human_approval_required: bool=True
    policy_scope: str='RULE_BASED_NOT_EVSI'


def choose_rule_action(obs:Observation,recapture_count:int=0,allowed=ALLOWED,threshold_mm:float=5.0,probe_count:int=0,max_probes:int=2,rotation_threshold_deg:float=3.):
    """Conservative measured tripwires, not a strength/safety certification."""
    allowed=frozenset(allowed)&ALLOWED
    if not obs.observation_id or not math.isfinite(threshold_mm) or threshold_mm<=0:
        raise ActionError('INVALID_OBSERVATION_OR_THRESHOLD')
    if not isinstance(rotation_threshold_deg,(float,int)) or isinstance(rotation_threshold_deg,bool) or not math.isfinite(rotation_threshold_deg) or rotation_threshold_deg<=0:
        raise ActionError('INVALID_ROTATION_THRESHOLD')
    if obs.relative_angle_deg is not None and (not isinstance(obs.relative_angle_deg,(float,int)) or isinstance(obs.relative_angle_deg,bool) or not math.isfinite(obs.relative_angle_deg)):
        raise ActionError('INVALID_ROTATION')
    vals=(obs.layer_slip_mm,obs.rope_shift_mm,obs.knot_slip_mm,obs.layer_max_drift_mm)
    for value in vals:
        if value is not None and (not isinstance(value,(int,float)) or not math.isfinite(value) or value<0):
            raise ActionError('INVALID_METRIC')
    if obs.quality!='VALID':
        candidates=[('RECAPTURE','LOW_OBSERVATION_QUALITY')] if recapture_count<1 else []
    elif all(v is None for v in vals):
        candidates=[('RECAPTURE','ALL_UNOBSERVABLE')] if recapture_count<1 else []
    else:
        layer=((obs.layer_slip_mm is not None and obs.layer_slip_mm>=threshold_mm) or
               (obs.layer_max_drift_mm is not None and obs.layer_max_drift_mm>=threshold_mm) or
               (obs.relative_angle_deg is not None and abs(obs.relative_angle_deg)>=rotation_threshold_deg))
        rope=obs.rope_shift_mm is not None and obs.rope_shift_mm>=threshold_mm
        knot=obs.knot_slip_mm is not None and obs.knot_slip_mm>=threshold_mm
        if sum((layer,rope,knot))>1:
            candidates=[('ABSTAIN','MULTIPLE_FAULTS_REQUIRE_REVIEW')]
        elif knot:
            candidates=[('RE_TIE','KNOT_SLIP_MEASURED')]
        elif layer:
            candidates=[('REORDER','LAYER_SLIP_MEASURED')]
        elif rope:
            # Crucial v4 blocker: a measured rope-only slip CANNOT fall through to KEEP.
            if obs.knot_slip_mm is None:
                candidates=[('PROBE_KNOT','ROPE_SLIP_KNOT_UNOBSERVED'),
                            ('ABSTAIN','ROPE_SLIP_NEEDS_INSPECTION')]
            else:
                candidates=[('REPOSITION_TWINE','ROPE_PATH_SLIP_MEASURED'),
                            ('ABSTAIN','ROPE_PATH_REVIEW')]
        elif obs.rope_shift_mm is None:
            # A missing ROPE measurement must never result in a LAYER probe.
            candidates=([('RECAPTURE','ROPE_PATH_NOT_OBSERVED')] if recapture_count<1 else [])
        elif obs.knot_slip_mm is None:
            candidates=[('PROBE_KNOT','KNOT_NOT_OBSERVED')]
            if recapture_count<1:candidates.append(('RECAPTURE','KNOT_NOT_OBSERVED'))
        elif obs.layer_slip_mm is None and obs.layer_max_drift_mm is None and obs.relative_angle_deg is None:
            candidates=[('PROBE_LAYER','LAYER_NOT_OBSERVED')]
            if recapture_count<1:candidates.append(('RECAPTURE','LAYER_NOT_OBSERVED'))
        else:
            candidates=[('KEEP','NO_MEASURED_TRIPWIRE_NOT_CERTIFIED')]
    for action,reason in candidates:
        if action in PROBE_ACTIONS and probe_count>=max_probes:continue
        if action in allowed:
            return Decision(action,reason,obs.observation_id, action in PHYSICAL_ACTIONS)
    # Always safe to abstain when all permitted candidates are unavailable.
    return Decision('ABSTAIN','NO_PERMITTED_ACTION',obs.observation_id,False)

@dataclass(frozen=True)
class Session:
    session_id:str='DEMO-SESSION'
    owner_sub:str='DEMO-OWNER'
    state:str='PLAN_READY'
    version:int=0
    planned_action_id:str|None=None
    planned_observation_id:str|None=None
    planned_policy_version:str=POLICY_VERSION
    allowed_actions:frozenset[str]=PHYSICAL_ACTIONS
    approved_action_id:str|None=None
    accepted_observation_ids:frozenset[str]=frozenset()
    region_rules_verified:bool=False
    safety_preflight_ok:bool=False
    probe_count:int=0
    max_probes:int=2
    last_idempotency_key:str|None=None
    last_request_fingerprint:str|None=None
    last_request_version:int|None=None


def _approval_fingerprint(s:Session, action_id:str, observation_id:str, auth_sub:str, expected_version:int)->str:
    body={'session_id':s.session_id,'action':action_id,'observation_id':observation_id,
          'owner_sub':auth_sub,'expected_version':expected_version,'policy_version':s.planned_policy_version}
    return sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def approval_event(s:Session,action_id:str,key:str,expected_version:int,
                   observation_id:str|None=None,auth_sub:str|None=None)->Session:
    """Pure event transition; DynamoDB conditional update must enforce the same invariants atomically."""
    if not key:raise ActionError('MISSING_KEY')
    if not auth_sub or auth_sub!=s.owner_sub:raise ActionError('NOT_AUTHORIZED')
    if not observation_id:raise ActionError('MISSING_OBSERVATION_ID')
    finger=_approval_fingerprint(s,action_id,observation_id,auth_sub,expected_version)
    if s.last_idempotency_key==key:
        if finger!=s.last_request_fingerprint:raise ActionError('IDEMPOTENCY_KEY_REUSE_CONFLICT')
        if s.state!='APPROVED':raise ActionError('REPLAY_RESULT_FROM_IDEMPOTENCY_STORE')
        return s
    if s.version!=expected_version:raise ActionError('VERSION_CONFLICT')
    if s.state in ('ABORTED','COMPLETE_WITH_LIMITS'):raise ActionError('TERMINAL_STATE')
    if s.state!='PLAN_READY':raise ActionError('INVALID_STATE')
    if not s.region_rules_verified or not s.safety_preflight_ok:raise ActionError('UNVERIFIED_CONSTRAINTS')
    if action_id not in PHYSICAL_ACTIONS or action_id not in s.allowed_actions:
        raise ActionError('ACTION_NOT_ALLOWLISTED')
    if s.planned_action_id!=action_id or s.planned_observation_id!=observation_id:
        raise ActionError('STALE_OR_UNISSUED_PLAN')
    if s.planned_policy_version!=POLICY_VERSION:raise ActionError('POLICY_VERSION_MISMATCH')
    if action_id in PROBE_ACTIONS and (s.max_probes<1 or s.probe_count>=s.max_probes):
        raise ActionError('PROBE_LIMIT_PREAPPROVAL')
    return replace(s,state='APPROVED',version=s.version+1,approved_action_id=action_id,
                   last_idempotency_key=key,last_request_fingerprint=finger,
                   last_request_version=expected_version)


def confirm_human_execution(s:Session,action_id:str,auth_sub:str|None=None,expected_version:int|None=None)->Session:
    if not auth_sub or auth_sub!=s.owner_sub:raise ActionError('NOT_AUTHORIZED')
    if expected_version is None or expected_version!=s.version:raise ActionError('VERSION_CONFLICT')
    if s.state!='APPROVED' or s.approved_action_id!=action_id or action_id not in PHYSICAL_ACTIONS:
        raise ActionError('UNAPPROVED_ACTION')
    if not s.safety_preflight_ok or not s.region_rules_verified:
        raise ActionError('UNVERIFIED_CONSTRAINTS')
    if action_id in PROBE_ACTIONS and (s.max_probes<1 or s.probe_count>=s.max_probes):
        raise ActionError('PROBE_LIMIT_PREEXECUTION')
    return replace(s,state='OUTCOME_PENDING',version=s.version+1)


def mark_probe_completed(s:Session,outcome_observation_id:str|None=None,auth_sub:str|None=None,
                         expected_version:int|None=None,max_probes:int=2)->Session:
    if not auth_sub or auth_sub!=s.owner_sub:raise ActionError('NOT_AUTHORIZED')
    if expected_version is None or expected_version!=s.version:raise ActionError('VERSION_CONFLICT')
    if s.state!='OUTCOME_PENDING':raise ActionError('INVALID_STATE')
    if s.approved_action_id not in PROBE_ACTIONS:raise ActionError('NOT_A_DIAGNOSTIC_PROBE')
    if not outcome_observation_id:raise ActionError('MISSING_OUTCOME_OBSERVATION')
    if outcome_observation_id not in s.accepted_observation_ids:
        raise ActionError('UNVERIFIED_OUTCOME_OBSERVATION')
    if s.probe_count>=min(s.max_probes,max_probes):raise ActionError('PROBE_LIMIT')
    return replace(s,probe_count=s.probe_count+1,state='PLAN_READY',version=s.version+1,
                   planned_action_id=None,planned_observation_id=None,approved_action_id=None)
