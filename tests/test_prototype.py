import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import os
import sys
from types import SimpleNamespace
from fastapi.testclient import TestClient
from app.knowledge import KB, grams
from app.llm import deterministic_explanation, explain
from app.main import app
from app.recommender import DEMO, recommend

client = TestClient(app)


def run_reco(**overrides):
    args=dict(user_id='U001', person_id='P001', identity_confirmed=True,
              event_type='장례', budget_krw=80000, attendance_with_meal=None, legal_risk=False)
    args.update(overrides)
    return recommend(**args)


class RecommendationTests(unittest.TestCase):
    def test_funeral_matches_history(self):
        result=run_reco()
        self.assertEqual(result['status'], 'RECOMMENDED')
        self.assertEqual(result['amount_krw'],50000)
        self.assertEqual(result['matched_source_id'],None)
        self.assertEqual(result['personal_history']['received_total_krw'],100000)
        self.assertEqual(result['personal_history']['paid_total_krw'],50000)

    def test_wedding_matches_real_conditions(self):
        r=run_reco(event_type='결혼',attendance_with_meal=True,budget_krw=150000)
        self.assertEqual(r['amount_krw'],100000)
        self.assertEqual(r['matched_source_id'],'INC-2025-05')

    def test_wedding_no_meal_no_survey(self):
        r=run_reco(event_type='결혼',attendance_with_meal=False,budget_krw=150000)
        self.assertIsNone(r.get('matched_source_id'))

    def test_identity(self):
        self.assertEqual(run_reco(identity_confirmed=False)['status'],'NEEDS_IDENTITY_CONFIRMATION')

    def test_budget(self):
        r=run_reco(budget_krw=60000)
        self.assertLessEqual(r['amount_krw'],60000)
        self.assertEqual(run_reco(budget_krw=1000)['status'],'NO_AFFORDABLE_CANDIDATE')
        self.assertEqual(run_reco(budget_krw=0)['status'],'NO_AFFORDABLE_CANDIDATE')

    def test_unknown_person(self):
        self.assertEqual(run_reco(person_id='P999')['status'],'FORBIDDEN_OR_NOT_FOUND')
        self.assertEqual(run_reco(person_id='P007')['status'],'FORBIDDEN_OR_NOT_FOUND')

    def test_zero_is_transaction_not_missing(self):
        r=run_reco(person_id='P004', event_type='백일')
        self.assertEqual(r['status'],'RECOMMENDED')
        self.assertEqual(r['personal_history']['explicit_zero_paid_count'],1)
        # P004에게 과거 0원과 10만원이 모두 기록되어 있다. 0원은 거래 건수에 포함되지만 앵커 중앙값에는 넣지 않는다.

    def test_legal_review(self):
        self.assertEqual(run_reco(legal_risk=True)['status'],'LEGAL_REVIEW_REQUIRED')

    def test_attendance_missing(self):
        self.assertEqual(run_reco(event_type='결혼',attendance_with_meal=None)['status'],'NEEDS_ATTENDANCE_CONTEXT')

    def test_same_named_different_persons(self):
        names=[p for p in DEMO['people'] if p['owner_user_id']=='U001' and p['name']=='김도윤']
        self.assertEqual(len(names),2)
        result=run_reco(person_id='P002',event_type='결혼',attendance_with_meal=True,budget_krw=150000)
        self.assertIsNone(result.get('matched_source_id'))
        self.assertNotEqual(result['personal_history']['received_total_krw'],100000)


class KnowledgeTests(unittest.TestCase):
    def test_only_public_material_in_index(self):
        serialized=json.dumps(KB.documents,ensure_ascii=False)
        self.assertNotIn('P001',serialized)
        self.assertNotIn('윤서진',serialized)
        self.assertNotIn('해든기획팀',serialized)

    def test_retrieval(self):
        items=KB.retrieve('직장 동료 결혼식 축의금 참석 식사',event_type='결혼',relationship='직장 동료')
        self.assertIn('INC-2025-05',[x['id'] for x in items])

    def test_not_using_nh_as_recommendation(self):
        self.assertIsNone(KB.eligible_amount_source(event_type='장례',relationship='직장 동료',attendance_with_meal=True))
        self.assertIsNone(KB.eligible_amount_source(event_type='결혼',relationship='독서 모임 지인',attendance_with_meal=True))
        self.assertIsNone(KB.eligible_amount_source(event_type='결혼',relationship='직장 동료',attendance_with_meal=False))

    def test_grams_korean(self):
        self.assertIn('축의',grams('축의금'))


