# -*- coding:utf-8 -*-
"""Build v4.3 evidence tables from the original v4.2 ledger and discovered local tests.
Does not mutate original v4.2 CSV. No network, physical study or AWS runs.
"""
from pathlib import Path
import csv,unittest,json,hashlib,subprocess,sys,datetime,collections,zipfile,os
BASE=Path(__file__).resolve().parent
CODE=BASE/'code'
sys.path.insert(0,str(CODE))

def readcsv(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def writecsv(p,headers,rows):
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=headers,extrasaction='ignore');w.writeheader();w.writerows(rows)
def all_tests(suite):
 for item in suite:
  if isinstance(item,unittest.TestSuite):yield from all_tests(item)
  else:yield item

def classify(test):
 cls=test.__class__.__name__.lower()
 if any(x in cls for x in ('geometry','pipelinefail','synthetic','vision')):return 'CV','V43-ROI'
 if 'metric' in cls:return 'MATH','V43-METRIC'
 if 'protocol' in cls:return 'PHYS','V43-PROTOCOL'
 if 'decisionadversarial' in cls:return 'AGENT','V43-DECISION'
 if 'witness' in cls:return 'AGENT','V43-WITNESS'
 if 'bridge' in cls:return 'AGENT','V43-BRIDGE'
 return 'AGENT','V43-SAFETY'

# Run all the named original and newly added tests in a clean subprocess.
command=[sys.executable,'-m','unittest','discover','-s','code','-p','test_*.py','-v']
proc=subprocess.run(command,cwd=BASE,env={**os.environ,'PYTHONPATH':str(CODE)},text=True,capture_output=True)
log=proc.stdout+proc.stderr
(BASE/'reports').mkdir(exist_ok=True)
logfile=BASE/'reports'/'v43_local_unittest.log';logfile.write_text(log,encoding='utf-8')
assert proc.returncode==0,log[-5000:]
original=readcsv(BASE/'v4.2_テストケース台帳_327件.csv')
oldmethods={r['runner_method'] for r in readcsv(BASE/'v4.2_ローカル実行証拠_120件.csv')}
loader=unittest.TestLoader();suite=loader.discover(str(CODE),'test_*.py',top_level_dir=str(CODE))
tests=list(all_tests(suite)); assert len(tests)==187,len(tests)
methods=[t._testMethodName for t in tests]
assert len(set(methods))==len(methods),'method names must be unique for evidence ledger'
new=[t for t in tests if t._testMethodName not in oldmethods]
assert len(new)==67,(len(new),len(oldmethods))
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
sha=hashlib.sha256(log.encode()).hexdigest()
evidence=[dict(r) for r in readcsv(BASE/'v4.2_ローカル実行証拠_120件.csv')]
for t in new:
 typ,req=classify(t)
 evidence.append(dict(runner_method=t._testMethodName,result='PASS',environment='LOCAL_OPENCV_4_13_NO_AWS',
    timestamp_utc=now,run_log_sha256=sha,evidence_scope=f'{typ}_SYNTHETIC_OR_PURE_TEST'))
assert len(evidence)==187
writecsv(BASE/'v4.3_ローカル実行証拠_187件.csv',list(evidence[0]),evidence)
oldheads=list(original[0]);test_rows=list(original)
reqs=[dict(r) for r in readcsv(BASE/'v4.2_要求仕様_81件.csv')];reqlist={r['requirement_id'] for r in reqs}
newreqs={
 'V43-ROI':('画像計測','異なる材料層へのROI帰属、重なり検査、観測領域最大変位と相対回転を検証','G0'),
 'V43-METRIC':('計測品質','物理単位・校正ID・平面・非負有限な不確実性をすべて検証','G0'),
 'V43-PROTOCOL':('実験仕様','安全承認された試験プロファイルの完全性・妥当な許容差・UTC凍結を検証','G3'),
 'V43-DECISION':('意思決定','原因別の欠測と回転を正しく扱い誤修正を防ぐ','G2'),
 'V43-WITNESS':('独創性','反例世界を明示し後悔量を低減する非接触追加観測または判断保留を選択','G2'),
 'V43-BRIDGE':('AgenticVision','画像計測値の相違が未校正モデル上の次の観測を変えることを追跡','G2'),
 'V43-SAFETY':('安全制御','ROI未検証・識別不能では物理的行動を提案しない','G1'),
}
for k,(typ,desc,gate) in newreqs.items():
 assert k not in reqlist
 q={col:'' for col in reqs[0]}
 q.update(requirement_id=k,requirement_type=typ,requirement=desc,gate=gate,design_status='SPECIFIED',
          implementation_status='LOCAL_PROTOTYPE',real_world_validation='NOT_RUN',
          acceptance_basis='LOCAL_REGRESSION_ONLY_PHYSICAL_NOT_PROVEN')
 reqs.append(q)
