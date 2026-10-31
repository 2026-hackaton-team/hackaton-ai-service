"""Dependency-free source-integrity checks for bridge's pinned offline Docker image.

These are NOT substitutes for FastAPI/HTTPX runtime tests.
"""
import ast
import hashlib
import json
import pathlib
import unittest

from gyeongjosa_ai import seed_db

ROOT = pathlib.Path(__file__).resolve().parent
SOURCE = ROOT / "app"
DATA = ROOT / "data"

class SourceContractTests(unittest.TestCase):
    def test_all_v4_modules_parse(self):
        for name in ("main", "orchestrator", "recommender", "knowledge",
                     "legal_policy", "relationship_analysis", "profile_store",
                     "llm", "query_planner", "evidence_resolver"):
            with self.subTest(module=name):
                ast.parse((SOURCE / (name + ".py")).read_text(encoding="utf-8"))

    def test_data_documents_are_stored_in_seed_db(self):
        for name in ("knowledge_base", "legal_rules", "original_demo",
                     "person_policy_profiles"):
            with self.subTest(data=name):
                self.assertTrue(seed_db.load(name))

    def test_legal_evidence_checksums_match(self):
        rules = seed_db.load("legal_rules")
        kb = seed_db.load("knowledge_base")
        docs = {d["id"]: d for d in kb["documents"]}
        self.assertTrue(rules["rules"])
        for rule in rules["rules"]:
            with self.subTest(rule=rule["id"]):
                for doc_id in rule["source_ids"]:
                    self.assertIn(doc_id, docs)
                    doc = docs[doc_id]
                    self.assertTrue(doc.get("verified"))
                    self.assertEqual(hashlib.sha256(doc["text"].encode("utf-8")).hexdigest(),
                                     rules["source_checksums"][doc_id])

    def test_v4_runtime_suite_is_present(self):
        for name in ("test_prototype.py", "test_scenario_regressions.py",
                     "test_v2.py", "test_v3.py", "test_v4.py"):
            with self.subTest(test_file=name):
                ast.parse((ROOT / "tests" / name).read_text(encoding="utf-8"))

    def test_v4_contract_fields_exist_in_api(self):
        main = (SOURCE / "main.py").read_text(encoding="utf-8")
        for field in ("relationship_text", "facts_confirmed", "allow_llm_analysis",
                      "duty_role", "identity_confirmed", "budget_krw"):
            with self.subTest(field=field):
                self.assertIn(field, main)

    def test_v4_private_recipient_profile_guard_exists(self):
        store = (SOURCE / "profile_store.py").read_text(encoding="utf-8")
        for marker in ("allow_connection_for_recommendation", "accepted_contacts",
                       "allow_recommendation", "not_shared"):
            with self.subTest(marker=marker):
                self.assertIn(marker, store)

    def test_relationship_text_is_not_appended_to_db_in_analysis(self):
        module = (SOURCE / "relationship_analysis.py").read_text(encoding="utf-8")
        self.assertIn("'text_retained':False", module)
        self.assertIn("allow_llm_analysis", module)
        self.assertIn("store=False", module)

    def test_original_frontend_has_v4_fields(self):
        script = (ROOT / "v4_demo_frontend" / "app.js").read_text(encoding="utf-8")
        for field in ("myDutyRole", "relationship_text", "facts_confirmed",
                      "allow_llm_analysis", "relationship_analysis"):
            with self.subTest(field=field):
                self.assertIn(field, script)
