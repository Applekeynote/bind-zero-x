# -*- coding: utf-8 -*-
"""Create a DRAFT independent-ground-truth envelope from recorded real trials.

This does not approve its own results and does not certify mechanical safety.
The project operator must separately audit video/GT evidence, freeze the
manifest, change approved to true with documented authorization, and pin the
final SHA256 in the deployment environment. Do not fabricate trial records.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,math
from pathlib import Path
from math import ceil

def canonical(data):return json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def digest(data):return hashlib.sha256(canonical(data).encode()).hexdigest()
def _num(x):
    v=float(x)
    if not math.isfinite(v) or v<0:raise ValueError('NEGATIVE_OR_NONFINITE_READING')
    return v

def build(calibration, records, csv_bytes, shape, threshold, p95_limit):
    if len(records)<30:raise ValueError('GT_SAMPLE_SIZE_AT_LEAST_30_INDEPENDENT_TRIALS')
    ids=set();bundle_ids=set();video_hashes=set();errors=[]
    modes=set()
    for item in records:
        if not item['trial_id'] or item['trial_id'] in ids:raise ValueError('DUPLICATE_OR_BLANK_TRIAL_ID')
        if not item['bundle_id'] or not item['gt_rater'] or not item['fault_mode']:
            raise ValueError('MISSING_INDEPENDENT_GT_PROVENANCE')
        video=item['video_sha256']
        if not (len(video)==64 and all(c in '0123456789abcdef' for c in video)):
            raise ValueError('INVALID_VIDEO_HASH')
        ids.add(item['trial_id']);bundle_ids.add(item['bundle_id']);video_hashes.add(video)
        modes.add(item['fault_mode'])
        errors.append(abs(_num(item['gt_mm'])-_num(item['cv_mm'])))
    from collections import Counter
    mode_counts=Counter(item['fault_mode'] for item in records)
    # The statistical evaluation unit is a PHYSICALLY DISTINCT bundle, not a
    # frame or repeated video of the same bundle. This is a necessary (not
    # sufficient) independence check. No significance/power is inferred.
    if len(bundle_ids)<30 or len(video_hashes)<30 or len(modes)<2 or min(mode_counts.values())<5:
        raise ValueError('INSUFFICIENT_PHYSICAL_DIVERSITY_INDEPENDENT_BUNDLES_VIDEOS_OR_MODES')
    if threshold<=0 or p95_limit<=0 or not all(math.isfinite(v) for v in [threshold,p95_limit]):
        raise ValueError('INVALID_PREREGISTERED_THRESHOLD')
    p95=sorted(errors)[ceil(.95*len(errors))-1] # nearest-rank observed sample P95
    return {'schema':'BZX-REAL-GT-ENVELOPE-V2','channel':'LAYER_VISIBLE_MAX_MM',
        'calibration_sha256':digest(calibration),'frame_shape':list(shape),
        'approved':False,'pre_registered':False,'independent_real_gt':False,
        'holdout_n':len(ids),'holdout_manifest_sha256':hashlib.sha256(csv_bytes).hexdigest(),
        'threshold_mm':threshold,'p95_absolute_error_mm':p95,'max_allowed_p95_mm':p95_limit,
        'unique_bundles':len(bundle_ids),'unique_videos':len(video_hashes),
        'independent_bundle_n':len(bundle_ids),'independent_video_n':len(video_hashes),
        'fault_mode_counts':dict(sorted(mode_counts.items())),
        'independence_unit':'UNIQUE_PHYSICAL_BUNDLE_ID_NOT_ROWS',
        'external_audit_receipt_sha256':None,
        'fault_modes':sorted(modes),'holdout_mae_mm':sum(errors)/len(errors),
        'status':'DRAFT_UNAPPROVED_NO_PRODUCTION_USE',
        'notes':'All flags default false. Independent audit and version freeze are mandatory.'}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--calibration',required=True)
    ap.add_argument('--holdout-csv',required=True)
    ap.add_argument('--threshold-mm',type=float,required=True)
    ap.add_argument('--max-p95-mm',type=float,required=True)
    ap.add_argument('--height',type=int,required=True);ap.add_argument('--width',type=int,required=True)
    ap.add_argument('--output',required=True)
    a=ap.parse_args()
    calibration=json.loads(Path(a.calibration).read_text(encoding='utf-8'))
    raw=Path(a.holdout_csv).read_bytes()
    records=list(csv.DictReader(raw.decode('utf-8-sig').splitlines()))
    data=build(calibration,records,raw,(a.height,a.width),a.threshold_mm,a.max_p95_mm)
    Path(a.output).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'DRAFT ONLY: n={data["holdout_n"]} P95={data["p95_absolute_error_mm"]:.4f} mm approved={data["approved"]}')
if __name__=='__main__':main()
