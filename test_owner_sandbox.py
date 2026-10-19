import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from owner_sandbox import obtain_token, NoRedirect


class OwnerSetupTests(unittest.TestCase):
    def test_credentials_only_target_sandbox_and_do_not_appear_in_output(self):
        with patch("urllib.request.build_opener") as build:
            build.return_value.open.return_value.__enter__.return_value.read.return_value = json.dumps({"access_token": "synthetic-test-token"}).encode()
            output = io.StringIO()
            with redirect_stdout(output):
                token = obtain_token("synthetic-client", "synthetic-secret")
            request = build.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, "https://api-m.sandbox.paypal.com/v1/oauth2/token")
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(token, "synthetic-test-token")
            self.assertEqual(output.getvalue(), "")
            self.assertIsInstance(build.call_args.args[0], NoRedirect)

    def test_missing_token_fails_before_app_start(self):
        with patch("urllib.request.build_opener") as build:
            build.return_value.open.return_value.__enter__.return_value.read.return_value = b'{}'
            with self.assertRaises(ValueError):
                obtain_token("synthetic-client", "synthetic-secret")
