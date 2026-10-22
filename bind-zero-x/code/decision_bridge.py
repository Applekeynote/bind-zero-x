# -*- coding: utf-8 -*-
"""RESEARCH-ONLY bridge: observed layer motion -> BIND-WITNESS hypothetical scenario.

NO rope/knot ground truth is inferred from image-only layer motion. A finite model is
an explicit uncalibrated ILLUSTRATION; real deployments must replace signatures and
losses with independent preregistered pilot measurements before any numeric claim.
"""
from witness_planner import recommend_witness
import math


def illustrative_witness_for_layer_evidence(value_mm,rotation_deg,*,threshold_mm=5.,angle_limit_deg=3.):
    if any(not isinstance(v,(float,int)) or not math.isfinite(v) for v in
           (value_mm,rotation_deg,threshold_mm,angle_limit_deg)):
        raise ValueError('INVALID_WITNESS_EVIDENCE')
    if value_mm<0 or threshold_mm<=0 or angle_limit_deg<=0:raise ValueError('INVALID_WITNESS_EVIDENCE')
    visible_layer_fault=value_mm>=threshold_mm or abs(rotation_deg)>=angle_limit_deg
    if visible_layer_fault:
        worlds=['LAYER_ONLY','LAYER_PLUS_ROPE']
        losses={
          'REORDER':{'LAYER_ONLY':0.,'LAYER_PLUS_ROPE':6.},
          'REPOSITION_TWINE':{'LAYER_ONLY':5.,'LAYER_PLUS_ROPE':2.},
          'ABSTAIN':{'LAYER_ONLY':2.,'LAYER_PLUS_ROPE':2.}}
        signatures={
          'ROPE_PATH':{'LAYER_ONLY':'rope_still','LAYER_PLUS_ROPE':'rope_moved'},
          'SIDE':{'LAYER_ONLY':'layer_moves','LAYER_PLUS_ROPE':'layer_moves'}}
        costs={'ROPE_PATH':.25,'SIDE':.5}
    else:
        worlds=['NO_DETECTED_LAYER_FAULT','ROPE_ONLY','KNOT_ONLY']
        losses={
          'KEEP':{'NO_DETECTED_LAYER_FAULT':0.,'ROPE_ONLY':6.,'KNOT_ONLY':6.},
          'REPOSITION_TWINE':{'NO_DETECTED_LAYER_FAULT':4.,'ROPE_ONLY':0.,'KNOT_ONLY':5.},
          'RE_TIE':{'NO_DETECTED_LAYER_FAULT':4.,'ROPE_ONLY':5.,'KNOT_ONLY':0.},
          'ABSTAIN':{'NO_DETECTED_LAYER_FAULT':2.,'ROPE_ONLY':2.,'KNOT_ONLY':2.}}
        signatures={
          'ROPE_PATH':{'NO_DETECTED_LAYER_FAULT':'rope_still','ROPE_ONLY':'rope_moved','KNOT_ONLY':'rope_still'},
          'KNOT_CLOSEUP':{'NO_DETECTED_LAYER_FAULT':'knot_still','ROPE_ONLY':'knot_still','KNOT_ONLY':'knot_moved'}}
        costs={'ROPE_PATH':.25,'KNOT_CLOSEUP':.25}
    result=recommend_witness(worlds,losses,signatures,costs)
    return {
       'next_observation':result.next_observation,
       'disposition':result.disposition,
       'counterexample_pair':result.counterexample_pair,
       'certificate_hash':result.certificate_hash,
       'initial_regret_units':result.regret_no_observation,
       'predicted_after_view_risk_units':result.risk_after_observation,
       'status':'ILLUSTRATIVE_UNCALIBRATED_WORLD_AND_VIEW_MODEL',
       'physical_action_authorized':False,
       'hypothetical_model':{'worlds':worlds,'losses':losses,'view_signatures':signatures,'costs':costs},
    }
