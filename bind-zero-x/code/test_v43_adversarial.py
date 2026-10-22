# coding: utf-8
"""Regression test battery for v4.2 independently reproduced errors.
SYNTHETIC/LOCAL ONLY. PASS never implies physical/AWS/OpenCV5 results.
"""
import hashlib,math,unittest
import numpy as np
from test_synthetic_opencv import image_pair
from vision_motion_core import metric_from_pair,validate_distinct_layer_rois
from research_pipeline import analyze,verify_roi_provenance,PipelineError
from measurement_contract import (PixelMetric,PlaneCalibration,MillimeterMetric,
    MeasurementError,px_to_mm,to_layer_observation)
from cape_rule_core import Observation,choose_rule_action,ActionError
from challenge_contract import freeze_profile,assert_profile_frozen
from evaluation_core import ProtocolError

class GeometryAdversarialTests(unittest.TestCase):
    def test_ROI_001_duplicate_roi_false_zero_denied(self):
        a,b,m=image_pair(slip=(9,0));m['lower']=m['upper'].copy()
        result,error=metric_from_pair(a,b,m)
        self.assertIsNone(result);self.assertEqual(error,'LAYER_ROI_NOT_INDEPENDENT')
    def test_ROI_002_overlap_denied(self):
        a,b,m=image_pair()
        m['lower']=m['lower'].copy();m['lower'][m['upper']>0]=255
        result,error=metric_from_pair(a,b,m)
        self.assertIsNone(result);self.assertEqual(error,'LAYER_ROI_OVERLAP_AMBIGUOUS')
    def test_ROI_003_empty_mask_still_denied(self):
        a,b,m=image_pair();m['upper'][:]=0
        result,error=metric_from_pair(a,b,m)
        self.assertIsNone(result);self.assertEqual(error,'NO_FEATURES')
    def test_ROI_004_bad_dtype(self):
        a,b,m=image_pair();m['lower']=m['lower'].astype(bool)
        self.assertEqual(validate_distinct_layer_rois(a,m),'INVALID_LAYER_ROI_DTYPE')
    def test_ROI_005_bad_shape(self):
        a,b,m=image_pair();m['lower']=m['lower'][:10,:10]
        self.assertEqual(validate_distinct_layer_rois(a,m),'INVALID_LAYER_ROI_SHAPE')
    def test_ROI_006_known_slip_still_measured(self):
        a,b,m=image_pair(slip=(9,0));r,e=metric_from_pair(a,b,m)
        self.assertIsNone(e);self.assertLess(abs(r['center_drift_px']-9),1.0)
    def test_ROI_007_one_layer_rotation_has_large_footprint_motion(self):
        a,b,m=image_pair(local_rotation=8);r,e=metric_from_pair(a,b,m)
        self.assertIsNone(e);self.assertLess(r['center_drift_px'],1.0)
        self.assertGreater(r['max_anchor_drift_px'],7.0)
        self.assertGreater(abs(r['relative_angle_deg']),7.)
    def test_ROI_008_common_rotation_zero_relative(self):
        a,b,m=image_pair(theta=12,tx=10,ty=-5);r,e=metric_from_pair(a,b,m)
        self.assertIsNone(e);self.assertLess(r['max_anchor_drift_px'],1.2)
    def test_ROI_009_rotation_changes_pipeline_decision(self):
        a,b,m=image_pair(local_rotation=8)
        r=analyze(a,b,m,dict(scale_mm_per_px=1.,plane_id='P',calibration_id='SYNTHETIC',verified=True),
                   'O',require_opencv5=False,threshold_mm=5.,roi_manifest=self.manifest(a,m))
        self.assertLess(r['measurement']['value_mm'],1.)
        self.assertGreater(r['measurement']['max_footprint_drift_mm'],7.)
        self.assertEqual(r['decision']['action'],'REQUEST_NONCONTACT_VIEW')
        self.assertEqual(r['decision']['research_candidate_only'],'REORDER')
    def test_ROI_010_px_to_mm_preserved_on_rotated_footprint(self):
        a,b,m=image_pair(local_rotation=8)
        r=analyze(a,b,m,dict(scale_mm_per_px=.2,plane_id='P',calibration_id='SYNTHETIC',verified=True),
                   'O',require_opencv5=False,threshold_mm=5.,roi_manifest=self.manifest(a,m))
        self.assertLess(r['measurement']['max_footprint_drift_mm'],4.5)
        # Angular threshold is a distinct research heuristic, not an mm conversion.
        self.assertEqual(r['decision']['action'],'REQUEST_NONCONTACT_VIEW')
        self.assertEqual(r['decision']['research_candidate_only'],'REORDER')
    def test_ROI_011_duplicate_roi_pipeline_rejects_not_measured(self):
        a,b,m=image_pair(slip=(9,0));m['lower']=m['upper'].copy()
        r=analyze(a,b,m,dict(scale_mm_per_px=.2,plane_id='P',calibration_id='SYN',verified=True),
                  'O',require_opencv5=False)
        self.assertIsNone(r['measurement'])
        self.assertEqual(r['decision']['reason'],'LAYER_ROI_NOT_INDEPENDENT')
    def manifest(self,a,m):
        return dict(operator_verified=True,frame0_sha256=hashlib.sha256(a.tobytes()).hexdigest(),
            layers={k:dict(mask_sha256=hashlib.sha256(v.tobytes()).hexdigest(),
                layer_label=k,source_id=f'ROI-{k}') for k,v in m.items()})
    def test_ROI_012_provenance_required_when_strict(self):
        a,b,m=image_pair()
        with self.assertRaisesRegex(PipelineError,'ROI_PROVENANCE_NOT_VERIFIED'):
            analyze(a,b,m,dict(scale_mm_per_px=1.,plane_id='P',calibration_id='CAL',verified=True),
                    'O',require_opencv5=False,require_roi_provenance=True)
    def test_ROI_013_frame_bound_manifest_passes(self):
        a,b,m=image_pair();self.assertTrue(verify_roi_provenance(a,m,self.manifest(a,m)))
    def test_ROI_014_roi_swapped_invalidates_hash(self):
        a,b,m=image_pair();manifest=self.manifest(a,m)
        altered=m.copy();altered['upper']=m['lower'];altered['lower']=m['upper']
        with self.assertRaisesRegex(PipelineError,'ROI_MASK_BINDING_MISMATCH'):
            verify_roi_provenance(a,altered,manifest)
    def test_ROI_015_manifest_reuse_source_id_denied(self):
        a,b,m=image_pair();manifest=self.manifest(a,m)
        manifest['layers']['lower']['source_id']='ROI-upper'
        with self.assertRaisesRegex(PipelineError,'ROI_SOURCE_ID_REUSED'):
            verify_roi_provenance(a,m,manifest)
    def test_ROI_016_manifest_other_frame_denied(self):
        a,b,m=image_pair();manifest=self.manifest(a,m)
        manifest['frame0_sha256']='0'*64
        with self.assertRaisesRegex(PipelineError,'ROI_FRAME_BINDING_MISMATCH'):
            verify_roi_provenance(a,m,manifest)

