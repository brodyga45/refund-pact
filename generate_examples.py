"""Generate transparent memory-format fixtures; no actual RAM is acquired."""
import hashlib
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
OUT = HERE / "examples"
MARKER = b"CONTEST_MARKER"


def main():
    OUT.mkdir(exist_ok=True)
    first, second = bytearray(b"." * 4096), bytearray(b"." * 4096)
    first[100:100 + len(MARKER)] = MARKER
    second[808:808 + len(MARKER)] = MARKER
    intact = (struct.pack("<IIQQQ", 0x4C694D45, 1, 0, 4095, 0) + first
              + struct.pack("<IIQQQ", 0x4C694D45, 1, 8192, 12287, 0) + second)
    records = []
    for name, data in [("intact.lime", intact), ("truncated.lime", intact[:-64])]:
        (OUT / name).write_bytes(data)
        records.append({"file": name, "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest()})
    manifest = {
        "generated_fixture": True, "real_OS_or_incident_memory": False,
        "files": records, "declared_mapped_ranges": [[0, 4096], [8192, 12288]],
        "normal_unmapped_range": [4096, 8192],
        "logical_marker_positions_in_intact": [100, 9000],
        "truncated_mutation": "Remove final64payloadbytes, leave declarations unchanged",
        "known_marker_9000_bytes_still_present_in_truncated": True,
        "purpose": "Show that a whole failed read can discard a marker before the truncated tail",
        "private_data_or_credentials": False,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest))


if __name__ == "__main__":
    main()
