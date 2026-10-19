import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from app import review

ROOT = Path(__file__).parent
CAPTURE = json.loads((ROOT / "fixtures/capture.json").read_text())
MESSAGE = (ROOT / "fixtures/message.txt").read_text()
CLAIM = json.loads((ROOT / "fixtures/claim.json").read_text())
USAGE = {"model": "test-double", "wall_seconds": 0, "prompt_tokens": 0, "output_tokens": 0}


class ReviewDeskTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = str(Path(self.tmp.name) / "review.sqlite")

    def tearDown(self):
        self.tmp.cleanup()

    def test_preflight_does_not_call_model(self):
        with patch("app.extract") as model:
            report = review("The refund of 20.00 USD has already arrived.", CAPTURE, "T1", self.ledger)
        model.assert_not_called()
        self.assertEqual(report["state"], "MANUAL_REVIEW")
        self.assertEqual(report["payment_writes"], 0)

    def test_repeat_ticket_restores_same_request(self):
        with patch("app.extract", return_value=(CLAIM, USAGE)):
            first = review(MESSAGE, CAPTURE, "T1", self.ledger)
            retry = review(MESSAGE, CAPTURE, "T1", self.ledger)
        self.assertFalse(first["replayed"])
        self.assertTrue(retry["replayed"])
        self.assertEqual(first["proposal"], retry["proposal"])

    def test_changed_amount_does_not_replace_existing_ticket(self):
        with patch("app.extract", return_value=(CLAIM, USAGE)):
            first = review(MESSAGE, CAPTURE, "T1", self.ledger)
        text = "Please refund 21.00 USD."
        changed = dict(CLAIM, amount="21.00", quote=text)
        with patch("app.extract", return_value=(changed, USAGE)):
            second = review(text, CAPTURE, "T1", self.ledger)
        self.assertIn("different amount", second["reason"])
        self.assertNotIn("proposal", second)

    def test_refunded_provider_state_needs_reconciliation(self):
        capture = dict(CAPTURE, status="PARTIALLY_REFUNDED")
        with patch("app.extract", return_value=(CLAIM, USAGE)):
            report = review(MESSAGE, capture, "T1", self.ledger)
        self.assertEqual(report["state"], "MANUAL_REVIEW")
        self.assertNotIn("proposal", report)

    def test_unavailable_model_has_no_synthetic_success_fallback(self):
        with patch("app.extract", side_effect=TimeoutError()):
            report = review(MESSAGE, CAPTURE, "T1", self.ledger)
        self.assertEqual(report["state"], "MANUAL_REVIEW")
        self.assertNotIn("proposal", report)
        self.assertNotIn("claim", report)

    def test_malformed_model_cannot_create_proposal(self):
        with patch("app.extract", return_value=({"approved": True}, USAGE)):
            report = review(MESSAGE, CAPTURE, "T1", self.ledger)
        self.assertEqual(report["state"], "MANUAL_REVIEW")
        self.assertNotIn("proposal", report)


if __name__ == "__main__":
    unittest.main()