class DecisionAdversarialTests(unittest.TestCase):
    def test_D_001_rope_unknown_layer_known_never_probe_layer(self):
        d=choose_rule_action(Observation('O','VALID',0,None,0))
        self.assertEqual(d.action,'RECAPTURE')
        self.assertEqual(d.reason,'ROPE_PATH_NOT_OBSERVED')
    def test_D_002_no_recaptures_left_rope_unknown_abstain(self):
        d=choose_rule_action(Observation('O','VALID',0,None,0),recapture_count=1)
        self.assertEqual(d.action,'ABSTAIN')
    def test_D_003_only_knot_unknown_probes_knot(self):
        self.assertEqual(choose_rule_action(Observation('O','VALID',0,0,None)).action,'PROBE_KNOT')
    def test_D_004_only_layer_unknown_probes_layer(self):
        self.assertEqual(choose_rule_action(Observation('O','VALID',None,0,0)).action,'PROBE_LAYER')
    def test_D_005_probe_limit_forbids_knot(self):
        d=choose_rule_action(Observation('O','VALID',0,0,None),probe_count=2,max_probes=2)
        self.assertNotIn(d.action,('PROBE_LAYER','PROBE_KNOT'))
    def test_D_006_footprint_trigger_even_center_zero(self):
        d=choose_rule_action(Observation('O','VALID',0,0,0,layer_max_drift_mm=8))
        self.assertEqual(d.action,'REORDER')
    def test_D_007_rotation_trigger_even_center_zero(self):
        d=choose_rule_action(Observation('O','VALID',0,0,0,relative_angle_deg=-8))
        self.assertEqual(d.action,'REORDER')
    def test_D_008_rotation_below_threshold_not_triggered(self):
        d=choose_rule_action(Observation('O','VALID',0,0,0,relative_angle_deg=1))
        self.assertEqual(d.action,'KEEP')
    def test_D_009_nonfinite_angle_rejected(self):
        with self.assertRaisesRegex(ActionError,'INVALID_ROTATION'):
            choose_rule_action(Observation('O','VALID',0,0,0,relative_angle_deg=float('nan')))
    def test_D_010_invalid_angle_threshold_rejected(self):
        with self.assertRaisesRegex(ActionError,'INVALID_ROTATION_THRESHOLD'):
            choose_rule_action(Observation('O','VALID',0,0,0),rotation_threshold_deg=-2)
    def test_D_011_rope_fault_not_keep(self):
        self.assertNotEqual(choose_rule_action(Observation('O','VALID',0,8,0)).action,'KEEP')
    def test_D_012_layer_plus_rope_abstention(self):
        self.assertEqual(choose_rule_action(Observation('O','VALID',8,8,0)).action,'ABSTAIN')

