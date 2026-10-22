# coding: utf-8
"""Research-only CLI: two frames, expert-supplied layer masks, explicit calibration.
One calibrated plane is required; multi-plane bundles require a separate geometry model.
This prototype does NOT segment layers autonomously, certify carrying safety, or deploy AWS.
"""
import argparse,json,hashlib,sys
from pathlib import Path
import cv2
from vision_motion_core import metric_from_pair
from measurement_contract import PixelMetric,PlaneCalibration,px_to_mm,to_layer_observation
from cape_rule_core import Observation,choose_rule_action
from decision_bridge import illustrative_witness_for_layer_evidence
from decision_gateway import gate_rule_with_witness
from witness_planner import recommend_witness
from failure_interaction_graph import build_fig

class PipelineError(ValueError):pass

def verify_roi_provenance(frame0,masks,manifest):
    """Operator-attested ROI identity and hash bindings; NOT algorithmic proof of segmentation."""
    if not isinstance(manifest,dict) or manifest.get('operator_verified') is not True:
        raise PipelineError('ROI_PROVENANCE_NOT_VERIFIED')
    digest=hashlib.sha256(frame0.tobytes()).hexdigest()
    if manifest.get('frame0_sha256')!=digest:raise PipelineError('ROI_FRAME_BINDING_MISMATCH')
    layers=manifest.get('layers')
    if not isinstance(layers,dict) or set(layers)!={'upper','lower'}:
        raise PipelineError('ROI_LAYER_MANIFEST_REQUIRED')
    ids=[]
    for label in ('upper','lower'):
        item=layers[label]
        if not isinstance(item,dict) or item.get('layer_label')!=label:
            raise PipelineError('ROI_LAYER_LABEL_MISMATCH')
        if item.get('mask_sha256')!=hashlib.sha256(masks[label].tobytes()).hexdigest():
            raise PipelineError('ROI_MASK_BINDING_MISMATCH')
        if not item.get('source_id'):raise PipelineError('ROI_SOURCE_ID_MISSING')
        ids.append(item['source_id'])
    if len(set(ids))!=2:raise PipelineError('ROI_SOURCE_ID_REUSED')
    return True

