# -*- coding: utf-8 -*-
"""Single conservative action gate: no independent rule can bypass a witness request.

This research gate cannot grant physical authorization to a toy-model witness.
The live implementation must additionally verify identity, safety, ownership,
regional rules, observation freshness, and durable human approval in AWS.
"""
from dataclasses import dataclass
import json
from cape_rule_core import Decision,PHYSICAL_ACTIONS
from witness_planner import DecisionWitness,verify_witness_certificate,model_fingerprint_from_payload

@dataclass(frozen=True)
class GatedDecision:
    action:str
    reason:str
    research_candidate_only:str|None
    physical_action_authorized:bool=False
    human_approval_required:bool=False

def gate_rule_with_witness(rule:Decision,witness:DecisionWitness,*,roi_identity_attested:bool,
                           model_calibrated:bool=False,independent_evidence_verified:bool=False,
                           trusted_model_fingerprint:str|None=None,
                           expected_video_sha256:str|None=None,
                           expected_calibration_id:str|None=None)->GatedDecision:
    if not verify_witness_certificate(witness):
        return GatedDecision('ABSTAIN','INVALID_WITNESS_CERTIFICATE',rule.action)
    bound_id=json.loads(witness.certificate_payload).get('observation_id')
    if bound_id not in ('RESEARCH_UNBOUND',rule.source_observation_id):
        return GatedDecision('ABSTAIN','STALE_WITNESS_OBSERVATION',rule.action)
    if (model_calibrated or independent_evidence_verified) and bound_id=='RESEARCH_UNBOUND':
        return GatedDecision('ABSTAIN','UNBOUND_WITNESS_CANNOT_APPROVE',rule.action)
    if model_calibrated or independent_evidence_verified:
        # Trust pins must originate from server-side preregistration, never from
        # a certificate submitted by a user or an LLM.
        if not trusted_model_fingerprint or not expected_video_sha256 or not expected_calibration_id:
            return GatedDecision('ABSTAIN','TRUSTED_EVIDENCE_BINDING_REQUIRED',rule.action)
        p=json.loads(witness.certificate_payload)
        if (model_fingerprint_from_payload(witness.certificate_payload)!=trusted_model_fingerprint or
            p.get('video_sha256')!=expected_video_sha256 or
            p.get('calibration_id')!=expected_calibration_id):
            return GatedDecision('ABSTAIN','TRUSTED_EVIDENCE_BINDING_MISMATCH',rule.action)
    if not roi_identity_attested:
        return GatedDecision('ABSTAIN','ROI_IDENTITY_UNATTESTED',rule.action)
    if witness.disposition=='REQUEST_NONCONTACT_VIEW':
        return GatedDecision('REQUEST_NONCONTACT_VIEW','WITNESS_REQUIRES_'+str(witness.next_observation),rule.action)
    if witness.disposition!='DIRECT_ACTION':
        return GatedDecision('ABSTAIN','UNRESOLVED_WITNESS',rule.action)
    if rule.action!=witness.recommendation:
        return GatedDecision('ABSTAIN','WITNESS_RULE_DISAGREEMENT',rule.action)
    # A pre-specified synthetic risk model is not physical evidence, regardless
    # of which apparently-correct action a local test chose.
    if not model_calibrated or not independent_evidence_verified:
        return GatedDecision('ABSTAIN','UNCALIBRATED_MODEL',rule.action)
    if rule.action not in PHYSICAL_ACTIONS:
        return GatedDecision('ABSTAIN','NO_PHYSICAL_CORRECTION_NEEDED_NOT_CERTIFIED',rule.action)
    return GatedDecision(rule.action,'PENDING_SEPARATE_HUMAN_APPROVAL',rule.action,
                         physical_action_authorized=False,human_approval_required=True)
