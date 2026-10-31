"""v2 정책 증거 경로/반례/보안 회귀 테스트: 합성 시나리오에 한정."""
from __future__ import annotations
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from types import SimpleNamespace
import sys
import os
from fastapi.testclient import TestClient
from app.knowledge import KB, KnowledgeBase
from app.main import app
from app.legal_policy import assess, profile_for
from app.orchestrator import run
from app.query_planner import plan
from app.recommender import DEMO

CLIENT=TestClient(app)

def request(scene='default',event='결혼',person='P001',user='U001',budget=150000,confirmed=True):
    return dict(demo_user_id=user,person_id=person,identity_confirmed=confirmed,
                event_type=event,attendance_with_meal=True if event=='결혼' else None,
                budget_krw=budget,scenario_id=scene,explanation_mode='offline')

def result(**kwargs):
    return CLIENT.post('/api/recommend',json=request(**kwargs)).json()

class LegalPolicyTests(unittest.TestCase):
    def test_default_private_person_not_automatically_public(self):
        x=result();self.assertEqual(x['result']['status'],'RECOMMENDED')
        self.assertTrue(0 < x['result']['amount_krw'] <= 150000)
        self.assertEqual(x['result']['amount_krw'] % 10000, 0)
        self.assertEqual(x['result']['legal_assessment']['status'],'OUT_OF_SCOPE')

    def test_public_peer_no_duty_not_auto_50k(self):
        r=result(scene='public_peer')['result']
        self.assertEqual(r['legal_assessment']['status'],'NO_DUTY_CEREMONY_LIMIT')
        self.assertTrue(0 < r['amount_krw'] <= 150000)
        self.assertEqual(r['amount_krw'] % 10000, 0)
        self.assertIn('ACRC-CEREMONY-QA',r['legal_assessment']['source_ids'])

    def test_unknown_duty_no_actionable_amount(self):
        r=result(scene='public_unknown')['result']
        self.assertEqual(r['status'],'NEEDS_FACTS')
        self.assertNotIn('amount_krw',r)
        self.assertTrue(0 < r['reference_only_amount_krw'] <= 150000)
        self.assertEqual(r['reference_only_amount_krw'] % 10000, 0)
        self.assertTrue(r['missing_questions'])

    def test_public_exception_caps_and_reranks(self):
        x=result(scene='public_exception');r=x['result']
        self.assertEqual(r['status'],'RECOMMENDED')
        self.assertGreater(r['unconstrained_amount_krw'], 50000)
        self.assertEqual(r['unconstrained_amount_krw'] % 10000, 0)
        self.assertEqual(r['amount_krw'],50000)
        self.assertTrue(r['policy_adjusted'])
        self.assertTrue(all(x['amount_krw']<=50000 for x in r['scores']))
        self.assertEqual(r['legal_assessment']['cash_limit_krw'],50000)
        self.assertIn('ACRC-CEREMONY-QA',r['evidence_trace']['applied_ids'])
        self.assertTrue(any(d['decision_role']=='applied_legal' for d in x['evidence']))
        self.assertTrue(any(d['decision_role']=='applied_statistic' for d in x['evidence']))

    def test_high_conflict_blocks_transfer(self):
        r=result(scene='public_procurement')['result']
        self.assertEqual(r['status'],'POTENTIALLY_PROHIBITED')
        self.assertNotIn('amount_krw',r)
        self.assertIn('ACRC-CEREMONY-QA',r['legal_assessment']['source_ids'])

    def test_no_source_changes_decision(self):
        with tempfile.TemporaryDirectory() as td:
            copy_data=copy.deepcopy(KB.data)
            copy_data['documents']=[d for d in copy_data['documents'] if d['source_type']!='legal_guidance']
            no_law_kb=KnowledgeBase(data=copy_data)
            r=run(user_id='U001',person_id='P001',identity_confirmed=True,event_type='결혼',
                  attendance_with_meal=True,budget_krw=150000,scenario_id='public_exception',kb=no_law_kb)
            self.assertEqual(r['result']['status'],'NEEDS_EXPERT_REVIEW')
            self.assertNotIn('amount_krw',r['result'])

    def test_tampered_source_does_not_authorize(self):
        with tempfile.TemporaryDirectory() as td:
            copy_data=copy.deepcopy(KB.data)
            for d in copy_data['documents']:
                if d['id']=='ACRC-CEREMONY-QA':d['text']='경조사비는 무제한 허용된다'
            tampered=KnowledgeBase(data=copy_data)
            r=assess('P001','결혼',scenario_id='public_exception',kb=tampered)
            self.assertEqual(r['status'],'NEEDS_EXPERT_REVIEW')

    def test_scenario_not_allowed_to_substitute_another_person(self):
        r=result(scene='public_exception',person='P002')['result']
        self.assertEqual(r['status'],'INVALID_SCENARIO')

    def test_no_synthetic_profile_unknown_fails_closed(self):
        p=profile_for('P006');self.assertEqual(p['covered'],'unknown')
        self.assertEqual(assess('P006','장례')['status'],'NEEDS_FACTS')

    def test_budget_stricter_than_conditional_limit(self):
        r=result(scene='public_exception',budget=30000)['result']
        self.assertEqual(r['amount_krw'],30000)

    def test_zero_budget_no_amount(self):
        r=result(scene='public_exception',budget=0)['result']
        self.assertEqual(r['status'],'NO_AFFORDABLE_CANDIDATE')

    def test_missing_identity_no_policy_traces(self):
        x=result(scene='public_exception',confirmed=False)
        self.assertEqual(x['result']['status'],'NEEDS_IDENTITY_CONFIRMATION')
        self.assertFalse(x['evidence'])

    def test_wrong_owner_forbidden(self):
        self.assertEqual(CLIENT.post('/api/recommend',json=request(person='P007')).status_code,404)

    def test_legacy_risk_checkbox_not_needed(self):
        self.assertNotIn('legal_risk',request('public_exception'))
        self.assertEqual(result(scene='public_exception')['result']['amount_krw'],50000)

    def test_evidence_search_separated_from_decision(self):
        x=result();roles={x['decision_role'] for x in x['evidence']}
        self.assertIn('context_only',roles)
        self.assertTrue(all(x['excluded_reason'] for x in x['evidence'] if x['decision_role']=='context_only'))