class MetricAdversarialTests(unittest.TestCase):
    def mk(self,**kwargs):
        return MillimeterMetric(8.,.1,'CAL','P','O',**kwargs)
    def test_M_001_nan_sigma_rejected_at_creation(self):
        with self.assertRaisesRegex(MeasurementError,'INVALID_MILLIMETER_UNCERTAINTY'):
            MillimeterMetric(8,float('nan'),'CAL','P','O')
    def test_M_002_inf_sigma_rejected(self):
        with self.assertRaisesRegex(MeasurementError,'INVALID_MILLIMETER_UNCERTAINTY'):
            MillimeterMetric(8,float('inf'),'CAL','P','O')
    def test_M_003_negative_sigma_rejected(self):
        with self.assertRaisesRegex(MeasurementError,'INVALID_MILLIMETER_UNCERTAINTY'):
            MillimeterMetric(8,-.1,'CAL','P','O')
    def test_M_004_nan_pixel_rejected(self):
        with self.assertRaisesRegex(MeasurementError,'INVALID_PIXEL_VALUE'):
            PixelMetric(float('nan'),'IMAGE_T0','P','O')
    def test_M_005_inf_scale_rejected(self):
        with self.assertRaisesRegex(MeasurementError,'INVALID_CALIBRATION_SCALE'):
            PlaneCalibration(float('inf'),'P','CAL',True)
    def test_M_006_wrong_max_calibration_rejected(self):
        m=MillimeterMetric(0.,0.,'CAL','P','O');other=MillimeterMetric(8.,0.,'OTHER','P','O')
        with self.assertRaisesRegex(MeasurementError,'INCONSISTENT_OBSERVATION_OR_UNIT'):
            to_layer_observation(m,layer_max_mm=other)
    def test_M_007_max_metric_boundary_uncertain(self):
        m=MillimeterMetric(.1,.01,'CAL','P','O');mx=MillimeterMetric(5.,.5,'CAL','P','O')
        o=to_layer_observation(m,threshold_mm=5.,layer_max_mm=mx)
        self.assertEqual(o.quality,'UNCERTAIN_METRIC_BOUNDARY')
    def test_M_008_nonfinite_angle_rejected(self):
        m=MillimeterMetric(.1,0.,'CAL','P','O')
        with self.assertRaisesRegex(MeasurementError,'INVALID_RELATIVE_ANGLE'):
            to_layer_observation(m,relative_angle_deg=float('inf'))
    def test_M_009_valid_mm_max_and_angle_transferred(self):
        m=MillimeterMetric(.1,.01,'CAL','P','O');mx=MillimeterMetric(8.,.1,'CAL','P','O')
        o=to_layer_observation(m,layer_max_mm=mx,relative_angle_deg=8.)
        self.assertEqual(o.layer_max_drift_mm,8.)
        self.assertEqual(o.relative_angle_deg,8.)
    def test_M_010_pixel_negative_sigma_rejected(self):
        with self.assertRaisesRegex(MeasurementError,'INVALID_PIXEL_UNCERTAINTY'):
            PixelMetric(8.,'IMAGE_T0','P','O',sigma_px=-1.)

