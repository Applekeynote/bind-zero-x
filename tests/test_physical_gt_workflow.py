"""Missing real data cannot be promoted to an approved ground-truth result."""
from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from validate_physical_gt import validate


class PhysicalGTWorkflow(unittest.TestCase):
    def test_missing_inputs_stay_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            result = validate(directory, (1080, 1920))
            self.assertEqual(result['status'], 'BLOCKED_PHYSICAL_DATA_REQUIRED')
            self.assertFalse(result['independent_gt_approved'])
            self.assertFalse((Path(directory) / 'derived' / 'gt-envelope-DRAFT.json').exists())

    def test_draft_preregistration_cannot_certify_header_only_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in ('raw', 'calibration', 'holdout', 'preregistration', 'training'):
                (root / folder).mkdir()
            (root / 'calibration/calibration.json').write_text('{}')
            (root / 'preregistration/FROZEN.json').write_text(json.dumps({'status': 'DRAFT_NOT_FROZEN'}))
            (root / 'training/bundle_ids.txt').write_text('')
            (root / 'holdout/independent_measurements.csv').write_text('trial_id,bundle_id\n')
            result = validate(root, (1080, 1920))
            self.assertEqual(result['status'], 'REJECTED_INPUT')
            self.assertEqual(result['reason'], 'PREREGISTRATION_NOT_FROZEN')
            self.assertFalse(result['independent_gt_approved'])


if __name__ == '__main__':
    unittest.main()
