# coding: utf-8
"""Fully labeled HYPOTHETICAL two-step demo; no real rope CV or physical GT."""
import json
from active_evidence_loop import start_research_loop,continue_research_loop,trace_dict

def main():
    w=['LAYER_ONLY','LAYER_AND_ROPE']
    l={'REORDER':{'LAYER_ONLY':0,'LAYER_AND_ROPE':6},
       'REPOSITION_TWINE':{'LAYER_ONLY':5,'LAYER_AND_ROPE':2},
       'ABSTAIN':{'LAYER_ONLY':2,'LAYER_AND_ROPE':2}}
    signs={'ROPE_PATH':{'LAYER_ONLY':'rope_still','LAYER_AND_ROPE':'rope_moved'}}
    s=start_research_loop('SYNTH-0001','OBS-SYNTH',w,l,signs,{'ROPE_PATH':0.25},'a'*64)
    before=trace_dict(s)
    after=continue_research_loop(s,'ROPE_PATH','rope_moved','b'*64,source='HUMAN_REPORTED')
    print(json.dumps({'before':before,'after':trace_dict(after),
          'warning':'HYPOTHETICAL MANUAL REPORT; NO REAL OPENCV5/AWS/PHYSICAL-GT'},
          ensure_ascii=False,indent=2))
if __name__=='__main__':main()
