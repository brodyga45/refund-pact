# ScanLedger — contest motivation and reproduction

Unsent candidate text for the 2026 Volatility Plugin Contest. This document is not an entry, a signed ICLA or an assertion that eligibility has been accepted. The current ICLA copy and confirmation of the intended Serbian sole-proprietor business-bank beneficiary have been requested once.

## What problem the candidate addresses

A byte-scan consumer needs to distinguish an empty result from a scan that failed to observe some declared memory ranges. In the tested Volatility API, a missing read or scanner exception can leave an ordinary list of hits without a warning at the levels captured by this experiment. This is not a newly discovered vulnerability: Volatility documents skipped chunks, and existing issue 2039 describes a separate linked-list truncation problem.

ScanLedger adds an explicit observation record around one sequential API scan. It preserves the upstream hits and records failed reads, incomplete scanner callbacks, padded-read requests, declared mappings and their unobserved portions. Normal physical-address gaps remain separate from read failures. It can help a downstream consumer avoid treating an unobserved range as an examined range.

## Demonstration sample and expected result

The attached source package contains two generated LiME-format fixtures, their construction script and their manifest. They are not acquired OS memory or real incident evidence. The intact fixture declares two memory regions with a normal address gap. Known harmless markers appear at logical addresses 100 and 9000. The truncated fixture retains its declarations and the second marker's bytes but removes the final 64 payload bytes.

Install the pinned official Volatility dependency and run the two commands in README.md. With the included 4096-byte chunk size, the intact fixture returns both markers and an `observed_mapped_ranges` report, exit 0. The truncated fixture returns the upstream result containing only 100; the ledger reports `partial`, exposes the read failure and unobserved mapped range, and exits 2. It does not recover the second marker or correct upstream results.

## Why the candidate may merit an award

The v2 addition demonstrates one explicit downstream policy instead of assuming
that structured diagnostics are useful by themselves. An actual CLI-to-JSON-to-
consumer run allows a narrowly labelled count of two returned entries for the
intact generated input. For the truncated input it retains the one returned hit
but withholds the count from that scoped export. Normal address gaps do not
automatically mean a damaged image. The consumer does not claim that either
outcome certifies forensic completeness or absence of an indicator.

This is an illustrative automated decision, not a practitioner acceptance test.
Properly configured logging/manual review remain alternatives, and simple format
validation can detect this particular deliberately truncated fixture. No
superiority over those alternatives, novelty, adoption or prize prospect is
established. The new example does not run arbitrary plugins or acquire memory.

The proposed contribution is a small, reproducible observation contract for software that consumes a byte scan. Its value would be the distinction between a completed observation and a partial observation, together with evidence sufficient to inspect that distinction. It requires neither a hosted service nor a model, and the CLI reads local raw or LiME files. It does not acquire memory or execute supplied search patterns.

The implementation restores the context's original read attributes and deliberately requires exclusive context ownership. Eight original checks cover byte positions and chunk boundaries, missing reads, scanner exceptions, ordinary mapping gaps, a truncated LiME file, range validation and an upstream last-byte failure. The original v1 clean environment reproduced both CLI outcomes; the extracted v1 ZIP passed its eight checks and all 15 published member hashes matched. The v2 example adds five decision checks and an actual two-case CLI-to-consumer run using an existing local environment, not another clean-install or speed claim.

This evidence supports a bounded candidate, not a claim of novelty, user adoption, forensic certification or a superior contest score. The judges would need to decide whether this API companion is sufficiently useful and distinct from existing work.

## Costs, limits and provenance

The three-pair 16 MiB microbenchmark had median upstream scan time 0.009818 seconds and instrumented time 0.013808 seconds. These timings exclude imports, file hashes and acquisition. Instrumentation has overhead; no performance improvement is claimed.

The report cannot establish complete acquisition, OS/plugin forensic completeness, correct scanner semantics or an indicator's absence. Read-error spans can overstate the actual missing bytes. Matching pre/post file hashes do not establish immutable history. Generic Intel, Windows and Linux plugin operation and production-scale use have not been validated.

Code, fixtures and documentation were prepared by Codex under brodyga45's direction. No human code review or field use is claimed. Volatility wrappers/Additions and the included notice use Volatility Software License 1.0; the candidate is not labeled MIT. No upstream modification is required, no maintainer has accepted this work, and no award or payment has occurred.

Public source: https://github.com/brodyga45/refund-pact/tree/codex/scanledger-candidate

Original published scan-core commit: 315c330dcdf31d1f66e26761c78418ca2bd8c173.
The v2 consumer example retains that scan implementation unchanged; its current
source/archive references are recorded in the accompanying v2 manifest.
