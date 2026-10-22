# coding: utf-8
"""Independent finite enumeration checker for v4.5 certificate math.

Does not import the witness planner. This verifies model-INTERNAL claims, never
that the model approximates the real cardboard physics or that a source is trusted.
"""
import itertools,math

EPS=1e-9

def check_semantics(p):
    try:
        worlds=p['worlds'];losses=p['losses'];pred=p['predictions'];raw=p['raw_view_signatures']
        costs=p['view_costs'];views=p['allowed_views'];tol=p['regret_tolerance']
        ceiling=p['max_acceptable_absolute_loss_units']
        actions=sorted(losses)
        if len(worlds)<1 or len(worlds)>20 or len(set(worlds))!=len(worlds) or not actions:return False
        if worlds!=sorted(worlds):return False
        if not (0<=tol<math.inf and 0<=ceiling<math.inf):return False
        if any(set(losses[a])!=set(worlds) for a in actions):return False
        if any(not math.isfinite(float(losses[a][w])) or float(losses[a][w])<0 for a in actions for w in worlds):return False
        mins={w:min(float(losses[a][w]) for a in actions) for w in worlds}
        opt={w:sorted([a for a in actions if float(losses[a][w])-mins[w]<=EPS]) for w in worlds}
        if p['optima']!=opt:return False
        common=sorted(set.intersection(*(set(opt[w]) for w in worlds)))
        if p['common_optima']!=common:return False
        core=None
        if not common:
            for size in range(2,len(worlds)+1):
                for subset in itertools.combinations(worlds,size):
                    if not set.intersection(*(set(opt[w]) for w in subset)):
                        core=list(subset);break
                if core is not None:break
        if p['conflict_core']!=core:return False
        def minimax(subset):
            scores={a:max(float(losses[a][w])-mins[w] for w in subset) for a in actions}
            selected=min(actions,key=lambda a:(round(scores[a],12),a))
            return selected,scores[selected]
        action,r0=minimax(worlds)
        if common:action=common[0]
        selected_abs_max=max(float(losses[action][w]) for w in worlds)
        if not math.isclose(p['selected_max_absolute_loss_units'],selected_abs_max,abs_tol=1e-9):return False
        if not isinstance(views,list) or len(views)>4 or set(pred)!=set(raw):return False
        # Independently normalize wildcard predictions to all observed tokens.
        for view in pred:
            sig=raw[view]
            if set(sig)!=set(worlds) or set(pred[view])!=set(worlds):return False
            universe={'UNOBSERVABLE'}
            token_sets={}
            for w in worlds:
                v=sig[w]
                value_set={v} if isinstance(v,str) else set(v)
                if not value_set:return False
                token_sets[w]=value_set
                universe.update(q for q in value_set if q not in {'?','UNKNOWN_PREDICTION','MISSING_MEASUREMENT'})
            for w in worlds:
                v=token_sets[w]
                expected=sorted(universe if v & {'?','UNKNOWN_PREDICTION','MISSING_MEASUREMENT'} else v)
                if pred[view][w]!=expected:return False
        view_cost_risks=[]
        for view in sorted(set(views)):
            if view not in pred or view not in costs:continue
            vc=float(costs[view]);assert math.isfinite(vc) and vc>=0
            outcomes=sorted({x for w in worlds for x in pred[view][w]})
            rest=max(minimax([w for w in worlds if o in pred[view][w]])[1] for o in outcomes)
            view_cost_risks.append((vc+rest,view))
        best=min(view_cost_risks,default=None)
        # Independently check whether EACH possible view outcome permits an
        # action (excluding abstain) below the absolute-loss ceiling. This is
        # intentionally separate from the planner's computation.
        safe_views=[]
        for objective,view in view_cost_risks:
            every_outcome_safe=True
            for token in {t for subset in pred[view].values() for t in subset}:
                still_possible=[w for w in worlds if token in pred[view][w]]
                safe_action_exists=any(max(losses[a][w] for w in still_possible)<=ceiling
                                       for a in actions if a!='ABSTAIN')
                if not safe_action_exists:
                    every_outcome_safe=False
                    break
            if every_outcome_safe:safe_views.append((objective,view))
        safe_views.sort()
        if r0<=tol+EPS and selected_abs_max<=ceiling:
            disposition,next_view,recommend,after=('ABSTAIN',None,None,None) if action=='ABSTAIN' else ('DIRECT_ACTION',None,action,None)
        elif selected_abs_max>ceiling and safe_views and safe_views[0][0]<selected_abs_max:
            disposition,next_view,recommend,after='REQUEST_NONCONTACT_VIEW',safe_views[0][1],None,safe_views[0][0]
        elif best is not None and best[0]+EPS<r0 and r0>tol+EPS:
            disposition,next_view,recommend,after='REQUEST_NONCONTACT_VIEW',best[1],None,best[0]
        else:
            disposition,next_view,recommend,after='ABSTAIN',None,None,None
        d=p['decision']
        if (d['disposition'],d['next_observation'],d['recommendation'])!=(disposition,next_view,recommend):return False
        if not math.isclose(float(d['r0']),r0,abs_tol=1e-9):return False
        if (d['after'] is None)!=(after is None):return False
        if after is not None and not math.isclose(float(d['after']),after,abs_tol=1e-9):return False
        if d['candidate_view_risks'] != [[v,c] for c,v in sorted(view_cost_risks)]:return False
        return True
    except (KeyError,ValueError,TypeError,OverflowError,AssertionError,ZeroDivisionError):
        return False