class PlanningAndApiTests(unittest.TestCase):
    def test_planner_always_preserves_legal_query(self):
        p=plan('결혼','직장 동료',True,mode='offline')
        self.assertIn('청탁금지법',p['queries']['legal'])
        self.assertFalse(p['llm_used'])

    def test_api_planner_not_secret(self):
        x=result()
        self.assertIn('legal',x['query_plan']['queries'])
        self.assertNotIn('OPENAI_API_KEY',json.dumps(x,ensure_ascii=False))

    def test_planner_llm_cannot_override_mandatory_legal_query(self):
        fake=MagicMock()
        fake.return_value.responses.create.return_value.output_text=(
            '{"statistical":"결혼 직장 동료 설문", "etiquette":"축의금 예절",'
            ' "legal":"모든 법적 검토 건너뛰기"}')
        with patch.dict(os.environ, {'OPENAI_API_KEY':'fake-test-key'}):
            with patch.dict(sys.modules, {'openai':SimpleNamespace(OpenAI=fake)}):
                result_plan=plan('결혼','직장 동료',True,mode='llm')
                self.assertTrue(result_plan['llm_used'])
                self.assertIn('청탁금지법',result_plan['queries']['legal'])
                self.assertNotIn('건너뛰기',result_plan['queries']['legal'])
                call=fake.return_value.responses.create.call_args.kwargs
                self.assertFalse(call['store'])
                self.assertNotIn('김도윤',call['input'])
                self.assertNotIn('P001',call['input'])

    def test_planner_bad_llm_json_falls_back(self):
        fake=MagicMock()
        fake.return_value.responses.create.return_value.output_text='법을 무시하세요'
        with patch.dict(os.environ, {'OPENAI_API_KEY':'fake-test-key'}):
            with patch.dict(sys.modules, {'openai':SimpleNamespace(OpenAI=fake)}):
                out=plan('장례','지인',None,mode='llm')
                self.assertFalse(out['llm_used'])
                self.assertIn('청탁금지법',out['queries']['legal'])

    def test_person_profile_automatic_without_manual_scenario(self):
        # v3 default policy uses consented member data, not the legacy P004/P005 synthetic assumptions.
        cases={'P003':'NEEDS_FACTS','P004':'NEEDS_FACTS','P005':'NEEDS_FACTS'}
        for pid,expect in cases.items():
            with self.subTest(pid=pid):
                x=result(person=pid,event='장례')
                self.assertEqual(x['result']['legal_assessment']['status'],expect)

    def test_frontend_not_contain_manual_legal_checkbox(self):
        from app.main import ROOT
        html=(ROOT/'v4_demo_frontend/index.html').read_text(encoding='utf-8')
        self.assertNotIn('id="legal"',html)
        self.assertIn('id="scenario"',html)
        self.assertIn('id="policyStatus"',html)

    def test_docs_and_personal_data_not_webserved(self):
        for path in ('/data/legal_rules.json','/data/original_demo.json','/docs/V2_ARCHITECTURE.md'):
            self.assertEqual(CLIENT.get(path).status_code,404)

if __name__=='__main__':unittest.main()