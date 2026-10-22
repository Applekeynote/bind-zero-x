# -*- coding: utf-8 -*-
"""v4.1 evaluation primitives. No virtual data is passed off as physical evidence.
A profile MUST specify target AND tolerance for each measured input; equality of arms alone
never makes an invalid challenge valid. Failed/aborted jobs remain in attempt summaries.
"""
import math
from collections import defaultdict

class ProtocolError(ValueError):pass


def selective_metrics(labels,predictions,modes=('LAYER','ROPE','KNOT')):
    if len(labels)!=len(predictions) or not labels:raise ProtocolError('LENGTH_OR_EMPTY')
    valid=set(modes);decided=[]
    for gt,pred in zip(labels,predictions):
        if not isinstance(gt,(set,frozenset)) or not gt<=valid:raise ProtocolError('INVALID_GT')
        if pred is not None:
            if not isinstance(pred,(set,frozenset)) or not pred<=valid:raise ProtocolError('INVALID_PRED')
            decided.append((gt,pred))
    per={}
    for mode in modes:
        tp=sum(mode in g and p is not None and mode in p for g,p in zip(labels,predictions))
        fp=sum(mode not in g and p is not None and mode in p for g,p in zip(labels,predictions))
        fn=sum(mode in g and (p is None or mode not in p) for g,p in zip(labels,predictions))
        per[mode]={'tp':tp,'fp':fp,'fn':fn,'precision':tp/(tp+fp) if tp+fp else None,
                   'recall':tp/(tp+fn) if tp+fn else None}
    return {'n':len(labels),'coverage':len(decided)/len(labels),
            'selective_exact_accuracy':(sum(g==p for g,p in decided)/len(decided) if decided else None),
            'per_mode':per,'no_decisions':not decided}


def _numeric(value,key):
    try:
        if isinstance(value,bool):raise TypeError()
        out=float(value)
    except (ValueError,TypeError):raise ProtocolError('INVALID_VALUE_'+key)
    if not math.isfinite(out):raise ProtocolError('NONFINITE_VALUE_'+key)
    return out


def validate_challenge(x,y,profile):
    """Reject incomplete/unfrozen protocols and drift from independent frozen targets.
    Values for approved targets and limits come from a real preflight, never this module.
    """
    from challenge_contract import assert_profile_frozen
    profile=assert_profile_frozen(profile)
    kind=profile['stimulus_type']
    for arm,row in (('A',x),('B',y)):
        if row.get('challenge_id')!=profile['challenge_id']:
            raise ProtocolError('CHALLENGE_ID_'+arm)
        if row.get('challenge_profile_revision')!=profile['revision']:
            raise ProtocolError('PROFILE_REVISION_'+arm)
        if row.get('challenge_profile_hash')!=profile['profile_hash']:
            raise ProtocolError('PROFILE_HASH_'+arm)
        if row.get('stimulus_type')!=kind:
            raise ProtocolError('STIMULUS_TYPE_'+arm)
    for name in ('material_batch','fixture_revision','stimulus_type','challenge_profile_revision'):
        if not x.get(name) or x.get(name)!=y.get(name):raise ProtocolError('MISMATCH_'+name)
    for name,spec in profile['input_targets'].items():
        target=_numeric(spec['target'],name);tol=_numeric(spec['tolerance'],name)
        for arm,row in (('A',x),('B',y)):
            if name not in row or row[name] is None:raise ProtocolError('MISSING_ACTUAL_INPUT_'+name)
            value=_numeric(row[name],name)
            if value<0 or (name=='duration_s' and value<=0):raise ProtocolError('NEGATIVE_OR_ZERO_INPUT_'+name)
            if abs(value-target)>tol+1e-9:
                raise ProtocolError('TARGET_DEVIATION_'+name+'_'+arm)
        if abs(_numeric(x[name],name)-_numeric(y[name],name))>tol+1e-9:
            raise ProtocolError('ARM_MISMATCH_'+name)
    return True


def _positive_int(value,field,allow_zero=False):
    if isinstance(value,bool) or not isinstance(value,int) or value<0 or (not allow_zero and value==0):
        raise ProtocolError('INVALID_'+field)
    return value


