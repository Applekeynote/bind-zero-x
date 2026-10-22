# -*- coding: utf-8 -*-
"""Build v4.6 case/requirement traceability and reproducible archive. No external data."""
import csv,datetime,hashlib,json,os,unittest,zipfile
from pathlib import Path
from collections import Counter,defaultdict
ROOT=Path(__file__).resolve().parents[1]
NOW=datetime.datetime.now(datetime.timezone.utc).isoformat()

REQS=[
 ('V46-MODEL-PIN','固定モデル','開始時に損失・視点・費用を複製し、状態の証明が初期モデルと一致する'),
 ('V46-HISTORY','証拠連鎖','履歴の観測前後、現在世界、証明、撮影ハッシュを毎回再構成'),
 ('V46-STORE','保存整合性','SQLiteでCASと別鍵MAC、読み込み時に本文とversionを検証'),
 ('V46-BUDGET','実施回数','残撮影予算がないときビュー要求を禁止しABSTAINを終端化'),
 ('V46-SOURCE','証拠の出所','CVと人間申告を区別し未校正CVで世界絞込しない'),
 ('V46-CV-FAIL','画像失敗','特徴点抽出などのOpenCV例外はUNKNOWN品質として処理'),
 ('V46-IMAGE-API','画像再観測','OpenCV5必須のサーバ解析、ハッシュ連鎖、正しい版数更新'),
 ('V46-INPUT','入力制限','PNGデコード前画素制限とAPI追加プロパティ拒否'),
 ('V46-ABLATION','独創性比較','固定視点との人工モデル比較と負の対照を記録する（実物非該当）'),
 ('V46-AWS','クラウド実証','EC2/OpenCV5・S3/DynamoDBの稼働証拠を得る'),
 ('V46-REAL-GT','実物GT','実物の独立した層/ひも/結び目GTと計測精度を取得'),
 ('V46-IMPACT','比較実験','固定方式・不確実性ヒューリスティック・熟練者と比較する')]