class ApiTests(unittest.TestCase):
    def test_home_and_health(self):
        self.assertEqual(client.get('/').status_code,200)
        health=client.get('/api/health').json()
        self.assertGreaterEqual(health['knowledge_documents'],6)
        self.assertNotIn('OPENAI_API_KEY',health)

    def test_demo_user_scope_and_403_equivalent(self):
        r=client.get('/api/demo/people?user_id=U001')
        self.assertEqual(r.status_code,200)
        self.assertTrue(all(p['id'].startswith('P0') for p in r.json()))
        self.assertEqual(client.get('/api/demo/people?user_id=U999').status_code,404)
        payload={'demo_user_id':'U001','person_id':'P007','identity_confirmed':True,'event_type':'장례','budget_krw':80000,'explanation_mode':'offline'}
        self.assertEqual(client.post('/api/recommend',json=payload).status_code,404)

    def test_recommendation_schema(self):
        payload={'demo_user_id':'U001','person_id':'P001','identity_confirmed':True,'event_type':'장례','budget_krw':80000,'explanation_mode':'offline'}
        r=client.post('/api/recommend',json=payload)
        self.assertEqual(r.status_code,200)
        data=r.json()
        self.assertEqual(data['result']['amount_krw'],50000)
        self.assertFalse(data['llm_used'])
        self.assertTrue(data['evidence'])
        self.assertNotIn('OPENAI_API_KEY',r.text)

    def test_survey_evidence_match(self):
        payload={'demo_user_id':'U001','person_id':'P001','identity_confirmed':True,'event_type':'결혼','budget_krw':150000,'attendance_with_meal':True,'explanation_mode':'offline'}
        evidence=client.post('/api/recommend',json=payload).json()['evidence']
        self.assertEqual(sum(bool(e['amount_reference_eligible']) for e in evidence),1)

    def test_validation(self):
        payload={'demo_user_id':'U001','person_id':'P001','identity_confirmed':True,'event_type':'장례','budget_krw':-5,'explanation_mode':'offline'}
        self.assertEqual(client.post('/api/recommend',json=payload).status_code,422)

    def test_docs_private_file_not_exposed(self):
        self.assertEqual(client.get('/data/original_demo.json').status_code,404)
        self.assertEqual(client.get('/.env').status_code,404)

    def test_mocked_llm_uses_store_false_and_does_not_send_names(self):
        result=run_reco()
        result['event_type']='장례'
        response=MagicMock()
        response.output_text='관계와 과거 내역을 고려했습니다. 최종 선택은 사용자가 결정합니다.'
        with patch.dict(os.environ, {'OPENAI_API_KEY':'test-secret-do-not-log'}):
            constructor=MagicMock()
            with patch.dict(sys.modules, {'openai': SimpleNamespace(OpenAI=constructor)}):
                constructor.return_value.responses.create.return_value=response
                explanation,used,warning=explain(result,KB.retrieve('장례 예산 부담',event_type='장례'),mode='llm')
                call=constructor.return_value.responses.create.call_args.kwargs
                self.assertFalse(call['store'])
                self.assertNotIn('윤서진',call['input'])
                self.assertNotIn('김도윤',call['input'])
                self.assertNotIn('P001',call['input'])
                self.assertNotIn('test-secret',call['input'])
                self.assertTrue(used)
                self.assertIsNone(warning)

    def test_mocked_llm_numeric_hallucination_fallback(self):
        result=run_reco()
        with patch.dict(os.environ, {'OPENAI_API_KEY':'test-secret-do-not-log'}):
            constructor=MagicMock()
            with patch.dict(sys.modules, {'openai': SimpleNamespace(OpenAI=constructor)}):
                constructor.return_value.responses.create.return_value.output_text='무조건 999999원을 내세요.'
                explanation,used,warning=explain(result,[],mode='llm')
                self.assertFalse(used)
                self.assertIn('최종 선택',explanation)
                self.assertIsNotNone(warning)

    def test_llm_fallback_when_offline(self):
        result=run_reco()
        explanation,used,warning=explain(result,[],mode='offline')
        self.assertFalse(used)
        self.assertIn('최종 선택',explanation)


if __name__=='__main__': unittest.main()