class ProtocolAdversarialTests(unittest.TestCase):
    def base(self):
        return dict(challenge_id='Q',revision='r1',stimulus_type='STATIC',
            frozen_at_utc='2026-10-12T00:00:00Z',preflight_approved=True,
            approved_force_limit_N=4.,
            input_targets={'input_force_N':{'target':2.,'tolerance':.2},
                           'duration_s':{'target':6.,'tolerance':.5}})
    def test_P_001_valid_profile(self):
        p=freeze_profile(self.base());self.assertEqual(assert_profile_frozen(p),p)
    def test_P_002_overwide_tolerance_rejected(self):
        p=self.base();p['input_targets']['input_force_N']['tolerance']=10.
        with self.assertRaisesRegex(ProtocolError,'UNREASONABLE_TARGET_TOLERANCE'):
            freeze_profile(p)
    def test_P_003_zero_rate_quasistatic_rejected(self):
        p=self.base();p['stimulus_type']='QUASISTATIC'
        p['input_targets']['force_rate_N_per_s']={'target':0.,'tolerance':0.}
        with self.assertRaisesRegex(ProtocolError,'BAD_INPUT_RANGE'):
            freeze_profile(p)
    def test_P_004_naive_freeze_timestamp_rejected(self):
        p=self.base();p['frozen_at_utc']='2026-10-12T12:00:00'
        with self.assertRaisesRegex(ProtocolError,'INVALID_FROZEN_TIMESTAMP'):
            freeze_profile(p)
    def test_P_005_non_utc_freeze_timestamp_rejected(self):
        p=self.base();p['frozen_at_utc']='2026-10-12T12:00:00+09:00'
        with self.assertRaisesRegex(ProtocolError,'INVALID_FROZEN_TIMESTAMP'):
            freeze_profile(p)
    def test_P_006_profile_tampering_detected_before_range_check(self):
        p=freeze_profile(self.base());p['input_targets']['duration_s']['target']=1.
        with self.assertRaisesRegex(ProtocolError,'PROFILE_TAMPERING'):
            assert_profile_frozen(p)
    def test_P_007_zero_amplitude_low_energy_rejected(self):
        p=self.base();p['stimulus_type']='LOW_ENERGY';p.pop('approved_force_limit_N')
        p['input_targets']={'input_amplitude_mm':{'target':0.,'tolerance':0.},
                            'input_frequency_Hz':{'target':1.,'tolerance':.1},
                            'duration_s':{'target':6.,'tolerance':.5}}
        with self.assertRaisesRegex(ProtocolError,'BAD_INPUT_RANGE'):
            freeze_profile(p)

if __name__=='__main__':unittest.main(verbosity=2)
