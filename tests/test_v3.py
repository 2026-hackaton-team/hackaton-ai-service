"""v3 private profile -> consent -> official RAG -> policy -> recommendation tests."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import app.main as server
from app.main import app
from app.profile_store import ProfileStore,profile_for_recipient
from app.recommender import DEMO
from app.knowledge import KB
from app.legal_policy import assess

C=TestClient(app)

def request(**changes):
    req={'demo_user_id':'U001','person_id':'P001','identity_confirmed':True,
         'event_type':'결혼','attendance_with_meal':True,'budget_krw':150000,
         'scenario_id':'default','explanation_mode':'offline'}
    req.update(changes)
    return C.post('/api/recommend',json=req)

class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=ProfileStore(Path(self.temp.name)/'test.sqlite3')
        self.patch=patch.object(server,'STORE',self.store)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def make_public(self,userid='U002',consent=True,visibility='accepted_contacts'):
        return C.post('/api/demo/onboarding',json={
            'demo_user_id':userid,'occupation':'civil_servant',
            'institution':'government','allow_recommendation':consent,'visibility':visibility})

    def test_profile_sqlite_persistence(self):
        self.assertEqual(self.make_public().status_code,200)
        again=ProfileStore(self.store.db_path)
        self.assertEqual(again.get('U002')['occupation'],'civil_servant')
        self.assertTrue(again.get('U002')['allow_recommendation'])

    def test_signup_profile_input_validation(self):
        self.assertEqual(C.post('/api/demo/onboarding',json={'demo_user_id':'U001','occupation':'unknown','institution':'unknown','visibility':'none','allow_recommendation':False}).status_code,200)
        self.assertEqual(C.post('/api/demo/onboarding',json={'demo_user_id':'U999','occupation':'unknown','institution':'unknown'}).status_code,404)
        self.assertEqual(C.post('/api/demo/onboarding',json={'demo_user_id':'U001','occupation':'private_employee','institution':'INVALID'}).status_code,422)

    def test_profile_consent_and_active_friendship(self):
        self.make_public()
        access=profile_for_recipient(store=self.store,data=DEMO,viewer_id='U001',person_id='P001')
        self.assertEqual(access['access'],'consented')
        self.assertEqual(access['policy']['covered'],'yes')
        self.assertEqual(profile_for_recipient(store=self.store,data=DEMO,viewer_id='U001',person_id='P006')['access'],'not_authorized')

    def test_other_person_occupation_not_returned_from_access_api(self):
        self.make_public()
        data=C.get('/api/demo/profile-access?demo_user_id=U001&person_id=P001').json()
        self.assertEqual(data['access'],'consented')
        self.assertNotIn('occupation',data)
        self.assertNotIn('institution',data)
        self.assertNotIn('civil_servant',str(data))
        self.assertEqual(C.get('/api/demo/profile-access?demo_user_id=U001&person_id=P007').status_code,404)

    def test_no_automatic_duty_from_occupation(self):
        self.make_public()
        r=request().json()['result']
        self.assertEqual(r['status'],'NEEDS_FACTS')
        self.assertEqual(r['legal_assessment']['profile_access'],'consented')
        self.assertIn('직무 관련',r['legal_assessment']['reason'])
        self.assertNotIn('amount_krw',r)

    def test_duty_related_and_exception_unknown_needs_facts(self):
        self.make_public()
        r=request(duty_context='duty_related').json()['result']
        self.assertEqual(r['status'],'NEEDS_FACTS')
        self.assertTrue(r['missing_questions'])

    def test_self_reported_exception_conditional_5만원(self):
        self.make_public()
        r=request(duty_context='duty_related',exception_context='yes').json()['result']
        self.assertEqual(r['status'],'RECOMMENDED')
        self.assertGreater(r['unconstrained_amount_krw'], 50000)
        self.assertEqual(r['unconstrained_amount_krw'] % 10000, 0)
        self.assertEqual(r['amount_krw'],50000)
        self.assertEqual(r['legal_assessment']['status'],'CONDITIONALLY_ALLOWED')
        self.assertTrue(r['legal_assessment']['provisional'])
        self.assertIn('ACRC-CEREMONY-QA',r['evidence_trace']['applied_ids'])

    def test_active_contract_blocks_money_even_with_consent(self):
        self.make_public()
        r=request(duty_context='contract_active').json()['result']
        self.assertEqual(r['status'],'NEEDS_FACTS')  # v4: 예외 미확인은 금지 확정 대신 확인 요청
        self.assertNotIn('amount_krw',r)

    def test_revoke_consent_immediately_stops_job_use(self):
        self.make_public()
        self.assertEqual(request(duty_context='duty_related',exception_context='yes').json()['result']['amount_krw'],50000)
        self.make_public(consent=False)
        data=request(duty_context='duty_related',exception_context='yes').json()['result']
        self.assertEqual(data['status'],'NEEDS_FACTS')
        self.assertEqual(data['legal_assessment']['profile_access'],'not_shared')
        self.assertNotIn('amount_krw',data)
        self.assertNotIn('civil_servant',json.dumps(data,ensure_ascii=False))

    def test_visibility_not_shared_disables_access(self):
        self.make_public(visibility='none')
        self.assertEqual(request().json()['result']['legal_assessment']['profile_access'],'not_shared')

    def test_same_name_separate_linkage(self):
        self.make_public()
        self.assertEqual(request(person_id='P002').json()['result']['legal_assessment']['profile_access'],'not_shared')
        self.assertEqual(request(person_id='P001').json()['result']['legal_assessment']['profile_access'],'consented')

    def test_private_employee_does_not_gain_public_duty_flag(self):
        d=request().json()['result']
        self.assertEqual(d['legal_assessment']['status'],'OUT_OF_SCOPE')
        self.assertTrue(0 < d['amount_krw'] <= 150000)
        self.assertEqual(d['amount_krw'] % 10000, 0)

    def test_public_sector_uncertain_classification(self):
        C.post('/api/demo/onboarding',json={'demo_user_id':'U002','occupation':'public_institution_employee',
                 'institution':'public_institution','allow_recommendation':True,'visibility':'accepted_contacts'})
        self.assertEqual(request().json()['result']['status'],'NEEDS_FACTS')

    def test_unknown_job_not_automatically_private(self):
        C.post('/api/demo/onboarding',json={'demo_user_id':'U002','occupation':'unknown',
                 'institution':'unknown','allow_recommendation':True,'visibility':'accepted_contacts'})
        self.assertEqual(request().json()['result']['status'],'NEEDS_FACTS')

    def test_source_tampering_still_fails_closed(self):
        self.make_public()
        import copy
        kb=copy.copy(KB)
        kb.documents=copy.deepcopy(KB.documents)
        for doc in kb.documents:
            if doc['id']=='ACRC-CEREMONY-QA': doc['text']+=' modified'
        ov={'covered':'yes','duty_related':'yes','exception_confirmed':'yes',
            'conflict':'none','provenance':'self_reported_context','description':'test'}
        self.assertEqual(assess('P001','결혼',kb=kb,profile_override=ov)['status'],'NEEDS_EXPERT_REVIEW')

    def test_credentialless_demo_cannot_be_exposed_as_authenticated(self):
        self.assertFalse(C.get('/api/demo/me/profile?demo_user_id=U002').json()['demo_authentication'])
        self.assertEqual(C.get('/api/health').json()['policy_engine'],'v4')
        self.assertEqual(C.get('/data/demo_profiles.db').status_code,404)

if __name__=='__main__':unittest.main()