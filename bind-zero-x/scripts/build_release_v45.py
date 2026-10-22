# coding: utf-8
"""Regenerate v4.5 CSV ledgers/requirements/mappings and deterministic package."""
from pathlib import Path
from datetime import datetime,timezone
import csv,re,hashlib,zipfile,collections,json

ROOT=Path(__file__).resolve().parents[1]
LOG=ROOT/'reports/v45_unittest_verbose.log'
now=datetime.now(timezone.utc).isoformat(timespec='seconds')

def readcsv(filename):
 with (ROOT/filename).open(encoding='utf-8-sig',newline='') as f:
  r=csv.DictReader(f);return r.fieldnames,list(r)

def writecsv(name,keys,rows):
 with (ROOT/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');w.writeheader();w.writerows(rows)

ledger_columns,ledger=readcsv('v4.4_テストケース台帳.csv')
req_columns,reqs=readcsv('v4.4_要求仕様.csv')
map_columns,relations=readcsv('v4.4_要求試験多対多対応.csv')
existing={r['test_id'] for r in ledger}
assert len(ledger)==451 and len(existing)==451
assert len(reqs)==98 and len(relations)==602

new_requirements=[
('V45-SEM-PROOF','証明','証明書を元の有限モデルから意味的に独立再計算し、偽の直接行動を拒否する','G0'),
('V45-ABS-LOSS','安全な意思決定','相対的な後悔量と別に最大絶対損失の限界を確認する','G0'),
('V45-MODEL-PIN','証拠管理','事前登録済みモデル・画像SHA・校正IDのサーバ側照合を必須にする','G0'),
('V45-FLOW','画像処理','前後方向の光学フローが異常値やNoneを返しても測定不能へ落とす','G0'),
('V45-MULTISTEP','能動知覚','提案された視点→新観測→可能世界の更新→再計画を実行する','G2'),
('V45-API-STATE','セッション','研究APIの認証・排他更新・再送・入力制限を実証する','G2'),
('V45-REAL-CV5','大会必須','実AWSワーカーがOpenCV 5による実映像の解析を実行する','G3'),
('V45-REAL-AWS','大会必須','AWS上で本人確認・状態管理・再観測とログ取得を完走する','G3'),
('V45-REAL-GT','物理実測','実段ボールの独立GTに対する層/ひも/結び目の計測成績を公開','G4'),
('V45-REAL-ABLATION','独創性','BIND-WITNESS方式E2と固定視点D/簡易E1を同一条件で比較する','G5'),
('V45-REAL-HUMAN','実用','熟練者BとE2を全束の作業完了率・失敗・総時間で比較する','G5'),
]
for rid,kind,desc,gate in new_requirements:
 reqs.append(dict(requirement_id=rid,requirement_type=kind,requirement=desc,gate=gate,
   primary_test_count='0',total_related_tests='0',primary_test_ids='',all_related_test_ids='',
   design_status='SPECIFIED',implementation_status='PARTIAL_LOCAL_OR_NOT_RUN',real_world_validation='NOT_RUN',
   acceptance_basis='REQUIRES_CODE_TEST_OR_INDEPENDENT_REAL_GT_AND_REAL_AWS'))

# New tests counted only if they appear in a passing verbose unittest log.
logs=LOG.read_text()
assert 'Ran 268 tests' in logs and '\nOK' in logs, logs[-250:]
method_lines=re.findall(r'^test_(V45_(?:\d{3}|API_\d{3}))_[^\s]*\s+\(([^\n]+?)\)\s+\.\.\.\s+ok$',logs,re.M)
assert len(method_lines)==34,(len(method_lines),method_lines)
log_hash=hashlib.sha256(LOG.read_bytes()).hexdigest()
req_of={
 '001':'V45-SEM-PROOF','002':'V45-SEM-PROOF','003':'V45-SEM-PROOF','009':'V45-SEM-PROOF',
 '004':'V45-ABS-LOSS','005':'V45-ABS-LOSS','008':'V45-ABS-LOSS',
 '006':'V45-MODEL-PIN','007':'V45-MODEL-PIN','023':'V45-MODEL-PIN',
 '010':'V45-FLOW','011':'V45-FLOW','012':'V45-FLOW','013':'V45-FLOW',
 '024':'V45-FLOW','025':'V45-FLOW',
 '014':'V45-MULTISTEP','015':'V45-MULTISTEP','016':'V45-MULTISTEP','017':'V45-MULTISTEP',
 '018':'V45-MULTISTEP','019':'V45-MULTISTEP','020':'V45-MULTISTEP','021':'V45-MULTISTEP','022':'V45-MULTISTEP',
 'API_001':'V45-API-STATE','API_002':'V45-API-STATE','API_003':'V45-API-STATE',
 'API_004':'V45-API-STATE','API_005':'V45-API-STATE','API_006':'V45-API-STATE','API_007':'V45-API-STATE'
}
req_of.update({'026':'V45-SEM-PROOF','027':'V45-SEM-PROOF'})
assert len(req_of)==34
new_ids=[]
for label,method in method_lines:
 suffix=label[4:] # e.g. 001 or API_001
 tid='V45-'+suffix.replace('_','-')
 rid=req_of[suffix]
 assert tid not in existing
 row={c:'' for c in ledger_columns}
 row.update(test_id=tid,requirement_id=rid,category='API' if suffix.startswith('API') else 'UNIT',
   priority='BLOCKER' if rid in ('V45-SEM-PROOF','V45-FLOW','V45-MODEL-PIN') else 'P0',
   setup='Local Python3.13/OpenCV4.13 controlled regression; not physical/AWS proof',
   input_or_stimulus=method,expected_oracle='unittest assert conditions all satisfied',
   quantitative_gate='actual unittest must PASS (not a physical performance hypothesis)',
   evidence='reports/v45_unittest_verbose.log',automation='AUTO',status='PASS',
   owner='SOLO_DEVELOPER',test_purpose='CONFORMANCE',hypothesis_status='NOT_EVALUATED',
   evidence_status='LOCAL_TEST_EXECUTED',gate_stage='G0' if rid not in ('V45-MULTISTEP','V45-API-STATE') else 'G2',
   threshold_status='EXPLICIT_ASSERTIONS',planned_execution_min='0.1',
   claim_supported_if_pass='LOCAL_CODE_CORRECTNESS_ONLY',last_run_at=now,
   observed_result='PASS: '+method,evidence_sha256=log_hash,
   source_version='v4.5',evidence_tier='LOCAL_MATH_SYNTHETIC_RESEARCH_API',
   preparation_min='0',collection_min='0',analysis_min='0',repeat_reserve_min='0',
   methodology='Unittest run on existing local environment; not independent real holdout',
   test_execution_status='PASS',effect_hypothesis_status='NOT_EVALUATED',
   runtime_scope='LOCAL_OPENCV4_OR_PURE_PYTHON',evaluation_role='CONFORMANCE_TEST')
 ledger.append(row);new_ids.append(tid)
 relations.append({'test_id':tid,'requirement_id':rid,'relation':'PRIMARY','rationale':'v4.5 executed named Python test'})

real_cases=[
('V45-REAL-001','V45-REAL-CV5','AWS EC2 real OpenCV5 vision runtime and logged analysis'),
('V45-REAL-002','V45-REAL-AWS','AWS durable multi-step owner/auth and signed raw request'),
('V45-REAL-003','V45-REAL-GT','Real multilayer cardboard independent known-displacement GT'),
('V45-REAL-004','V45-REAL-ABLATION','E2 vs D/E1 mechanistic paired masked evaluation'),
('V45-REAL-005','V45-REAL-HUMAN','E2 vs skilled B all-sheets-completed job comparison'),
('V45-REAL-006','V45-MULTISTEP','Two real OpenCV5 captures alter next-view/replanning in AWS'),
]
for tid,rid,desc in real_cases:
 assert tid not in existing
 r={c:'' for c in ledger_columns}
 r.update(test_id=tid,requirement_id=rid,category='REAL_AWS_OR_PHYSICAL',priority='BLOCKER',
     setup='Pre-register materials, camera, owner and independent GT first',input_or_stimulus=desc,
     expected_oracle='Raw real-world evidence + independently reproducible comparison',
     quantitative_gate='THRESHOLD_AND_SAMPLE_SIZE_TO_FREEZE_BEFORE_HOLDOUT',
     evidence='REQUIRES_REAL_RAW_DATA',automation='MANUAL_OR_SEMI_AUTO',status='NOT_RUN',
     owner='SOLO_DEVELOPER_NOT_YET_SCHEDULED',test_purpose='EFFECT_VALIDATION',
     hypothesis_status='NOT_EVALUATED',evidence_status='NOT_COLLECTED',gate_stage='G3_G5',
     threshold_status='TO_FREEZE_BEFORE_HOLDOUT',planned_execution_min='VARIABLE',
     claim_supported_if_pass='REAL_MEASURED_RESULT_ONLY',source_version='v4.5',
     evidence_tier='REAL_NOT_RUN',preparation_min='TBD',collection_min='TBD',
     analysis_min='TBD',repeat_reserve_min='TBD',methodology='Real paired trial/AWS runtime',
     test_execution_status='NOT_RUN',effect_hypothesis_status='NOT_EVALUATED',
     runtime_scope='NOT_VERIFIED',evaluation_role='PHYSICAL_OR_AWS_VALIDATION')
 ledger.append(r);relations.append({'test_id':tid,'requirement_id':rid,'relation':'PRIMARY','rationale':'v4.5 requires independent real/AWS proof'})

# Added cross-cutting relations
extra=[('V45-002','V45-MODEL-PIN'),('V45-006','V45-SEM-PROOF'),('V45-007','V45-SEM-PROOF'),
       ('V45-020','V45-REAL-GT'),('V45-API-002','V45-MULTISTEP'),('V45-API-004','V45-MODEL-PIN'),
       ('V45-REAL-006','V45-REAL-CV5'),('V45-REAL-004','V45-MULTISTEP')]
for t,r in extra:relations.append(dict(test_id=t,requirement_id=r,relation='SECONDARY',rationale='Cross-cutting v4.5 dependency'))

all_tests={x['test_id'] for x in ledger};all_reqs={x['requirement_id'] for x in reqs}
assert len(ledger)==491 and len(all_tests)==491
assert len(reqs)==109 and len(all_reqs)==109
assert len(relations)==602+40+8
assert all(x['test_id'] in all_tests and x['requirement_id'] in all_reqs for x in relations)
assert len({(x['test_id'],x['requirement_id']) for x in relations})==len(relations)
for req in reqs:
  relevant=[x for x in relations if x['requirement_id']==req['requirement_id']]
  prim=sorted(x['test_id'] for x in relevant if x['relation']=='PRIMARY')
  req.update(primary_test_count=str(len(prim)),total_related_tests=str(len(relevant)),
             primary_test_ids=';'.join(prim),
             all_related_test_ids=';'.join(sorted(x['test_id'] for x in relevant)))

writecsv('v4.5_テスト台帳_491件.csv',ledger_columns,ledger)
writecsv('v4.5_要求仕様_109件.csv',req_columns,reqs)
writecsv('v4.5_要求試験対応_650件.csv',map_columns,relations)
evidence_cols=['test_id','unittest_id','status','tier','evidence_sha256']
_,old_evidence=readcsv('v4.4_ローカル実行証拠.csv')
new_evidence=old_evidence+[
 dict(test_id='V45-'+label[4:].replace('_','-'),unittest_id=method,status='PASS',
      tier='LOCAL_PURE_SYNTHETIC_OR_RESEARCH_API',evidence_sha256=log_hash)
 for label,method in method_lines]
assert len(new_evidence)==268
writecsv('v4.5_ローカル検算_268件.csv',evidence_cols,new_evidence)

status=collections.Counter(x['status'] for x in ledger)
assert status=={'PASS':268,'NOT_RUN':223},status
summary={'version':'4.5','local_tests_pass':268,'test_ledger_total':491,'real_tests_pending':223,
         'requirements':109,'requirement_test_links':len(relations),
         'opencv_local':'4.13.x development; 5.x NOT_VERIFIED','aws_runtime':'NOT_VERIFIED',
         'physical_comparison':'NOT_RUN','local_unittest_log_sha256':log_hash,
         'adversarial_regressions_fixed':3,'official_95_plus_score':'NOT_PROVEN'}
(ROOT/'reports/v45_integrity_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

# Create release archive; exclude earlier stale manifest files, build pycache, and self ZIP.
archive=Path('/mnt/data/BIND_ZERO_X_v4.5_95点超目標_独創性・実装強化一式.zip')
files=[]
for p in ROOT.rglob('*'):
 if not p.is_file():continue
 r=p.relative_to(ROOT)
 if '__pycache__' in r.parts or p.suffix in ('.pyc','.zip') or r.name in ('SHA256SUMS_v43.txt','SHA256SUMS_v44.txt','SHA256SUMS_v45.txt'):
  continue
 files.append((r,p))
files.sort(key=lambda x:str(x[0]))
manifest=''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {r.as_posix()}\n' for r,p in files)
(ROOT/'SHA256SUMS_v45.txt').write_text(manifest,encoding='utf-8')
files.append((Path('SHA256SUMS_v45.txt'),ROOT/'SHA256SUMS_v45.txt'))
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=7) as z:
 for rel,p in files:z.write(p,rel.as_posix())
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 assert len(z.namelist())==len(files)
 for r,p in files:
  assert hashlib.sha256(z.read(r.as_posix())).digest()==hashlib.sha256(p.read_bytes()).digest()
print(json.dumps({'archive':str(archive),'files':len(files),**summary},ensure_ascii=False,indent=2))
