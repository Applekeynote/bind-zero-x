# -*- coding: utf-8 -*-
"""Standalone post-extraction integrity check. Does not claim external validation."""
import csv,hashlib,json,ast
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
def rows(name):
 with (ROOT/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
 bad=[]
 for line in (ROOT/'SHA256SUMS_v46.txt').read_text().splitlines():
  if not line:continue
  digest,path=line.split('  ',1)
  f=ROOT/path
  if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest()!=digest:bad.append(path)
 if bad:raise AssertionError('Hashes differ: '+str(bad))
 ledger=rows('v4.6_テスト台帳_550件.csv')
 requirements=rows('v4.6_要求仕様_121件.csv')
 edges=rows('v4.6_要求試験対応_717件.csv')
 evidence=rows('v4.6_ローカル検算_317件.csv')
 assert (len(ledger),len(requirements),len(edges),len(evidence))==(550,121,717,317)
 assert Counter(r['status'] for r in ledger)=={'PASS':317,'NOT_RUN':233}
 test_ids={r['test_id'] for r in ledger};req_ids={r['requirement_id'] for r in requirements}
 assert len(test_ids)==550 and len(req_ids)==121
 assert all(e['test_id'] in test_ids and e['requirement_id'] in req_ids for e in edges)
 assert len({e['test_method'] for e in evidence})==317 and all(e['result']=='PASS' for e in evidence)
 for path in (ROOT/'code').glob('*.py'):ast.parse(path.read_text(encoding='utf-8'),filename=path.as_posix())
 result={'files_checked':sum(bool(x) for x in (ROOT/'SHA256SUMS_v46.txt').read_text().splitlines()),
         'tests_plan':550,'local_python_pass':317,'external_not_run':233,'requirements':121,'links':717,
         'opencv5_aws_physical_evidence':'NOT_PROVIDED','result':'PACKAGE_INTEGRITY_PASS'}
 print(json.dumps(result,ensure_ascii=False,indent=2))
 return result
if __name__=='__main__':main()
