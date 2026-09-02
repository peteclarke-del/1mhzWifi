#!/usr/bin/env python3
"""Report software that loads over the MOS extended vector table &0D9F-&0DEF.

A filing system installed through MOS extended vectors keeps its dispatch
entries in that table. If a title loads a file across it, the filing system
loses its vectors mid-load, which is the problem WiCFS answers with a
trampoline below the loader overwrite range.

An earlier SSD plan assumed disc software could not touch the table because DFS
lives there, and so would need no trampoline. This measures that rather than
assuming it, over both DFS `.ssd` catalogues and cassette `.uef` streams.

Catalogue entries with `load=&0000` carry no fixed load address - the program
places them itself - so they are excluded. Results are floors either way: a
title can write to page &0D at run time without loading a file there.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

SPEC = importlib.util.spec_from_file_location(
    "uef_loader_scan", Path(__file__).resolve().parent / "uef_loader_scan.py"
)
uef_loader_scan = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(uef_loader_scan)

TABLE_LOW, TABLE_HIGH = 0x0D9F, 0x0DEF


def covers_table(load: int, length: int) -> bool:
    """A file with no fixed load address cannot be said to cover anything."""
    return load != 0 and load <= TABLE_HIGH and load + length > TABLE_LOW


def dfs_catalogue(path: Path) -> list[tuple[str, int, int]]:
    """Name, load address and length for each file in a DFS disc image."""
    image = path.read_bytes()
    if len(image) < 512:
        raise ValueError("shorter than the two catalogue sectors")
    names, meta = image[0:256], image[256:512]
    if meta[5] % 8:
        raise ValueError("catalogue length is not a whole number of entries")
    entries = []
    for index in range(meta[5] // 8):
        at = 8 + index * 8
        record = meta[at:at + 8]
        # The top bits of byte 6 extend load, length and execution addresses.
        load = record[0] | (record[1] << 8) | (((record[6] >> 2) & 3) << 16)
        length = record[4] | (record[5] << 8) | (((record[6] >> 4) & 3) << 16)
        name = names[at:at + 7].decode("latin-1").rstrip()
        directory = chr(names[at + 7] & 0x7F)
        entries.append((f"{directory}.{name}", load & 0xFFFF, length))
    return entries


def scan_disc(path: Path) -> list[str]:
    return [name for name, load, length in dfs_catalogue(path)
            if covers_table(load, length)]


def scan_tape(path: Path) -> list[str]:
    return [entry["name"] for entry in uef_loader_scan.cassette_files(path)
            if covers_table(entry["load_address"] & 0xFFFF, len(entry["data"]))]


def survey(paths: list[Path]) -> dict[str, Any]:
    hits, examined, unreadable = [], 0, []
    for path in paths:
        scan = scan_disc if path.suffix.lower() == ".ssd" else scan_tape
        try:
            files = scan(path)
        except Exception as error:            # untrusted third-party media
            unreadable.append({"path": path.name, "error": str(error)})
            continue
        examined += 1
        if files:
            hits.append({"image": path.name, "files": files})
    return {"examined": examined, "unreadable": unreadable, "overlapping": hits}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", nargs="+", type=Path,
                        help=".ssd or .uef files, or directories to walk")
    parser.add_argument("--json", action="store_true")
    arguments = parser.parse_args()

    paths: list[Path] = []
    for entry in arguments.path:
        if entry.is_dir():
            paths.extend(sorted(p for p in entry.rglob("*")
                                if p.suffix.lower() in (".ssd", ".uef")))
        else:
            paths.append(entry)

    report = survey(paths)
    if arguments.json:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    for hit in report["overlapping"]:
        print(f"{hit['image']}: {', '.join(hit['files'])}")
    examined = report["examined"]
    count = len(report["overlapping"])
    print()
    print(f"images examined          : {examined}")
    print(f"unreadable               : {len(report['unreadable'])}")
    share = f"  ({100.0 * count / examined:.1f}%)" if examined else ""
    print(f"loading over &0D9F-&0DEF : {count}{share}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
