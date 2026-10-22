# -*- coding: utf-8 -*-
"""BIND ZERO-X v4.6 proof-bound, fail-closed RESEARCH loop.

The finite world model is hypothetical. A certificate proves only mathematical
self-consistency, NEVER physical correctness or permission to intervene.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
import hashlib, json
from witness_planner import (recommend_witness, restrict_worlds_after_view,
    verify_witness_certificate, WitnessError, DecisionWitness, ALLOWED_VIEWS)

class LoopError(ValueError): pass
MAX_VIEWS=2

@dataclass(frozen=True)
class EvidenceStep:
    seq:int
    view:str
    source:str
    signature:str
    capture_sha256:str
    worlds_before:tuple[str,...]
    worlds_after:tuple[str,...]
    before_certificate_hash:str
    after_certificate_hash:str|None
    note:str
    parent_observation_id:str=''
    child_observation_id:str=''

@dataclass(frozen=True)
class ResearchLoop:
    session_id:str
    observation_id:str
    worlds:tuple[str,...]
    losses:dict
    view_signatures:dict
    view_costs:dict
    candidate_views:tuple[str,...]
    initial_image_sha256:str
    steps:tuple[EvidenceStep,...]
    view_budget:int
    witness:DecisionWitness
    disposition:str
    approval_authorized:bool=False
    model_fingerprint:str=''
    initial_capture_origin:str='CLIENT_CLAIM_ONLY'


def _snapshot(obj):
    """Detach mutable caller dictionaries/lists, normalize collections."""
    def walk(x):
        if isinstance(x,dict):return {str(k):walk(v) for k,v in x.items()}
        if isinstance(x,(set,frozenset)):return sorted(walk(v) for v in x)
        if isinstance(x,(list,tuple)):return [walk(v) for v in x]
        return x
    try:
        return json.loads(json.dumps(walk(obj),allow_nan=False,sort_keys=True))
    except (TypeError,ValueError) as e:raise LoopError('INVALID_MODEL_SNAPSHOT') from e


def _fingerprint(s:ResearchLoop)->str:
    payload=dict(session_id=s.session_id,observation_id=s.observation_id,
        initial_image_sha256=s.initial_image_sha256,view_budget=s.view_budget,
        initial_capture_origin=s.initial_capture_origin,
        candidate_views=list(s.candidate_views),losses=s.losses,
        view_signatures=s.view_signatures,view_costs=s.view_costs)
    return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False,
                       separators=(',',':'),allow_nan=False).encode()).hexdigest()


def _make_witness(s,worlds,steps):
    used={x.view for x in steps}
    allowed={k:{w:v[w] for w in worlds} for k,v in s.view_signatures.items()
             if k not in used}
    costs={k:s.view_costs[k] for k in allowed if k in s.view_costs}
    losses={a:{w:row[w] for w in worlds} for a,row in s.losses.items()}
    obs=s.observation_id if not steps else f'{s.observation_id}:view{len(steps)}'
    image=s.initial_image_sha256 if not steps else steps[-1].capture_sha256
    return recommend_witness(worlds,losses,allowed,costs,
        allowed_views=(allowed.keys() if steps else ALLOWED_VIEWS),
        observation_id=obs,video_sha256=image)


def _disposition(s,w,steps):
    if len(steps)>=s.view_budget and w.disposition=='REQUEST_NONCONTACT_VIEW':
        return 'ABSTAIN'
    return w.disposition


def validate_loop(s:ResearchLoop)->bool:
    """Reconstruct all decisions and posterior worlds using pinned start model.

    Checks a research trace, not the authenticity of an image or the truth of
    the hypothetical loss/prediction model. Store MAC checks provenance at rest.
    """
    try:
        if not isinstance(s,ResearchLoop) or s.approval_authorized is not False:
            raise LoopError('SESSION_NOT_RESEARCH_ONLY')
        if s.initial_capture_origin not in ('CLIENT_CLAIM_ONLY','SERVER_CAPTURED_PNG'):
            raise LoopError('UNKNOWN_INITIAL_CAPTURE_PROVENANCE')
        if not isinstance(s.view_budget,int) or isinstance(s.view_budget,bool) or not 0<=s.view_budget<=MAX_VIEWS:
            raise LoopError('INVALID_VIEW_BUDGET')
        if not isinstance(s.model_fingerprint,str) or s.model_fingerprint!=_fingerprint(s):
            raise LoopError('PINNED_MODEL_MISMATCH')
        initial=tuple(sorted(next(iter(s.losses.values()))))
        if not initial or set(s.candidate_views)!=set(s.view_signatures):
            raise LoopError('INVALID_INITIAL_MODEL')
        worlds=initial
        prior=[]
        w=_make_witness(s,worlds,prior)
        seen_captures={s.initial_image_sha256}
        for index,step in enumerate(s.steps,1):
            if index>s.view_budget or step.seq!=index or step.view in {x.view for x in prior}:
                raise LoopError('INVALID_EVIDENCE_SEQUENCE')
            if w.disposition!='REQUEST_NONCONTACT_VIEW' or w.next_observation!=step.view:
                raise LoopError('UNEXPECTED_VIEW_IN_HISTORY')
            if step.worlds_before!=worlds or step.before_certificate_hash!=w.certificate_hash:
                raise LoopError('HISTORY_MODEL_MISMATCH')
            if (step.parent_observation_id!=s.observation_id or
                step.child_observation_id!=f'{s.observation_id}:view{index}'):
                raise LoopError('HISTORY_OBSERVATION_PARENT_CHILD_MISMATCH')
            if step.source not in ('CV_LAYER_ONLY','CV_UNCALIBRATED','HUMAN_REPORTED'):
                raise LoopError('UNKNOWN_EVIDENCE_SOURCE')
            if (not isinstance(step.capture_sha256,str) or len(step.capture_sha256)!=64 or
                any(c not in '0123456789abcdef' for c in step.capture_sha256) or
                step.capture_sha256 in seen_captures):
                raise LoopError('EVIDENCE_CAPTURE_BINDING_INVALID')
            seen_captures.add(step.capture_sha256)
            posterior=restrict_worlds_after_view(worlds,step.view,step.signature,s.view_signatures)
            if posterior!=step.worlds_after or step.note!='RESEARCH_MODEL_ONLY_NO_PHYSICAL_AUTHORIZATION':
                raise LoopError('INVALID_WORLD_UPDATE_HISTORY')
            prior.append(step)
            worlds=posterior
            w=_make_witness(s,worlds,prior)
            if w.certificate_hash!=step.after_certificate_hash:
                raise LoopError('POSTERIOR_CERTIFICATE_MISMATCH')
        if (worlds!=s.worlds or w!=s.witness or not verify_witness_certificate(w) or
            s.disposition!=_disposition(s,w,prior)):
            raise LoopError('CURRENT_CERTIFICATE_MODEL_MISMATCH')
        return True
    except (WitnessError,KeyError,TypeError,ValueError,StopIteration,AttributeError) as e:
        if isinstance(e,LoopError):raise
        raise LoopError('INVALID_MODEL_OR_HISTORY') from e


def start_research_loop(session_id,observation_id,worlds,losses,view_signatures,view_costs,
                        initial_image_sha256,*,view_budget=MAX_VIEWS,initial_capture_origin='CLIENT_CLAIM_ONLY'):
    if not all(isinstance(x,str) and bool(x.strip()) for x in (session_id,observation_id)):
        raise LoopError('INVALID_SESSION_ID')
    if (not isinstance(initial_image_sha256,str) or len(initial_image_sha256)!=64 or
        any(c not in '0123456789abcdef' for c in initial_image_sha256)):
        raise LoopError('INITIAL_IMAGE_HASH_REQUIRED')
    if not isinstance(view_budget,int) or isinstance(view_budget,bool) or not 0<=view_budget<=MAX_VIEWS:
        raise LoopError('INVALID_VIEW_BUDGET')
    if initial_capture_origin not in ('CLIENT_CLAIM_ONLY','SERVER_CAPTURED_PNG'):
        raise LoopError('UNKNOWN_INITIAL_CAPTURE_PROVENANCE')
    frozen_losses=_snapshot(losses)
    frozen_views=_snapshot(view_signatures)
    frozen_costs=_snapshot(view_costs)
    w=recommend_witness(worlds,frozen_losses,frozen_views,frozen_costs,
        observation_id=observation_id,video_sha256=initial_image_sha256)
    s=ResearchLoop(session_id,observation_id,w.possible_worlds,frozen_losses,
        frozen_views,frozen_costs,tuple(sorted(frozen_views)),initial_image_sha256,
        (),view_budget,w,w.disposition)
    s=replace(s,initial_capture_origin=initial_capture_origin)
    s=replace(s,model_fingerprint=_fingerprint(s),disposition=_disposition(s,w,()))
    validate_loop(s)
    return s


def continue_research_loop(s:ResearchLoop,view:str,signature:str,capture_sha256:str,
                           *,source:str,cv_result:dict|None=None,cv_threshold_mm:float=5.0,
                           trusted_cv_validator=None):
    validate_loop(s)
    if len(s.steps)>=s.view_budget or s.disposition!='REQUEST_NONCONTACT_VIEW':
        raise LoopError('VIEW_BUDGET_EXHAUSTED_OR_TERMINAL')
    if s.witness.next_observation!=view:
        raise LoopError('UNAUTHORIZED_OR_STALE_VIEW')
    if (not isinstance(capture_sha256,str) or len(capture_sha256)!=64 or
        any(c not in '0123456789abcdef' for c in capture_sha256)):
        raise LoopError('CAPTURE_HASH_REQUIRED')
    if capture_sha256==s.initial_image_sha256 or any(x.capture_sha256==capture_sha256 for x in s.steps):
        raise LoopError('REUSED_IMAGE_NOT_NEW_EVIDENCE')
    if source not in ('CV_LAYER_ONLY','CV_UNCALIBRATED','HUMAN_REPORTED'):
        raise LoopError('UNRECOGNIZED_EVIDENCE_SOURCE')
    if source=='CV_LAYER_ONLY':
        if view not in ('SIDE','TOP') or not isinstance(cv_result,dict):
            raise LoopError('CV_CHANNEL_UNSUPPORTED')
        if not callable(trusted_cv_validator) or trusted_cv_validator(view,cv_result,capture_sha256) is not True:
            raise LoopError('CV_WORKER_ATTESTATION_REQUIRED')
        m=cv_result.get('measurement')
        if not isinstance(m,dict) or m.get('uncertainty_status')!='EMPIRICALLY_CALIBRATED':
            raise LoopError('CV_MEASUREMENT_NOT_CALIBRATED')
        if m.get('capture_sha256')!=capture_sha256:raise LoopError('CV_IMAGE_BINDING_MISMATCH')
        val=m.get('max_footprint_drift_mm')
        if isinstance(val,bool) or not isinstance(val,(int,float)) or not 0<=val<1e6:
            raise LoopError('INVALID_CV_MEASUREMENT')
        expected='layer_moves' if val>=cv_threshold_mm else 'layer_still'
        if signature!=expected:raise LoopError('CV_SIGNATURE_MISMATCH')
    elif source=='CV_UNCALIBRATED':
        if signature not in ('?','UNKNOWN_PREDICTION','MISSING_MEASUREMENT'):
            raise LoopError('UNCALIBRATED_CV_CANNOT_CLASSIFY')
        if not isinstance(cv_result,dict) or not callable(trusted_cv_validator) or not trusted_cv_validator(view,cv_result,capture_sha256):
            raise LoopError('CV_WORKER_ATTESTATION_REQUIRED')
        if cv_result.get('measurement') is None or cv_result['measurement'].get('uncertainty_status')!='NOT_CALIBRATED_UNCERTAINTY_NOT_ZERO':
            raise LoopError('RESEARCH_CV_RESULT_REQUIRED')
    elif cv_result is not None:
        raise LoopError('HUMAN_CV_PROVENANCE_MIXED')
    try:remaining=restrict_worlds_after_view(s.worlds,view,signature,s.view_signatures)
    except WitnessError as e:raise LoopError(str(e)) from e
    draft=EvidenceStep(len(s.steps)+1,view,source,signature,capture_sha256,s.worlds,remaining,
                       s.witness.certificate_hash,None,
                       'RESEARCH_MODEL_ONLY_NO_PHYSICAL_AUTHORIZATION',
                       parent_observation_id=s.observation_id,
                       child_observation_id=f'{s.observation_id}:view{len(s.steps)+1}')
    steps=s.steps+(draft,)
    new_w=_make_witness(s,remaining,steps)
    steps=steps[:-1]+(replace(draft,after_certificate_hash=new_w.certificate_hash),)
    result=replace(s,worlds=remaining,steps=steps,witness=new_w,
                   disposition=_disposition(s,new_w,steps),approval_authorized=False)
    validate_loop(result)
    return result


def trace_dict(s:ResearchLoop)->dict:
    validate_loop(s)
    return dict(session_id=s.session_id,observation_id=s.observation_id,
                possible_worlds=list(s.worlds),disposition=s.disposition,
                next_view=s.witness.next_observation if s.disposition=='REQUEST_NONCONTACT_VIEW' else None,
                modeled_recommendation=(s.witness.recommendation if s.disposition=='DIRECT_ACTION' else None),
                model_fingerprint=s.model_fingerprint,
                initial_capture_origin=s.initial_capture_origin,physical_action_authorized=False,
                steps=[step.__dict__ for step in s.steps],
                scientific_status='HYPOTHETICAL_MODEL_NOT_EMPIRICALLY_VALIDATED')
