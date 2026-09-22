"""Resolve a ROM source symbol to its address.

Tests used to hard-code the workspace addresses they watched: &0D90 for the
error block, &0DAE for the UEF stream generation. When the workspace moved
into the ROM image those constants silently stopped describing anything, and
the tests failed in ways that looked like the ROM had broken rather than the
test. Ask the sources instead.
"""

from __future__ import annotations

import re
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "rom-side/1mhz-wifi/src"
EQUATE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*(?:\\.*)?$")

_equates: dict[str, str] = {}


def _load() -> dict[str, str]:
    if not _equates:
        for path in sorted(SRC.glob("*.asm")):
            for line in path.read_text().splitlines():
                if line.lstrip().startswith("\\"):
                    continue
                match = EQUATE.match(line)
                if match:
                    _equates.setdefault(match.group(1), match.group(2))
    return _equates


def symbol(name: str, depth: int = 0) -> int:
    """The address `name` resolves to, following equates and + offsets."""
    if depth > 8:
        raise AssertionError(f"{name}: equate chain too deep")
    text = _load().get(name)
    if text is None:
        raise AssertionError(f"{name} is not an equate in {SRC}")
    total = 0
    for term in re.split(r"\s*\+\s*", text):
        term = term.strip()
        hexadecimal = re.fullmatch(r"&([0-9A-Fa-f]+)", term)
        if hexadecimal:
            total += int(hexadecimal.group(1), 16)
        elif re.fullmatch(r"\d+", term):
            total += int(term)
        else:
            total += symbol(term, depth + 1)
    return total
