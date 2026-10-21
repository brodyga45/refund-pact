"""Example consumer of trusted local ScanLedger CLI JSON, under VSL 1.0.

Decide whether to export this run's scoped observation count. This is not a
forensic completeness, indicator-absence, or authenticity verifier.
"""
import argparse
import json
from pathlib import Path

SCOPE = ("Returned hit entries in this run's declared mapped requested ranges only; "
         "not indicator absence, scanner correctness, acquisition or OS/plugin completeness")


def export_decision(report):
    """Retain partial observations, but withhold their publication as a scoped count."""
    reasons = []
    hits = report.get("hits") if isinstance(report, dict) else None
    hits_valid = isinstance(hits, list) and all(type(x) is int and x >= 0 for x in hits)
    if not isinstance(report, dict):
        report = {}
    if type(report.get("schema_version")) is not int or report.get("schema_version") != 1:
        reasons.append("unsupported_or_missing_schema")
    if not hits_valid:
        reasons.append("missing_or_invalid_hit_entries")
    if report.get("observation_status") != "observed_mapped_ranges":
        reasons.append("observation_not_reported_complete_within_its_narrow_scope")
    if not report.get("mapped_ranges") or not report.get("completed_scanner_ranges"):
        reasons.append("no_declared_mapped_observations")
    for key in ("unobserved_mapped_ranges", "read_failures", "scanner_errors", "padded_read_requests"):
        if report.get(key) != []:
            reasons.append(key + "_nonempty_or_missing")
    if "top_level_exception" not in report or report["top_level_exception"] is not None:
        reasons.append("top_level_exception_or_missing_status")
    before, after = report.get("input_sha256_before"), report.get("input_sha256_after")
    if (report.get("input_stability_check_equal") is not True
            or not isinstance(before, str) or len(before) != 64
            or any(c not in "0123456789abcdef" for c in before) or before != after):
        reasons.append("input_stability_not_established_by_producer")
    eligible = not reasons
    return {
        "consumer_example_version": 1,
        "decision": "export_scoped_observation_count" if eligible else "withhold_scoped_count_for_review",
        "count_for_scoped_export": len(hits) if eligible else None,
        "observed_hit_entries_retained": len(hits) if hits_valid else None,
        "returned_hits_retained": hits if hits_valid else None,
        "requested_range": report.get("requested_range"),
        "declared_mapped_ranges": report.get("mapped_ranges"),
        "reasons": reasons,
        "claim_scope": SCOPE,
        "next_action": ("Export only with the scope label and source report."
                        if eligible else "Retain observations; review the input/run before treating the count as complete even in the declared scope."),
        "trust_boundary": "Consumes a trusted local producer report; does not authenticate its claims or reopen the input.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        report = None
    result = export_decision(report)
    print(json.dumps(result, indent=2))
    return 0 if result["count_for_scoped_export"] is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())
