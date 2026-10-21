"""Decision boundaries, including real saved generated-LiME CLI reports."""
import copy
import json
from pathlib import Path
import unittest
from consumer_gate import export_decision

ROOT = Path(__file__).resolve().parent


class ConsumerDecisionChecks(unittest.TestCase):
    def setUp(self):
        self.clean = json.loads((ROOT / "results/intact-cli.json").read_text())
        self.partial = json.loads((ROOT / "results/truncated-cli.json").read_text())

    def test_intact_with_normal_address_gap_allows_scoped_count(self):
        self.assertEqual(self.clean["unmapped_requested_ranges"], [[4096, 8192]])
        result = export_decision(self.clean)
        self.assertEqual(result["count_for_scoped_export"], 2)
        self.assertEqual(result["returned_hits_retained"], [100, 9000])
        self.assertIn("not indicator absence", result["claim_scope"])

    def test_truncated_retains_positive_observation_but_withholds_count(self):
        result = export_decision(self.partial)
        self.assertIsNone(result["count_for_scoped_export"])
        self.assertEqual(result["observed_hit_entries_retained"], 1)
        self.assertEqual(result["returned_hits_retained"], [100])

    def test_zero_hits_does_not_turn_into_indicator_absence_claim(self):
        report = copy.deepcopy(self.clean)
        report["hits"] = []
        result = export_decision(report)
        self.assertEqual(result["count_for_scoped_export"], 0)
        self.assertIn("not indicator absence", result["claim_scope"])
        report["observation_status"] = "partial"
        self.assertIsNone(export_decision(report)["count_for_scoped_export"])

    def test_positive_label_cannot_hide_reported_errors_or_input_change(self):
        for field, value in [("read_failures", [{"start": 8192}]),
                             ("input_stability_check_equal", False)]:
            with self.subTest(field=field):
                report = copy.deepcopy(self.clean)
                report[field] = value
                self.assertIsNone(export_decision(report)["count_for_scoped_export"])

    def test_bare_hits_unknown_schema_or_no_mapped_data_are_not_certificates(self):
        for report in [[100], {"hits": []}, {**self.clean, "schema_version": 2},
                       {**self.clean, "mapped_ranges": []}]:
            with self.subTest(report_type=type(report).__name__):
                self.assertIsNone(export_decision(report)["count_for_scoped_export"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
