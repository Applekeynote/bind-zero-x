# coding: utf-8
"""Regenerate BIND ZERO-X v4.4 deterministic local evidence and distribution.
Run from the extracted archive root. Does NOT conduct real GT/AWS/physical trials.
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime,timezone
from hashlib import sha256
from zipfile import ZipFile,ZIP_DEFLATED
import csv,os,subprocess,sys,unittest,json,collections

ROOT=Path(__file__).resolve().parent
OLD_CASES=ROOT/'v4.3_テストケース台帳_394件.csv'
OLD_REQ=ROOT/'v4.3_要求仕様_88件.csv'
OLD_LINK=ROOT/'v4.3_要求テスト多対多対応.csv'


def readcsv(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def writecsv(p,rows,fields):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)

def all_tests(suite):
    for t in suite:
        if isinstance(t,unittest.TestSuite):yield from all_tests(t)
        else:yield t

def main():
    env=dict(os.environ,PYTHONPATH=str(ROOT/'code'),PYTHONWARNINGS='ignore::ResourceWarning')
    cmd=[sys.executable,'-m','unittest','discover','-s','code','-p','test_*.py','-v']
    run=subprocess.run(cmd,env=env,cwd=ROOT,capture_output=True,text=True,timeout=120)
    full='$ '+' '.join(cmd)+'\n'+run.stdout+'\n'+run.stderr
    (ROOT/'v4.4_ローカル実行ログ.txt').write_text(full,encoding='utf-8')
    if run.returncode:raise RuntimeError('LOCAL_TEST_FAILURE: inspect v4.4_ローカル実行ログ.txt')
    import cv2
    loader=unittest.TestLoader()
    suite=loader.discover(str(ROOT/'code'),pattern='test_*.py',top_level_dir=str(ROOT/'code'))
    ids=sorted(t.id() for t in all_tests(suite))
    newids=sorted(t for t in ids if t.startswith('test_v44_'))
    expected_legacy=187
    if len(ids)-len(newids)!=expected_legacy:raise RuntimeError(f'LEGACY_COUNT_CHANGED {len(ids)}-{len(newids)}')
    cases=readcsv(OLD_CASES);requests=readcsv(OLD_REQ);links=readcsv(OLD_LINK)
    assert len(cases)==394 and len(requests)==88 and len(links)==543
    now=datetime.now(timezone.utc).isoformat(timespec='seconds')
    log_sha=sha256(full.encode()).hexdigest()
    evidence=[{'test_id':r['test_id'],'unittest_id':'V43_HISTORICAL_TRACE_MAPPING','status':r['status'],
               'tier':r['evidence_tier'],'evidence_sha256':r['evidence_sha256']} for r in cases if r['status']=='PASS']
    fields=list(cases[0]);linkfields=list(links[0]);reqfields=list(requests[0])
    requirement_definitions=[
      ('V44-CWC-OPT','証明','各世界の最適行動集合と最小衝突集合を適切に検出する', 'G0'),
      ('V44-CWC-OBS','証明','未知・観測不能・結果集合を分けて最悪後悔を過大に改善しない','G0'),
      ('V44-CWC-INTEGRITY','監査','全仮定と画像/観測IDをハッシュに結び出力と照合する','G0'),
      ('V44-FIG','画像/診断','3チャンネルの観測欠測と更新版を記録','G0'),
      ('V44-GATE','安全制御','証拠が足りない状況で先行ルールが介入を指示しても拒否','G0'),
      ('V44-CV-SIGMA','画像品質','未校正の不確実性を0として表示しない','G0'),
      ('V44-RESEARCH-API','クラウド開発','研究専用APIの認証・限界・版強制・容量制限','G0'),
      ('V44-MTRACK','独創性評価','Eと固定視点Dの真の実益を比較','G5'),
      ('V44-UTRACK','社会効果評価','Eと熟練者Bの実効性能を比較','G6'),
      ('V44-AWS-REAL','大会必須','実AWSでOpenCV5を実行し保存/再計画を追跡','G3')]
    for rid,typ,description,gate in requirement_definitions:
        item=dict.fromkeys(reqfields,'')
        item.update(requirement_id=rid,requirement_type=typ,requirement=description,gate=gate,
                    design_status='SPECIFIED',implementation_status='LOCAL_ONLY' if gate=='G0' else 'NOT_RUN',
                    real_world_validation='NOT_RUN',acceptance_basis='CURRENT_LOCAL_SCOPE_ONLY_OR_REAL_HOLDOUT_REQUIRED')
        requests.append(item)
    def req_for(testname):
        if 'WitnessSecurityV44' in testname:
            if any(x in testname for x in ('hash','certificate','image_content','model_version','video_sha','loss_nonopt')):return 'V44-CWC-INTEGRITY'
            if any(x in testname for x in ('unknown','occlusion','possible_outcome','view_without','falsification')):return 'V44-CWC-OBS'
            return 'V44-CWC-OPT'
        if 'FIGV44' in testname:return 'V44-FIG'
        if 'UnifiedGateV44' in testname:
            return 'V44-CV-SIGMA' if 'sigma' in testname else 'V44-GATE'
        if 'ApiV44' in testname:return 'V44-RESEARCH-API'
        raise ValueError('UNMAPPED_V44_TEST '+testname)
    for i,name in enumerate(newids,1):
        tid=f'V44-LOCAL-{i:03d}';req=req_for(name)
        category='API' if 'ApiV44' in name else 'AGENT'
        if 'FIGV44' in name:category='CV'
        item=dict.fromkeys(fields,'')
        item.update(test_id=tid,requirement_id=req,category=category,priority='BLOCKER' if category=='API' or req in ('V44-CWC-OPT','V44-GATE') else 'P0',
                    setup='code/'+name.split('.')[0]+'.py::'+name.split('.')[-1],input_or_stimulus='Deterministic regression fixture in source',
                    expected_oracle='unittest assertion passes',quantitative_gate='exact assert in source',evidence='v4.4_ローカル実行ログ.txt',
                    automation='AUTO',status='PASS',owner='ROLE:SOLO_DEVELOPER',test_purpose='CONFORMANCE',
                    hypothesis_status='NOT_EVALUATED',evidence_status='COLLECTED_LOCAL',gate_stage='G0',
                    threshold_status='FIXED_CODE_ASSERTIONS',planned_execution_min='1',
                    claim_supported_if_pass='NONE_ALONE; does not demonstrate real superiority',
                    last_run_at=now,observed_result=name+':PASS',evidence_sha256=log_sha,
                    source_version='v4.4',evidence_tier='LOCAL_SYNTHETIC_OR_PURE_CODE',
                    preparation_min='0',collection_min='0',analysis_min='1',repeat_reserve_min='1',
                    methodology='Synthetic/pure-code regression',test_execution_status='PASS',
                    effect_hypothesis_status='NOT_EVALUATED',runtime_scope='LOCAL_OPENCV_'+cv2.__version__,
                    evaluation_role='CONFORMANCE_TEST')
        cases.append(item)
        links.append(dict(test_id=tid,requirement_id=req,relation='PRIMARY',rationale='Exact runnable method: '+name))
        evidence.append({'test_id':tid,'unittest_id':name,'status':'PASS','tier':'LOCAL_SYNTHETIC_OR_PURE_CODE','evidence_sha256':log_sha})
    # Evidence-oriented main study gates, all NOT_RUN and not hidden inside local PASS.
    real_specs=[
      ('M01','V44-MTRACK','AGENT','BLOCKER','E-vs-D wrong correction and view count','Prospective holdout, fixed matched budget, pre-registered success criterion'),
      ('M02','V44-MTRACK','AGENT','P0','Common optimal action saves extra image','Real noncontact paired world disambiguation and time'),
      ('M03','V44-MTRACK','AGENT','P0','Unobservable conditions abstain instead of guessing','Independent occlusion GT and selective accuracy'),
      ('U01','V44-UTRACK','PHYS','BLOCKER','E-vs-skilled-B all-sheets job completion','Independent configurations, matched challenge Q'),
      ('U02','V44-UTRACK','PHYS','P0','E-vs-B total job time with split bundles','All completions/failures included; cluster uncertainty'),
      ('U03','V44-UTRACK','PHYS','P0','E-vs-B D_res and K_res separately','Independent physical GT and all abort records'),
      ('UX01','V44-UTRACK','UX','P0','Actual user view burden and abstention','Independent task observation, no simulated scores'),
      ('GT01','V44-CV-SIGMA','CV','BLOCKER','Independent planar mm GT for camera tracking','0/2/5/10 mm, common rotations, real camera'),
      ('AWS01','V44-AWS-REAL','CLOUD','BLOCKER','AWS EC2 real OpenCV5 version/runtime','Real request ID, Docker digest, image output'),
      ('AWS02','V44-AWS-REAL','CLOUD','BLOCKER','AWS S3/DynamoDB authenticated iterative flow','Owner/version/idempotency and approval independent E2E')]
    for key,req,category,priority,title,expected in real_specs:
        tid='V44-REAL-'+key
        item=dict.fromkeys(fields,'')
        item.update(test_id=tid,requirement_id=req,category=category,priority=priority,
                    setup='Pre-registration required: v4.4_実物比較実験_前登録と中止条件.md',
                    input_or_stimulus=title,expected_oracle=expected,quantitative_gate='TO_FREEZE_BEFORE_HOLDOUT',
                    evidence='REQUIRES_REAL_RAW_DATA',automation='SEMI_AUTO' if category in ('PHYS','CV') else 'MANUAL',
                    status='NOT_RUN',owner='ROLE:SOLO_DEVELOPER',test_purpose='EFFECT_VALIDATION',
                    hypothesis_status='NOT_EVALUATED',evidence_status='NOT_COLLECTED',gate_stage='G5' if req=='V44-MTRACK' else ('G6' if req=='V44-UTRACK' else 'G3'),
                    threshold_status='TO_FREEZE_AFTER_PILOT_BEFORE_HOLDOUT',planned_execution_min='VARIABLE_NOT_ESTIMATED',
                    claim_supported_if_pass='Only the preregistered comparison and observed uncertainty',
                    last_run_at='',observed_result='',evidence_sha256='',source_version='v4.4',
                    evidence_tier='REAL_NOT_RUN',preparation_min='TBD',collection_min='TBD',analysis_min='TBD',repeat_reserve_min='TBD',
                    methodology='Independent actual field or AWS evidence required',test_execution_status='NOT_RUN',
                    effect_hypothesis_status='NOT_EVALUATED',runtime_scope='NOT_VERIFIED',evaluation_role='EFFECT_VALIDATION')
        cases.append(item)
        links.append(dict(test_id=tid,requirement_id=req,relation='PRIMARY',rationale='Prospective independent proof; not run'))
    # Correct v4.3 uncovered requirements, preserving historical test associations.
    candidate_links={'V43-BRIDGE':'V44-GATE','V43-SAFETY':'V44-GATE'}
    for rid,target in candidate_links.items():
        for row in links:
            if row['requirement_id']==target:
                links.append(dict(test_id=row['test_id'],requirement_id=rid,relation='SECONDARY',
                                  rationale='v4.4 integrated regression exercises prior requirement'))
                break
    seen=set();ordered=[]
    for row in links:
        key=(row['test_id'],row['requirement_id'])
        if key not in seen:seen.add(key);ordered.append(row)
    links=ordered
    idset=[r['test_id'] for r in cases];reqset=[r['requirement_id'] for r in requests]
    assert len(idset)==len(set(idset)) and len(reqset)==len(set(reqset))
    assert all(x['test_id'] in idset and x['requirement_id'] in reqset for x in links)
    map_by_req=collections.defaultdict(list)
    for link in links:map_by_req[link['requirement_id']].append(link)
    for req in requests:
        grouped=map_by_req.get(req['requirement_id'],[])
        req['primary_test_ids']=';'.join(x['test_id'] for x in grouped if x['relation']=='PRIMARY')
        req['all_related_test_ids']=';'.join(x['test_id'] for x in grouped)
        req['primary_test_count']=str(sum(x['relation']=='PRIMARY' for x in grouped))
        req['total_related_tests']=str(len(grouped))
    assert all(x['total_related_tests']!='0' for x in requests), 'Uncovered requirement'
    writecsv(ROOT/'v4.4_テストケース台帳.csv',cases,fields)
    writecsv(ROOT/'v4.4_要求仕様.csv',requests,reqfields)
    writecsv(ROOT/'v4.4_要求試験多対多対応.csv',links,linkfields)
    writecsv(ROOT/'v4.4_ローカル実行証拠.csv',evidence,list(evidence[0]))
    assert len(evidence)==len(ids)==sum(r['status']=='PASS' for r in cases)
    tally={'cases':len(cases),'local_pass':len(ids),'not_run':sum(x['status']=='NOT_RUN' for x in cases),
           'requirements':len(requests),'links':len(links),'opencv_local':cv2.__version__,
           'aws_opencv5':'NOT_RUN','real_gt':'NOT_RUN','human_benchmark':'NOT_RUN',
           'actual_unittest_methods_mapped_from_v44':len(newids),'historical_unittest_total':187,
           'log_sha256':log_sha,'created_at_utc':now}
    (ROOT/'v4.4_検証結果と制約.json').write_text(json.dumps(tally,ensure_ascii=False,indent=2),encoding='utf-8')
    skip={'SHA256SUMS_v44.txt','BIND_ZERO_X_v4.4_95点超目標_証明付き能動知覚_改訂一式.zip'}
    files=[f for f in sorted(ROOT.rglob('*')) if f.is_file() and f.name not in skip and '__pycache__' not in f.parts]
    (ROOT/'SHA256SUMS_v44.txt').write_text(''.join(f'{sha256(f.read_bytes()).hexdigest()}  {f.relative_to(ROOT).as_posix()}\n' for f in files),encoding='utf-8')
    files.append(ROOT/'SHA256SUMS_v44.txt')
    target=ROOT/'BIND_ZERO_X_v4.4_95点超目標_証明付き能動知覚_改訂一式.zip'
    with ZipFile(target,'w',ZIP_DEFLATED,compresslevel=9) as z:
        for f in files:z.write(f,f.relative_to(ROOT).as_posix())
    print(json.dumps({**tally,'zip_size':target.stat().st_size,'file_count':len(files)},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
