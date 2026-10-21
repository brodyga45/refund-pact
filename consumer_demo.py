"""Run the bounded generated-LiME scan-to-consumer example (VSL 1.0)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output:
        out = args.output
        out.mkdir(parents=True, exist_ok=False)
    else:
        out = Path(tempfile.mkdtemp(prefix="scanledger-consumer-"))
    env = os.environ.copy()
    # Keep dependency startup/cache writes inside this owned output directory.
    env["XDG_CACHE_HOME"] = str(out.resolve() / "cache")
    if (ROOT / "upstream").is_dir():
        env["PYTHONPATH"] = str(ROOT / "upstream")
    else:
        env.pop("PYTHONPATH", None)
    rows = []
    for name, expected_scan, expected_count in [("intact", 0, 2), ("truncated", 2, None)]:
        sample = ROOT / "examples" / (name + ".lime")
        before = sha(sample)
        scan = subprocess.run([sys.executable, str(ROOT / "scanledger.py"), str(sample),
                               "--format", "lime", "--needle", "CONTEST_MARKER", "--chunk-size", "4096"],
                              env=env, capture_output=True, text=True, timeout=20)
        (out / (name + "-scan.json")).write_text(scan.stdout)
        (out / (name + "-scan.stderr.txt")).write_text(scan.stderr)
        assert scan.returncode == expected_scan, (name, scan.returncode)
        report = json.loads(scan.stdout)
        decision = subprocess.run([sys.executable, str(ROOT / "consumer_gate.py"),
                                   str(out / (name + "-scan.json"))],
                                  capture_output=True, text=True, timeout=10)
        (out / (name + "-decision.json")).write_text(decision.stdout)
        result = json.loads(decision.stdout)
        assert result["count_for_scoped_export"] == expected_count
        assert decision.returncode == expected_scan
        assert report["hits"] == result["returned_hits_retained"]
        assert sha(sample) == before
        rows.append({"fixture": name, "generated_not_acquired_OS_memory": True,
                     "input_sha256_unchanged": before,
                     "scan_exit": scan.returncode, "consumer_exit": decision.returncode,
                     "observation_status": report["observation_status"],
                     "decision": result["decision"],
                     "observed_hit_entries_retained": result["observed_hit_entries_retained"],
                     "count_for_scoped_export": result["count_for_scoped_export"],
                     "normal_unmapped_ranges": report["unmapped_requested_ranges"]})
    receipt = {"workflow": "Actual local ScanLedger CLI -> JSON -> consumer CLI",
               "cases": rows,
               "meaning": "A partial positive hit list is retained for review rather than exported as a completed scoped count. Normal declared address gaps do not block the intact case.",
               "not_established": ["Indicator absence or scanner semantic correctness", "Acquisition or OS/plugin forensic completeness",
                                   "Practical superiority to correctly configured logging/manual review", "Real practitioner adoption, novelty or award"],
               "core_scan_algorithm_changed": False, "new_LLM_or_paid_API_calls": 0,
               "new_cash_spend": 0, "performance_benchmark": False}
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
