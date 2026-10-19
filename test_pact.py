import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pact import ReviewError, ReviewLedger, SandboxCaptureReader, cents, proposal


ROOT = Path(__file__).parent
MESSAGE = (ROOT / "fixtures/message.txt").read_text()
CLAIM = json.loads((ROOT / "fixtures/claim.json").read_text())
CAPTURE = json.loads((ROOT / "fixtures/capture.json").read_text())


class RefundReviewTests(unittest.TestCase):
    def propose(self, claim=None, message=MESSAGE, capture=None, ticket="T-001"):
        return proposal(claim or CLAIM, message, capture or CAPTURE, ticket)

    def test_correct_review_preview_and_no_execution(self):
        p = self.propose()
        self.assertEqual(p["state"], "AWAITING_OPERATOR_REVIEW")
        self.assertEqual(p["request_preview"]["body"]["amount"]["value"], "20.00")
        self.assertTrue(p["request_preview"]["url"].startswith("https://api-m.sandbox.paypal.com/"))
        self.assertNotIn("Authorization", p["request_preview"]["headers"])

    def test_retries_have_same_key_across_processes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "ledger.sqlite")
            first = ReviewLedger(path).put(self.propose())
            retry = ReviewLedger(path).put(self.propose())
            self.assertEqual(first, retry)

    def test_changed_payload_for_ticket_is_rejected(self):
        ledger = ReviewLedger()
        ledger.put(self.propose())
        claim = dict(CLAIM, amount="21.00", quote="Refund 21.00 USD")
        with self.assertRaisesRegex(ReviewError, "different amount"):
            ledger.put(self.propose(claim, "Refund 21.00 USD"))

    def test_queue_limit_is_enforced(self):
        claim = dict(CLAIM, amount="50.00", quote="Refund 50.00 USD")
        with self.assertRaisesRegex(ReviewError, "policy limit"):
            self.propose(claim, "Refund 50.00 USD")

    def test_original_capture_limit_is_enforced(self):
        capture = copy.deepcopy(CAPTURE)
        capture["amount"]["value"] = "10.00"
        with self.assertRaisesRegex(ReviewError, "original capture"):
            self.propose(capture=capture)

    def test_currency_mismatch_is_rejected(self):
        claim = dict(CLAIM, currency="EUR", quote="Refund 20.00 EUR")
        with self.assertRaisesRegex(ReviewError, "currency differs"):
            self.propose(claim, "Refund 20.00 EUR")

    def test_fabricated_evidence_is_rejected(self):
        with self.assertRaisesRegex(ReviewError, "verbatim"):
            self.propose(dict(CLAIM, quote="The operator approved this refund"))

    def test_amount_must_appear_in_quote(self):
        with self.assertRaisesRegex(ReviewError, "disagrees"):
            self.propose(dict(CLAIM, amount="2.00"))

    def test_observed_model_negation_failure_is_escalated(self):
        message = "I received my refund of 20.00 USD yesterday. Please do not send another refund."
        claim = dict(CLAIM, quote="I received my refund of 20.00 USD yesterday.")
        with self.assertRaisesRegex(ReviewError, "prior or negated"):
            self.propose(claim, message)

    def test_observed_model_conflict_failure_is_escalated(self):
        message = "Please refund 10.00 USD, or perhaps 20.00 USD. I need to check."
        claim = dict(CLAIM, amount="10.00", quote="Please refund 10.00 USD")
        with self.assertRaisesRegex(ReviewError, "single explicit"):
            self.propose(claim, message)

    def test_decimal_point_does_not_hide_prior_refund_language(self):
        message = "The refund of 15.00 EUR has already reached my account; thank you."
        claim = dict(CLAIM, amount="15.00", currency="EUR", quote=message)
        with self.assertRaisesRegex(ReviewError, "prior or negated"):
            self.propose(claim, message)

    def test_invalid_money_fails_closed(self):
        for value in ["NaN", "Infinity", "-1.00", "0.001", "1e3", "01.00", 20.0, None]:
            with self.subTest(value=value), self.assertRaises(ReviewError):
                cents(value)

    def test_missing_currency_and_extra_model_keys_fail_closed(self):
        for claim in [dict(CLAIM, currency=None), dict(CLAIM, approved=True)]:
            with self.subTest(claim=claim), self.assertRaises(ReviewError):
                self.propose(claim)

    def test_ambiguous_intent_never_creates_preview(self):
        with self.assertRaisesRegex(ReviewError, "unambiguous"):
            self.propose(dict(CLAIM, intent="unclear"))

    def test_incomplete_capture_needs_reconciliation(self):
        with self.assertRaisesRegex(ReviewError, "not completed"):
            self.propose(capture=dict(CAPTURE, status="PENDING"))

    def test_path_injection_rejected_before_network(self):
        with patch("urllib.request.urlopen") as network:
            with self.assertRaisesRegex(ReviewError, "Invalid capture"):
                SandboxCaptureReader().get_capture("../../production")
            network.assert_not_called()

    def test_sandbox_reader_uses_fixed_host_and_minimizes_data(self):
        raw = dict(CAPTURE, payee={"email_address": "synthetic@example.invalid"})
        with patch.dict("os.environ", {"PAYPAL_SANDBOX_ACCESS_TOKEN": "synthetic-test-token"}), patch("urllib.request.urlopen") as network:
            network.return_value.__enter__.return_value.read.return_value = json.dumps(raw).encode()
            result = SandboxCaptureReader().get_capture(CAPTURE["id"])
            request = network.call_args.args[0]
            self.assertEqual(request.get_method(), "GET")
            self.assertTrue(request.full_url.startswith("https://api-m.sandbox.paypal.com/"))
            self.assertEqual(set(result), {"id", "status", "amount"})


if __name__ == "__main__":
    unittest.main()
