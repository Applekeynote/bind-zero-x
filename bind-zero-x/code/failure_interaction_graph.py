# -*- coding: utf-8 -*-
"""Typed FIG evidence graph (v4.4) for a small two-layer research fixture.

Edges encode *candidate physical dependencies*, NOT a learned causal discovery.
Nodes carry per-channel observation status and provenance; UNKNOWN is never 0.
"""
from __future__ import annotations
from dataclasses import dataclass,asdict
from hashlib import sha256
import json,math

class GraphError(ValueError):pass
KINDS=frozenset({'LAYER_CONTACT','ROPE_PATH','KNOT_END'})
STATES=frozenset({'OBSERVED','UNKNOWN','UNCERTAIN'})

@dataclass(frozen=True)
class EvidenceNode:
    node_id:str
    kind:str
    state:str
    observation_id:str
    value_mm:float|None=None
    plane_id:str|None=None
    calibration_id:str|None=None
    uncertainty_mm:float|None=None
    reason:str|None=None
    def __post_init__(self):
        if self.kind not in KINDS or self.state not in STATES or not self.node_id or not self.observation_id:
            raise GraphError('INVALID_FIG_ID_KIND_OR_STATE')
        if self.state=='OBSERVED' and (self.value_mm is None or self.plane_id is None or self.calibration_id is None):
            raise GraphError('OBSERVED_REQUIRES_EVIDENCE_AND_CALIBRATION')
        if self.state!='OBSERVED' and not self.reason:raise GraphError('UNAVAILABLE_REQUIRES_REASON')
        for v in (self.value_mm,self.uncertainty_mm):
            if v is not None and (isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0):
                raise GraphError('NONFINITE_FIG_MEASUREMENT')

@dataclass(frozen=True)
class InteractionEdge:
    node_a:str
    node_b:str
    relation:str
    def __post_init__(self):
        if not self.node_a or not self.node_b or self.node_a==self.node_b or self.relation!='CAN_COINCIDE_NOT_CAUSAL':
            raise GraphError('INVALID_INTERACTION_EDGE')

@dataclass(frozen=True)
class FailureInteractionGraph:
    nodes:tuple[EvidenceNode,...]
    edges:tuple[InteractionEdge,...]
    revision:int=0
    def __post_init__(self):
        ids=[n.node_id for n in self.nodes]
        if len(set(ids))!=len(ids):raise GraphError('DUPLICATE_NODE')
        if any(e.node_a not in ids or e.node_b not in ids for e in self.edges):
            raise GraphError('DANGLING_EDGE')
        if self.revision<0:raise GraphError('INVALID_REVISION')
    def evolve(self,updated:EvidenceNode):
        if updated.node_id not in {n.node_id for n in self.nodes}:raise GraphError('UNKNOWN_NODE')
        return FailureInteractionGraph(tuple(updated if n.node_id==updated.node_id else n for n in self.nodes),
                                       self.edges,self.revision+1)
    def fingerprint(self):
        data={'nodes':[asdict(n) for n in sorted(self.nodes,key=lambda n:n.node_id)],
              'edges':[asdict(e) for e in sorted(self.edges,key=lambda e:(e.node_a,e.node_b))],
              'revision':self.revision}
        return sha256(json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    def missing_channels(self):return tuple(sorted(n.kind for n in self.nodes if n.state!='OBSERVED'))

def build_fig(layer_metric,observation_id,*,rope_metric=None,knot_metric=None,layer_quality='OBSERVED'):
    if layer_quality not in STATES:raise GraphError('INVALID_LAYER_QUALITY')
    def node(ident,kind,metric,reason):
        if metric is None:
            return EvidenceNode(ident,kind,'UNKNOWN',observation_id,reason=reason)
        if metric.observation_id!=observation_id:raise GraphError('OBSERVATION_MISMATCH')
        return EvidenceNode(ident,kind,'OBSERVED',observation_id,
                            value_mm=metric.value_mm,plane_id=metric.plane_id,
                            calibration_id=metric.calibration_id,uncertainty_mm=metric.sigma_mm)
    layer=node('L01','LAYER_CONTACT',layer_metric,'LAYER_NOT_MEASURED')
    if layer_quality!='OBSERVED':
        layer=EvidenceNode('L01','LAYER_CONTACT',layer_quality,observation_id,
                           reason='UNCERTAIN_LAYER' if layer_quality=='UNCERTAIN' else 'LAYER_NOT_MEASURED')
    return FailureInteractionGraph((layer,node('R01','ROPE_PATH',rope_metric,'ROPE_NOT_MEASURED'),
                                    node('K01','KNOT_END',knot_metric,'KNOT_NOT_MEASURED')),
                                   (InteractionEdge('L01','R01','CAN_COINCIDE_NOT_CAUSAL'),
                                    InteractionEdge('R01','K01','CAN_COINCIDE_NOT_CAUSAL')))
