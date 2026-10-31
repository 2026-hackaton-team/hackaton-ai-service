"""CPI 환산과 공개 근거의 추천 안전성 회귀 테스트."""

import unittest

from app.inflation import DATA, adjust_amount
from app.knowledge import KB
from app.recommender import recommend


class AmountEvidenceTests(unittest.TestCase):
    def test_monthly_adjustment_uses_published_indices(self):
        adjusted = adjust_amount(100000, "2025-09-21")
        self.assertEqual(adjusted["adjusted_amount_krw"], 102879)
        self.assertEqual(adjusted["original_amount_krw"], 100000)
        self.assertEqual(adjusted["status"], "monthly")
        self.assertEqual(adjusted["reference_month"], "2026-09")

    def test_older_record_uses_annual_mean_with_explicit_status(self):
        adjusted = adjust_amount(100000, "2023-05-20")
        self.assertEqual(adjusted["adjusted_amount_krw"], round(100000 * 120.43 / 111.59))
        self.assertEqual(adjusted["status"], "annual")
        self.assertEqual(adjusted["source_period"], "2023")

    def test_missing_or_future_cpi_never_uses_fabricated_rate(self):
        for date, status in (("2010-01-01", "unavailable"), ("2026-10-31", "after_reference")):
            with self.subTest(date=date):
                adjusted = adjust_amount(50000, date)
                self.assertEqual(adjusted["adjusted_amount_krw"], 50000)
                self.assertEqual(adjusted["status"], status)

    def test_zero_amount_and_reference_month_are_stable(self):
        self.assertEqual(adjust_amount(0, "2025-09-01")["adjusted_amount_krw"], 0)
        self.assertEqual(adjust_amount(50000, "2026-09-15")["adjusted_amount_krw"], 50000)
        self.assertEqual(DATA["reference_index"], DATA["monthly"][DATA["reference_month"]])

    def test_unmatched_surveys_and_wedding_prices_do_not_anchor_amount(self):
        ids = {d["id"] for d in KB.documents}
        self.assertIn("GAYEON-2026-08", ids)
        self.assertIn("KCA-WEDDING-2026", ids)
        self.assertIn("CPI-KR-2026-09", ids)
        for source_id in ("GAYEON-2026-08", "KCA-WEDDING-2026", "CPI-KR-2026-09"):
            self.assertFalse(KB.by_id[source_id]["can_anchor_amount"])
        self.assertIsNone(KB.eligible_amount_source(
            event_type="결혼", relationship="친구", attendance_with_meal=True))

    def test_historical_public_means_have_distinct_cpi_equivalents(self):
        nh = KB.by_id["NH-2026-05"]
        originals = {f["year"]: f["value"] for f in nh["facts"] if f["metric"] == "mean_transfer_krw"}
        adjusted = [f for f in nh["facts"] if f["metric"] == "cpi_equivalent_mean_krw"]
        self.assertEqual(len(adjusted), 3)
        for fact in adjusted:
            year = fact["observed_year"]
            self.assertEqual(fact["nominal_value"], originals[year])
            self.assertEqual(fact["value"], adjust_amount(originals[year], f"{year}-01-01")["adjusted_amount_krw"])
            self.assertEqual(fact["cpi_precision"], "annual")
            self.assertEqual(fact["reference_month"], "2026-09")
        self.assertFalse(nh["can_anchor_amount"])

    def test_person_history_uses_adjusted_values_but_keeps_nominal_totals(self):
        dataset = {
            "event_categories": ["결혼"],
            "people": [{"id": "P999", "owner_user_id": "U999", "relationship": "친구"}],
            "private_events": [
                {"id": "E001", "owner_user_id": "U999", "category": "결혼", "start_date": "2023-05-20"},
                {"id": "E002", "owner_user_id": "U999", "category": "결혼", "start_date": "2026-09-20"},
            ],
            "transactions": [
                {"id": "T001", "owner_user_id": "U999", "private_event_id": "E001",
                 "contact_person_id": "P999", "direction": "paid", "amount_krw": 100000},
                {"id": "T002", "owner_user_id": "U999", "private_event_id": "E002",
                 "contact_person_id": "P999", "direction": "received", "amount_krw": 100000},
            ],
        }
        result = recommend(user_id="U999", person_id="P999", identity_confirmed=True,
                           event_type="결혼", attendance_with_meal=True,
                           budget_krw=30000, dataset=dataset)
        self.assertEqual(result["status"], "RECOMMENDED")
        self.assertLessEqual(result["amount_krw"], 30000)
        history = result["personal_history"]
        self.assertEqual(history["paid_total_krw"], 100000)
        self.assertEqual(history["received_total_krw"], 100000)
        self.assertGreater(history["paid_median_current_krw"], 100000)
        self.assertEqual(history["received_median_current_krw"], 100000)
        self.assertEqual(history["cpi_coverage"]["annual"], 1)
        self.assertEqual(history["cpi_coverage"]["monthly"], 1)
        self.assertEqual(dataset["transactions"][0]["amount_krw"], 100000)
        held = recommend(user_id="U999", person_id="P999", identity_confirmed=True,
                         event_type="결혼", attendance_with_meal=True,
                         budget_krw=30000, legal_risk=True, dataset=dataset)
        self.assertEqual(held["status"], "LEGAL_REVIEW_REQUIRED")
        self.assertNotIn("amount_krw", held)


if __name__ == "__main__":
    unittest.main()
