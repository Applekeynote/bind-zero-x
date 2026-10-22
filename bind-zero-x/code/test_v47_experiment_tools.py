# -*- coding: utf-8 -*-
"""Synthetic fixtures ONLY. Not a real clinical/physical experiment."""
import unittest,sys,hashlib,tempfile,csv
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from prepare_gt_envelope import build
from analyze_physical_comparison import analyze

class ExperimentToolsV47(unittest.TestCase):
    def data(self,n=30):
        return [{'trial_id':str(i),'bundle_id':str(i),'fault_mode':('SLIP' if i%2 else 'STILL'),
            'gt_rater':'RATER2','video_sha256':f'{i+1:064x}','gt_mm':str(i/10),
            'cv_mm':str(i/10+0.1)} for i in range(n)]
    def test_V47_028_heldout_records_generate_DRAFT_only(self):
        m=build({'verified':True},self.data(),b'fictional entries',(256,256),1.0,.2)
        self.assertFalse(m['approved']);self.assertFalse(m['independent_real_gt'])
        self.assertEqual(m['holdout_n'],30)
    def test_V47_029_small_sample_rejected(self):
        with self.assertRaisesRegex(ValueError,'SAMPLE_SIZE'):
            build({},self.data(29),b'bytes',(200,200),1,.2)
    def test_V47_030_duplicate_trials_rejected(self):
        d=self.data();d[1]['trial_id']=d[0]['trial_id']
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):
            build({},d,b'bytes',(200,200),1,.2)
    def test_V47_031_single_bundle_rejected(self):
        d=self.data()
        for row in d:row['bundle_id']='one'
        with self.assertRaisesRegex(ValueError,'DIVERSITY'):
            build({},d,b'bytes',(200,200),1,.2)
    def test_V47_032_empty_physical_trials_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'t.csv';p.write_text('case_id,pair_id\n')
            with self.assertRaisesRegex(ValueError,'NO_REAL_TRIALS'):
                analyze(p)
    def test_V47_033_completed_with_missing_sheets_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'t.csv'
            row={'case_id':'A','pair_id':'P','D0_D1_E1_E2_or_B':'E2','original_sheet_count':3,
             'carried_sheet_count':2,'elapsed_seconds':15,'completed':'1','wrong_intervention':'0','video_sha256':'a'*64}
            with p.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(row));w.writeheader();w.writerow(row)
            with self.assertRaisesRegex(ValueError,'INCOMPLETE_SHEETS'):
                analyze(p)
if __name__=='__main__':unittest.main()