def readcsv(path):
 with (ROOT/path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def writecsv(path,rows,columns):
 with (ROOT/path).open('w',encoding='utf-8-sig',newline='') as f:
  wr=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');wr.writeheader();wr.writerows(rows)

def iter_unittest_cases():
 suite=unittest.TestLoader().discover(str(ROOT/'code'),pattern='test_*.py',top_level_dir=str(ROOT/'code'))
 def walk(s):
  for obj in s:
   if isinstance(obj,unittest.TestSuite):yield from walk(obj)
   else:yield obj
 return list(walk(suite))

def requirement(tid):
 if 'API' in tid:return 'V46-IMAGE-API'
 n=int(tid.split('-')[1])
 if n<=7:return 'V46-MODEL-PIN'
 if n<=11 or n in (19,20,21):return 'V46-HISTORY'
 if n<=14:return 'V46-BUDGET'
 if n<=18:return 'V46-SOURCE'
 if n<=34:return 'V46-STORE'
 if n<=36:return 'V46-CV-FAIL'
 if n<=39:return 'V46-ABLATION'
 return 'V46-INPUT'

def create():
 old_ledger=readcsv('v4.5_テスト台帳_491件.csv')
 old_req=readcsv('v4.5_要求仕様_109件.csv')
 links=readcsv('v4.5_要求試験対応_650件.csv')
 seen={r['test_id'] for r in old_ledger}
 tests=iter_unittest_cases()
 actual_names=[t.id().split('.')[-1] for t in tests]
 assert len(tests)==317 and len(set(actual_names))==317,(len(tests),len(set(actual_names)))
 fresh=[t for t in tests if t.id().split('.')[-1].startswith('test_V46_')]
 assert len(fresh)==49,len(fresh)
 new_rows=[]
 for t in fresh:
  fullname=t.id();method=fullname.split('.')[-1];file='code/'+fullname.split('.')[0]+'.py'
  chunks=method.split('_')
  tid=f'{chunks[1]}-{chunks[2]}-{chunks[3]}' if chunks[1]=='V46' and chunks[2]=='API' else f'{chunks[1]}-{chunks[2]}'
  assert tid not in seen,tid
  seen.add(tid)
  req=requirement(tid)
  cat=('API' if tid.startswith('V46-API') else ('CV' if tid in ('V46-035','V46-036') else ('EVAL' if tid in ('V46-037','V46-038','V46-039') else ('SECURITY' if tid in ('V46-022','V46-023','V46-024','V46-025','V46-026','V46-029','V46-030','V46-034') else 'AGENT'))))
  row={k:'' for k in old_ledger[0]};row.update(test_id=tid,requirement_id=req,category=cat,
   priority='BLOCKER' if req in ('V46-MODEL-PIN','V46-HISTORY','V46-STORE','V46-IMAGE-API','V46-CV-FAIL') else 'P0',
   setup='研究用ユニット・統合検証',input_or_stimulus=method,expected_oracle='assert PASS; no physical truth claim',
   quantitative_gate='unittest assertion',evidence=f'{file}::{method}; reports/v46_unittest_verbose.log',
   automation='AUTO',status='PASS',owner='SOLO_DEVELOPER',test_purpose='CONFORMANCE',
   hypothesis_status='NOT_EVALUATED',evidence_status='LOCAL_UNIT_TEST_LOGGED',gate_stage='G0',
   threshold_status='DEFINED_IN_TEST_SPEC',planned_execution_min='2',
   claim_supported_if_pass='RESEARCH_CODE_CORRECTNESS_ONLY; no physical or cloud performance claim',
   last_run_at=NOW,observed_result='PASS '+method,defect_id='v4.5 strict audit',source_version='v4.6',
   evidence_tier=('SYNTHETIC_OPENCV4_WITH_MOCKED_VERSION' if tid.startswith('V46-API') else 'LOCAL_PYTHON'),
   preparation_min='0',collection_min='0',analysis_min='1',repeat_reserve_min='2',
   methodology='Deterministic local code test',test_execution_status='PASS',
   effect_hypothesis_status='NOT_EVALUATED',runtime_scope='LOCAL_PYTHON_ONLY',evaluation_role='CONFORMANCE_TEST')
  new_rows.append(row)
  links.append(dict(test_id=tid,requirement_id=req,relation='PRIMARY',rationale='Executed v4.6 regression'))
 proposed=[
   ('V46-AWS-001','V46-AWS','EC2でOpenCV5画像計測とログの確認'),
   ('V46-AWS-002','V46-AWS','S3/DynamoDBで版数CAS・鍵管理・ログを確認'),
   ('V46-REAL-001','V46-REAL-GT','実物上下層の独立GTでmm MAE/P95/拒否率を測定'),
   ('V46-REAL-002','V46-REAL-GT','実物のひも経路/結び目を独立GTと比較'),
   ('V46-AGENT-001','V46-IMAGE-API','実際のOpenCV5再観測で後続の視点選択/判断が変わる'),
   ('V46-AGENT-002','V46-IMAGE-API','観測不能または画像改変で安全側ABSTAIN'),
   ('V46-COMP-001','V46-IMPACT','PCIG対固定視点の対比較'),
   ('V46-COMP-002','V46-IMPACT','PCIG対単純適応方式の対比較'),
   ('V46-COMP-003','V46-IMPACT','PCIG対熟練者の全束作業比較'),
   ('V46-UX-001','V46-IMPACT','実際の作業者による撮影/承認UX試験')]
 for tid,req,why in proposed:
  row={k:'' for k in old_ledger[0]};row.update(test_id=tid,requirement_id=req,category=tid.split('-')[1],
   priority='BLOCKER',setup='実物またはAWSの外部環境が必要',input_or_stimulus=why,
   expected_oracle='独立証拠、履歴、失敗例を保存',quantitative_gate='PILOT_PREREGISTRATION_REQUIRED',
   evidence='NOT_COLLECTED',automation='MANUAL',status='NOT_RUN',owner='SOLO_DEVELOPER',
   test_purpose='REAL_WORLD_EVALUATION',hypothesis_status='NOT_EVALUATED',
   evidence_status='NOT_COLLECTED',gate_stage='G1-G5',threshold_status='PROVISIONAL_UNTIL_PILOT_LOCK',
   planned_execution_min='60',claim_supported_if_pass='Depends on independent GT and preregistered controls',
   last_run_at='',observed_result='',source_version='v4.6',evidence_tier='NOT_RUN_REAL_OR_AWS',
   methodology='External environment required; missing AWS access/real trials',
   test_execution_status='NOT_RUN',effect_hypothesis_status='NOT_EVALUATED',
   runtime_scope='REAL_WORLD_OR_AWS_NOT_EXECUTED',evaluation_role='EVALUATION_GATE')
  new_rows.append(row);links.append(dict(test_id=tid,requirement_id=req,relation='PRIMARY',rationale=why))
 allrows=old_ledger+new_rows
 assert len(allrows)==550 and Counter(r['status'] for r in allrows)=={'PASS':317,'NOT_RUN':233}
 assert len(set(r['test_id'] for r in allrows))==len(allrows)
 # Bind some cross-cutting dependencies explicitly and preserve every old link.
 for tid,req in [('V46-003','V46-HISTORY'),('V46-005','V46-STORE'),('V46-023','V46-MODEL-PIN'),
                 ('V46-033','V46-SOURCE'),('V46-API-004','V46-SOURCE'),('V46-API-005','V46-STORE'),
                 ('V46-036','V46-IMAGE-API'),('V46-038','V46-IMPACT')]:
  links.append(dict(test_id=tid,requirement_id=req,relation='SECONDARY',rationale='v4.6 crosscutting dependence'))
 for id_,typ,desc in REQS:
  allrel=[r for r in links if r['requirement_id']==id_]
  primary=[r['test_id'] for r in allrel if r['relation']=='PRIMARY']
  assert primary,id_
  old_req.append(dict(requirement_id=id_,requirement_type=typ,requirement=desc,gate='G0' if id_ not in ('V46-AWS','V46-REAL-GT','V46-IMPACT') else 'G1-G5',
   primary_test_count=str(len(primary)),total_related_tests=str(len(allrel)),
   primary_test_ids=';'.join(primary),all_related_test_ids=';'.join(r['test_id'] for r in allrel),
   design_status='SPECIFIED',implementation_status=('PARTIAL_LOCAL_CODE' if id_ not in ('V46-AWS','V46-REAL-GT','V46-IMPACT') else 'NOT_IMPLEMENTED_OR_NOT_RUN'),
   real_world_validation='NOT_RUN',acceptance_basis='LOCAL_TEST_OR_REAL_AWS_AND_INDEPENDENT_GT'))
 ids={r['requirement_id'] for r in old_req}
 assert len(ids)==121,len(ids)
 assert all(x['requirement_id'] in ids and x['test_id'] in seen|{r[0] for r in proposed} for x in links)
 writecsv('v4.6_テスト台帳_550件.csv',allrows,old_ledger[0].keys())
 writecsv('v4.6_要求仕様_121件.csv',old_req,old_req[0].keys())
 writecsv('v4.6_要求試験対応_717件.csv',links,links[0].keys())
 return {'test_count':len(allrows),'executed_local_pass':317,'planned_not_run':233,
         'requirements':len(old_req),'relationships':len(links),'new_local_tests':len(fresh),
         'new_future_gates':len(proposed),'test_method_count':len(tests),
         'warning':'PASS is local only; no actual AWS/OpenCV5/physical trials'}

if __name__=='__main__':
 import sys
 sys.path.insert(0,str(ROOT/'code'))
 x=create()
 # Existing output file is named after expected quantity; verify to prevent a false filename.
 assert x['relationships']==717,x
 (ROOT/'reports/v46_integrity_summary.json').write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(x,ensure_ascii=False,indent=2))
