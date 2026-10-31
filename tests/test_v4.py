"""v4 bidirectional occupation + free-text + evidence/policy regression."""
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock,patch
from fastapi.testclient import TestClient
import app.main as server
from app.main import app
from app.profile_store import ProfileStore,profile_for_recipient
from app.relationship_analysis import analyze
from app.recommender import DEMO

C=TestClient(app)


def reco(**kwargs):
    payload=dict(demo_user_id='U001',person_id='P001',identity_confirmed=True,
                 event_type='결혼',attendance_with_meal=True,budget_krw=150000,
                 explanation_mode='offline',scenario_id='default')
    payload.update(kwargs)
    res=C.post('/api/recommend',json=payload)
    assert res.status_code==200,(res.status_code,res.text)
    return res.json()


class V4Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=ProfileStore(Path(self.temp.name)/'v4.db')
        self.pt=patch.object(server,'STORE',self.store)
        self.pt.start()

    def tearDown(self):
        self.pt.stop();self.temp.cleanup()

    def put(self,uid,occupation='civil_servant',institution='government',role='general',share=True):
        response=C.post('/api/demo/onboarding',json=dict(demo_user_id=uid,
            occupation=occupation,institution=institution,duty_role=role,
            allow_recommendation=share,visibility='accepted_contacts' if share else 'none'))
        self.assertEqual(response.status_code,200)

    def test_legacy_migration_preserves_profiles(self):
        path=Path(self.temp.name)/'legacy.sqlite3'
        with closing(sqlite3.connect(path)) as db, db:
            db.execute('CREATE TABLE profiles (user_id TEXT PRIMARY KEY, occupation TEXT NOT NULL, institution TEXT NOT NULL, allow_recommendation INTEGER NOT NULL, visibility TEXT NOT NULL, updated_at TEXT NOT NULL)')
            db.execute('INSERT INTO profiles VALUES (?,?,?,?,?,?)',('U001','civil_servant','government',1,'accepted_contacts','old'))
        s=ProfileStore(path,seed=False)
        self.assertEqual(s.get('U001')['occupation'],'civil_servant')
        self.assertEqual(s.get('U001')['duty_role'],'unknown')
        s.put('U001',occupation='civil_servant',institution='government',allow_recommendation=True,visibility='accepted_contacts',duty_role='procurement')
        self.assertEqual(ProfileStore(path,seed=False).get('U001')['duty_role'],'procurement')

    def test_schema_rejects_unknown_role(self):
        self.assertEqual(C.post('/api/demo/onboarding',json=dict(demo_user_id='U001',occupation='civil_servant',institution='government',duty_role='root_access')).status_code,422)
        self.assertEqual(C.post('/api/recommend',json=dict(demo_user_id='U001',person_id='P001',identity_confirmed=True,event_type='결혼',relationship_text='a'*401)).status_code,422)

    def test_self_role_used_without_exposing_recipient_job(self):
        self.put('U001',role='procurement')
        self.put('U002',share=True)
        d=reco(relationship_text='제가 계약 심사를 맡은 상대방입니다.')
        a=d['relationship_analysis']
        self.assertTrue(a['sender_profile_used'])
        self.assertTrue(a['sender_duty_role_used'])
        self.assertTrue(a['sender_ethics_risk'])
        self.assertEqual(d['result']['status'],'NEEDS_EXPERT_REVIEW')
        self.assertNotIn('civil_servant',json.dumps(d,ensure_ascii=False))
        self.assertNotIn('procurement',json.dumps(d,ensure_ascii=False))

    def test_unconfirmed_text_stays_hypothesis_and_holds(self):
        self.put('U002')
        d=reco(relationship_text='저는 상대 회사의 계약 심사를 담당합니다.')
        self.assertEqual(d['relationship_analysis']['status'],'hypothesis_needs_confirmation')
        self.assertEqual(d['result']['status'],'NEEDS_FACTS')
        self.assertNotIn('amount_krw',d['result'])
        self.assertEqual(d['relationship_analysis']['possible_duty_context'],'contract_active')

    def test_confirmed_text_no_exception_never_recommends(self):
        self.put('U002')
        d=reco(relationship_text='상대방의 계약을 심사합니다.',facts_confirmed=True,exception_context='no')
        self.assertEqual(d['relationship_analysis']['source'],'user_confirmed_text')
        self.assertEqual(d['result']['status'],'POTENTIALLY_PROHIBITED')
        self.assertNotIn('amount_krw',d['result'])

    def test_confirmed_contract_exception_yes_does_not_auto_cap(self):
        self.put('U002')
        d=reco(relationship_text='상대방 계약 심사 중입니다.',facts_confirmed=True,exception_context='yes')
        self.assertEqual(d['result']['status'],'NEEDS_EXPERT_REVIEW')
        self.assertNotIn('amount_krw',d['result'])

    def test_confirmed_general_duty_with_exception_can_cap(self):
        self.put('U002')
        d=reco(relationship_text='상대와 업무상 관련성이 있습니다.',facts_confirmed=True,exception_context='yes')
        self.assertEqual(d['result']['status'],'RECOMMENDED')
        self.assertGreater(d['result']['unconstrained_amount_krw'], 50000)
        self.assertEqual(d['result']['unconstrained_amount_krw'] % 10000, 0)
        self.assertEqual(d['result']['amount_krw'],50000)
        self.assertIn('ACRC-CEREMONY-QA',d['result']['evidence_trace']['applied_ids'])

    def test_sender_public_recipient_private_still_review_conflict(self):
        self.put('U001',role='procurement')
        # seeded U002 is a private employee and shared
        d=reco(relationship_text='저는 구청의 발주 계약 담당이고 상대는 거래처 대표입니다.')
        self.assertEqual(d['result']['status'],'NEEDS_EXPERT_REVIEW')
        self.assertNotIn('amount_krw',d['result'])
        self.assertEqual(d['result']['legal_assessment']['source_ids'],[])

    def test_role_alone_does_not_prove_relation(self):
        self.put('U001',role='procurement')
        self.put('U002')
        d=reco()
        self.assertEqual(d['result']['status'],'NEEDS_FACTS')
        self.assertFalse(d['relationship_analysis']['sender_ethics_risk'])

    def test_no_consent_does_not_use_recipient_private_job(self):
        self.put('U002',share=False)
        d=reco(relationship_text='업무상 관련이 있어요',facts_confirmed=True,exception_context='yes')
        self.assertEqual(d['result']['status'],'NEEDS_FACTS')
        self.assertEqual(d['result']['legal_assessment']['profile_access'],'not_shared')
        self.assertNotIn('civil_servant',str(d))

    def test_natural_text_never_persists(self):
        self.put('U002')
        marker='TEST_PRIVATE_USER_INPUT_DO_NOT_STORE'
        reco(relationship_text='계약 심사 '+marker)
        with closing(sqlite3.connect(self.store.db_path)) as db:
            dump=' '.join(' '.join(str(v) for v in row) for row in db.execute('SELECT * FROM profiles'))
        self.assertNotIn(marker,dump)
        self.assertNotIn(marker,Path('app/relationship_analysis.py').read_text(encoding='utf-8'))

    def test_no_llm_call_without_explicit_opt_in(self):
        self.put('U002')
        with patch('app.relationship_analysis._llm_hint',side_effect=AssertionError('unexpected LLM')):
            d=reco(relationship_text='저는 계약 담당자입니다.',allow_llm_analysis=False)
        self.assertFalse(d['relationship_analysis']['used_llm'])

    def test_opted_llm_hint_is_not_confirmed(self):
        self.put('U002')
        with patch('app.relationship_analysis._llm_hint',return_value=('duty_related','')):
            d=reco(relationship_text='동료 관계',allow_llm_analysis=True)
        self.assertEqual(d['relationship_analysis']['possible_duty_context'],'duty_related')
        self.assertEqual(d['relationship_analysis']['duty_context'],'unknown')
        self.assertEqual(d['result']['status'],'NEEDS_FACTS')

    def test_llm_only_hint_never_upgraded_to_confirmed_even_if_checkbox(self):
        self.put('U002')
        with patch('app.relationship_analysis._llm_hint',return_value=('none','')):
            d=reco(relationship_text='잘 아는 사람',facts_confirmed=True,allow_llm_analysis=True)
        self.assertEqual(d['relationship_analysis']['duty_context'],'unknown')
        self.assertEqual(d['result']['status'],'NEEDS_FACTS')

    def test_external_llm_input_omits_profile_db(self):
        constructor=MagicMock()
        constructor.return_value.responses.create.return_value.output_text='{"duty_hint":"contract_active"}'
        with patch.dict(os.environ,{'OPENAI_API_KEY':'fake-key'}),patch.dict('sys.modules',{'openai':SimpleNamespace(OpenAI=constructor)}):
            result=analyze(sender={'occupation':'civil_servant','duty_role':'procurement'},
                           recipient={'covered':'yes'},relationship_text='계약 심사 관계',allow_llm_analysis=True)
        kwargs=constructor.return_value.responses.create.call_args.kwargs
        self.assertFalse(kwargs['store'])
        self.assertNotIn('civil_servant',kwargs['input'])
        self.assertNotIn('procurement',kwargs['input'])
        self.assertNotIn('user_id',kwargs['input'])
        self.assertEqual(result['duty_context'],'unknown')

    def test_explicit_none_does_not_override_stronger_text_risk(self):
        self.put('U002')
        d=reco(duty_context='none',relationship_text='제가 이 거래처의 계약 심사 중이에요')
        # An explicit "no duty" that contradicts a contract-risk sentence cannot silently greenlight payment.
        self.assertNotEqual(d['result']['legal_assessment']['status'],'NO_DUTY_CEREMONY_LIMIT')

    def test_same_name_independent_ids(self):
        self.put('U002')
        d1=reco(person_id='P001')
        d2=reco(person_id='P002')
        self.assertEqual(d1['result']['legal_assessment']['profile_access'],'consented')
        self.assertEqual(d2['result']['legal_assessment']['profile_access'],'not_shared')

    def test_offtopic_natural_text_not_policy_confirmation(self):
        self.put('U002')
        d=reco(relationship_text='오늘 저녁에 피자 먹고 싶어요',facts_confirmed=True)
        self.assertEqual(d['relationship_analysis']['duty_context'],'unknown')
        self.assertEqual(d['result']['status'],'NEEDS_FACTS')

    def test_health(self):
        self.assertEqual(C.get('/api/health').json()['policy_engine'],'v4')

if __name__=='__main__':unittest.main()
