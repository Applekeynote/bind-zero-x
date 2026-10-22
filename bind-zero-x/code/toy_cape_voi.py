# coding: utf-8
"""Fully specified finite-state action-value calculation for simulation only.
No physical transition probabilities are learned/estimated; NEVER use the default
example to authorize a real probe. All inputs must come from a preregistered model.
"""
from dataclasses import dataclass
import math

class ModelError(ValueError):pass

@dataclass(frozen=True)
class ProbeValue:
    probe:str
    expected_total_loss:float
    information_only:bool=False


def _prob(values):
    if not values or any(not isinstance(v,(float,int)) or not math.isfinite(v) or v<0 for v in values):
        raise ModelError('INVALID_PROBABILITY')
    if abs(sum(values)-1)>1e-9:raise ModelError('PROBABILITIES_NOT_NORMALIZED')


def choose_probe_finite(prior,loss,models,probe_costs,permitted):
    """Finite belief-state optimizer: prior[state], loss[(act,state)],
    models[probe][state] = [(next_state, observed_outcome, probability),...].
    probe's physical transition is accounted for BEFORE choosing the final action.
    No auto authorization or user-facing 'safe' claim.
    """
    if not prior or not loss:raise ModelError('EMPTY_MODEL')
    _prob(list(prior.values()))
    states=frozenset(prior)
    actions={u for u,m in loss}
    if not actions or any((u,m) not in loss for u in actions for m in states):
        raise ModelError('INCOMPLETE_LOSS')
    if any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in loss.values()):
        raise ModelError('NONFINITE_LOSS')
    baseline=min(sum(prior[m]*loss[(u,m)] for m in states) for u in actions)
    results=[ProbeValue('NO_PROBE',baseline)]
    for probe in sorted(permitted):
        if probe=='NO_PROBE':continue
        if probe not in models or probe not in probe_costs:raise ModelError('UNREGISTERED_PROBE')
        cost=probe_costs[probe]
        if not isinstance(cost,(float,int)) or not math.isfinite(cost) or cost<0:
            raise ModelError('INVALID_PROBE_COST')
        predicted={}
        for state,b in prior.items():
            if state not in models[probe]:raise ModelError('MISSING_TRANSITION')
            triples=models[probe][state]
            _prob([p for _,_,p in triples])
            for nxt,ob,p in triples:
                if nxt not in states:raise ModelError('UNKNOWN_NEXT_STATE')
                k=ob
                if not isinstance(k,str) or not k:raise ModelError('BAD_OBSERVATION')
                predicted[(k,nxt)]=predicted.get((k,nxt),0)+b*p
        obs=set(o for o,_ in predicted)
        loss_after=0.
        for o in obs:
            loss_after+=min(sum(prob*loss[(u,m)] for (ob,m),prob in predicted.items() if ob==o)
                            for u in actions)
        results.append(ProbeValue(probe,cost+loss_after))
    best=min(results,key=lambda z:(z.expected_total_loss,z.probe!='NO_PROBE',z.probe))
    return {'chosen_probe':best.probe,'baseline_risk':baseline,
            'risk_by_probe':{x.probe:x.expected_total_loss for x in results},
            'simulation_only_not_calibrated':True}
