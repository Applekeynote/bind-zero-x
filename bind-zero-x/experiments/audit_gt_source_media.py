# -*- coding: utf-8 -*-
"""Offline GT media integrity/pre-registration auditor; NEVER self-approves GT.

Runs on real bytes at paths supplied by an independent reviewer. Checks
file hash, bundle-level holdout disjointness, and key provenance fields.
Video bytes could still be synthetic; a human must independently inspect.
"""
from __future__ import annotations
import argparse,csv,hashlib,json
from collections import Counter
from pathlib import Path

class AuditError(ValueError):pass

REQUIRED={'trial_id','bundle_id','fault_mode','gt_mm','cv_mm','gt_rater',
          'video_sha256','video_file'}

def _hash_file(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def audit(csv_file,media_root,preregistration_file,training_bundles_file=None):
    prereg_path=Path(preregistration_file)
    p=json.loads(prereg_path.read_text(encoding='utf-8'))
    if p.get('status')!='FROZEN_BEFORE_GT_COLLECTION' or not p.get('frozen_utc') or not p.get('primary_endpoint'):
        raise AuditError('PREREGISTRATION_NOT_FROZEN')
    training=set()
    if training_bundles_file:
        raw=Path(training_bundles_file).read_text(encoding='utf-8').splitlines()
        training={x.strip() for x in raw if x.strip()}
    root=Path(media_root).resolve(strict=True)
    with Path(csv_file).open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if not reader.fieldnames or not REQUIRED.issubset(reader.fieldnames):
            raise AuditError('REQUIRED_PROVENANCE_COLUMNS_MISSING')
        rows=list(reader)
    if len(rows)<30:raise AuditError('INSUFFICIENT_GT_ROWS')
    bundles=set();videos=set();trials=set();modes=Counter();raters=set()
    for r in rows:
        ident=r['trial_id'];bundle=r['bundle_id'];v=r['video_sha256']
        if not ident or ident in trials or not bundle or not r['gt_rater']:
            raise AuditError('DUPLICATE_OR_MISSING_GT_PROVENANCE')
        if bundle in training:raise AuditError('TRAIN_HOLDOUT_BUNDLE_LEAKAGE')
        if bundle in bundles:raise AuditError('REPEATED_PHYSICAL_BUNDLE_NOT_INDEPENDENT')
        if v in videos:raise AuditError('DUPLICATE_HOLDOUT_VIDEO')
        if len(v)!=64 or any(x not in '0123456789abcdef' for x in v):
            raise AuditError('INVALID_VIDEO_DIGEST')
        # Resolve without strict=True first to reject missing / escaped paths
        # consistently, including traversal through symlinks.
        path=(root/r['video_file']).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise AuditError('VIDEO_PATH_ESCAPES_MEDIA_ROOT')
        if _hash_file(path)!=v:raise AuditError('VIDEO_CONTENT_SHA256_MISMATCH')
        trials.add(ident);bundles.add(bundle);videos.add(v);raters.add(r['gt_rater'])
        modes[r['fault_mode']]+=1
    if len(bundles)<30 or len(videos)<30 or len(modes)<2 or min(modes.values())<5:
        raise AuditError('INSUFFICIENT_BUNDLE_LEVEL_DIVERSITY')
    return {'audit_status':'BYTES_AND_IDS_VALIDATED_NOT_INDEPENDENT_PHYSICAL_GT_APPROVAL',
        'real_world_ground_truth_approved':False,
        'n_trials':len(rows),'n_unique_bundles':len(bundles),'n_unique_videos':len(videos),
        'n_raters':len(raters),'fault_mode_counts':dict(sorted(modes.items())),
        'holdout_csv_sha256':_hash_file(Path(csv_file)),
        'preregistration_sha256':_hash_file(prereg_path),
        'training_exclusion_list_sha256':(_hash_file(Path(training_bundles_file)) if training_bundles_file else None),
        'remaining_human_checklist':['Blind GT measurement and device calibration',
           'Physical media authenticity and acquisition timestamps',
           'Holdout independence relative to training data',
           'Signed independent review before any approved production registry']}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--holdout-csv',required=True);p.add_argument('--media-root',required=True)
    p.add_argument('--preregistration',required=True);p.add_argument('--training-bundles')
    p.add_argument('--output',required=True)
    a=p.parse_args();result=audit(a.holdout_csv,a.media_root,a.preregistration,a.training_bundles)
    Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
