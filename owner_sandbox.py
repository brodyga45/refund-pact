"""Owner-run sandbox authentication, then start the local review desk."""
import argparse
import base64
import getpass
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def obtain_token(client_id, client_secret):
    if not client_id or not client_secret:
        raise ValueError("Both sandbox credentials are required")
    basic = base64.b64encode((client_id + ":" + client_secret).encode()).decode()
    request = urllib.request.Request(
        "https://api-m.sandbox.paypal.com/v1/oauth2/token",
        data=b"grant_type=client_credentials",
        headers={"Authorization": "Basic " + basic,
                 "Content-Type": "application/x-www-form-urlencoded"})
    # Never send the credentials to a redirect destination.
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(request, timeout=20) as response:
        token = json.load(response).get("access_token")
    if not isinstance(token, str) or not token.strip():
        raise ValueError("Sandbox response did not contain an access token")
    return token


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between1 and65535")
    if not sys.stdin.isatty():
        print("Run this helper in an interactive local terminal for hidden credential entry.")
        return 1
    print("Owner-only setup for an existing PayPal SANDBOX app.")
    print("Credentials go only to https://api-m.sandbox.paypal.com/v1/oauth2/token")
    print("Both inputs are hidden. They are not saved or printed.")
    client_id = getpass.getpass("Sandbox Client ID: ")
    secret = getpass.getpass("Sandbox Secret: ")
    try:
        token = obtain_token(client_id, secret)
    except urllib.error.HTTPError as error:
        print(f"Sandbox authentication returned HTTP {error.code}. Review the sandbox app credentials.")
        return 1
    except (OSError, ValueError, TimeoutError):
        print("Sandbox authentication was unavailable or incomplete. Review desk was not started.")
        return 1
    finally:
        del client_id, secret
    os.environ["PAYPAL_SANDBOX_ACCESS_TOKEN"] = token
    print("Sandbox authentication succeeded. Token stays in this process environment.")
    from app import main as desk_main
    sys.argv = [str(Path(__file__).with_name("app.py")), "--port", str(args.port)]
    try:
        desk_main()
    finally:
        os.environ.pop("PAYPAL_SANDBOX_ACCESS_TOKEN", None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
