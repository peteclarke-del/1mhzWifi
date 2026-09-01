#!/usr/bin/env python3
"""Report cassette files in a UEF and any direct write to the FILEV vector.

Many published Electron titles defend their tape loader by stamping FILEV
(`&0212`) with the Electron MOS 1.00 cassette entry `&F1D6`, usually alongside
OSBYTE `163,128,1` and `?&2AC=0`. The stamp is written blind: it overwrites
whatever filing system currently owns the vector, including the WiCFS guard.
This scanner measures how much of a corpus does that, so the question is
settled by counting rather than by one title's symptoms.

The stamp is matched as literal text. BBC BASIC tokenises keywords but leaves
`?`, `&` and digits as ASCII, so the assignment survives verbatim in the
tokenised program and needs no detokeniser to find or to quote.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import struct
import sys
from pathlib import Path
from typing import Any

SPEC = importlib.util.spec_from_file_location(
    "uef_map", Path(__file__).resolve().parent / "uef_map.py"
)
uef_map = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(uef_map)

# `?&212=<low>` then `?&213=<high>`, in either hex or decimal, allowing the
# spacing published loaders actually use.
BYTE = r"(?:&([0-9A-Fa-f]{1,2})|(\d{1,3}))"
STAMP = re.compile(
    rf"\?\s*&\s*212\s*=\s*{BYTE}\s*:\s*\?\s*&\s*213\s*=\s*{BYTE}".encode(),
    re.IGNORECASE,
)
ANY_STAMP = re.compile(rb"\?\s*&\s*212\s*=", re.IGNORECASE)
OSBYTE_163 = re.compile(rb"163\s*:\s*X%\s*=\s*128", re.IGNORECASE)


def _value(hex_text: bytes | None, decimal_text: bytes | None) -> int:
    return int(hex_text, 16) if hex_text else int(decimal_text)


def printable_run(data: bytes, at: int, limit: int = 160) -> str:
    """The printable text surrounding a match, for quoting in a report."""
    start = at
    while start > 0 and 32 <= data[start - 1] < 127 and at - start < limit:
        start -= 1
    end = at
    while end < len(data) and 32 <= data[end] < 127 and end - at < limit:
        end += 1
    return data[start:end].decode("latin-1").strip()


def cassette_files(path: Path) -> list[dict[str, Any]]:
    """Reassemble whole cassette files from the &0100 blocks of a UEF."""
    raw, _, _ = uef_map.decode_container(path.read_bytes())
    files: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    position, index = uef_map.HEADER_SIZE, 0
    while position + 6 <= len(raw):
        chunk_type, length = struct.unpack_from("<HI", raw, position)
        start, end = position + 6, position + 6 + length
        if end > len(raw):
            break
        if chunk_type == 0x0100:
            block = uef_map.inspect_cfs_block(raw[start:end], index, position)
            if block is not None:
                at = start + block["data_offset_in_chunk"]
                data = raw[at:at + block["data_length"]]
                if block["block_number"] == 0 or current is None:
                    current = {
                        "name": block["name"],
                        "load_address": block["load_address"],
                        "execution_address": block["execution_address"],
                        "data": bytearray(),
                    }
                    files.append(current)
                current["data"].extend(data)
                if block["last_block"]:
                    current = None
            index += 1
        position = end
    return files


def scan(path: Path) -> dict[str, Any]:
    report: dict[str, Any] = {"path": str(path), "files": [], "stamps": []}
    for entry in cassette_files(path):
        data = bytes(entry["data"])
        report["files"].append({
            "name": entry["name"],
            "load_address": f"&{entry['load_address'] & 0xFFFFFFFF:X}",
            "execution_address": f"&{entry['execution_address'] & 0xFFFFFFFF:X}",
            "length": len(data),
        })
        for match in STAMP.finditer(data):
            low = _value(match.group(1), match.group(2))
            high = _value(match.group(3), match.group(4))
            report["stamps"].append({
                "file": entry["name"],
                "filev": f"&{(high << 8) | low:04X}",
                "mos_cassette_entry": ((high << 8) | low) == 0xF1D6,
                "with_osbyte_163": bool(OSBYTE_163.search(data)),
                "text": printable_run(data, match.start()),
            })
        if not STAMP.search(data):
            for match in ANY_STAMP.finditer(data):
                report["stamps"].append({
                    "file": entry["name"],
                    "filev": None,
                    "mos_cassette_entry": False,
                    "with_osbyte_163": bool(OSBYTE_163.search(data)),
                    "text": printable_run(data, match.start()),
                })
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("uef", nargs="+", type=Path,
                        help="UEF files, or directories to walk with --scan")
    parser.add_argument("--scan", action="store_true",
                        help="walk directories and summarise the whole corpus")
    parser.add_argument("--json", action="store_true")
    arguments = parser.parse_args()

    paths: list[Path] = []
    for entry in arguments.uef:
        paths.extend(sorted(entry.rglob("*.uef")) if entry.is_dir() else [entry])

    reports, unreadable = [], []
    for path in paths:
        try:
            reports.append(scan(path))
        except (uef_map.UefError, OSError, ValueError) as error:
            unreadable.append({"path": str(path), "error": str(error)})

    stamped = [r for r in reports if r["stamps"]]
    summary = {
        "examined": len(reports),
        "unreadable": len(unreadable),
        "stamping_filev": len(stamped),
        "stamping_mos_cassette_entry": sum(
            1 for r in stamped
            if any(s["mos_cassette_entry"] for s in r["stamps"])
        ),
        "with_osbyte_163": sum(
            1 for r in stamped if any(s["with_osbyte_163"] for s in r["stamps"])
        ),
    }
    if arguments.json:
        json.dump({"summary": summary, "reports": reports,
                   "unreadable": unreadable}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    if arguments.scan:
        for report in stamped:
            targets = sorted({s["filev"] or "?" for s in report["stamps"]})
            print(f"{Path(report['path']).name}: FILEV <- {', '.join(targets)}")
        print()
        for key, value in summary.items():
            print(f"{key.replace('_', ' '):32} {value}")
        return 0

    for report in reports:
        print(f"File: {report['path']}")
        for entry in report["files"]:
            print(f"  {entry['name']:<12} load={entry['load_address']:<10} "
                  f"exec={entry['execution_address']:<10} len={entry['length']}")
        for stamp in report["stamps"]:
            target = stamp["filev"] or "(unrecognised form)"
            note = " MOS cassette entry" if stamp["mos_cassette_entry"] else ""
            print(f"  FILEV stamp in {stamp['file']!r}: {target}{note}")
            print(f"    {stamp['text']}")
    for entry in unreadable:
        print(f"unreadable: {entry['path']}: {entry['error']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
