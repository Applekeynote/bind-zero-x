"""v4.9 operational and audit regressions. No AWS/OpenCV5/physical GT claims."""
import csv,hashlib,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from capture_archive import persist_capture,verify_capture,audit_archive
from capture_lifecycle import start_captured
from research_loop_store import SQLiteResearchLoops,StoreError
from active_evidence_loop import start_research_loop
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from analyze_physical_comparison import analyze,read

W=('A','B')
LOSSES={'REORDER':{'A':0,'B':8},'RE_TIE':{'A':8,'B':0},'ABSTAIN':{'A':3,'B':3}}
VIEWS={'SIDE':{'A':'a','B':'b'}}
COSTS={'SIDE':.1}
def capture_image():return b'\x89PNG\r\n\x1a\nsynthetic-test-only'
def images():return dict.fromkeys(('frame0','frame1','upper_mask','lower_mask'),capture_image())

class StoreOperations(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.db=self.root/'s.db';self.archive=self.root/'archive'
  self.env=patch.dict(os.environ,{'BZX_CAPTURE_ARCHIVE_DIR':str(self.archive)})
  self.env.start();self.store=SQLiteResearchLoops(self.db)
 def tearDown(self):self.env.stop();self.temp.cleanup()
 def captured(self,session='s'):
  return start_captured(self.store,self.archive,session_id=session,observation_id='o',raw_images=images(),metadata={},worlds=W,losses=LOSSES,view_signatures=VIEWS,view_costs=COSTS)
 def test_001_captured_receipt_verifies(self):
  result,receipt=self.captured();self.assertTrue(verify_capture(self.archive,receipt));self.assertEqual(self.store.read('s')[0],0)
 def test_002_missing_archive_refuses_read(self):
  _,receipt=self.captured();(self.archive/(receipt+'.json')).unlink()
  with self.assertRaisesRegex(StoreError,'EVIDENCE_UNAVAILABLE'):self.store.read('s')
 def test_003_deleted_png_refuses_read(self):
  _,receipt=self.captured();m=json.loads((self.archive/(receipt+'.json')).read_text());(self.archive/(m['images']['frame0']['sha256']+'.png')).unlink()
  with self.assertRaisesRegex(StoreError,'EVIDENCE_UNAVAILABLE'):self.store.read('s')
 def test_004_duplicate_reservation_before_write(self):
  self.captured();before={x.name for x in self.archive.iterdir()}
  with self.assertRaisesRegex(StoreError,'SESSION_EXISTS'):self.captured()
  self.assertEqual(before,{x.name for x in self.archive.iterdir()})
 def test_005_reservation_competing_request(self):
  self.store.reserve_capture_start('s')
  with self.assertRaisesRegex(StoreError,'ALREADY_RESERVED'):self.captured()
  self.assertFalse(self.archive.exists())
 def test_006_failure_releases_reservation(self):
  with self.assertRaises(ValueError):
   start_captured(self.store,self.archive,session_id='s',observation_id='o',raw_images={},metadata={},worlds=W,losses=LOSSES,view_signatures=VIEWS,view_costs=COSTS)
  self.captured()
 def test_007_archive_audit_detects_orphan(self):
  _,r=self.captured()
  (self.archive/('f'*64+'.json')).write_text('{}')
  report=audit_archive(self.archive,[r]);self.assertIn('f'*64+'.json',report['orphan_candidates_REVIEW_BEFORE_DELETE'])
 def test_008_archive_audit_detects_missing(self):
  _,r=self.captured();(self.archive/(r+'.json')).unlink()
  self.assertIn(r,audit_archive(self.archive,[r])['missing_or_corrupt_receipts'])
 def test_009_claim_only_session_not_archive_dependent(self):
  s=start_research_loop('s','o',W,LOSSES,VIEWS,COSTS,'a'*64)
  self.store.start(s);self.assertEqual(self.store.read('s')[0],0)

class ArmCoverage(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.f=Path(self.tmp.name)/'t.csv'
 def tearDown(self):self.tmp.cleanup()
 def test_010_accepts_ablation_arm(self):
  rows=[{'case_id':str(i),'pair_id':'P','D0_D1_E1_E2_or_B':arm,'original_sheet_count':'5','carried_sheet_count':'5','completed':'1','elapsed_seconds':'50','wrong_intervention':'0','video_sha256':hashlib.sha256(arm.encode()).hexdigest()} for i,arm in enumerate(('E2','E2-ablated'))]
  with self.f.open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
  result=analyze(self.f);self.assertEqual(result['group_summaries']['E2-ablated']['n'],1)
 def test_011_missing_hash_is_explicit(self):
  row={'case_id':'1','pair_id':'P','D0_D1_E1_E2_or_B':'E2','original_sheet_count':'5','carried_sheet_count':'5','completed':'1','elapsed_seconds':'50','wrong_intervention':'0','video_sha256':''}
  with self.f.open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=row);w.writeheader();w.writerow(row)
  self.assertEqual(analyze(self.f)['missing_video_hash_n'],1)
 def test_012_report_never_asserts_empirical_result(self):
  row={'case_id':'1','pair_id':'P','D0_D1_E1_E2_or_B':'E2','original_sheet_count':'5','carried_sheet_count':'5','completed':'1','elapsed_seconds':'50','wrong_intervention':'0','video_sha256':''}
  with self.f.open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=row);w.writeheader();w.writerow(row)
  self.assertEqual(analyze(self.f)['evidence_status'],'UNVERIFIED_INPUT_NO_EMPIRICAL_CLAIM')
