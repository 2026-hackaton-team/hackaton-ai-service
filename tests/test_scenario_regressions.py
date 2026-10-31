"""Regression coverage for legacy scenario metadata and the main UI path."""
import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.legal_policy import PROFILES


class ScenarioApiRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_p001_lists_all_scenarios(self):
        response = self.client.get('/api/demo/scenarios', params={'person_id': 'P001'})
        self.assertEqual(response.status_code, 200, response.text)
        rows = response.json()
        self.assertEqual({x['id'] for x in rows}, {
            'default','public_peer','public_unknown','public_exception','public_procurement'
        })
        for row in rows:
            self.assertIsInstance(row['description'], str)
            self.assertTrue(row['description'].strip())
            self.assertTrue(row['label'].strip())

    def test_other_people_get_only_default(self):
        for pid in ('P002','P003','P004','P005'):
            with self.subTest(person_id=pid):
                response = self.client.get('/api/demo/scenarios', params={'person_id':pid})
                self.assertEqual(response.status_code, 200)
                self.assertEqual([x['id'] for x in response.json()], ['default'])

    def test_preset_scenario_can_recommend(self):
        payload = {
            'demo_user_id':'U001','person_id':'P001','identity_confirmed':True,
            'event_type':'결혼','attendance_with_meal':True,'budget_krw':150000,
            'scenario_id':'public_exception','explanation_mode':'offline'
        }
        response = self.client.post('/api/recommend', json=payload)
        self.assertEqual(response.status_code, 200)
        result = response.json()['result']
        self.assertNotEqual(result['status'], 'INVALID_SCENARIO')
        self.assertEqual(result['legal_assessment']['status'], 'CONDITIONALLY_ALLOWED')

    def test_default_after_list_can_recommend(self):
        response = self.client.get('/api/demo/scenarios', params={'person_id':'P001'})
        self.assertEqual(response.status_code, 200)
        payload = {
            'demo_user_id':'U001','person_id':'P001','identity_confirmed':True,
            'event_type':'장례','budget_krw':80000,'explanation_mode':'offline'
        }
        response = self.client.post('/api/recommend', json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.json()['result']['status'], 'INVALID_SCENARIO')

    def test_legacy_missing_description_falls_back_to_profile(self):
        scenario = PROFILES['scenarios']['public_peer']
        self.assertNotIn('description', scenario)
        response = self.client.get('/api/demo/scenarios',params={'person_id':'P001'})
        row = next(r for r in response.json() if r['id']=='public_peer')
        self.assertEqual(row['description'],scenario['profile']['description'])


if __name__ == '__main__':
    unittest.main()
