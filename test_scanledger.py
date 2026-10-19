"""Independent byte-position and format fixtures, not real incident memories."""
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
os.environ["XDG_CACHE_HOME"] = str(ROOT / "cache")
sys.path.insert(0, str(ROOT / "upstream"))
from volatility3.framework import contexts, constants, exceptions
from volatility3.framework.layers import lime, physical
from volatility3.framework.layers.scanners import BytesScanner
from scanledger import audit_scan

NEEDLE = b"CONTEST_MARKER"


def known_buffer(size, offsets):
    data = bytearray(b"." * size)
    for offset in offsets:
        data[offset:offset + len(NEEDLE)] = NEEDLE
    return bytes(data)


def scanner():
    result = BytesScanner(NEEDLE)
    result.chunk_size = 4096
    result.overlap = len(NEEDLE) - 1
    return result


def buffer_layer(data, cls=physical.BufferDataLayer):
    context = contexts.Context()
    layer = cls(context=context, config_path="sample", name="sample", buffer=data)
    context.layers.add_layer(layer)
    return context, layer


def lime_file(path, truncate=0):
    # Two declared 4096-byte regions separated by a normal unmapped region.
    data = b"".join([
        struct.pack("<IIQQQ", 0x4C694D45, 1, 0, 4095, 0),
        known_buffer(4096, [100]),
        struct.pack("<IIQQQ", 0x4C694D45, 1, 8192, 12287, 0),
        known_buffer(4096, [808]),
    ])
    path.write_bytes(data[:-truncate] if truncate else data)


def open_lime(path):
    context = contexts.Context()
    context.config["file.location"] = path.resolve().as_uri()
    base = physical.FileLayer(context, "file", "file")
    context.layers.add_layer(base)
    context.config["lime.base_layer"] = "file"
    layer = lime.LimeLayer(context, "lime", "lime")
    context.layers.add_layer(layer)
    return context, layer, base


class AuditChecks(unittest.TestCase):
    def setUp(self):
        constants.OFFLINE = True
        constants.PARALLELISM = constants.Parallelism.Off

    def test_clean_edges_and_chunk_boundary_match_known_positions(self):
        positions = [0, 4089, 8192, 16384 - len(NEEDLE)]
        data = known_buffer(16384, positions)
        context, layer = buffer_layer(data)
        baseline = list(layer.scan(context, scanner(), sections=[(0, len(data))]))
        report = audit_scan(context, layer.name, scanner(), 0, len(data))
        self.assertEqual(baseline, positions)
        self.assertEqual(report["hits"], positions)
        self.assertEqual(report["observation_status"], "observed_mapped_ranges")
        self.assertEqual(report["unobserved_mapped_ranges"], [])
        self.assertEqual(layer.read(0, len(data)), data)

    def test_no_hits_is_observed_only_when_all_mapped_bytes_checked(self):
        context, layer = buffer_layer(b"." * 16384)
        report = audit_scan(context, layer.name, scanner(), 0, 16384)
        self.assertEqual(report["hits"], [])
        self.assertEqual(report["observation_status"], "observed_mapped_ranges")
        self.assertEqual(report["completed_scanner_ranges"], [[0, 16384]])

    def test_read_failure_marks_unknown_without_changing_upstream_hits(self):
        class Faulted(physical.BufferDataLayer):
            def read(self, offset, length, pad=False):
                if offset < 8192 and offset + length > 4096:
                    raise exceptions.InvalidAddressException(self.name, 4096, "fixture")
                return super().read(offset, length, pad)
        context, layer = buffer_layer(known_buffer(16384, [100, 9000]), Faulted)
        baseline = list(layer.scan(context, scanner(), sections=[(0, 16384)]))
        report = audit_scan(context, layer.name, scanner(), 0, 16384)
        self.assertEqual(baseline, [9000])
        self.assertEqual(report["hits"], baseline)
        self.assertEqual(report["observation_status"], "partial")
        self.assertTrue(report["read_failures"])
        self.assertTrue(any(low <= 100 < high for low, high in report["unobserved_mapped_ranges"]))
        self.assertNotIn("read", vars(layer))

    def test_scanner_exception_is_visible_when_upstream_swallows_it(self):
        class Broken(BytesScanner):
            def __call__(self, data, offset):
                if offset >= 4096:
                    raise RuntimeError("fixture scanner failure")
                yield from super().__call__(data, offset)
        context, layer = buffer_layer(known_buffer(16384, [100, 9000]))
        first = Broken(NEEDLE); first.chunk_size = 4096; first.overlap = len(NEEDLE) - 1
        baseline = list(layer.scan(context, first, sections=[(0, 16384)]))
        second = Broken(NEEDLE); second.chunk_size = 4096; second.overlap = len(NEEDLE) - 1
        report = audit_scan(context, layer.name, second, 0, 16384)
        self.assertEqual(baseline, [100])
        self.assertEqual(report["hits"], baseline)
        self.assertEqual(report["observation_status"], "partial")
        self.assertEqual(report["scanner_errors"][0]["exception"], "RuntimeError")
        self.assertTrue(any(low <= 9000 < high for low, high in report["unobserved_mapped_ranges"]))

    def test_valid_lime_normal_address_gap_is_not_a_read_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "generated.lime"
            lime_file(path)
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            context, layer, base = open_lime(path)
            try:
                baseline = list(layer.scan(context, scanner(), sections=[(0, 12288)]))
                report = audit_scan(context, layer.name, scanner(), 0, 12288)
                self.assertEqual(baseline, [100, 9000])
                self.assertEqual(report["hits"], baseline)
                self.assertEqual(report["unmapped_requested_ranges"], [[4096, 8192]])
                self.assertEqual(report["read_failures"], [])
                self.assertEqual(report["unobserved_mapped_ranges"], [])
                self.assertEqual(report["observation_status"], "observed_mapped_ranges")
                self.assertNotIn("read", vars(base))
                self.assertNotIn("read", vars(layer))
            finally:
                base.destroy()
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)

    def test_truncated_lime_exposes_loss_on_real_format_without_fault_hook(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "truncated.lime"
            lime_file(path, truncate=64)
            context, layer, base = open_lime(path)
            try:
                baseline = list(layer.scan(context, scanner(), sections=[(0, 12288)]))
                report = audit_scan(context, layer.name, scanner(), 0, 12288)
                self.assertEqual(baseline, [100])
                self.assertEqual(report["hits"], baseline)
                self.assertEqual(report["observation_status"], "partial")
                self.assertTrue(report["read_failures"])
                self.assertTrue(any(low <= 9000 < high for low, high in report["unobserved_mapped_ranges"]))
            finally:
                base.destroy()

    def test_upstream_last_byte_failure_is_not_mislabeled_observed(self):
        context, layer = buffer_layer(b"0123456789X")
        with self.assertRaises(IndexError):
            list(layer.scan(context, BytesScanner(b"X"), sections=[(10, 1)]))
        report = audit_scan(context, layer.name, BytesScanner(b"X"), 10, 1)
        self.assertEqual(report["hits"], [])
        self.assertEqual(report["top_level_exception"], "IndexError")
        self.assertEqual(report["unobserved_mapped_ranges"], [[10, 11]])
        self.assertEqual(report["observation_status"], "partial")

    def test_invalid_requested_ranges_do_not_claim_any_coverage(self):
        context, layer = buffer_layer(b"abc")
        for start, length in [(0, 0), (-1, 1), (0, 4)]:
            with self.assertRaises(ValueError):
                audit_scan(context, layer.name, scanner(), start, length)
        self.assertNotIn("read", vars(layer))


if __name__ == "__main__":
    unittest.main(verbosity=2)
