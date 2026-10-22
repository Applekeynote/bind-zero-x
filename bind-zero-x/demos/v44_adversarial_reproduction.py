# -*- coding: utf-8 -*-
"""BIND ZERO-X v4.4 strict audit reproductions (not product tests).

Run from extracted v4.4 root:
    python v44_adversarial_reproduction.py
Every PASS below means that a reported defect was REPRODUCED, not that the
product passed the corresponding security/reliability requirement.
"""
import sys, json, hashlib
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / 'code'))

import numpy as np
from witness_planner import recommend_witness, verify_witness_certificate
from decision_gateway import gate_rule_with_witness
from cape_rule_core import Decision
from vision_motion_core import estimate_motion

findings = []

def record(code, reproduced, detail):
    findings.append({'id':code,'reproduced':bool(reproduced),'detail':str(detail)})

# R1: Published fields and SHA256 are mutually consistent, but the verifier does
# not recompute the claimed disposition from the input losses and view models.
w = recommend_witness(
    ['A','B'],
    {'REORDER':{'A':0,'B':6}, 'RE_TIE':{'A':6,'B':0},
     'ABSTAIN':{'A':2,'B':2}},
    {'SIDE':{'A':'left','B':'right'}},{'SIDE':0.1},observation_id='OBS')
assert w.disposition == 'REQUEST_NONCONTACT_VIEW'
payload = json.loads(w.certificate_payload)
payload['decision']['disposition']='DIRECT_ACTION'
payload['decision']['next_observation']=None
payload['decision']['recommendation']='REORDER'
raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
forged=replace(w, disposition='DIRECT_ACTION',next_observation=None,recommendation='REORDER',
               certificate_payload=raw,certificate_hash=hashlib.sha256(raw.encode()).hexdigest())
accepted=verify_witness_certificate(forged)
gated=gate_rule_with_witness(Decision('REORDER','TEST','OBS'),forged,
                             roi_identity_attested=True,model_calibrated=True,
                             independent_evidence_verified=True)
record('ADV-01',accepted and gated.action=='REORDER' and gated.human_approval_required,
       f'valid_original={w.disposition}, forged_verify={accepted}, gated={gated.action}, '
       f'human_approval_required={gated.human_approval_required}, '
       f'physical_action_authorized={gated.physical_action_authorized}')

# R2: Backward optical flow can return (None,None,None). The estimator must
# return FLOW_FAILED or TRACKING_UNAVAILABLE, not throw AttributeError.
im=np.zeros((100,100),dtype=np.uint8); mask=np.full_like(im,255)
pts=np.array([[[i*4.+5,j*4.+5]] for i in range(4) for j in range(4)],dtype=np.float32)
with patch('cv2.goodFeaturesToTrack',return_value=pts), patch(
        'cv2.calcOpticalFlowPyrLK',side_effect=[
            (pts.copy(),np.ones((len(pts),1),dtype=np.uint8),None),
            (None,None,None)]):
    try:
        estimated=estimate_motion(im,im,mask)
        record('ADV-02',False,f'Handled gracefully: {estimated}')
    except AttributeError as e:
        record('ADV-02',True,f'Unhandled {type(e).__name__}: {e}')

# R3: The finite model permits omitting abstain and constraining its action
# universe to an arbitrarily high-loss single action. Worst-case regret 0 alone
# therefore does not bound absolute physical risk.
w_bad=recommend_witness(['A','B'],{'KEEP':{'A':100,'B':100}}, {}, {},observation_id='OBS')
record('ADV-03',w_bad.disposition=='DIRECT_ACTION' and w_bad.recommendation=='KEEP',
       f'disposition={w_bad.disposition}, recommended={w_bad.recommendation}, '
       f'max_absolute_loss=100, regret={w_bad.regret_no_observation}')

print(json.dumps({'audit':'v4.4 adversarial checks',
                  'pass_means':'reported defect was reproducible',
                  'findings':findings},ensure_ascii=False,indent=2))
