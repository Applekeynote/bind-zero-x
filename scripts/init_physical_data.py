"""Prepare an empty, maintainable real-data workspace; never invent samples."""
from pathlib import Path
import csv
import json

root = Path(__file__).resolve().parents[1] / 'data' / 'physical'
for folder in ('raw', 'calibration', 'holdout', 'training', 'preregistration', 'reviews', 'derived'):
    (root / folder).mkdir(parents=True, exist_ok=True)
columns = ['trial_id', 'bundle_id', 'fault_mode', 'gt_mm', 'cv_mm', 'gt_rater', 'video_sha256', 'video_file']
target = root / 'holdout' / 'independent_measurements.csv'
if not target.exists():
    with target.open('w', encoding='utf-8', newline='') as handle:
        csv.writer(handle).writerow(columns)
draft = root / 'preregistration' / 'DRAFT.json'
if not draft.exists():
    draft.write_text(json.dumps(dict(status='DRAFT_NOT_FROZEN', frozen_utc=None,
        primary_endpoint=None, required_independent_bundles=30,
        threshold_mm=5.0, max_p95_mm=0.5,
        note='Proposed thresholds only. Freeze with an independent reviewer BEFORE collection.'), indent=2), encoding='utf-8')
print(root)
print('Created EMPTY collection structure; no physical observations or approval were generated.')
