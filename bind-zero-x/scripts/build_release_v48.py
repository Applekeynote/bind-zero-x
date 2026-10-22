# -*- coding: utf-8 -*-
"""Regenerate v4.8 ledger from real LOCAL test method inventory, no fake real/AWS PASS.

Idempotent on a newly unpacked v4.7 distribution. The ZIP output filename and
location are supplied by --output; it does not submit to any contest.
"""
from __future__ import annotations
import argparse,collections,csv,datetime,hashlib,json,re,subprocess,sys,unittest,zipfile
from pathlib import Path
R=Path(__file__).resolve().parents[1]

def load(name):
    with (R/name).open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);return list(reader),reader.fieldnames

def write(name,rows,columns):
    with (R/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(rows)

def methods():
    suite=unittest.TestLoader().discover(str(R/'code'),pattern='test_v48_*.py',top_level_dir=str(R/'code'))
    def walk(s):
        for item in s:
            if isinstance(item,unittest.TestSuite):yield from walk(item)
            else:yield item
    return list(walk(suite))

def main(output):
    run=subprocess.run([sys.executable,'-m','unittest','discover','-s','code','-p','test_*.py','-v'],
      cwd=R,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=180)
    log=R/'reports/v48_unittest_verbose.log';log.write_text(run.stdout,encoding='utf-8')
    if run.returncode or 'Ran 386 tests' not in run.stdout or '\nOK\n' not in run.stdout:
        raise RuntimeError('CURRENT_LOCAL_TESTS_FAILED '+run.stdout[-1000:])
    digest=hashlib.sha256(log.read_bytes()).hexdigest()
    tests,cols=load('v4.7_テスト台帳_591件.csv')
    evidence,ev_cols=load('v4.7_ローカル検算_350件.csv')
    reqs,req_cols=load('v4.7_要求仕様_131件.csv')
    traces,trace_cols=load('v4.7_要求試験対応_766件.csv')
    assert (len(tests),len(evidence),len(reqs),len(traces))==(591,350,131,766)
    descriptions={
      'V48-STAT':'未完了試行と完了試行の区別、元全枚数の完了率、複合指標、ペア時間条件付け',
      'V48-GT-BUNDLE':'GTの独立評価単位は束でありレコード数は有効nではない',
      'V48-GT-REGISTRY':'V1レジストリ廃止、V2の独立束と外部監査承認レシートを要求',
      'V48-GT-MEDIA':'動画原本バイトSHA、凍結済み事前登録、学習/ホールドアウト分離を点検',
      'V48-CAPTURE':'初回PNGの原本・ROI・校正を結合する不変受領マニフェスト',
      'V48-API':'サーバ受領画像の初回セッションとクライアント申告ハッシュを区別',
      'V48-REAL':'実物束の独立GTと盲検評価の収集・統計検証',
      'V48-AWS':'本物のOpenCV5/AWSと耐久保存/ロール認可を実行証明',
      'V48-SCIENCE':'凍結済み事前登録・公平なD1/E1/E2/B比較の検証',
      'V48-UX':'実利用者が完了・保留・追加撮影を操作できるUIの検証'}
    ids={}
    for i in range(1,37):
        req=('V48-STAT' if i<=12 else 'V48-GT-BUNDLE' if i<=15 else
             'V48-GT-REGISTRY' if i<=17 else 'V48-GT-MEDIA' if i<=22 else
             'V48-CAPTURE' if i<=28 else 'V48-API')
        ids['V48-'+str(i).zfill(3)]=req
    testsuite=methods();assert len(testsuite)==36,len(testsuite)
    inventory={}
    for obj in testsuite:
        m=re.match('test_V48_(\\d{3})_',obj._testMethodName)
        assert m,obj.id()
        tid='V48-'+m.group(1);assert tid not in inventory
        inventory[tid]=obj.id()
    assert len(inventory)==36 and set(inventory)==set(ids)
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    old_ids={r['test_id'] for r in tests}
    for tid,full in sorted(inventory.items()):
        assert tid not in old_ids
        req=ids[tid];row={k:'' for k in cols}
        row.update(test_id=tid,requirement_id=req,category=req.split('-',1)[1],
         priority='BLOCKER' if int(tid[-3:]) in (1,13,14,16,17,18,23,24,29,30,31) else 'P0',
         setup='ローカル合成/有限モデル/モック、実物の外部GTやOpenCV5は未使用',
         input_or_stimulus=full,expected_oracle='unittest assertion',
         quantitative_gate='PASS on controlled local runtime',
         evidence='reports/v48_unittest_verbose.log',automation='AUTO',status='PASS',
         owner='ROLE:SOLO_DEVELOPER',test_purpose='CONFORMANCE',
         hypothesis_status='NOT_EVALUATED',evidence_status='LOCAL_RETEST_LOG',gate_stage='G0',
         threshold_status='CODE_ASSERTION_ONLY',planned_execution_min='2',
         claim_supported_if_pass='LOCAL_CONFORMANCE_ONLY_NOT_PHYSICAL_EFFECT',last_run_at=now,
         observed_result='PASS',evidence_sha256=digest,source_version='v4.8',
         evidence_tier='LOCAL_SYNTHETIC_PURE_CODE_OR_MOCK',
         methodology='real executed unittest, synthetic inputs only',
         test_execution_status='PASS',effect_hypothesis_status='NOT_EVALUATED',
         runtime_scope='LOCAL_OPENCV4_WITH_MOCKED_VERSION_WHERE_MARKED',evaluation_role='CONFORMANCE_TEST')
        tests.append(row)
        evidence.append(dict(test_method=full,result='PASS',
             runtime_scope='LOCAL_OPENCV4_WITH_MOCKED_V5_NO_REAL_GT',
             tool_version_claim='NO_GENUINE_OPENCV5_OR_AWS_TEST',
             evidence='reports/v48_unittest_verbose.log',evidence_sha256=digest,run_at_utc=now))
        traces.append(dict(test_id=tid,requirement_id=req,relation='PRIMARY',
            rationale='Executable v4.8 synthetic / pure code assertion; no independent efficacy evidence'))
    planned=[
     ('GATE-01','V48-AWS','AWS EC2実環境でOpenCV5のビルド・稼働を検証'),
     ('GATE-02','V48-AWS','S3/DynamoDBとKMS/IAM/認証・監査の実稼働'),
     ('GATE-03','V48-REAL','束単位で30以上独立する実GT原動画と装置校正'),
     ('GATE-04','V48-REAL','GTの盲検監査署名と損失・誤差の妥当性'),
     ('GATE-05','V48-SCIENCE','独立事前登録・乱数割付・主要評価項目の外部凍結'),
     ('GATE-06','V48-SCIENCE','E2 vs 固定2視点D1の本物の介入誤り評価'),
     ('GATE-07','V48-SCIENCE','E2 vs 単純適応E1とPCIG除去方式の比較'),
     ('GATE-08','V48-SCIENCE','E2 vs 経験者Bの元枚数完了率と全作業時間'),
     ('GATE-09','V48-UX','利用者が判断保留・再撮影・完了を操作可能なUIと試験'),
     ('GATE-10','V48-API','本物のOpenCV5実画像結果が追加視点/世界集合に及ぼす効果')]
    for suffix,req,desc in planned:
        tid='V48-'+suffix
        row={k:'' for k in cols}
        row.update(test_id=tid,requirement_id=req,category='REAL_OR_CLOUD',priority='BLOCKER',
             setup='本物のEC2/実物装置/第三者レビューが必要',
             input_or_stimulus=desc,expected_oracle='外部で再計算可能な生証拠',
             evidence='NOT_COLLECTED',status='NOT_RUN',owner='ROLE:EXTERNAL_OWNER_UNASSIGNED',
             test_purpose='EFFECT_OR_ELIGIBILITY',hypothesis_status='NOT_EVALUATED',
             evidence_status='NOT_COLLECTED',gate_stage='G1-G5',threshold_status='PREREG_REQUIRED',
             claim_supported_if_pass='CONDITIONAL_ONLY_AFTER_INDEPENDENT_REVIEW',
             source_version='v4.8',evidence_tier='REAL_WORLD_NOT_RUN',test_execution_status='NOT_RUN',
             runtime_scope='AWS_OR_REAL_WORLD_PENDING',evaluation_role='MANDATORY_REAL_GATE')
        tests.append(row);traces.append(dict(test_id=tid,requirement_id=req,relation='PRIMARY',
            rationale='Not run, no AWS / real GT or human experiment evidence collected'))
        ids[tid]=req
    assert len(tests)==637 and len(evidence)==386 and len(traces)==812
    # additional conceptual links, separate from independent test count.
    secondary=[('V48-001','V48-SCIENCE'),('V48-003','V48-UX'),('V48-013','V48-REAL'),
               ('V48-014','V48-REAL'),('V48-018','V48-REAL'),('V48-019','V48-GT-REGISTRY'),
               ('V48-023','V48-AWS'),('V48-024','V48-API'),('V48-029','V48-AWS'),
               ('V48-030','V48-SCIENCE')]
    for tid,req in secondary:
        traces.append(dict(test_id=tid,requirement_id=req,relation='SECONDARY',
            rationale='Secondary conceptual relevance; not an additional independent test'))
    assert len(traces)==822
    for rid,description in descriptions.items():
        primary=sorted(t for t,r in ids.items() if r==rid)
        all_related=sorted({x['test_id'] for x in traces if x['requirement_id']==rid})
        row={k:'' for k in req_cols}
        row.update(requirement_id=rid,requirement_type='v4.8追加仕様',requirement=description,
            gate='G1-G5' if rid in ('V48-AWS','V48-REAL','V48-SCIENCE','V48-UX') else 'G0',
            primary_test_count=len(primary),total_related_tests=len(all_related),
            primary_test_ids=';'.join(primary),all_related_test_ids=';'.join(all_related),
            design_status='SPECIFIED',implementation_status=('REAL_NOT_RUN' if rid in
                ('V48-AWS','V48-REAL','V48-SCIENCE','V48-UX') else 'LOCAL_VALIDATED'),
            real_world_validation='NOT_STARTED',
            acceptance_basis='Physical/empirical claims require independent ground truth and/or real AWS')
        reqs.append(row)
    assert len(reqs)==141
    tset={r['test_id'] for r in tests};rset={r['requirement_id'] for r in reqs}
    assert len(tset)==637 and len(rset)==141
    assert all(x['test_id'] in tset and x['requirement_id'] in rset for x in traces)
    assert all(any(x['test_id']==tid for x in traces) for tid in tset)
    assert all(any(x['requirement_id']==rid for x in traces) for rid in rset)
    assert collections.Counter(x['status'] for x in tests)=={'PASS':386,'NOT_RUN':251}
    write('v4.8_テスト台帳_637件.csv',tests,cols)
    write('v4.8_ローカル検算_386件.csv',evidence,ev_cols)
    write('v4.8_要求仕様_141件.csv',reqs,req_cols)
    write('v4.8_要求試験対応_822件.csv',traces,trace_cols)
    summary={'version':'v4.8','local_test_methods_pass':386,'planned_test_cases':637,
      'not_run':251,'requirements':141,'requirement_test_relations':822,
      'local_opencv_version':'4.13.0','actual_opencv5_executed':False,
      'actual_aws_workload_verified':False,'independent_physical_gt_verified':False,
      'real_efficacy_experiment_completed':False,'real_worker_ui_tested':False,
      'official_score_claim':None,'score_goal':96,
      'only_logged_evidence':'LOCAL_UNIT_TESTS_WITH_SYNTHETIC_OR_MOCK_INPUTS',
      'unittest_log_sha256':digest}
    (R/'reports/v48_verification_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    files=sorted(x for x in R.rglob('*') if x.is_file() and '__pycache__' not in x.parts and x.name!='SHA256SUMS_v48.txt'
                 and not x.name.endswith('.pyc') and x.name!='.DS_Store')
    manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(R))+'\n' for p in files)
    (R/'SHA256SUMS_v48.txt').write_text(manifest,encoding='utf-8')
    files.append(R/'SHA256SUMS_v48.txt')
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for f in sorted(files):z.write(f,str(f.relative_to(R)))
    print(json.dumps({'output':str(output),'files':len(files),**summary},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    a=p.parse_args();main(Path(a.output))
