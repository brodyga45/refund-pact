"""CLI proof on generated LiME plus bounded CPU-only paired timing."""
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
os.environ["XDG_CACHE_HOME"] = str(ROOT / "cache")
sys.path.insert(0, str(ROOT / "upstream"))
from volatility3.framework import constants, contexts
from volatility3.framework.layers.physical import BufferDataLayer
from volatility3.framework.layers.scanners import BytesScanner
from scanledger import audit_scan


def main():
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    results = []
    child_env = {"XDG_CACHE_HOME": str(ROOT / "cache"), "PYTHONPATH": str(ROOT / "upstream")}
    for name, expected_exit, expected_hits, expected_status in [
        ("intact", 0, [100, 9000], "observed_mapped_ranges"),
        ("truncated", 2, [100], "partial"),
    ]:
        began = time.monotonic()
        process = subprocess.run([
            sys.executable, str(ROOT / "scanledger.py"), str(ROOT / "examples" / (name + ".lime")),
            "--format", "lime", "--needle", "CONTEST_MARKER", "--chunk-size", "4096",
        ], env=child_env, capture_output=True, text=True, timeout=30)
        report = json.loads(process.stdout)
        assert process.returncode == expected_exit, process.stderr
        assert report["hits"] == expected_hits, report
        assert report["observation_status"] == expected_status, report
        assert report["input_stability_check_equal"] is True
        (out / (name + "-cli.json")).write_text(json.dumps(report, indent=2) + "\n")
        results.append({"file": name, "exit": process.returncode,
                        "hits": report["hits"], "observation_status": expected_status,
                        "CLI_wall_seconds": round(time.monotonic() - began, 6)})

    constants.PARALLELISM = constants.Parallelism.Off
    size = 16 * 1024 * 1024
    needle = b"BENCHMARK_MARKER"
    positions = [123, size // 2 + 777, size - len(needle)]
    data = bytearray(b"." * size)
    for position in positions:
        data[position:position + len(needle)] = needle
    context = contexts.Context()
    layer = BufferDataLayer(context, "benchmark", "benchmark", bytes(data))
    context.layers.add_layer(layer)
    pairs = []
    for _ in range(3):
        scanner = BytesScanner(needle); scanner.chunk_size = 1024 * 1024; scanner.overlap = len(needle) - 1
        began = time.monotonic()
        baseline = list(layer.scan(context, scanner, sections=[(0, size)]))
        baseline_seconds = time.monotonic() - began
        scanner = BytesScanner(needle); scanner.chunk_size = 1024 * 1024; scanner.overlap = len(needle) - 1
        began = time.monotonic()
        observed = audit_scan(context, layer.name, scanner, 0, size)
        audit_seconds = time.monotonic() - began
        assert baseline == positions == observed["hits"]
        assert observed["observation_status"] == "observed_mapped_ranges"
        pairs.append({"baseline_seconds": baseline_seconds, "audit_seconds": audit_seconds})
    report = {
        "generated_examples_only": True, "CLI": results,
        "paired_benchmark": {"input_bytes": size, "pairs": pairs,
            "baseline_median_seconds": statistics.median(x["baseline_seconds"] for x in pairs),
            "audit_median_seconds": statistics.median(x["audit_seconds"] for x in pairs),
            "all_hits_match_known_truth": True,
            "limits": "Tiny local paired timing; API only, excludes imports, file hashes and disk acquisition"},
        "production_or_OS_validation": False, "cash_or_network_operations": 0,
    }
    (out / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
