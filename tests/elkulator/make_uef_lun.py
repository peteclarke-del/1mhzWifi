#!/usr/bin/env python3
"""Build a small BeebSCSI LUN holding named UEF titles.

The acceptance sweeps ran against a photographed half-gigabyte hard-disc
image. Reproducing one failing title does not need that, and depending on a
large artifact in /tmp means the reproduction disappears the first time the
directory is cleared. This builds an ADFS image containing only the titles
asked for, in $.UEF where the runner's adfs-beebscsi profile looks for them,
together with the .dsc geometry sidecar BeebSCSI needs.

    python3 tests/elkulator/make_uef_lun.py --out /tmp/repro EXILE:'*Exile*'

Each argument is NAME:GLOB. NAME is the ADFS filename the host will load
(so it must satisfy ADFS naming); GLOB selects the source .uef under the
sample corpus. Requires oaknut-adfs, which is what Acorn File Forge uses.
"""

from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

SECTOR = 256
SECTORS_PER_TRACK = 33
HEADS = 4


def build(entries: dict[str, Path], out_dir: Path, capacity: str) -> tuple[Path, Path]:
    from oaknut.adfs import ADFS

    out_dir.mkdir(parents=True, exist_ok=True)
    lun = out_dir / "scsi0.dat"
    with ADFS.create_file(lun, capacity=capacity, title="UEFTEST",
                          boot_option=0) as filesystem:
        directory = filesystem.root / "UEF"
        directory.mkdir()
        for name, source in entries.items():
            (directory / name).import_file(source)

    # BeebSCSI reads geometry from a 22-byte descriptor beside the image.
    # Bytes 13..15 hold the block count; the host derives the rest.
    blocks = lun.stat().st_size // SECTOR
    descriptor = bytearray(22)
    descriptor[4] = HEADS
    descriptor[13] = (blocks >> 16) & 0xFF
    descriptor[14] = (blocks >> 8) & 0xFF
    descriptor[15] = blocks & 0xFF
    descriptor[16] = SECTORS_PER_TRACK
    dsc = out_dir / "scsi0.dsc"
    dsc.write_bytes(bytes(descriptor))
    return lun, dsc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True,
                        help="directory to write scsi0.dat and scsi0.dsc into")
    parser.add_argument("--samples", type=Path, default=Path("samples"),
                        help="root of the local UEF corpus (not committed)")
    parser.add_argument("--capacity", default="32MiB",
                        help="ADFS image capacity, e.g. 32MiB")
    parser.add_argument("titles", nargs="+", metavar="NAME:GLOB",
                        help="ADFS name and a glob selecting its source .uef")
    args = parser.parse_args()

    if not args.samples.is_dir():
        print(f"sample corpus not found: {args.samples}", file=sys.stderr)
        return 2

    entries: dict[str, Path] = {}
    for spec in args.titles:
        name, separator, pattern = spec.partition(":")
        if not separator:
            print(f"expected NAME:GLOB, got {spec!r}", file=sys.stderr)
            return 2
        matches = sorted(glob.glob(f"{args.samples}/**/{pattern}.uef", recursive=True))
        if not matches:
            print(f"no .uef matched {pattern!r} under {args.samples}", file=sys.stderr)
            return 1
        entries[name] = Path(matches[0])

    lun, dsc = build(entries, args.out, args.capacity)
    for name, source in entries.items():
        print(f"  {name:10s} <- {source.name} ({source.stat().st_size} bytes)")
    print(f"LUN {lun} ({lun.stat().st_size} bytes), geometry {dsc}")
    print("Use with: --profile adfs-beebscsi "
          f"--beebscsi-lun {lun} --beebscsi-dsc {dsc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
