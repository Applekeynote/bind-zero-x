# -*- coding: utf-8 -*-
"""Model-only ablation arithmetic; no empirical outcomes."""
import unittest,sys,base64
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'comparisons'))
from finite_model_ablation import SCENARIOS,one_case,main
from api_research import _decode
from fastapi import HTTPException

class FiniteModelAblationV46(unittest.TestCase):
    def test_V46_037_static_top_negative_control_equal(self):
        case=SCENARIOS[0]
        for w in ('A','B'):
            self.assertEqual(one_case(case,w,'PCIG')['hypothetical_loss'],
                             one_case(case,w,'STATIC_TOP')['hypothetical_loss'])
    def test_V46_038_information_only_if_view_has_registered_signal(self):
        case=SCENARIOS[3]
        for w in ('A','B'):
            r=one_case(case,w,'PCIG')
            self.assertEqual(r['final_action'],'ABSTAIN')
            self.assertIsNone(r['chosen_view'])
    def test_V46_039_model_internal_aggregate_is_explicit(self):
        s=main()
        self.assertEqual(s['evidence_scope'],'HYPOTHETICAL_FINITE_MODEL_ONLY_NOT_REAL_GT')
        self.assertEqual(len(s['cases']),16)
        self.assertLess(s['summary']['PCIG']['mean_hypothetical_loss'],
                        s['summary']['STATIC_TOP']['mean_hypothetical_loss'])
    def test_V46_040_png_preflight_rejects_huge_dimensions(self):
        png=b'\x89PNG\r\n\x1a\n'+b'0'*8+(100000).to_bytes(4,'big')+(100000).to_bytes(4,'big')
        with self.assertRaises(HTTPException) as ctx:_decode(base64.b64encode(png).decode())
        self.assertEqual(ctx.exception.status_code,413)
    def test_V46_041_png_preflight_rejects_short_header(self):
        with self.assertRaises(HTTPException) as ctx:_decode(base64.b64encode(b'\x89PNG\r\n\x1a\n').decode())
        self.assertEqual(ctx.exception.status_code,422)
if __name__=='__main__':unittest.main()
