# -*- coding: utf-8 -*-
"""SYNTHETIC FINITE-MODEL ABLATION ONLY -- not physical measured outcomes.

Precisely specified hypothetical worlds and losses. Does not infer treatment
benefit in cardboard binding; never call this an empirical baseline study.
"""
from __future__ import annotations
import json
from pathlib import Path
from witness_planner import recommend_witness,restrict_worlds_after_view

ACTS={'A':'REORDER','B':'RE_TIE'}
LOSSES={'REORDER':{'A':0,'B':6},'RE_TIE':{'A':6,'B':0},'ABSTAIN':{'A':2,'B':2}}

SCENARIOS=[
    dict(name='top_already_diagnostic',signatures={
        'TOP':{'A':'layer_moves','B':'layer_still'},
        'ROPE_PATH':{'A':'?','B':'?'},
        'SIDE':{'A':'?','B':'?'}}),
    dict(name='rope_path_only_diagnostic',signatures={
        'TOP':{'A':'?','B':'?'},'ROPE_PATH':{'A':'rope_still','B':'rope_moves'},
        'SIDE':{'A':'?','B':'?'}}),
    dict(name='side_only_diagnostic',signatures={
        'TOP':{'A':'?','B':'?'},'ROPE_PATH':{'A':'?','B':'?'},
        'SIDE':{'A':'edge_moves','B':'edge_still'}}),
    dict(name='no_informative_view',signatures={
        'TOP':{'A':'?','B':'?'},'SIDE':{'A':'?','B':'?'},
        'ROPE_PATH':{'A':'?','B':'?'}}),
]

def one_case(model,truth,method):
    sig=model['signatures']
    costs={v:0.2 for v in sig}
    if method=='PCIG':
        cert=recommend_witness(['A','B'],LOSSES,sig,costs,
                                observation_id='SYNTHETIC',video_sha256='0'*64)
        view=cert.next_observation if cert.disposition=='REQUEST_NONCONTACT_VIEW' else None
    else:view='TOP'  # prespecified static-view baseline, no model-aware selection
    worlds=('A','B')
    if view:
        token=sig[view][truth]
        if token!='?':worlds=restrict_worlds_after_view(worlds,view,token,sig)
    next_cert=recommend_witness(worlds,{a:{w:r[w] for w in worlds} for a,r in LOSSES.items()}, {}, {},
                               observation_id='SYNTHETIC:AFTER')
    action=next_cert.recommendation if next_cert.disposition=='DIRECT_ACTION' else 'ABSTAIN'
    return dict(scenario=model['name'],true_world=truth,method=method,chosen_view=view,
                worlds_after=worlds,final_action=action,
                hypothetical_loss=LOSSES[action][truth]+(costs[view] if view else 0),
                physical_trial=False,agentic_opencv5_evidence=False)

def main():
    rows=[one_case(case,w,method) for case in SCENARIOS for w in ('A','B') for method in ('PCIG','STATIC_TOP')]
    grouped={}
    for m in ('PCIG','STATIC_TOP'):
        selected=[r['hypothetical_loss'] for r in rows if r['method']==m]
        grouped[m]={'mean_hypothetical_loss':sum(selected)/len(selected),'n_simulated_world_cases':len(selected)}
    output={'evidence_scope':'HYPOTHETICAL_FINITE_MODEL_ONLY_NOT_REAL_GT',
            'purpose':'Falsifiable demonstration of a model-internal view selection comparison',
            'scenario_count':len(SCENARIOS),'summary':grouped,'cases':rows,
            'limitations':['Contrived loss function','Synthetic view signatures','No camera','No AWS',
                           'No OpenCV5 runtime','No human comparison','No independence/realism claim']}
    path=Path(__file__).with_name('finite_model_ablation_result.json')
    path.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(output['summary'],ensure_ascii=False))
    return output
if __name__=='__main__':main()
