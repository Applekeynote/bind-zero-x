"""Recheck downloaded AWS synthetic evidence against the local reference run."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'bind-zero-x' / 'code'))
from capture_archive import verify_capture


def verify():
    reports = []
    for name in ('opencv5-local', 'opencv5-aws'):
        folder = ROOT / 'runtime' / 'evidence' / name
        report = json.loads((folder / 'execution.json').read_bytes())
        receipt = report['receipt_sha256']
        if not verify_capture(folder / 'captures', receipt):
            raise ValueError(name + ': INVALID_CAPTURE_ARCHIVE')
        manifest = json.loads((folder / 'captures' / (receipt + '.json')).read_bytes())
        actual = {key: item['sha256'] for key, item in manifest['images'].items()}
        if actual != report['input_sha256']:
            raise ValueError(name + ': INPUT_REPORT_MISMATCH')
        # The producer hashes OpenCV's UTF-8 text before Windows write_text
        # expands LF to CRLF. Universal-newline reading restores that contract.
        build = hashlib.sha256((folder / 'opencv-build.txt').read_text(encoding='utf-8').encode()).hexdigest()
        if build != report['build_information_sha256']:
            raise ValueError(name + ': BUILD_INFORMATION_MISMATCH')
        if report['opencv_version'] != '5.0.0' or report['input_tier'] != 'SYNTHETIC_OPENCV5_API_SMOKE_NOT_PHYSICAL_GT':
            raise ValueError(name + ': UNEXPECTED_RUNTIME_OR_INPUT_TIER')
        reports.append(report)
    local, aws = reports
    if (local['input_sha256'] != aws['input_sha256']
            or aws['aws_execution_environment'] != 'AWS_CloudShell'
            or aws['aws_region'] != 'ap-northeast-1'):
        raise ValueError('AWS_REFERENCE_MISMATCH')
    return dict(status='PASS', input_pngs_matching=4, archives_reverified=2,
                opencv_version=aws['opencv_version'], aws_region=aws['aws_region'],
                physical_gt_verified=False, aws_deployment_verified=False)


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
