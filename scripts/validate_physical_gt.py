"""Audit actual physical media and prepare an UNAPPROVED GT envelope.

Does not collect physical measurements, freeze a preregistration after the fact,
or sign an independent review. Missing data produces a blocked report.
"""
import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'bind-zero-x' / 'experiments'))
from audit_gt_source_media import audit
from prepare_gt_envelope import build


def validate(root, shape):
    root = Path(root)
    output = root / 'derived'
    output.mkdir(parents=True, exist_ok=True)
    paths = dict(calibration=root / 'calibration' / 'calibration.json',
                 holdout=root / 'holdout' / 'independent_measurements.csv',
                 preregistration=root / 'preregistration' / 'FROZEN.json',
                 training=root / 'training' / 'bundle_ids.txt')
    missing = [str(p.relative_to(root)) for p in paths.values() if not p.is_file()]
    report = dict(status='BLOCKED_PHYSICAL_DATA_REQUIRED', independent_gt_approved=False,
                  missing_files=missing)
    if not missing:
        try:
            p = json.loads(paths['preregistration'].read_text(encoding='utf-8-sig'))
            media_audit = audit(paths['holdout'], root / 'raw', paths['preregistration'], paths['training'])
            raw = paths['holdout'].read_bytes()
            rows = list(csv.DictReader(raw.decode('utf-8-sig').splitlines()))
            calibration = json.loads(paths['calibration'].read_text(encoding='utf-8-sig'))
            envelope = build(calibration, rows, raw, shape, float(p['threshold_mm']), float(p['max_p95_mm']))
            (output / 'gt-envelope-DRAFT.json').write_text(json.dumps(envelope, indent=2), encoding='utf-8')
            report.update(status='BYTES_VALIDATED_INDEPENDENT_REVIEW_REQUIRED', media_audit=media_audit,
                          p95_absolute_error_mm=envelope['p95_absolute_error_mm'],
                          sample_count=envelope['holdout_n'])
        except (ValueError, OSError, KeyError, TypeError) as exc:
            report.update(status='REJECTED_INPUT', reason=str(exc)[:200])
    (output / 'gt-validation-status.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-root', default=str(ROOT / 'data' / 'physical'))
    parser.add_argument('--height', required=True, type=int)
    parser.add_argument('--width', required=True, type=int)
    args = parser.parse_args()
    report = validate(args.data_root, (args.height, args.width))
    raise SystemExit(0 if report['status'] == 'BYTES_VALIDATED_INDEPENDENT_REVIEW_REQUIRED' else 2)
