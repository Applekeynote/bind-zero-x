# -*- coding: utf-8 -*-
"""BIND-WITNESS v4.4: conservative finite-model action-ambiguity witness.

Novelty is a *hypothesized integration* into a binding workflow, NOT the invention
of minimax regret, formal certificates, or active perception. Signatures and losses
are explicit assumptions until separately calibrated on real holdout fixtures.
This module NEVER permits physical actions; authorization is a separate gate.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from itertools import combinations
from typing import Any
import json,math

class WitnessError(ValueError):pass
ALLOWED_VIEWS=frozenset({'TOP','SIDE','ROPE_PATH','KNOT_CLOSEUP'})
ACTIONS=frozenset({'KEEP','REORDER','RE_TIE','REPOSITION_TWINE','SPLIT_2','ABSTAIN'})
# '?' and 'UNKNOWN_PREDICTION' mean ANY outcome could be produced by that world.
# 'UNOBSERVABLE' is an observed failure to see, not a diagnosis of the world.
UNKNOWN_TOKENS=frozenset({'?','UNKNOWN_PREDICTION','MISSING_MEASUREMENT'})
UNOBSERVABLE='UNOBSERVABLE'
POLICY_VERSION='CWC-4.5'
DEFAULT_MAX_ABSOLUTE_LOSS_UNITS=10.0
MAX_WORLDS=20
MAX_VIEWS=4
MAX_SIGNATURES_PER_WORLD=16
MAX_SIGNATURES_PER_VIEW=64
MAX_SIGNATURE_LENGTH=128

def _canonical(obj):
    return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)

def _number(x):
    return isinstance(x,(float,int)) and not isinstance(x,bool) and math.isfinite(x)

@dataclass(frozen=True)
class DecisionWitness:
    disposition:str
    next_observation:str|None
    recommendation:str|None
    possible_worlds:tuple[str,...]
    counterexample_pair:tuple[str,str]|None
    regret_no_observation:float
    risk_after_observation:float|None
    selection_scope:str='HYPOTHETICAL_FINITE_MODEL_NOT_CALIBRATED'
    certificate_hash:str=''
    conflict_core:tuple[str,...]|None=None
    common_optimal_actions:tuple[str,...]=()
    certificate_payload:str=''
    candidate_view_risks:tuple[tuple[str,float],...]=()

def _normalize_signatures(ws,view_signatures,views):
    if not isinstance(view_signatures,dict):raise WitnessError('INVALID_VIEW_SIGNATURE')
    result={}
    for view in sorted(views):
        if view not in view_signatures:continue
        sig=view_signatures[view]
        if not isinstance(sig,dict) or set(sig)!=set(ws):raise WitnessError('INVALID_VIEW_SIGNATURE')
        sets={}
        for w in ws:
            val=sig[w]
            if isinstance(val,str):vals={val}
            elif isinstance(val,(list,tuple,set,frozenset)):
                if len(val)>MAX_SIGNATURES_PER_WORLD:raise WitnessError('SIGNATURE_LIMIT_EXCEEDED')
                if any(not isinstance(v,str) or len(v)>MAX_SIGNATURE_LENGTH for v in val):
                    raise WitnessError('SIGNATURE_LIMIT_EXCEEDED')
                vals=set(val)
            else:raise WitnessError('INVALID_VIEW_SIGNATURE')
            if not vals or any(not isinstance(v,str) or not v.strip() for v in vals):
                raise WitnessError('INVALID_VIEW_SIGNATURE')
            if any(len(v)>MAX_SIGNATURE_LENGTH for v in vals):raise WitnessError('SIGNATURE_LIMIT_EXCEEDED')
            sets[w]=vals
        # Any unknown prediction could return any of the world's known signals,
        # or a failed/occluded observation. This deliberately prevents optimistic
        # partitioning of '?' against a known positive signature.
        universe={UNOBSERVABLE}
        for vals in sets.values():
            universe.update(v for v in vals if v not in UNKNOWN_TOKENS)
            if len(universe)>MAX_SIGNATURES_PER_VIEW:raise WitnessError('SIGNATURE_LIMIT_EXCEEDED')
        result[view]={w:tuple(sorted(universe if sets[w]&UNKNOWN_TOKENS else sets[w])) for w in ws}
    return result

def _conflict_core(worlds,optimal):
    shared=set.intersection(*(optimal[w] for w in worlds))
    if shared:return None
    # Find minimum number of worlds with no shared optimal action, not a fake
    # pair created by lexicographic tie-breaking. Pair may not exist at all.
    for k in range(2,len(worlds)+1):
        for subset in combinations(worlds,k):
            if not set.intersection(*(optimal[w] for w in subset)):
                return subset
    return None

def model_fingerprint_from_payload(certificate_payload:str)->str:
    """Model identity for comparison with a TRUSTED server-side registry.

    The payload itself is untrusted; the caller MUST supply its own pinned fingerprint.
    This hash alone does not authenticate a model or prove a real-world fact.
    """
    p=json.loads(certificate_payload)
    keys=('worlds','losses','raw_view_signatures','view_costs','allowed_views',
          'regret_tolerance','max_acceptable_absolute_loss_units','model_version')
    return sha256(_canonical({k:p[k] for k in keys}).encode()).hexdigest()


def verify_witness_certificate(witness:DecisionWitness)->bool:
    """Semantic verification: recompute the full decision from disclosed assumptions.

    Self-consistency is NOT proof of trusted model provenance or physical truth.
    Model authorization requires an independently pinned model fingerprint.
    """
    try:
        if not isinstance(witness,DecisionWitness):return False
        raw=witness.certificate_payload
        if not isinstance(raw,str) or not raw or len(raw)>250_000:return False
        if sha256(raw.encode()).hexdigest()!=witness.certificate_hash:return False
        p=json.loads(raw)
        if raw!=_canonical(p) or p.get('policy_version')!=POLICY_VERSION:return False
        original=recommend_witness(
            p['worlds'],p['losses'],p['raw_view_signatures'],p['view_costs'],
            regret_tolerance=p['regret_tolerance'],allowed_views=p['allowed_views'],
            observation_id=p['observation_id'],video_sha256=p['video_sha256'],
            calibration_id=p['calibration_id'],model_version=p['model_version'],
            max_acceptable_absolute_loss_units=p['max_acceptable_absolute_loss_units'])
        # Ensures EVERY derived property (including optima, conflict core, risks,
        # bound observation ID and all view predictions) matches the recomputation.
        from independent_witness_checker import check_semantics
        return (original==witness and original.certificate_payload==raw and
                check_semantics(p))
    except (KeyError,TypeError,ValueError,OverflowError,RecursionError,WitnessError):
        return False

def recommend_witness(worlds,losses,view_signatures,view_costs,*,regret_tolerance=0.0,
                      allowed_views=ALLOWED_VIEWS,observation_id='RESEARCH_UNBOUND',
                      video_sha256=None,calibration_id=None,model_version='EXPLICIT_TOY_MODEL',
                      physical_action_authorized=False,
                      max_acceptable_absolute_loss_units=DEFAULT_MAX_ABSOLUTE_LOSS_UNITS):
    """Minimize worst-case regret+noncontact view cost; fail closed on ambiguity.

    DIRECT_ACTION means *model-internal* adequate action, never an authorization.
    Unknown prediction sets are expanded conservatively. Costs share the same
    dimensionless registered loss units. A 0-regret view cannot be selected solely
    because it is free (requires strict risk reduction).
    """
    if physical_action_authorized:raise WitnessError('WITNESS_CANNOT_AUTHORIZE_PHYSICAL_ACTION')
    try:ws=tuple(sorted(set(worlds)))
    except (TypeError,ValueError):raise WitnessError('INVALID_WORLD_SET')
    if not ws or len(ws)>MAX_WORLDS or any(not isinstance(w,str) or not w for w in ws):
        raise WitnessError('INVALID_WORLD_SET')
    if not isinstance(losses,dict) or not losses or not set(losses)<=ACTIONS:
        raise WitnessError('INVALID_ACTION_SET')
    if not _number(regret_tolerance) or regret_tolerance<0:raise WitnessError('INVALID_REGRET_TOLERANCE')
    if not _number(max_acceptable_absolute_loss_units) or max_acceptable_absolute_loss_units<0:
        raise WitnessError('INVALID_ABSOLUTE_LOSS_CEILING')
    if not isinstance(observation_id,str) or not observation_id.strip():raise WitnessError('INVALID_OBSERVATION_ID')
    if not isinstance(model_version,str) or not model_version.strip():raise WitnessError('INVALID_MODEL_VERSION')
    if video_sha256 is not None and (not isinstance(video_sha256,str) or len(video_sha256)!=64 or
                                      any(c not in '0123456789abcdef' for c in video_sha256)):
        raise WitnessError('INVALID_VIDEO_SHA256')
    try:allowed=set(allowed_views)&ALLOWED_VIEWS
    except TypeError:raise WitnessError('INVALID_ALLOWED_VIEWS')
    if len(allowed)>MAX_VIEWS:raise WitnessError('TOO_MANY_VIEWS')
    for action,row in losses.items():
        if not isinstance(row,dict) or set(row)!=set(ws):raise WitnessError('INCOMPLETE_LOSS_TABLE')
        if any(not _number(v) or v<0 for v in row.values()):raise WitnessError('INVALID_LOSS')
    actions=tuple(sorted(losses))
    best_in_world={w:min(float(losses[a][w]) for a in actions) for w in ws}
    opt={w:{a for a in actions if float(losses[a][w])-best_in_world[w]<=1e-9} for w in ws}
    common=tuple(sorted(set.intersection(*(opt[w] for w in ws))))
    core=_conflict_core(ws,opt)
    pair=core if core is not None and len(core)==2 else None

    def risk(subset):
        vals={a:max(float(losses[a][w])-best_in_world[w] for w in subset) for a in actions}
        candidate=min(actions,key=lambda a:(round(vals[a],12),a))
        return candidate,vals[candidate]
    act0,r0=risk(ws)
    if common:act0=common[0]   # Avoid fabricated conflict via tie-breaks

    if not isinstance(view_costs,dict):raise WitnessError('INVALID_VIEW_COST')
    normalized=_normalize_signatures(ws,view_signatures,allowed)
    candidates=[]
    for view in sorted(allowed):
        if view not in normalized or view not in view_costs:continue
        cost=view_costs[view]
        if not _number(cost) or cost<0:raise WitnessError('INVALID_VIEW_COST')
        outcomes=sorted({x for v in normalized[view].values() for x in v})
        # Multiple worlds can emit the SAME result, so this is a cover,
        # NOT a partition when predictions have overlapping possibility sets.
        remaining=max(risk(tuple(w for w in ws if outcome in normalized[view][w]))[1]
                      for outcome in outcomes)
        candidates.append((float(cost)+remaining,view,remaining))
    best=min(candidates,default=None)
    worst_absolute_for_selected=max(float(losses[act0][w]) for w in ws)
    # Minimax regret=0 does NOT bound the absolute consequence (e.g. KEEP=100
    # everywhere). Never issue DIRECT_ACTION above a separately-set ceiling.
    absolute_acceptable=worst_absolute_for_selected<=max_acceptable_absolute_loss_units
    # A view may be justified by decreasing ABSOLUTE loss exposure even when
    # raw regret is within tolerance. Every possible outcome must admit at
    # least one non-ABSTAIN action under the registered absolute ceiling.
    # This is a conservative, model-internal calculation, not physical safety.
    feasible_absolute_views=[]
    for score,view,remaining_regret in candidates:
        signatures=normalized[view]
        outcomes={sig for poss in signatures.values() for sig in poss}
        worst_best_absolute=0.0
        for observed in outcomes:
            subset=tuple(w for w in ws if observed in signatures[w])
            if not subset:continue
            available=[a for a in actions if a!='ABSTAIN']
            best_abs=min((max(float(losses[a][w]) for w in subset) for a in available),default=float('inf'))
            worst_best_absolute=max(worst_best_absolute,best_abs)
        if worst_best_absolute<=max_acceptable_absolute_loss_units:
            feasible_absolute_views.append((score,view,remaining_regret,worst_best_absolute))
    feasible_absolute_views.sort()
    if r0<=regret_tolerance+1e-9 and absolute_acceptable:
        disposition=('ABSTAIN' if act0=='ABSTAIN' else 'DIRECT_ACTION')
        nextview=None;recommendation=(None if act0=='ABSTAIN' else act0);after=None
    elif not absolute_acceptable and feasible_absolute_views and feasible_absolute_views[0][0]<worst_absolute_for_selected:
        disposition='REQUEST_NONCONTACT_VIEW';nextview=feasible_absolute_views[0][1]
        recommendation=None;after=feasible_absolute_views[0][0]
    elif best is not None and best[0]+1e-9<r0 and r0>regret_tolerance+1e-9:
        disposition='REQUEST_NONCONTACT_VIEW';nextview=best[1];recommendation=None;after=best[0]
    else:
        disposition='ABSTAIN';nextview=None;recommendation=None;after=None
    payload={'policy_version':POLICY_VERSION,'observation_id':observation_id,
             'video_sha256':video_sha256,'calibration_id':calibration_id,'model_version':model_version,
             'worlds':list(ws),'losses':{a:{w:float(losses[a][w]) for w in ws} for a in actions},
             'predictions':{v:{w:list(vals) for w,vals in s.items()} for v,s in normalized.items()},
             'raw_view_signatures':{v:{w:(sorted(view_signatures[v][w]) if isinstance(view_signatures[v][w],(list,tuple,set,frozenset)) else view_signatures[v][w]) for w in ws} for v in sorted(normalized)},
             'view_costs':{v:float(view_costs[v]) for v in sorted(normalized) if v in view_costs},
             'allowed_views':sorted(allowed),'regret_tolerance':float(regret_tolerance),
             'max_acceptable_absolute_loss_units':float(max_acceptable_absolute_loss_units),
             'selected_max_absolute_loss_units':worst_absolute_for_selected,
             'optima':{w:sorted(opt[w]) for w in ws},'common_optima':list(common),
             'conflict_core':list(core) if core else None,
             'decision':{'disposition':disposition,'next_observation':nextview,'recommendation':recommendation,
                         'r0':r0,'after':after,'candidate_view_risks':[(v,c) for c,v,_ in sorted(candidates)]},
             'evidence_scope':'MODEL_INTERNAL_ONLY_NOT_PHYSICAL_CERTIFICATE'}
    raw=_canonical(payload)
    digest=sha256(raw.encode('utf-8')).hexdigest()
    return DecisionWitness(disposition,nextview,recommendation,ws,pair,r0,after,
                           certificate_hash=digest,conflict_core=core,common_optimal_actions=common,
                           certificate_payload=raw,
                           candidate_view_risks=tuple((v,c) for c,v,_ in sorted(candidates)))

def restrict_worlds_after_view(worlds,view,actual_signature,view_signatures):
    if view not in ALLOWED_VIEWS or view not in view_signatures:raise WitnessError('UNREGISTERED_VIEW')
    ws=tuple(sorted(set(worlds)))
    normalized=_normalize_signatures(ws,view_signatures,{view})
    if actual_signature in UNKNOWN_TOKENS or actual_signature in ('MISSING_MEASUREMENT',):
        return ws  # No evidence, never a fabricated update.
    if not isinstance(actual_signature,str) or not actual_signature:raise WitnessError('INVALID_ACTUAL_SIGNATURE')
    posterior=tuple(w for w in ws if actual_signature in normalized[view][w])
    if not posterior:raise WitnessError('MODEL_FALSIFIED_BY_OBSERVATION')
    return posterior