relations=readcsv(BASE/'v4.2_要求テスト多対多対応.csv')
usedids={r['test_id'] for r in original}
for i,t in enumerate(new,1):
 typ,req=classify(t)
 tid=f'V43-REG-{i:03d}'
 assert tid not in usedids
 d={h:'' for h in oldheads}
 d.update(test_id=tid,requirement_id=req,category=typ,priority='P0' if typ in ('CV','PHYS') else 'P1',
    setup='v4.3 local regression',input_or_stimulus=t._testMethodName,
    expected_oracle='unittest assertion matches behavior',quantitative_gate='assertions pass',
    evidence='reports/v43_local_unittest.log',automation='AUTO',status='PASS',owner='LOCAL_TEST_RUNNER',
    test_purpose='IMPLEMENTATION_CONTRACT_NOT_PHYSICAL_BENEFIT',hypothesis_status='NOT_EVALUATED',
    evidence_status='LOCAL_ONLY',gate_stage='LOCAL_REGRESSION',threshold_status='CODE_ASSERTION',
    planned_execution_min='1',claim_supported_if_pass='Only local code regression; no physical utility',
    last_run_at=now,observed_result='PASS (LOCAL)',evidence_sha256=sha,
    source_version='v4.3',evidence_tier='LOCAL_SYNTHETIC_OR_PURE_CODE',
    methodology='unit/integration synthetic',test_execution_status='PASS',
    effect_hypothesis_status='NOT_EVALUATED',runtime_scope='LOCAL_CV4_NOT_AWS',
    evaluation_role='REGRESSION_NOT_CLAIM')
 test_rows.append(d)
 relations.append(dict(test_id=tid,requirement_id=req,relation='PRIMARY',
     rationale='v4.3 method regression; does not validate real-world effect'))
assert len(test_rows)==394
assert len(reqs)==88
relids={r['requirement_id'] for r in relations}
for r in reqs:
 tid=[q['test_id'] for q in test_rows if q['requirement_id']==r['requirement_id']]
 related=[q['test_id'] for q in relations if q['requirement_id']==r['requirement_id']]
 r.update(primary_test_count=str(len(tid)),total_related_tests=str(len(related)),
          primary_test_ids=';'.join(tid),all_related_test_ids=';'.join(related))
writecsv(BASE/'v4.3_テストケース台帳_394件.csv',oldheads,test_rows)
writecsv(BASE/'v4.3_要求仕様_88件.csv',list(reqs[0]),reqs)
writecsv(BASE/'v4.3_要求テスト多対多対応.csv',list(relations[0]),relations)
# Independent validation
assert len({r['test_id'] for r in test_rows})==len(test_rows)
assert len({r['requirement_id'] for r in reqs})==len(reqs)
assert all(r['test_id'] in {x['test_id'] for x in test_rows} and r['requirement_id'] in {x['requirement_id'] for x in reqs} for r in relations)
assert collections.Counter(r['status'] for r in test_rows)=={'PASS':187,'NOT_RUN':207}
assert len(relations)==476+len(new)
prior=[
 ('P1','Interactive Perception for Deformable Object Manipulation','Weng et al 2024','active camera & manipulator, deformable objects','active perception is prior art; cannot claim first','domain-specific layer/twine/knot decision witnesses; must demonstrate gains','https://doi.org/10.1109/LRA.2024.3431943','KNOWN_OVERLAP'),
 ('P2','Robotic perception and manipulation of deformable linear objects: survey','Caporali et al 2026','prior vision/tactile planning of ropes and cables','rope and knot visual tracking not original','multi-cause cardboard binding job and selective abstention','https://doi.org/10.1177/02783649261432253','KNOWN_OVERLAP'),
 ('P3','Method and apparatus for inspecting binding straps','JP3325709B2','binding strap inspection including cardboard','direct adjacent patent: visual/physical strap inspection','not industrial inspection; targeted witness-based view selection requires comparison','https://patents.google.com/patent/JP3325709B2/en','HIGH_OVERLAP'),
 ('P4','Image-controlled strapping equipment','EP3501995B1','visual feedback for industrial binding','camera-guided binding also prior art','human-in-loop manual bundling with abstention certificate','https://patents.google.com/patent/EP3501995B1/en','OVERLAP'),
 ('P5','Optical-mechanical binding control','US9051071B2','machine binding optical/mechanical control','vision and binding are not new','repair actions and no-force targeted extra camera observation','https://patents.google.com/patent/US9051071B2/en','OVERLAP'),
 ('P6','Bundle looseness help','JP6895227B2','binding assistance','binding aid market competes','interactive failure-mode evidence rather than binding tool','https://patents.google.com/patent/JP6895227B2/ja','OVERLAP'),
 ('P7','Prevent cardboard misalignment','JP6038627B2','slip mitigation','physical slip prevention already exists','detect cause and compare alternatives; may offer no value in easy cases','https://patents.google.com/patent/JP6038627B2/ja','OVERLAP'),
]
writecsv(BASE/'v4.3_先行技術・独創性境界.csv',
 ['id','name','source','known_features','overlap_risk','limited_differentiation_hypothesis','url','status'],
 [dict(zip(['id','name','source','known_features','overlap_risk','limited_differentiation_hypothesis','url','status'],r)) for r in prior])

