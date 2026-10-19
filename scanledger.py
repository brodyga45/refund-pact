"""Report observation gaps in one sequential Volatility API byte scan.

Original experiment code, 2026. Distributed wrappers/Additions are subject to
Volatility Software License 1.0; see upstream/LICENSE.txt. This is not an OS
forensic completeness guarantee. No memory acquisition or network is performed.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import time

from volatility3.framework import constants, contexts, interfaces
from volatility3.framework.layers import lime, physical
from volatility3.framework.layers.scanners import BytesScanner


def merged_ranges(ranges):
    result = []
    for start, end in sorted(ranges):
        if end <= start:
            continue
        if result and start <= result[-1][1]:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result


def unobserved_ranges(start, end, completed):
    result = []
    cursor = start
    for low, high in merged_ranges(completed):
        low, high = max(low, start), min(high, end)
        if high <= low:
            continue
        if cursor < low:
            result.append([cursor, low])
        cursor = max(cursor, high)
    if cursor < end:
        result.append([cursor, end])
    return result


@contextmanager
def observe_reads(context, failures, padded_reads):
    """Observe this context only, then restore every original instance attribute.

    The caller must own this context exclusively during the sequential scan.
    Read failures are conservative uncertainty spans, not exact missing pages.
    """
    restore = []
    try:
        for name in context.layers:
            layer = context.layers[name]
            had_attribute = "read" in vars(layer)
            instance_value = vars(layer).get("read")
            original = layer.read

            def observed(offset, length, pad=False, _read=original, _name=name):
                if pad:
                    padded_reads.append({"layer": _name, "start": offset, "length": length})
                try:
                    return _read(offset, length, pad)
                except Exception as error:
                    failures.append({
                        "layer": _name, "start": offset, "length": length,
                        "exception": type(error).__name__,
                        "invalid_address": getattr(error, "invalid_address", None),
                    })
                    raise

            layer.read = observed
            restore.append((layer, had_attribute, instance_value))
        yield
    finally:
        for layer, had_attribute, instance_value in reversed(restore):
            if had_attribute:
                layer.read = instance_value
            else:
                del layer.read


class ObservedScanner(interfaces.layers.ScannerInterface):
    thread_safe = False
    _version = (0, 1, 0)
    _required_framework_version = (2, 0, 0)

    def __init__(self, scanner, callbacks, errors):
        super().__init__()
        self.original = scanner
        self.callbacks = callbacks
        self.errors = errors
        self.chunk_size = scanner.chunk_size
        self.overlap = scanner.overlap

    def __call__(self, data, offset):
        row = {"start": offset, "end": offset + len(data), "completed": False}
        self.callbacks.append(row)
        self.original.context = self.context
        self.original.layer_name = self.layer_name
        try:
            yield from self.original(data, offset)
            row["completed"] = True
        except Exception as error:
            self.errors.append({"start": offset, "end": offset + len(data),
                                "exception": type(error).__name__})
            raise


def audit_scan(context, layer_name, scanner, start, length):
    """Return actual upstream hits plus a bounded observation claim.

    This is an instrumentation mode, not a recovery algorithm. It cannot detect
    a scanner's semantic mistakes or prove that the acquired image was complete.
    """
    layer = context.layers[layer_name]
    end = start + length
    if length <= 0 or start < layer.minimum_address or end > layer.maximum_address + 1:
        raise ValueError("Requested nonempty range must fit the layer's address envelope")
    failures, padded, callbacks, scanner_errors = [], [], [], []
    wrapped = ObservedScanner(scanner, callbacks, scanner_errors)
    began = time.monotonic()
    hits = []
    top_error = None
    mapped = []
    with observe_reads(context, failures, padded):
        try:
            if isinstance(layer, interfaces.layers.TranslationLayerInterface):
                mapped = merged_ranges((max(start, offset), min(end, offset + size))
                    for offset, size, *_ in layer.mapping(start, length, ignore_errors=True))
            else:
                mapped = [[start, end]]
            for hit in layer.scan(context, wrapped, sections=[(start, length)]):
                hits.append(hit)
        except Exception as error:
            top_error = type(error).__name__
    completed = merged_ranges((c["start"], c["end"]) for c in callbacks if c["completed"])
    missing = [part for low, high in mapped for part in unobserved_ranges(low, high, completed)]
    unmapped = unobserved_ranges(start, end, mapped)
    partial = bool(missing or failures or scanner_errors or top_error or padded)
    return {
        "schema_version": 1,
        "observation_status": "partial" if partial else "observed_mapped_ranges",
        "claim_scope": "Declared mapped byte ranges delivered to completed scanner callbacks in this run only",
        "requested_range": [start, end], "ranges_are_half_open": True,
        "mapped_ranges": mapped, "unmapped_requested_ranges": unmapped,
        "unobserved_mapped_ranges": missing, "completed_scanner_ranges": completed,
        "hits": hits, "read_failures": failures, "scanner_errors": scanner_errors,
        "padded_read_requests": padded, "top_level_exception": top_error,
        "scanner_callbacks": callbacks,
        "wall_seconds": round(time.monotonic() - began, 6),
        "limitations": [
            "No guarantee about acquisition completeness or OS/plugin forensic completeness",
            "No validation of scanner semantics; padded reads conservatively mark partial",
            "Exclusive context ownership and sequential execution required",
            "Read failure spans may exceed the truly unreadable bytes",
            "Unmapped ranges may be normal physical address gaps; they are not labelled failed reads",
        ],
    }


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--format", choices=["raw", "lime"], default="raw")
    parser.add_argument("--needle", required=True, help="Literal UTF-8 bytes; never executes a pattern")
    parser.add_argument("--start", type=lambda v: int(v, 0))
    parser.add_argument("--length", type=lambda v: int(v, 0))
    parser.add_argument("--chunk-size", type=int, default=0x1000000)
    args = parser.parse_args()
    needle = args.needle.encode("utf-8")
    if not needle or len(needle) > 65536 or not 1 <= args.chunk_size <= 0x4000000:
        parser.error("Use a nonempty needle <=64KiB and chunk size between1 and64MiB")
    constants.OFFLINE = True
    context = contexts.Context()
    image = args.image.resolve(strict=True)
    before_stat = image.stat()
    before_hash = file_hash(image)
    context.config["file.location"] = image.as_uri()
    file_layer = physical.FileLayer(context, "file", "file")
    context.layers.add_layer(file_layer)
    selected = file_layer
    if args.format == "lime":
        context.config["lime.base_layer"] = "file"
        selected = lime.LimeLayer(context, "lime", "lime")
        context.layers.add_layer(selected)
    start = selected.minimum_address if args.start is None else args.start
    length = selected.maximum_address + 1 - start if args.length is None else args.length
    scanner = BytesScanner(needle)
    scanner.chunk_size = args.chunk_size
    scanner.overlap = len(needle) - 1
    try:
        report = audit_scan(context, selected.name, scanner, start, length)
        after_hash, after_stat = file_hash(image), image.stat()
        stable = (before_hash == after_hash and
                  (before_stat.st_dev, before_stat.st_ino, before_stat.st_size, before_stat.st_mtime_ns) ==
                  (after_stat.st_dev, after_stat.st_ino, after_stat.st_size, after_stat.st_mtime_ns))
        if not stable:
            report["observation_status"] = "partial"
        report.update(input_name=image.name, input_sha256_before=before_hash,
                      input_sha256_after=after_hash, input_stability_check_equal=stable,
                      needle_sha256=hashlib.sha256(needle).hexdigest(), image_format=args.format)
        report["limitations"].append("Matching pre/post hashes do not prove absence of concurrent modifications; use a stable readonly input")
        print(json.dumps(report, indent=2))
    finally:
        file_layer.destroy()
    return 2 if report["observation_status"] == "partial" else 0


if __name__ == "__main__":
    raise SystemExit(main())
