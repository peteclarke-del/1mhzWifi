"""Where the tests find the host ROM's sources.

The network ROM is dp111's Pi1MHz beeb/1mhz-wifi with this project's patches
and sources applied, and this repository keeps only those additions. The
complete tree exists only once rom-side/build_rom.sh has composed it, so it
is composed here, once per test process. It is recomposed every time rather
than reused when present: a tree left over from before a change to a patch or
a source lets a test pass against code that no longer exists.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
ROM_SRC = REPO / ".build-rom"

subprocess.run(
    [str(REPO / "rom-side/build_rom.sh"), "--sources", str(ROM_SRC)],
    check=True, stdout=subprocess.DEVNULL,
)


def without_merged_wicfs(source: str) -> str:
    """Upstream's 1mhzwifi.asm with its IF INCLUDE_WICFS blocks removed.

    Upstream's root can merge the filing system into the network bank. This
    project builds it with INCLUDE_WICFS=0 and ships the filing system as its
    own image, so what those blocks contain is not in the network ROM. The
    blocks do not nest; an ELSE keeps its branch, which is the one built.
    """
    kept, skipping = [], False
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("IF INCLUDE_WICFS"):
            skipping = True
            continue
        if skipping and stripped in ("ELSE", "ENDIF"):
            skipping = False
            continue
        if not skipping:
            kept.append(line)
    return "\n".join(kept)
