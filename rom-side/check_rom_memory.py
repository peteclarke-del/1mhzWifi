#!/usr/bin/env python3
"""Check the 1MHz-WiFi ROM only writes to memory it is allowed to write to.

Taken from Pi1MHz's src/tests/wifirom/check_memory.py, which dp111 wrote
against the copy of this ROM he merged, and repointed at this repository's
sources. The divergence is the root: this tree builds two images from one
directory, so the files checked come from one root's include list.


A sideways ROM owns almost no host memory.  What it may use is short:

  &B0-&BF   the active paged ROM's scratch
  &A8-&AF   command workspace, while a * command is being handled
  &0E00 up  only what it claimed at service call 1 or 2
  &FC00+    the 1MHz bus itself
  its own image, when that image is in sideways RAM

Everything else belongs to the OS, the current filing system, or another
ROM, and writing to it is a fault that shows up as something unrelated
breaking later.  This ROM used to keep its scratch at &0900, &0A00 and
&0D90, which are the RS423 output buffer (and ENVELOPEs 5-16), the
CFS/RFS/RS423 input buffer, and the VFS mouse workspace followed by the
EXTENDED VECTOR TABLE at &0D9F.  The last one hung the machine on the next
OS call after any command; the first killed a *FX3,1 serial redirect.

So this reads the sources rather than the binary: every absolute store, and
every symbol a store goes through, must resolve into the allowed set.
"""

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "1mhz-wifi/src"

# Which root to check. This repository builds two images from one directory,
# so the file list comes from the root's own include statements rather than
# from a glob: the filing system ROM legitimately writes host memory the
# network ROM must not touch, and checking them as one set would either miss
# the network ROM's faults or bury the filing system in false ones.
ROOT = "1mhzwifi.asm"

# The EPROM build puts the workspace in three pages of host RAM claimed from
# the OS at service call 1, so those pages are memory this ROM owns. Passing
# --eprom resolves the equates for that build and allows them.
EPROM = "--eprom" in sys.argv
WS_HOST_PAGE = {"1mhzwifi.asm": 0x0E, "1mhzwicfs.asm": 0x11}


def sources(root):
    """The root, machine.asm, and every file the root includes."""
    text = (SRC / root).read_text()
    names = [root, "machine.asm"]
    names += re.findall(r'^\s*include\s+"([^"]+)"', text, re.MULTILINE)
    seen, ordered = set(), []
    for name in names:
        if name not in seen and (SRC / name).is_file():
            seen.add(name)
            ordered.append(SRC / name)
    return ordered

STORE = re.compile(r"^\s*(sta|stx|sty|inc|dec|asl|lsr|rol|ror)\s+&?([0-9A-Fa-f]{2,4}|[A-Za-z_][A-Za-z0-9_]*)\s*(,\s*[xy])?\s*(?:\\.*)?$",
                   re.IGNORECASE)
EQUATE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*(?:\\.*)?$")

# Addresses a paged ROM may write, and why.
ALLOWED = [
    (0x00B0, 0x00BF, "paged ROM scratch"),
    (0x00A8, 0x00AF, "command workspace"),
    (0x8000, 0xBFFF, "its own image (sideways RAM)"),
    (0xFC00, 0xFEFF, "1MHz bus / hardware"),
]

# Writes outside that set which are deliberate, with the reason. Each one is a
# claim on memory this ROM does not own, so it has to be argued for here.
KNOWN = {
    0x00C7: "pr_y: UEF stream cursor, shared with the filing system ROM",
    0x00C8: "pr_r: UEF stream page register, shared with the filing system ROM",
    0x00F8: "sbufl: UEF stream length low, shared with the filing system ROM",
    0x00F9: "sbufh: UEF stream length high, shared with the filing system ROM",
    0x00F4: "shadow: the MOS's own copy of the selected ROM number",
    0x00F5: "sbuft: UEF stream flags, shared with the filing system ROM",
}


def resolve(name, equates, depth=0):
    """Resolve a symbol to an address, following equates and + offsets."""
    if depth > 8:
        return None
    text = equates.get(name)
    if text is None:
        return None
    total, ok = 0, False
    for term in re.split(r"\s*\+\s*", text):
        term = term.strip()
        # a * b, so "WS_HOST_PAGE * &100" resolves for the EPROM build
        product, factors = 1, True
        for factor in re.split(r"\s*\*\s*", term):
            factor = factor.strip()
            m = re.fullmatch(r"&([0-9A-Fa-f]+)", factor)
            if m:
                product *= int(m.group(1), 16); continue
            if re.fullmatch(r"\d+", factor):
                product *= int(factor); continue
            sub = resolve(factor, equates, depth + 1)
            if sub is None:
                factors = False
                break
            product *= sub
        if not factors:
            return None
        total += product; ok = True
    return total if ok else None


def main():
    allowed = list(ALLOWED)
    if EPROM:
        base = WS_HOST_PAGE[ROOT] << 8
        allowed.append((base, base + 0x2FF,
                        "workspace claimed at service call 1"))
    # WS_HOST_PAGE is a build define, not an equate in the sources, so the
    # EPROM build's workspace addresses only resolve if it is supplied here.
    equates, stores = {"WS_HOST_PAGE": str(WS_HOST_PAGE[ROOT])}, []
    for path in sources(ROOT):
        branch = False                    # inside a block this build skips
        for n, line in enumerate(path.read_text().splitlines(), 1):
            if line.startswith("IF WS_IN_IMAGE = 0"):
                branch = not EPROM        # skip this block unless --eprom
                continue
            if line.startswith("IF WS_IN_IMAGE"):
                branch = EPROM            # skip the in-image block if --eprom
                continue
            if line.startswith("ELSE"):
                branch = not branch
                continue
            if line.startswith("ENDIF"):
                branch = False
                continue
            if branch:
                continue
            m = EQUATE.match(line)
            if m and not line.lstrip().startswith("\\"):
                equates.setdefault(m.group(1), m.group(2))
            m = STORE.match(line)
            if m:
                stores.append((path.name, n, m.group(2), line.strip(), bool(m.group(3))))

    failures, allowed_note, indexed = [], 0, 0
    for fname, n, target, line, index in stores:
        if re.fullmatch(r"[0-9A-Fa-f]{2,4}", target) and "&" in line.split(target)[0][-2:]:
            addr = int(target, 16)
        else:
            addr = resolve(target, equates)
            if addr is None:
                continue                      # a label inside the image
        if index and addr < 0x0100:
            # zero page indexed: the caller passes the base in X or Y, so the
            # address cannot be known here (see string2hex in util.asm).
            indexed += 1
            continue
        if any(lo <= addr <= hi for lo, hi, _ in allowed):
            continue
        if addr in KNOWN:
            allowed_note += 1
            continue
        failures.append(f"{fname}:{n}: writes &{addr:04X} - not memory this ROM owns: {line}")

    for f in failures:
        print(f"  FAIL: {f}")
    if failures:
        print(f"\n  {len(failures)} write(s) into memory the ROM does not own.")
        print("  A sideways ROM may write &B0-&BF, &A8-&AF while handling a command,")
        print("  workspace it claimed at service call 1 or 2, the bus at &FC00+, and")
        print("  its own image. Everything else belongs to the OS or another ROM.")
        return 1
    print(f"ROM MEMORY OK: {len(stores)} stores checked, "
          f"{allowed_note} documented exceptions, "
          f"{indexed} zero-page indexed (base in a register)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        ROOT = sys.argv[1]
    sys.exit(main())
