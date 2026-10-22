# -*- coding: utf-8 -*-
"""Package manifest/traceability validation; run separately after package generation.
This file does not run as unittest in the base run because the CSV package is generated later.
"""
from __future__ import annotations
import csv
from collections import defaultdict
from pathlib import Path

def validate_package_tables(root:Path):
    def load(p):
        with (root/p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
    cases=load('v4.2_テストケース台帳_327件.csv')
    requirements=load('v4.2_要求仕様_81件.csv')
    links=load('v4.2_要求テスト多対多対応.csv')
    ids=[r['test_id'] for r in cases]
    assert len(set(ids))==len(ids) and len(ids)==327
    reqids=[r['requirement_id'] for r in requirements]
    assert len(set(reqids))==len(reqids)
    mappings=defaultdict(list)
    for link in links:
        assert link['test_id'] in ids and link['requirement_id'] in reqids
        mappings[link['test_id']].append(link)
    assert all(mappings[x] for x in ids), 'test without requirement'
    assert all(r['automation'] in {'AUTO','MANUAL','SEMI_AUTO','REVIEW'} for r in cases)
    assert all(r['status'] in {'PASS','FAIL','NOT_RUN','BLOCKED','INCONCLUSIVE','N_A'} for r in cases)
    assert all(r['evidence_tier'] != 'REAL_PHYSICAL' for r in cases if r['status']=='PASS')
    assert all(r['evidence_tier']!='REAL_PHYSICAL' for r in cases if r['category']=='PHYS' and r['status']=='PASS')
    return len(cases),len(requirements),len(links),sum(r['status']=='PASS' for r in cases)

if __name__=='__main__':
    print(validate_package_tables(Path(__file__).resolve().parent.parent))