report=f'''BIND ZERO-X v4.3 ACTUAL LOCAL VALIDATION REPORT
UTC: {now}
Python: {sys.version.split()[0]}
Tests: {len(tests)} discovered / {len(tests)} PASS
Source v4.2 ledger: 327 (120 old local PASS, 207 NOT_RUN)
v4.3 regression tests: {len(new)} added and PASS (local only)
Current ledger: {len(test_rows)} cases (187 local PASS, 207 NOT_RUN)
Requirements: {len(reqs)}; requirement-test links: {len(relations)}
OpenCV local version: 4.13.0 (NOT OpenCV5)
AWS: NOT_RUN; Physical independent GT: NOT_RUN; Human comparison: NOT_RUN.
Novelty: finite deterministic illustrative witness planner; no real-world improvement proven.
Run log SHA256: {sha}
WARNING: PASS test category PHYS can refer to software profile checks; never label as physical evidence.
'''
(BASE/'reports'/'v43_verification_report.txt').write_text(report,encoding='utf-8')
# Reproducible file digest manifest; no ZIP itself in manifest (avoid recursive hash).
manifest_paths=[q for q in BASE.rglob('*') if q.is_file() and q.suffix not in ('.pyc','.zip')
                and '__pycache__' not in q.parts and q.name not in ('patch_v43.py','SHA256SUMS_v43.txt')]
manifest_text=''.join(f'{hashlib.sha256(q.read_bytes()).hexdigest()}  {q.relative_to(BASE)}\n'
                      for q in sorted(manifest_paths))
(BASE/'SHA256SUMS_v43.txt').write_text(manifest_text,encoding='utf-8')
# only package needed sources; include v4.2 reference and all v4.3 products.
newzip=Path('/mnt/data/BIND_ZERO_X_v4.3_95点超目標_独創性強化_改訂版一式.zip')
items=[BASE/'BIND_ZERO_X_v4.3_95点超を目指す実装・独創性・実証設計.md',
       BASE/'README_v43.md',BASE/'v4.3_先行技術・独創性境界.csv',
       BASE/'v4.3_テストケース台帳_394件.csv',BASE/'v4.3_要求仕様_88件.csv',
       BASE/'v4.3_要求テスト多対多対応.csv',BASE/'v4.3_ローカル実行証拠_187件.csv',
       BASE/'BIND_ZERO_X_v4.2_95点超目標_詳細設計書.txt',
       BASE/'v4.2_変更設計・95点超達成ゲート.md',
       BASE/'v4.2_テストケース台帳_327件.csv',
       BASE/'v4.2_要求仕様_81件.csv',
       BASE/'v4.2_要求テスト多対多対応.csv',
       BASE/'v4.2_ローカル実行証拠_120件.csv',
       BASE/'demos'/'demo_bind_witness.py',
       BASE/'demos'/'合成画像_B4_観測で選択が変わるトレース.json',
       BASE/'deploy'/'Dockerfile',BASE/'deploy'/'AWS_EC2_実装と証拠取得.md',
       BASE/'templates'/'physical_trial_template_v42.csv',BASE/'templates'/'preregistration_v42.json',
       BASE/'reports'/'v43_local_unittest.log',BASE/'reports'/'v43_verification_report.txt',
       BASE/'build_v43_release.py',BASE/'SHA256SUMS_v43.txt']+sorted(CODE.glob('*.py'))
with zipfile.ZipFile(newzip,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=8) as z:
 for file in items:z.write(file,arcname=file.relative_to(BASE))
with zipfile.ZipFile(newzip) as z:
 assert z.testzip() is None
 assert len(z.namelist())==len(items)
print(report)
print('ZIP',newzip, 'bytes',newzip.stat().st_size,'members',len(items))
