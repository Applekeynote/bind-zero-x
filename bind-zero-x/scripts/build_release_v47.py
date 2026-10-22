# -*- coding: utf-8 -*-
"""Build repeatable v4.7 distribution from unpacked v4.6 inputs.
Do not promote mocked/OpenCV4 unit tests to physical/AWS empirical evidence.
"""
from pathlib import Path
import sys,csv,subprocess,hashlib,zipfile,unittest,datetime,json,collections
R=Path(__file__).resolve().parents[1]

def load(name):
    with (R/name).open('r',encoding='utf-8-sig',newline='') as fp:
        reader=csv.DictReader(fp)
        return list(reader),reader.fieldnames

def write(name,rows,cols):
    with (R/name).open('w',encoding='utf-8-sig',newline='') as fp:
        writer=csv.DictWriter(fp,fieldnames=cols,extrasaction='ignore');writer.writeheader();writer.writerows(rows)

def main():
    cmd=[sys.executable,'-m','unittest','discover','-p','test_*.py','-v']
    run=subprocess.run(cmd,cwd=R/'code',stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=180)
    log=R/'reports/v47_unittest_verbose.log';log.write_text(run.stdout,encoding='utf-8')
    if run.returncode!=0:raise RuntimeError('TEST_FAILED '+run.stdout[-3500:])
    assert 'Ran 350 tests' in run.stdout,run.stdout[-500:]
    evidence_hash=hashlib.sha256(log.read_bytes()).hexdigest()
    tests,headers=load('v4.6_テスト台帳_550件.csv')
    previous,prev_cols=load('v4.6_ローカル検算_317件.csv')
    reqs,req_cols=load('v4.6_要求仕様_121件.csv')
    traces,trace_cols=load('v4.6_要求試験対応_717件.csv')
    assert len(tests)==550 and len(previous)==317 and len(reqs)==121 and len(traces)==717
    suite=unittest.TestLoader().discover(str(R/'code'),pattern='test_v47_*.py',top_level_dir=str(R/'code'))
    def walk(s):
        for obj in s:
            if isinstance(obj,unittest.TestSuite):yield from walk(obj)
            else:yield obj
    items=list(walk(suite))
    assert len(items)==33,len(items)
    method_names={t._testMethodName:t.id() for t in items}
    assert len(method_names)==33
    req_map={
        'V47-CAL':'校正bool型・参照平面の正当性と防偽装',
        'V47-ROI':'ROI内の可視点に限定したSE(2)最大変位',
        'V47-RISK':'絶対損失を考慮した視点選択と保守的ABSTAIN',
        'V47-GT':'サーバ固定・独立GT記録と誤差範囲による観測トークン',
        'V47-LINK':'セッション・親子観測ID・撮影・証明の一貫性',
        'V47-AGENT':'画像変化が後続の世界集合・計画を変える研究用結合',
        'V47-EXPERIMENT':'独立GTの作成と第三者承認の責務分離',
        'V47-STAT':'元全枚数・総時間・対照の厳格入力検証',
        'V47-AWS':'真正OpenCV 5のAWS処理・監査ログを独立に実証',
        'V47-REAL':'物理GT・D0/D1/E1/E2/B比較を実行し効果の限界も報告'}
    primary={}
    for i in range(1,34):
        if i in (1,2,3,4,5,22,23):v='V47-CAL'
        elif i in (6,7):v='V47-ROI'
        elif i in (8,9,10):v='V47-RISK'
        elif i in tuple(range(11,21)):v='V47-GT'
        elif i in (21,24,25):v='V47-LINK'
        elif i in (26,27):v='V47-AGENT'
        elif i in (28,29,30,31):v='V47-EXPERIMENT'
        elif i in (32,33):v='V47-STAT'
        else:raise AssertionError(i)
        primary[f'V47-{i:03d}']=v
    planned=[('V47-GATE-01','V47-AWS','実AWSのOpenCV5 `cv2.getBuildInformation()` とコンテナdigestの記録'),
             ('V47-GATE-02','V47-REAL','実物3種の束で独立GT取得・P95誤差算出'),
             ('V47-GATE-03','V47-AGENT','実画像の証拠で再観測とプラン変更を実証'),
             ('V47-GATE-04','V47-REAL','E2対固定D1の誤介入・撮影コスト比較'),
             ('V47-GATE-05','V47-REAL','E2対単純適応E1の比較（負の結果も公開）'),
             ('V47-GATE-06','V47-REAL','E2対経験者Bの全枚数完了率・総時間'),
             ('V47-GATE-07','V47-AWS','S3/DynamoDB/認証/IAM/監査のAWS E2E'),
             ('V47-GATE-08','V47-EXPERIMENT','物理本試験前の外部前登録凍結と盲検レビュー')]
    primary.update({x:y for x,y,_ in planned})
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    by_id={t['test_id']:t for t in tests}
    for name,full in method_names.items():
        import re
        m=re.match(r'test_(V47-\d{3})_',name.replace('V47_', 'V47-'))
        # The name is test_V47_001_foo; parse directly
        m=re.match(r'test_V47_(\d{3})_',name)
        assert m,name
        tid='V47-'+m.group(1)
        assert tid not in by_id
        cat={'CAL':'MEASUREMENT','ROI':'CV','RISK':'AGENT','GT':'GT_GATE',
             'LINK':'API','AGENT':'CV_AGENT','EXPERIMENT':'GT_PROTOCOL','STAT':'STAT'}[primary[tid].split('-')[1]]
        row={k:'' for k in headers}
        row.update(test_id=tid,requirement_id=primary[tid],category=cat,
          priority='BLOCKER' if int(m.group(1)) in (1,2,6,8,21,22,24,25,26,27) else 'P0',
          setup='ローカル合成・数理・モック、実物の測定ではない',
          input_or_stimulus=full,expected_oracle='unittest assertion PASS',
          quantitative_gate='1/1 PASS on local runtime',evidence='reports/v47_unittest_verbose.log',
          automation='AUTO',status='PASS',owner='ROLE:SOLO_DEVELOPER',test_purpose='CONFORMANCE',
          hypothesis_status='NOT_EVALUATED',evidence_status='LOCAL_RETEST_LOG',gate_stage='G0',
          threshold_status='CODE_ASSERTION_ONLY',planned_execution_min='2',
          claim_supported_if_pass='LOCAL_CONFORMANCE_ONLY_NO_AWS_OR_REAL_GT',last_run_at=now,
          observed_result='PASS',evidence_sha256=evidence_hash,source_version='v4.7',
          evidence_tier='LOCAL_SYNTHETIC_OR_PURE_CODE',methodology='offline deterministic pytest/unittest',
          test_execution_status='PASS',effect_hypothesis_status='NOT_EVALUATED',
          runtime_scope='LOCAL_OPENCV4_AND_MOCKED_V5_NO_REAL_GT',evaluation_role='CONFORMANCE_TEST')
        tests.append(row)
        previous.append(dict(test_method=full,result='PASS',runtime_scope=row['runtime_scope'],
            tool_version_claim='OPENCV4_AND_MOCKED_OPENCV5_NOT_GENUINE_V5',
            evidence=row['evidence'],evidence_sha256=evidence_hash,run_at_utc=now))
        traces.append(dict(test_id=tid,requirement_id=primary[tid],relation='PRIMARY',
            rationale='Executable v4.7 regression test; only local validity'))
    for tid,rid,desc in planned:
        row={k:'' for k in headers}
        row.update(test_id=tid,requirement_id=rid,category='AWS' if rid=='V47-AWS' else 'REAL_PHYSICAL',
            priority='BLOCKER',setup='外部の実AWS/実物装置/独立評価が必要',
            input_or_stimulus=desc,expected_oracle='独立記録・実行ログ・比較完了',
            evidence='NOT_COLLECTED',automation='SEMI_AUTO',status='NOT_RUN',
            owner='ROLE:SOLO_DEVELOPER+INDEPENDENT_REVIEWER_PLANNED',test_purpose='EFFECT_OR_ELIGIBILITY',
            hypothesis_status='NOT_EVALUATED',evidence_status='NOT_COLLECTED',gate_stage='G1-G5',
            threshold_status='PREREGISTRATION_REQUIRED',planned_execution_min='VARIABLE',
            claim_supported_if_pass='CONDITIONAL_ONLY_AFTER_INDEPENDENT_REVIEW',source_version='v4.7',
            evidence_tier='REAL_NOT_RUN',test_execution_status='NOT_RUN',
            effect_hypothesis_status='NOT_EVALUATED',runtime_scope='EXTERNAL_PENDING',
            evaluation_role='MANDATORY_REAL_OR_CLOUD_GATE')
        tests.append(row)
        traces.append(dict(test_id=tid,requirement_id=rid,relation='PRIMARY',
            rationale='Not run — must complete using actual AWS/physical apparatus'))
    assert len(tests)==591,len(tests)
    assert len(previous)==350,len(previous)
    assert len({r['test_id'] for r in tests})==591
    assert len({r['test_method'] for r in previous})==350
    # Additional cross-cutting links are intentionally secondary (not double counting).
    for tid,rid in [('V47-001','V47-GT'),('V47-006','V47-AGENT'),('V47-008','V47-AGENT'),
                    ('V47-021','V47-AGENT'),('V47-024','V47-LINK'),('V47-026','V47-GT'),
                    ('V47-027','V47-GT'),('V47-028','V47-REAL'),('V47-032','V47-REAL')]:
        if primary[tid]!=rid:
            traces.append(dict(test_id=tid,requirement_id=rid,relation='SECONDARY',
                rationale='Secondary traceability; no new independent evidence'))
    assert len(traces)==766,len(traces)
    for req_id,desc in req_map.items():
        pids=sorted(t for t,v in primary.items() if v==req_id)
        linked=sorted({x['test_id'] for x in traces if x['requirement_id']==req_id})
        row={k:'' for k in req_cols}
        row.update(requirement_id=req_id,requirement_type='v4.7追加要件',requirement=desc,
          gate='G1-G5' if req_id in ('V47-AWS','V47-REAL') else 'G0',
          primary_test_count=str(len(pids)),total_related_tests=str(len(linked)),
          primary_test_ids=';'.join(pids),all_related_test_ids=';'.join(linked),
          design_status='SPECIFIED',implementation_status=('NOT_VERIFIED' if req_id in ('V47-AWS','V47-REAL') else 'LOCAL_PARTIAL'),
          real_world_validation='NOT_STARTED',acceptance_basis='Real AWS/independent GT mandatory for empirical claim')
        reqs.append(row)
    assert len(reqs)==131 and len(traces)==766
    test_ids={x['test_id'] for x in tests};req_ids={x['requirement_id'] for x in reqs}
    assert all(x['test_id'] in test_ids and x['requirement_id'] in req_ids for x in traces)
    assert all(any(x['test_id']==tid for x in traces) for tid in test_ids)
    assert all(any(x['requirement_id']==rid for x in traces) for rid in req_ids)
    c=collections.Counter(x['status'] for x in tests)
    assert c=={'PASS':350,'NOT_RUN':241},c
    write('v4.7_テスト台帳_591件.csv',tests,headers)
    write('v4.7_ローカル検算_350件.csv',previous,prev_cols)
    write('v4.7_要求仕様_131件.csv',reqs,req_cols)
    write('v4.7_要求試験対応_766件.csv',traces,trace_cols)
    summary={'package_version':'v4.7','test_cases':591,'local_pass':350,'not_run':241,
        'requirements':131,'traces':766,'cv_in_container':'4.13.0_or_runtime_value_not_a_V5_claim',
        'physical_ground_truth_trials':0,'aws_running_tests':0,'opencv5_executed':False,
        'simulation_or_mock_included':True,'code_test_log_sha256':evidence_hash,
        'evidence_scope':'LOCAL_PURE_CODE_AND_MOCKED_CV5_ONLY',
        'official_score_claim':None,'target_score':96}
    (R/'reports/v47_audit_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    # Do not include package checksum file in its own manifest.
    excluded={'SHA256SUMS_v47.txt'}
    files=sorted(q for q in R.rglob('*') if q.is_file() and '.pyc' not in q.suffix and
        '__pycache__' not in q.parts and q.name not in excluded and q.name!='patch_v47.py' and not q.name.endswith('.zip') and not (q.parent.name=='reports' and q.name in {'v47_initial_test.log','v47_gate_test.log','v47_after_step_binding.log','v47_existing.log','v47_after_experiment_tests.log','v47_new_regressions.log','v47_full_tests.log'}))
    manifest=''.join(f'{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.relative_to(R).as_posix()}\n' for f in files)
    (R/'SHA256SUMS_v47.txt').write_text(manifest,encoding='utf-8')
    files.append(R/'SHA256SUMS_v47.txt')
    name='BIND_ZERO_X_v4.7_95点超目標_監査欠陥修正・独創性評価_改訂一式.zip'
    out=Path('/mnt/data')/name
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        for f in files:z.write(f,f.relative_to(R).as_posix())
    # Separate extraction and hash verification
    verify=Path('/mnt/data/bzx_v47_fresh_verify')
    verify.mkdir(exist_ok=True)
    with zipfile.ZipFile(out) as z:z.extractall(verify)
    for line in (verify/'SHA256SUMS_v47.txt').read_text(encoding='utf-8').splitlines():
        digest,path=line.split('  ',1)
        assert hashlib.sha256((verify/path).read_bytes()).hexdigest()==digest,path
    retest=subprocess.run(cmd,cwd=verify/'code',stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=180)
    if retest.returncode or 'Ran 350 tests' not in retest.stdout:
        raise RuntimeError('FRESH_EXTRACTION_TEST_FAILURE '+retest.stdout[-3500:])
    print('Release file:',out,'size:',out.stat().st_size,'members:',len(files))
    print('Manifest digest files:',len(files)-1,'fresh extraction:350/350 PASS')
    print('Ledger',dict(c),'requests',len(reqs),'links',len(traces),'summary',summary)

if __name__=='__main__':main()
