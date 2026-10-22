# coding: utf-8
"""Fail-closed contracts for observed image movement.
A scalar conversion is valid ONLY on a calibrated, known plane with a frozen
camera geometry; multi-depth/image-only inputs may not be converted to mm.
No safety/load certification is conveyed by a successful conversion.
"""
from dataclasses import dataclass
import math
from cape_rule_core import Observation

class MeasurementError(ValueError): pass

def _finite(v):
    return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)

def _id_ok(v):
    return isinstance(v,str) and bool(v.strip())

@dataclass(frozen=True)
class PixelMetric:
    value_px:float
    reference_frame:str
    plane_id:str
    observation_id:str
    sigma_px:float=0.0
    def __post_init__(self):
        if not _finite(self.value_px) or self.value_px<0:raise MeasurementError('INVALID_PIXEL_VALUE')
        if not _finite(self.sigma_px) or self.sigma_px<0:raise MeasurementError('INVALID_PIXEL_UNCERTAINTY')
        if not all(_id_ok(v) for v in (self.reference_frame,self.plane_id,self.observation_id)):
            raise MeasurementError('INVALID_PIXEL_PROVENANCE')

@dataclass(frozen=True)
class PlaneCalibration:
    scale_mm_per_px:float
    plane_id:str
    calibration_id:str
    verified:bool
    sigma_scale_mm_per_px:float=0.0
    frozen:bool=True
    reference_frame:str='IMAGE_T0'
    supported_depth_range_mm:tuple|None=None
    def __post_init__(self):
        if not _finite(self.scale_mm_per_px) or self.scale_mm_per_px<=0:raise MeasurementError('INVALID_CALIBRATION_SCALE')
        if not _finite(self.sigma_scale_mm_per_px) or self.sigma_scale_mm_per_px<0:raise MeasurementError('INVALID_CALIBRATION_UNCERTAINTY')
        if not all(_id_ok(v) for v in (self.plane_id,self.calibration_id,self.reference_frame)):
            raise MeasurementError('INVALID_CALIBRATION_IDENTITY')
        # bool('false') == True in Python. Exact bool types are required; this
        # research contract must never promote strings or integers to attestations.
        if type(self.verified) is not bool or type(self.frozen) is not bool:
            raise MeasurementError('INVALID_CALIBRATION_BOOLEAN_TYPE')
        if self.supported_depth_range_mm is not None:
            d=self.supported_depth_range_mm
            if (not isinstance(d,(tuple,list)) or len(d)!=2 or not all(_finite(v) for v in d)
                or d[0]<0 or d[1]<d[0]):
                raise MeasurementError('INVALID_CALIBRATION_DEPTH_RANGE')

@dataclass(frozen=True)
class MillimeterMetric:
    value_mm:float
    sigma_mm:float
    calibration_id:str
    plane_id:str
    observation_id:str
    provenance:str='CALIBRATED_2D_ESTIMATE_NOT_GT'
    def __post_init__(self):
        if not _finite(self.value_mm) or self.value_mm<0:raise MeasurementError('INVALID_MILLIMETER_VALUE')
        if not _finite(self.sigma_mm) or self.sigma_mm<0:raise MeasurementError('INVALID_MILLIMETER_UNCERTAINTY')
        if not all(_id_ok(v) for v in (self.calibration_id,self.plane_id,self.observation_id)):
            raise MeasurementError('INVALID_MILLIMETER_PROVENANCE')


def px_to_mm(metric:PixelMetric,calib:PlaneCalibration)->MillimeterMetric:
    if not isinstance(metric,PixelMetric) or not isinstance(calib,PlaneCalibration):
        raise MeasurementError('EXPLICIT_PIXEL_METRIC_AND_CALIBRATION_REQUIRED')
    for val in (metric.value_px,metric.sigma_px,calib.scale_mm_per_px,calib.sigma_scale_mm_per_px):
        if isinstance(val,bool) or not isinstance(val,(int,float)) or not math.isfinite(val):
            raise MeasurementError('NONFINITE_OR_NONNUMERIC')
    if metric.value_px<0 or metric.sigma_px<0 or calib.sigma_scale_mm_per_px<0 or calib.scale_mm_per_px<=0:
        raise MeasurementError('INVALID_MEASUREMENT_OR_SCALE')
    if calib.verified is not True or calib.frozen is not True or not calib.calibration_id:
        raise MeasurementError('UNCALIBRATED_OR_UNFROZEN')
    if not metric.observation_id or metric.plane_id!=calib.plane_id or metric.reference_frame!=calib.reference_frame:
        raise MeasurementError('PLANE_OR_REFERENCE_MISMATCH')
    v=metric.value_px*calib.scale_mm_per_px
    sigma=math.hypot(metric.sigma_px*calib.scale_mm_per_px,
                     metric.value_px*calib.sigma_scale_mm_per_px)
    return MillimeterMetric(v,sigma,calib.calibration_id,calib.plane_id,metric.observation_id)


def to_layer_observation(layer_mm:MillimeterMetric,rope_mm:MillimeterMetric|None=None,
                         knot_mm:MillimeterMetric|None=None,quality:str='VALID',
                         threshold_mm:float|None=None,uncertainty_multiplier:float=2.0,
                         layer_max_mm:MillimeterMetric|None=None,relative_angle_deg:float|None=None)->Observation:
    if not isinstance(layer_mm,MillimeterMetric):
        raise MeasurementError('MM_METRIC_REQUIRED')
    for m in (rope_mm,knot_mm,layer_max_mm):
        if m is not None and (not isinstance(m,MillimeterMetric) or
             m.observation_id!=layer_mm.observation_id or
             m.calibration_id!=layer_mm.calibration_id or m.plane_id!=layer_mm.plane_id):
            raise MeasurementError('INCONSISTENT_OBSERVATION_OR_UNIT')
    if relative_angle_deg is not None and not _finite(relative_angle_deg):
        raise MeasurementError('INVALID_RELATIVE_ANGLE')
    if threshold_mm is not None:
        if not math.isfinite(threshold_mm) or threshold_mm<=0 or not math.isfinite(uncertainty_multiplier) or uncertainty_multiplier<0:
            raise MeasurementError('INVALID_THRESHOLD_OR_UNCERTAINTY')
        for candidate in (layer_mm,layer_max_mm):
            if candidate is not None and candidate.sigma_mm>0 and abs(candidate.value_mm-threshold_mm)<=uncertainty_multiplier*candidate.sigma_mm:
                quality='UNCERTAIN_METRIC_BOUNDARY'
    return Observation(layer_mm.observation_id,quality,layer_mm.value_mm,
                       None if rope_mm is None else rope_mm.value_mm,
                       None if knot_mm is None else knot_mm.value_mm,
                       layer_max_drift_mm=None if layer_max_mm is None else layer_max_mm.value_mm,
                       relative_angle_deg=relative_angle_deg)
