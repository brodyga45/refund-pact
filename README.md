# ScanLedger

Experimental observation reports for one sequential Volatility 3 byte scan. ScanLedger preserves the hits returned by the upstream API and records whether its declared mapped ranges reached completed scanner callbacks. It distinguishes normal address gaps from failed reads and aborted scanner callbacks.

This is a candidate research tool for the [2026 Volatility Plugin Contest](https://volatilityfoundation.org/volatility-plugin-contest/). It is not entered, accepted, awarded or paid. No claim of production or real-incident validation is made.

## A concrete example

The two included LiME files are generated fixtures, not acquired OS memory. Each intact region contains a known harmless marker. The format declares regions `[0,4096)` and `[8192,12288)` with a normal physical-address gap between them.

On the intact sample, the unmodified Volatility API returns both markers, at 100 and 9000. ScanLedger returns the same hits, records the normal unmapped gap, reports `observed_mapped_ranges`, and exits 0.

The second fixture removes 64 bytes from the last payload but retains its LiME declarations. The marker at 9000 remains physically in that file. The upstream API returns only the marker at 100 because the read containing the second marker fails. ScanLedger preserves that result, reports `partial`, identifies the failed read and unobserved declared range, and exits 2. It does not recover the lost hit or pretend the failed read identifies the exact missing bytes.

The [fixture manifest](examples/manifest.json) states how the samples were constructed. Actual command outputs are in [results/](results/).

## Run

Use Python 3.10+ and the pinned official Volatility checkout:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python generate_examples.py
.venv/bin/python scanledger.py examples/intact.lime --format lime --needle CONTEST_MARKER --chunk-size 4096
.venv/bin/python scanledger.py examples/truncated.lime --format lime --needle CONTEST_MARKER --chunk-size 4096
```

Exit 2 is the expected diagnostic result for the truncated fixture. Raw local files are also supported with `--format raw`; there is no memory acquisition, remote input, arbitrary plugin runner or hosted API. Only literal UTF-8 needles are accepted, not executable patterns.

A local source checkout can be used by setting `PYTHONPATH` to that checkout. In the development workspace, `python3 test_scanledger.py` uses `upstream/`. For a separately installed dependency, remove that development checkout directory or place it at the tested commit. The test harness also works when the dependency is installed and no `upstream/` exists.

## A downstream decision: whether to export a scoped count

The v2 consumer example is a strict example policy for a developer consuming
trusted local CLI JSON. It preserves partial positive observations but withholds
their publication as a completed observation count even within the declared
mapped window. It does not certify the source report or an indicator's absence.

After installing the pinned dependency, run this one command into a new directory:

```sh
.venv/bin/python consumer_demo.py --output consumer-run
```

This actually runs both generated LiME inputs through ScanLedger and then through
`consumer_gate.py`. The demo returns success only when the expected decisions
occur; its dependency cache stays inside that owned output directory.

| Generated input | Returned hit entries retained | Count allowed for scoped export | Consumer decision |
| --- | ---: | ---: | --- |
| Intact | 2 | 2 | Export with the narrow scope and producer report |
| Truncated | 1 | withheld | Retain the hit; review the input/run before publishing such a count |

The confirmed outputs are in `results/consumer-v2-confirmed/`. A normal declared
address gap is allowed in the intact case. Five additional decision checks cover
this distinction, partial zero-hit input, contradictory error/stability fields,
unsupported/bare reports and a window with no mapped observations:
`.venv/bin/python test_consumer_gate.py`. These are authored checks, not a human review.

This demonstrates an automated consumer action on controlled fixtures, not
practitioner adoption or superior forensic utility. Correctly configured logs,
conservative manual review, or simple format/size validation are credible
alternatives; format validation alone can identify this deliberately simple
truncated fixture. The example has not established superiority to those options.
Exporting explicitly labelled partial results may also be a valid policy; this
example deliberately chooses a stricter one. It never equates a zero scoped count
with clean memory, correct scanner semantics, or complete acquisition.

## What the report establishes

- `mapped_ranges`: the ranges the layer declares mapped for the requested window.
- `unmapped_requested_ranges`: normal gaps in that declaration, not automatically errors or damaged capture evidence.
- `completed_scanner_ranges`: ranges passed to callbacks that completed in this run.
- `unobserved_mapped_ranges`: declared mapped ranges not covered by those completed callbacks.
- Read and scanner exceptions, padded-read requests and top-level failures conservatively produce `partial`.
- Pre/post SHA-256 and file metadata checks detect observed input changes. Matching hashes do not prove a file was immutable throughout execution; use a stable read-only input.

The observer temporarily intercepts reads only on the supplied context and restores its instance attributes afterward. The caller must own the context exclusively. Execution is deliberately sequential.

`observed_mapped_ranges` is not a clean-bill-of-health result, evidence of acquisition completeness, a finding that an indicator is absent, or a guarantee of OS/plugin forensic completeness. A scanner can return semantically incorrect results without raising. Generic Intel/Windows/Linux plugin operation has not been validated here; the CLI supports raw and LiME inputs only.

## Evidence and cost

Eight checks exercise known byte positions, chunk boundaries, normal LiME gaps, deliberate read/scanner failures, a genuinely truncated generated LiME payload, requested-range validation and restoration of read methods. All passed on the tested checkout. A clean virtual environment installed the pinned Git commit as version 2.28.3, then ran both CLI cases without the development PYTHONPATH; the expected exit codes and results were preserved. A last-byte request exposes an upstream `IndexError`; the tool records that failure as partial instead of claiming to repair it.

A small three-pair benchmark scanned 16 MiB each time. Median upstream time was 0.009818 seconds; the diagnostic API took 0.013808 seconds. These tiny local timings exclude imports, file hashing and disk acquisition, and are not capacity or performance guarantees. The first CLI examples each took about 1 second including startup and file hashes; a separate clean virtual-environment run took 0.35 and 0.25 seconds. Startup/cache variance is material at these tiny sizes.

The experiment performs no model inference or paid API operation. That does not imply zero allocated development or local-compute cost.

## Prior work and licensing

Volatility already documents that scans may skip missing/unmappable chunks. [Issue 2039](https://github.com/volatilityfoundation/volatility3/issues/2039) separately describes linked-list truncation without a structured completeness signal. ScanLedger does not claim to discover incomplete-memory behavior; it explores a downstream structured observation record for scan consumers. A targeted search has not established novelty or contest acceptance.

Tested official source: [77ff0b1932d77527f850c8ced01d85805ea7bf97](https://github.com/volatilityfoundation/volatility3/tree/77ff0b1932d77527f850c8ced01d85805ea7bf97), reporting version 2.28.3. No upstream source changes are required. The wrapper/Additions and required notice are provided under [Volatility Software License 1.0](LICENSE.txt), not described as MIT.

The scan core and fixtures were prepared by Codex under the account owner's direction on 19 October 2026; the consumer example and accompanying report were updated on 21 October 2026. No human code review or field deployment is claimed. Signed contest ICLA, entrant eligibility and the specific business-bank award recipient remain unconfirmed; publication is not a contest submission.
