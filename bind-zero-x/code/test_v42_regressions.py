# coding:utf-8
"""Adversarial regressions discovered in October 12 audit. Unit tests only."""
import unittest, tempfile, os, threading
from pathlib import Path
from cape_rule_core import Session, ActionError, approval_event,confirm_human_execution
from measurement_contract import PixelMetric,PlaneCalibration,px_to_mm,to_layer_observation,MeasurementError
from challenge_contract import freeze_profile,assert_profile_frozen
from evaluation_core import validate_challenge, summarize_all_attempts, ProtocolError, validate_attempt
from session_repository import DurableSessions

class CriticalV42Tests(unittest.TestCase):
    def setup_session(self,**kwargs):
        d=dict(session_id='S1',owner_sub='U',planned_action_id='PROBE_KNOT',
              planned_observation_id='O',region_rules_verified=True,safety_preflight_ok=True)
        d.update(kwargs);return Session(**d)
    def test_001_approval_denies_probe_limit(self):
        s=self.setup_session(probe_count=2,max_probes=2)
        with self.assertRaisesRegex(ActionError,'PROBE_LIMIT_PREAPPROVAL'):
            approval_event(s,'PROBE_KNOT','key',0,'O','U')
    def test_002_execution_denies_probe_limit(self):
        s=self.setup_session(state='APPROVED',version=1,probe_count=2,approved_action_id='PROBE_KNOT')
        with self.assertRaisesRegex(ActionError,'PROBE_LIMIT_PREEXECUTION'):
            confirm_human_execution(s,'PROBE_KNOT','U',1)
    def test_003_nonprobe_still_allowed_at_limit(self):
        s=self.setup_session(planned_action_id='REORDER',probe_count=2)
        a=approval_event(s,'REORDER','key',0,'O','U');self.assertEqual(a.state,'APPROVED')
    def test_004_duplicate_probe_approval_refused(self):
        s=self.setup_session(probe_count=1)
        a=approval_event(s,'PROBE_KNOT','key',0,'O','U')
        with self.assertRaisesRegex(ActionError,'INVALID_STATE'):
            approval_event(a,'PROBE_KNOT','other',1,'O','U')
    def test_005_scale_px_to_mm(self):
        r=px_to_mm(PixelMetric(4,'IMAGE_T0','TOP','O'),PlaneCalibration(.2,'TOP','CAL',True))
        self.assertAlmostEqual(r.value_mm,.8)
        self.assertEqual(to_layer_observation(r).layer_slip_mm,.8)
    def test_006_unknown_scale(self):
        with self.assertRaisesRegex(MeasurementError,'UNCALIBRATED'):
            px_to_mm(PixelMetric(4,'IMAGE_T0','TOP','O'),PlaneCalibration(.2,'TOP','CAL',False))
    def test_007_cross_plane(self):
        with self.assertRaisesRegex(MeasurementError,'PLANE_OR_REFERENCE_MISMATCH'):
            px_to_mm(PixelMetric(4,'IMAGE_T0','TOP','O'),PlaneCalibration(.2,'BOTTOM','CAL',True))
    def test_008_wrong_unit_object(self):
        with self.assertRaisesRegex(MeasurementError,'MM_METRIC_REQUIRED'):
            to_layer_observation(PixelMetric(4,'IMAGE_T0','TOP','O'))
    def test_009_uncertainty_propagation(self):
        r=px_to_mm(PixelMetric(4,'IMAGE_T0','P','O',.5),
                   PlaneCalibration(.2,'P','CAL',True,.02))
        self.assertAlmostEqual(r.sigma_mm,(.1**2+.08**2)**.5)
    def static_profile(self):
        return freeze_profile({'challenge_id':'Q','revision':'r1','stimulus_type':'STATIC',
           'frozen_at_utc':'2026-10-12T00:00:00+00:00','preflight_approved':True,
           'approved_force_limit_N':3.,'input_targets':{'input_force_N':{'target':2,'tolerance':.2},
                                                        'duration_s':{'target':6,'tolerance':.5}}})
    def arms(self,p):
        d=dict(challenge_id='Q',challenge_profile_revision='r1',challenge_profile_hash=p['profile_hash'],
               material_batch='T',fixture_revision='V',stimulus_type='STATIC',input_force_N=2.,duration_s=6.)
        return d.copy(),d.copy()
    def test_010_profile_missing_duration(self):
        p={'challenge_id':'Q','revision':'r1','stimulus_type':'STATIC',
           'frozen_at_utc':'2026-10-12T00:00:00Z','preflight_approved':True,
           'approved_force_limit_N':3.,'input_targets':{'input_force_N':{'target':2,'tolerance':.2}}}
        with self.assertRaisesRegex(ProtocolError,'REQUIRED_INPUT_TARGETS'):
            freeze_profile(p)
    def test_011_incomplete_target_waveform(self):
        p=self.static_profile();x,y=self.arms(p)
        y.pop('duration_s')
        with self.assertRaisesRegex(ProtocolError,'MISSING_ACTUAL_INPUT_duration_s'):
            validate_challenge(x,y,p)
    def test_012_both_100n_rejected(self):
        p=self.static_profile();x,y=self.arms(p);x['input_force_N']=y['input_force_N']=100
        with self.assertRaisesRegex(ProtocolError,'TARGET_DEVIATION'):
            validate_challenge(x,y,p)
    def test_013_profile_hash_tampering(self):
        p=self.static_profile();p['input_targets']['duration_s']['target']=2
        with self.assertRaisesRegex(ProtocolError,'PROFILE_TAMPERING'):assert_profile_frozen(p)
    def test_014_profile_hash_mismatch_arm(self):
        p=self.static_profile();x,y=self.arms(p);y['challenge_profile_hash']='FAKE'
        with self.assertRaisesRegex(ProtocolError,'PROFILE_HASH'):validate_challenge(x,y,p)
    def test_015_preflight_is_mandatory(self):
        p={'challenge_id':'Q','revision':'r1','stimulus_type':'NONCONTACT',
           'frozen_at_utc':'2026-10-12T00:00:00Z','preflight_approved':False,
           'input_targets':{'duration_s':{'target':1.,'tolerance':.1}}}
        with self.assertRaisesRegex(ProtocolError,'PREFLIGHT_NOT_APPROVED'):
            freeze_profile(p)
    def record(self,**kw):
        d={'configuration_id':'C1','trial_id':'T1','method':'E','job_status':'COMPLETED',
           'original_sheet_count':7,'evaluated_sheet_count':7,'total_time_s':20.}
        d.update(kw);return d
    def test_016_negative_time(self):
        with self.assertRaisesRegex(ProtocolError,'NEGATIVE_TIME'):
            summarize_all_attempts([self.record(total_time_s=-20)])
    def test_017_zero_sheets(self):
        with self.assertRaisesRegex(ProtocolError,'INVALID_ORIGINAL_SHEET_COUNT'):
            summarize_all_attempts([self.record(original_sheet_count=0,evaluated_sheet_count=0)])
    def test_018_more_than_original(self):
        with self.assertRaisesRegex(ProtocolError,'EXCESS_EVALUATED_SHEETS'):
            summarize_all_attempts([self.record(evaluated_sheet_count=8)])
    def test_019_completed_missing_time(self):
        with self.assertRaisesRegex(ProtocolError,'MISSING_COMPLETED_TIME'):
            summarize_all_attempts([self.record(total_time_s=None)])
    def test_020_abort_count_and_nonnegative(self):
        r=summarize_all_attempts([self.record(job_status='ABORTED',total_time_s=None)])
        self.assertEqual(r['E']['aborted'],1)
        self.assertEqual(r['E']['completed'],0)
    def test_021_sqlite_replay_after_advance(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'sessions.db';repo=DurableSessions(path)
            s=self.setup_session(planned_action_id='REORDER');repo.create(s)
            first=repo.approve('S1','REORDER','key',0,'O','U')
            later=repo.confirm('S1','REORDER',1,'U')
            repo2=DurableSessions(path)
            replay=repo2.approve('S1','REORDER','key',0,'O','U')
            self.assertEqual(replay,first)
            self.assertEqual(repo2.read('S1','U').state,'OUTCOME_PENDING')
    def test_022_sqlite_same_key_conflicting_payload(self):
        with tempfile.TemporaryDirectory() as temp:
            repo=DurableSessions(Path(temp)/'s.db');repo.create(self.setup_session(planned_action_id='REORDER'))
            repo.approve('S1','REORDER','key',0,'O','U')
            with self.assertRaisesRegex(ActionError,'IDEMPOTENCY_KEY_REUSE_CONFLICT'):
                repo.approve('S1','RE_TIE','key',0,'O','U')
    def test_023_sqlite_no_other_owner(self):
        with tempfile.TemporaryDirectory() as temp:
            repo=DurableSessions(Path(temp)/'s.db');repo.create(self.setup_session(planned_action_id='REORDER'))
            with self.assertRaisesRegex(ActionError,'NOT_AUTHORIZED'):
                repo.approve('S1','REORDER','key',0,'O','OTHER')
    def test_024_sqlite_conflicting_concurrent_approvals(self):
        with tempfile.TemporaryDirectory() as temp:
            repo=DurableSessions(Path(temp)/'s.db');repo.create(self.setup_session(planned_action_id='REORDER'))
            results=[]
            def action(k):
                try:repo.approve('S1','REORDER',k,0,'O','U');results.append('OK')
                except ActionError:results.append('REJECT')
            threads=[threading.Thread(target=action,args=(x,)) for x in ('K1','K2')]
            for t in threads:t.start()
            for t in threads:t.join()
            self.assertEqual(sorted(results),['OK','REJECT'])
    def test_025_negative_force_limit(self):
        p={'challenge_id':'Q','revision':'r1','stimulus_type':'STATIC',
           'frozen_at_utc':'2026-10-12T00:00:00Z','preflight_approved':True,
           'approved_force_limit_N':-1,'input_targets':{'input_force_N':{'target':2,'tolerance':.2},
                                                       'duration_s':{'target':6,'tolerance':.5}}}
        with self.assertRaisesRegex(ProtocolError,'FORCE_LIMIT_INCONSISTENT'):freeze_profile(p)

if __name__=='__main__':unittest.main(verbosity=2)