def validate_attempt(r):
    status=r.get('job_status')
    if status not in ('COMPLETED','ABORTED','FAILED','INCOMPLETE','NOT_RUN'):
        raise ProtocolError('INVALID_JOB_STATUS')
    n=_positive_int(r.get('original_sheet_count'),'ORIGINAL_SHEET_COUNT')
    done=_positive_int(r.get('evaluated_sheet_count'),'EVALUATED_SHEET_COUNT',allow_zero=True)
    if done>n:raise ProtocolError('EXCESS_EVALUATED_SHEETS')
    if status=='COMPLETED' and n!=done:raise ProtocolError('FALSE_COMPLETE_SHEETS')
    t=r.get('total_time_s')
    if status=='COMPLETED' and t is None:raise ProtocolError('MISSING_COMPLETED_TIME')
    if t is not None and _numeric(t,'total_time_s')<0:raise ProtocolError('NEGATIVE_TIME')
    return True


def summarize_all_attempts(records,methods=('B','E')):
    """Counts all attempted jobs, including failures; completed times are conditional only."""
    out={}
    for m in methods:
        subset=[r for r in records if r.get('method')==m]
        if len({(r.get('configuration_id'),r.get('trial_id')) for r in subset})!=len(subset):
            raise ProtocolError('DUPLICATE_TRIAL')
        statuses=defaultdict(int)
        for r in subset:
            validate_attempt(r)
            statuses[r['job_status']]+=1
        completed=[r for r in subset if r['job_status']=='COMPLETED']
        times=[_numeric(r['total_time_s'],'total_time_s') for r in completed]
        attempted=sum(v for k,v in statuses.items() if k!='NOT_RUN')
        out[m]={'attempted':attempted, 'completed':len(completed),
                'aborted':statuses['ABORTED'],'failed':statuses['FAILED'],
                'incomplete':statuses['INCOMPLETE'],'not_run':statuses['NOT_RUN'],
                'completion_rate':len(completed)/attempted if attempted else None,
                'observed_completed_times_s':times,
                'timing_scope':'COMPLETERS_ONLY_NO_CENSORED_IMPUTATION',
                'all_attempts_accounted_for':True}
    return out


def paired_effect(records,control,treatment,metric,profile):
    """Only complete *paired* configurations. Call summarize_all_attempts for failures too."""
    by=defaultdict(dict)
    for row in records:
        cfg=row['configuration_id'];m=row['method']
        if m in by[cfg]:raise ProtocolError('DUPLICATE_ARM')
        by[cfg][m]=row
    values=[];unpaired=[]
    for cfg,arms in sorted(by.items()):
        if control not in arms or treatment not in arms:
            unpaired.append(cfg);continue
        x,y=arms[control],arms[treatment]
        for r in (x,y):validate_attempt(r)
        if any(r.get('job_status')!='COMPLETED' for r in (x,y)):
            raise ProtocolError('CENSORED_OR_INCOMPLETE_'+cfg)
        for r in (x,y):
            if r.get('original_sheet_count')!=r.get('evaluated_sheet_count'):
                raise ProtocolError('SHEET_MISMATCH_'+cfg)
        validate_challenge(x,y,profile)
        a=x.get(metric);b=y.get(metric)
        if a is None or b is None:raise ProtocolError('MISSING_OUTCOME_'+cfg)
        aa=_numeric(a,metric);bb=_numeric(b,metric)
        if metric.endswith(('_s','_mm','_N')) and min(aa,bb)<0:raise ProtocolError('NEGATIVE_OUTCOME_'+metric)
        values.append({'configuration_id':cfg,'delta_treatment_minus_control':bb-aa})
    return {'n_independent_configs':len(values),'paired_deltas':values,'unpaired_configs':unpaired,
            'interpretation':'EXPLORATORY_COMPLETE_PAIRS_NOT_ITT'}


def utility_gate(effects,n_min=8,meaningful_improvement=10.):
    if effects['n_independent_configs']<n_min:return 'INCONCLUSIVE_INSUFFICIENT_CONFIGS'
    ds=sorted(x['delta_treatment_minus_control'] for x in effects['paired_deltas'])
    med=ds[len(ds)//2] if len(ds)%2 else (ds[len(ds)//2-1]+ds[len(ds)//2])/2
    if med<=-meaningful_improvement:return 'EXPLORATORY_IMPROVEMENT_ONLY'
    if med>=meaningful_improvement:return 'EXPLORATORY_WORSE_ONLY'
    return 'INCONCLUSIVE_SMALL_EFFECT'
