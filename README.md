# Refund Pact

An experimental refund review assistant for merchants using PayPal. A local language model extracts a customer's explicit refund request, a deterministic policy checks the proposed amount against the original capture and review-queue limit, and an immutable ledger preserves the same sandbox request preview for retries of the same support ticket.

Status: working local review desk under development for the PayPal AI Hackathon. Not registered, submitted, accepted, awarded or paid. The PayPal adapter has not yet been exercised against an actual sandbox account. There is no production payment integration.

## Review desk

```sh
python3 app.py
```

Open `http://127.0.0.1:8765`. Select a synthetic scenario, read or edit the message, and click **Review request**. The desk calls the local model, shows the evidence and policy result, preserves one proposal per capture/ticket, and exports the review as JSON. Review the same ticket again to see the existing proposal restored. Change its requested amount to see the conflict escalated. Select **Provider state changed** to see why an already partially refunded capture needs reconciliation.

The first model load can take about a minute. The app does not replace an unavailable model with a canned success response. It listens only on loopback. No customer data is sent to a hosted AI service. Use synthetic data for this experiment.

The optional **PayPal sandbox** mode becomes available only when an owner-managed `PAYPAL_SANDBOX_ACCESS_TOKEN` is present in the server environment. It performs a read-only capture lookup. Credentials are not entered in the web page, returned to the browser, or committed to the repository. It is not a verified live integration until exercised against an actual sandbox capture.

For an owner who already has a sandbox app, a helper avoids copying tokens into shell history or chat:

```sh
python3 owner_sandbox.py
```

The owner enters the existing **sandbox** Client ID and Secret in hidden terminal prompts. The helper sends them only to PayPal's sandbox OAuth endpoint, refuses redirects, retains the access token in this process environment, and starts the same local desk. It does not save credentials to a file. Close the process to end the session. In the desk, select PayPal sandbox and enter a capture ID belonging to that sandbox app. Account creation, new credentials, required agreements and identity checks remain owner actions. The helper's authentication path is unit-tested with synthetic responses; actual authentication remains unverified until the owner runs it with authorized sandbox credentials.

## Run

Python 3.10+; no Python packages needed. For fresh AI inference, install Ollama from its official source and provide the `qwen2.5:3b-instruct` model. Model use and availability are subject to its own license. This prototype does not bundle model weights. The development computer already had Ollama and this model.

```sh
python3 pact.py --message fixtures/message.txt --capture-fixture fixtures/capture.json --ticket T-001
```

All included customer/capture data is synthetic. The default model endpoint is `http://127.0.0.1:11434/api/chat`. No hosted AI API key is required. Local compute still consumes resources; no claim of zero fully allocated cost is made.

For a deterministic replay that makes **no new AI inference**:

```sh
python3 pact.py --message fixtures/message.txt --capture-fixture fixtures/capture.json --ticket T-001 --claim-fixture fixtures/claim.json
```

For persistent retry/conflict review, add `--ledger /tmp/refund-pact-demo.sqlite`. A changed amount on the same ticket is rejected. The ledger stores ticket text excerpts and amounts; use synthetic data for this experiment.

Run the tests:

```sh
python3 -m unittest -v
```

## What the prototype establishes

- An actual local model can propose structured data; the policy layer treats it as untrusted.
- Amount, ISO currency and evidence must appear literally in the message. Ambiguous requests go to manual review.
- A conservative English preflight escalates multiple explicit amounts and some prior/negated refund phrases before inference. This intentionally rejects legitimate multi-amount messages too; it is not a complete natural-language safety boundary.
- Decimal amounts use integer cents; the policy checks the original capture, currency, completion status and a configurable queue limit.
- The same capture/ticket produces one immutable request body and stable UUID `PayPal-Request-Id`. This demonstrates request preparation, not provider-side execution or exactly-once delivery.
- There is no function that sends refund POST requests. Every successful proposal waits for operator review.

## PayPal integration status

`SandboxCaptureReader` implements only `GET /v2/payments/captures/{capture_id}` against a fixed sandbox hostname. After the owner provisions sandbox access, it can be selected using `--sandbox-capture-id` and an owner-managed `PAYPAL_SANDBOX_ACCESS_TOKEN` environment variable. Never paste credentials into chat or commit them. The reader retains only ID, status and amount; full provider responses are not written to disk.

The request preview follows `POST /v2/payments/captures/{capture_id}/refund`, but is not sent. See [Payments v2](https://developer.paypal.com/api/payments/v2) and [PayPal idempotency](https://developer.paypal.com/api/rest/reference/idempotency/). The API does not promise indefinite retention of idempotency keys. A real refund implementation would require fresh reconciliation of previous refunds, operator authorization, ambiguous-response handling and explicit sandbox testing. Original captured amount is **not** the remaining refundable balance.

## Limitations and next evidence

Literal grounding does not prove that a refund is deserved or that the model correctly understood negation, conflicting context, or a malicious message. The operator must review the original request. No merchant/user validation or production reliability is claimed. Existing customer-support products already offer AI-assisted refunds; this project does not claim to invent them. Its intended focus is an inspectable PayPal-specific review and retry trail. Before considering a submission: exercise actual PayPal sandbox integration; record a working demo under three minutes; and resolve entrant category, business payout and required owner acceptance.

The original eight-case evaluation found two incorrect suggestions: a prior refund acknowledgement and conflicting requested amounts. Those failures are preserved outside the distributable source in the experiment evidence. The preflight was added in response. A replay of the same model outputs is regression evidence, not new accuracy evidence. `python3 evaluate.py --suite holdout` evaluates a separate small synthetic set with fresh inference; neither set establishes production accuracy.

## Authorship

New code created on 19 October 2026 by Codex acting under the portfolio owner's direction. The included fixture extraction is authored test data. Fresh inference uses the explicitly named local model. No human code review, customer deployment, savings, prize or payment is claimed. MIT license covers this repository's original code, not PayPal services or model weights.
