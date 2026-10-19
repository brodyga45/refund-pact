"""Local review desk. Serves synthetic scenarios; optionally reads PayPal sandbox."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
from urllib.error import HTTPError, URLError

from pact import extract, preflight, proposal, ReviewLedger, ReviewError, SandboxCaptureReader

ROOT = Path(__file__).parent
SCENARIOS = [
    {"id": "mug", "title": "A broken mug", "ticket": "RP-1001", "label": "Partial refund",
     "message": (ROOT / "fixtures/message.txt").read_text().strip(), "capture_status": "COMPLETED"},
    {"id": "prior", "title": "Already received", "ticket": "RP-1002", "label": "Prior refund",
     "message": "The refund of 20.00 USD has already reached my account; thank you. Please do not send another refund.", "capture_status": "COMPLETED"},
    {"id": "limit", "title": "Above queue limit", "ticket": "RP-1003", "label": "Policy exception",
     "message": "The package arrived damaged. Please refund 50.00 USD.", "capture_status": "COMPLETED"},
    {"id": "provider", "title": "Provider state changed", "ticket": "RP-1004", "label": "Reconcile first",
     "message": "Please refund 20.00 USD for the broken mug.", "capture_status": "PARTIALLY_REFUNDED"},
]
INFERENCE_LOCK = threading.Lock()


def review(message, capture, ticket, ledger_path, source="synthetic_fixture"):
    result = {"ticket": ticket, "capture": capture, "capture_source": source,
              "payment_writes": 0, "state": "MANUAL_REVIEW", "replayed": False}
    try:
        preflight(message)
    except ReviewError as error:
        return dict(result, reason=str(error), inference={"new_inference": False, "reason": "preflight escalation"})
    try:
        with INFERENCE_LOCK:
            claim, usage = extract(message)
        result.update(claim=claim, inference=usage)
        value = proposal(claim, message, capture, ticket)
        ledger = ReviewLedger(ledger_path)
        try:
            previous = ledger.db.execute("SELECT fingerprint FROM previews WHERE capture=? AND ticket=?",
                                         (value["capture_id"], value["ticket_id"])).fetchone()
            saved = ledger.put(value)
            result.update(proposal=saved, state=saved["state"], replayed=previous is not None)
        finally:
            ledger.db.close()
    except ReviewError as error:
        result["reason"] = str(error)
    except (ValueError, KeyError, OSError, TimeoutError):
        result["reason"] = "The local model is unavailable or returned incomplete data. Review the request manually."
    return result


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # Do not log customer text, tokens or capture identifiers.

    def respond(self, status, content, kind="application/json"):
        body = content if isinstance(content, bytes) else json.dumps(content).encode()
        self.send_response(status)
        self.send_header("Content-Type", kind + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def host_allowed(self):
        return self.headers.get("Host") in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")

    def do_GET(self):
        if not self.host_allowed():
            return self.respond(403, {"error": "Local access only"})
        if self.path == "/":
            raw = (ROOT / "desk.html").read_text().replace("__SESSION_TOKEN__", self.server.review_token)
            return self.respond(200, raw.encode(), "text/html")
        if self.path == "/api/scenarios":
            return self.respond(200, {"scenarios": SCENARIOS,
                                      "sandbox_configured": bool(os.environ.get("PAYPAL_SANDBOX_ACCESS_TOKEN"))})
        return self.respond(404, {"error": "Not found"})

    def do_POST(self):
        origins = (f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}")
        if not self.host_allowed() or self.headers.get("Origin") not in origins or not secrets.compare_digest(self.headers.get("X-Review-Token", ""), self.server.review_token):
            return self.respond(403, {"error": "Open the local review desk to use this endpoint"})
        if self.path != "/api/review":
            return self.respond(404, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 10000 or self.headers.get("Content-Type") != "application/json":
                return self.respond(400, {"error": "A JSON request under 10KB is required"})
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                return self.respond(400, {"error": "A JSON object is required"})
            scenario = next(x for x in SCENARIOS if x["id"] == data.get("scenario"))
            message = data.get("message", "")
            ticket = data.get("ticket", "")
            if not isinstance(message, str) or not 1 <= len(message) <= 5000 or not isinstance(ticket, str):
                return self.respond(400, {"error": "Enter a ticket and a message up to 5000 characters"})
            source = "synthetic_fixture"
            capture = json.loads((ROOT / "fixtures/capture.json").read_text())
            capture["status"] = scenario["capture_status"]
            if data.get("mode") == "sandbox":
                capture = SandboxCaptureReader().get_capture(data.get("capture_id", ""))
                source = "paypal_sandbox_read"
            result = review(message, capture, ticket, self.server.ledger_path, source)
            self.respond(200, result)
        except (ReviewError, StopIteration, ValueError, TypeError):
            self.respond(400, {"error": "Invalid scenario, capture or request. No proposal was saved."})
        except HTTPError as error:
            self.respond(502, {"error": f"PayPal sandbox returned HTTP {error.code}. No proposal was saved."})
        except (URLError, TimeoutError):
            self.respond(502, {"error": "PayPal sandbox could not be reached. No proposal was saved."})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--ledger", default=str(ROOT / "outputs/review-desk.sqlite"))
    args = parser.parse_args()
    Path(args.ledger).parent.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.review_token = secrets.token_urlsafe(32)
    server.ledger_path = args.ledger
    print(f"Refund Pact review desk: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