def analyze(frame0,frame1,masks,calibration,observation_id,
            *,require_opencv5=True,threshold_mm=5.,require_roi_provenance=False,roi_manifest=None):
    if require_opencv5 and cv2.__version__.split('.')[0]!='5':
        raise PipelineError('OPENCV5_RUNTIME_REQUIRED')
    if frame0 is None or frame1 is None:
        raise PipelineError('FRAME_REQUIRED')
    if frame0.shape!=frame1.shape or len(frame0.shape)!=2:
        raise PipelineError('FRAME_FORMAT_MISMATCH')
    if set(masks)!={'upper','lower'} or any(m.shape!=frame0.shape for m in masks.values()):
        raise PipelineError('LAYER_MASKS_REQUIRED')
    if require_roi_provenance and roi_manifest is None:raise PipelineError('ROI_PROVENANCE_NOT_VERIFIED')
    if roi_manifest is not None:verify_roi_provenance(frame0,masks,roi_manifest)
    metrics,err=metric_from_pair(frame0,frame1,masks)
    if err is not None:
        return {'measurement':None,'decision':{'action':'RECAPTURE','reason':str(err)},
                'opencv_version':cv2.__version__,'source_tier':'REAL_OR_SYNTHETIC_UNDETERMINED_INPUT',
                'limitations':['EXPERT_MASKS_REQUIRED','NO_SAFETY_CERTIFICATION']}
    cm=PlaneCalibration(**calibration)
    metric=px_to_mm(PixelMetric(metrics['center_drift_px'],'IMAGE_T0',cm.plane_id,observation_id),cm)
    maximum=px_to_mm(PixelMetric(metrics['max_anchor_drift_px'],'IMAGE_T0',cm.plane_id,observation_id),cm)
    # No rope/knot image analysis is performed. Never set them to synthetic zeros.
    observation=to_layer_observation(metric,threshold_mm=threshold_mm,
                                      layer_max_mm=maximum,relative_angle_deg=metrics['relative_angle_deg'])
    d=choose_rule_action(observation,threshold_mm=threshold_mm)
    research_witness=illustrative_witness_for_layer_evidence(maximum.value_mm,metrics['relative_angle_deg'],threshold_mm=threshold_mm)
    # Re-evaluate the exact model supplied to the bridge; do NOT infer that its
    # hypothetical certificate represents empirically calibrated physics.
    hyp=research_witness['hypothetical_model']
    formal_witness=recommend_witness(hyp['worlds'],hyp['losses'],hyp['view_signatures'],
                                    hyp['costs'],observation_id=observation_id,
                                    calibration_id=metric.calibration_id,
                                    model_version=('ILLUSTRATIVE_V4.3_MODEL|ROI='+
                                         hashlib.sha256(json.dumps(roi_manifest,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                                         if roi_manifest is not None else 'ILLUSTRATIVE_V4.3_MODEL|NO_ROI'),
                                    video_sha256=hashlib.sha256(frame0.tobytes()+frame1.tobytes()).hexdigest())
    gated=gate_rule_with_witness(d,formal_witness,roi_identity_attested=roi_manifest is not None)
    research_witness['certificate_hash']=formal_witness.certificate_hash
    research_witness['certificate_payload']=formal_witness.certificate_payload
    research_witness['conflict_core']=formal_witness.conflict_core
    research_witness['candidate_view_risks']=formal_witness.candidate_view_risks
    research_witness['certificate_scope']='INTERNAL_CONSISTENCY_ONLY_NO_PHYSICAL_TRUTH_PROOF'
    decision={'action':gated.action,'reason':gated.reason,
              'human_approval_required':gated.human_approval_required,
              'physical_action_authorized':gated.physical_action_authorized,
              'research_candidate_only':gated.research_candidate_only}
    fig=build_fig(metric,observation_id)
    return {'research_witness':research_witness,'fig_fingerprint':fig.fingerprint(),
            'fig_missing_channels':fig.missing_channels(),
            'measurement':{'value_mm':metric.value_mm,'sigma_mm':None,
                           'uncertainty_status':'NOT_CALIBRATED_UNCERTAINTY_NOT_ZERO',
                           'tracking_p90_error_px_by_layer':metrics['tracking_p90_error_px_by_layer'],
                           'calibration_id':metric.calibration_id,
                           'relative_angle_deg':metrics['relative_angle_deg'],
                           'max_footprint_drift_mm':maximum.value_mm,
                           'max_footprint_sigma_mm':None},
            'decision':decision,
            'opencv_version':cv2.__version__,'source_tier':'RESEARCH_FRAME_PAIR_WITH_EXPERT_ROI',
            'limitations':['ROPE_AND_KNOT_NOT_MEASURED','NO_SAFETY_CERTIFICATION',
                           'NO_AUTOMATIC_LAYER_DETECTION','PLANAR_CALIBRATION_ASSUMED',
                           'UNCERTAINTY_NOT_EMPIRICALLY_CALIBRATED',
                           'ROI_OPERATOR_ATTESTED' if roi_manifest is not None else 'ROI_ID_UNVERIFIED']}


def load_image(path):
    b=Path(path).read_bytes()
    if len(b)>15_000_000:raise PipelineError('IMAGE_TOO_LARGE')
    import numpy as np
    im=cv2.imdecode(np.frombuffer(b,dtype=np.uint8),cv2.IMREAD_GRAYSCALE)
    if im is None or im.shape[0]*im.shape[1]>8_000_000:raise PipelineError('IMAGE_DECODE_FAILED_OR_TOO_LARGE')
    return im

def main():
    parser=argparse.ArgumentParser()
    for name in ('frame0','frame1','upper-mask','lower-mask','calibration'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--observation-id',default='RESEARCH-OBS')
    parser.add_argument('--dev-allow-opencv4',action='store_true')
    parser.add_argument('--roi-manifest',default=None)
    args=parser.parse_args()
    im0=load_image(args.frame0);im1=load_image(args.frame1)
    masks={k:load_image(p) for k,p in (('upper',args.upper_mask),('lower',args.lower_mask))}
    calib=json.loads(Path(args.calibration).read_text(encoding='utf-8'))
    manifest=json.loads(Path(args.roi_manifest).read_text(encoding='utf-8')) if args.roi_manifest else None
    out=analyze(im0,im1,masks,calib,args.observation_id,
                require_opencv5=not args.dev_allow_opencv4,
                require_roi_provenance=not args.dev_allow_opencv4,
                roi_manifest=manifest)
    print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
