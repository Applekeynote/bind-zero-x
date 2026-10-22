# -*- coding: utf-8 -*-
"""Fail-closed, descriptive paired PHYSICAL trial analysis.

No synthetic trial is called real; the analyzer cannot prove a CSV's physical
provenance. Completion and aborted work are FIRST-CLASS outcomes. Never publish
unconditional speed gain from elapsed times for failed/incomplete attempts.
A pre-registered primary endpoint and independent blinded GT remain mandatory.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,math,random,statistics
from collections import Counter
from pathlib import Path
ARMS=('D0','D1','E1','E2','E2-ablated','B')
REQUIRED={'case_id','pair_id','D0_D1_E1_E2_or_B','original_sheet_count',
          'carried_sheet_count','completed','elapsed_seconds','wrong_intervention',
          'video_sha256'}

def read(csv_path):
    with Path(csv_path).open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        rows=list(reader)
        if not rows:raise ValueError('NO_REAL_TRIALS_NO_BENEFIT_CLAIM')
        if not reader.fieldnames or not REQUIRED.issubset(reader.fieldnames):
            raise ValueError('MISSING_REQUIRED_COLUMNS')
    seen=set(); by_pair={}; baseline_n={}; valid=[]
    for row in rows:
        r=dict(row);case=r['case_id'];pair=r['pair_id'];arm=r['D0_D1_E1_E2_or_B']
        if not case or case in seen or arm not in ARMS or not pair:raise ValueError('BAD_TRIAL_ID_OR_ARM')
        seen.add(case)
        key=(pair,arm)
        if key in by_pair:raise ValueError('DUPLICATE_ARM_IN_PAIR')
        try:
            if any(not r[x] for x in ('original_sheet_count','carried_sheet_count','elapsed_seconds')):
                raise ValueError()
            n=int(r['original_sheet_count']);carried=int(r['carried_sheet_count']);t=float(r['elapsed_seconds'])
        except (TypeError,ValueError,OverflowError):
            raise ValueError('INVALID_PHYSICAL_OUTCOME')
        if n<=0 or not 0<=carried<=n or not math.isfinite(t) or t<0:
            raise ValueError('INVALID_PHYSICAL_OUTCOME')
        if r['completed'] not in ('0','1') or r['wrong_intervention'] not in ('0','1'):
            raise ValueError('MISSING_BINARY_OUTCOME')
        if r['completed']=='1' and carried!=n:raise ValueError('INCOMPLETE_SHEETS_REPORTED_COMPLETE')
        if pair in baseline_n and baseline_n[pair]!=n:
            raise ValueError('PAIRED_CASE_DIFFERENT_ORIGINAL_SHEET_COUNTS')
        baseline_n[pair]=n
        if r['video_sha256'] and (len(r['video_sha256'])!=64 or any(c not in '0123456789abcdef' for c in r['video_sha256'])):
            raise ValueError('INVALID_VIDEO_HASH')
        r['_completed']=int(r['completed']);r['_wrong']=int(r['wrong_intervention'])
        r['_elapsed']=t;r['_n']=n;r['_carried']=carried
        by_pair[key]=r;valid.append(r)
    return valid,by_pair

def _boot_ci(deltas,iterations=2000,seed=47):
    if len(deltas)<2:return None
    rng=random.Random(seed);n=len(deltas)
    samples=sorted(sum(deltas[rng.randrange(n)] for _ in range(n))/n for _ in range(iterations))
    return [samples[int(.025*(iterations-1))],samples[int(.975*(iterations-1))]]

def _mean(values):return statistics.mean(values) if values else None

def analyze(csv_path):
    records,by_pair=read(csv_path)
    groups={arm:[r for r in records if r['D0_D1_E1_E2_or_B']==arm] for arm in ARMS}
    group_summaries={}
    for arm,rs in groups.items():
        done=sum(r['_completed'] for r in rs)
        group_summaries[arm]={
            'n':len(rs),'completed_n':done,'incomplete_or_aborted_n':len(rs)-done,
            'completion_rate':done/len(rs) if rs else None,
            'incomplete_or_aborted_rate':(len(rs)-done)/len(rs) if rs else None,
            'total_original_sheets':sum(r['_n'] for r in rs),
            'total_carried_sheets':sum(r['_carried'] for r in rs),
            'sheet_completion_fraction':sum(r['_carried'] for r in rs)/sum(r['_n'] for r in rs) if rs else None,
            'wrong_intervention_rate':_mean([r['_wrong'] for r in rs]),
            'successful_without_wrong_intervention_rate':_mean([int(r['_completed'] and not r['_wrong']) for r in rs]),
            'completed_only_mean_elapsed_seconds':_mean([r['_elapsed'] for r in rs if r['_completed']]),
            'all_trial_elapsed_mean_NOT_SPEED':_mean([r['_elapsed'] for r in rs]),
            'abort_reasons':dict(sorted(Counter(r.get('abort_reason','') or 'UNSPECIFIED' for r in rs if not r['_completed']).items())),
        }
    comparisons={}
    for control in ('D0','D1','E1','B'):
        pairs=sorted({pair for pair,arm in by_pair if arm=='E2' and (pair,control) in by_pair})
        if not pairs:
            comparisons[control]={'status':'NO_MATCHED_PAIRS','n_pairs':0}
            continue
        e2=[by_pair[(p,'E2')] for p in pairs]; c=[by_pair[(p,control)] for p in pairs]
        complete=[p for p in pairs if by_pair[(p,'E2')]['_completed'] and by_pair[(p,control)]['_completed']]
        completed_deltas=[by_pair[(p,'E2')]['_elapsed']-by_pair[(p,control)]['_elapsed'] for p in complete]
        complete_deltas=[x['_completed']-y['_completed'] for x,y in zip(e2,c)]
        error_deltas=[y['_wrong']-x['_wrong'] for x,y in zip(e2,c)]
        # Positive indicates E2 has a higher fraction of trials which both
        # completed ALL original sheets and avoided a wrong intervention.
        # This is a candidate PREREG endpoint, never silently designated primary.
        composite_deltas=[int(x['_completed'] and not x['_wrong'])-
                          int(y['_completed'] and not y['_wrong']) for x,y in zip(e2,c)]
        fraction_deltas=[x['_carried']/x['_n']-y['_carried']/y['_n'] for x,y in zip(e2,c)]
        e2_fail=sum(1 for r in e2 if not r['_completed'])
        control_fail=sum(1 for r in c if not r['_completed'])
        comparisons[control]={
            'status':'DESCRIPTIVE_ONLY_NOT_PREREGISTERED',
            'n_pairs':len(pairs),'joint_completed_pairs':len(complete),
            'n_excluded_from_speed_because_incomplete':len(pairs)-len(complete),
            'E2_completed_n':len(e2)-e2_fail,'control_completed_n':len(c)-control_fail,
            'E2_incomplete_n':e2_fail,'control_incomplete_n':control_fail,
            'E2_minus_control_completion_rate':_mean(complete_deltas),
            'completion_rate_difference_paired_bootstrap_95pct_CI':_boot_ci(complete_deltas),
            'E2_minus_control_sheet_completion_fraction_mean':_mean(fraction_deltas),
            'E2_minus_control_success_without_wrong_intervention_rate':_mean(composite_deltas),
            'success_without_wrong_intervention_paired_bootstrap_95pct_CI':_boot_ci(composite_deltas),
            'error_reduction_mean':_mean(error_deltas),
            'error_reduction_cluster_bootstrap_95pct_CI':_boot_ci(error_deltas),
            'completed_pair_only_E2_minus_control_elapsed_sec':_mean(completed_deltas),
            'completed_pair_only_time_bootstrap_95pct_CI':_boot_ci(completed_deltas),
            'unconditional_speed_claim_permitted':False,
            'interpretation':('Speed is conditional on both arms completing; not an unconditional time-saving '
                               'effect. Check completion before speed. No causal claim without verified randomization.'),
        }
    return {'data_sha256':hashlib.sha256(Path(csv_path).read_bytes()).hexdigest(),
        'status':'REAL_TRIAL_INPUT_UNDER_AUDIT_NOT_OFFICIAL_EFFECT_EVIDENCE',
        'n_records':len(records),'group_counts':{a:len(v) for a,v in groups.items()},
        'group_summaries':group_summaries,'comparisons':comparisons,
        'evidence_status':'UNVERIFIED_INPUT_NO_EMPIRICAL_CLAIM',
        'missing_video_hash_n':sum(not r.get('video_sha256') for r in records),
        'warnings':['CSV is user-provided; real-world provenance has not been verified by this script',
            'Never use incomplete/aborted durations to claim efficiency',
            'Conditional speed among completed cases is subject to selection bias',
            'Paired bootstrap intervals are descriptive, not corrected for multiplicity/clustering by bundle',
            'Primary endpoint, randomization, blinded independent GT and preregistration must be verified externally']}

def main():
    p=argparse.ArgumentParser();p.add_argument('trial_csv');p.add_argument('--output',required=True)
    a=p.parse_args();res=analyze(a.trial_csv)
    Path(a.output).write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(res,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
