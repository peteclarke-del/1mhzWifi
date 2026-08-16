#!/usr/bin/env python3
"""Reject writes by the final WiCFS source into the MOS keyboard buffer."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


WRITE_OPS = {"STA", "STX", "STY", "INC", "DEC", "ASL", "LSR", "ROL", "ROR"}
EQUATE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^\\:]+)")
INSTRUCTION = re.compile(
    r"^\s*(?:\.[A-Za-z_][A-Za-z0-9_.]*\s+)?"
    r"(STA|STX|STY|INC|DEC|ASL|LSR|ROL|ROR)\s+([^\\:]+)", re.I
)
NAME = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
HEX = re.compile(r"&([0-9A-Fa-f]+)")
FILENAME_WRITE = re.compile(r"^\s*STA\s+&0?3D2\s*,\s*X\s*$", re.I)
FILENAME_LIMIT = re.compile(r"^\s*CPX\s+#(?:&0*A|10)\s*$", re.I)
BOUNDS_BRANCH = re.compile(r"^\s*BCS\s+[A-Za-z_.][A-Za-z0-9_.]*\s*$", re.I)


def evaluate(expression: str, symbols: dict[str, int]) -> int | None:
    expression = expression.strip().split(",", 1)[0]
    if expression.startswith("#") or expression.startswith("("):
        return None
    expression = HEX.sub(lambda match: "0x" + match.group(1), expression)
    expression = NAME.sub(
        lambda match: str(symbols[match.group(0)])
        if match.group(0) in symbols
        else match.group(0),
        expression,
    )
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return None
    allowed = (ast.Expression, ast.Constant, ast.Add, ast.Sub, ast.BinOp,
               ast.UnaryOp, ast.UAdd, ast.USub)
    if any(not isinstance(node, allowed) for node in ast.walk(tree)):
        return None
    try:
        value = eval(compile(tree, "<wicfs-address>", "eval"), {"__builtins__": {}})
    except (NameError, TypeError):
        return None
    return value if isinstance(value, int) else None


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {Path(sys.argv[0]).name} /path/to/wicfs.asm", file=sys.stderr)
        return 2
    source = Path(sys.argv[1])
    lines = source.read_text().splitlines()
    symbols: dict[str, int] = {}
    unresolved: dict[str, str] = {}
    for line in lines:
        match = EQUATE.match(line)
        if match:
            unresolved[match.group(1)] = match.group(2).strip()
    while unresolved:
        progress = False
        for name, expression in list(unresolved.items()):
            value = evaluate(expression, symbols)
            if value is not None:
                symbols[name] = value
                del unresolved[name]
                progress = True
        if not progress:
            break

    failures: list[str] = []
    for number, line in enumerate(lines, 1):
        if FILENAME_WRITE.match(line.split("\\", 1)[0]):
            window = [candidate.split("\\", 1)[0].strip()
                      for candidate in lines[max(0, number - 14):number - 1]]
            if not any(FILENAME_LIMIT.match(candidate) for candidate in window) or not any(
                BOUNDS_BRANCH.match(candidate) for candidate in window
            ):
                failures.append(
                    f"{source}:{number}: {line.strip()} has no local ten-byte bound"
                )
        match = INSTRUCTION.match(line)
        if not match or match.group(1).upper() not in WRITE_OPS:
            continue
        address = evaluate(match.group(2), symbols)
        if address is not None and 0x03E0 <= address <= 0x03FF:
            failures.append(f"{source}:{number}: {line.strip()} resolves to &{address:04X}")
    if failures:
        print("WiCFS writes into the MOS keyboard input buffer:", file=sys.stderr)
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"Final WiCFS source keyboard-buffer write audit: OK ({source})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
