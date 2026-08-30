#!/usr/bin/env python3
"""Audit final assembled ROM labels and cross-module low-RAM allocations."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


EQUATE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^\\:]+)")
HEX = re.compile(r"&([0-9A-Fa-f]+)")
NAME = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")


def evaluate(expression: str, symbols: dict[str, int]) -> int | None:
    expression = HEX.sub(lambda match: "0x" + match.group(1), expression.strip())
    expression = NAME.sub(
        lambda match: str(symbols[match.group(0)])
        if match.group(0) in symbols else match.group(0),
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
        value = eval(compile(tree, "<ram-layout>", "eval"), {"__builtins__": {}})
    except (NameError, TypeError):
        return None
    return value if isinstance(value, int) else None


def source_symbols(source_dir: Path) -> dict[str, int]:
    unresolved: dict[str, str] = {}
    for source in sorted(source_dir.glob("*.asm")):
        for line in source.read_text().splitlines():
            match = EQUATE.match(line)
            if match:
                unresolved[match.group(1)] = match.group(2).strip()
    symbols: dict[str, int] = {}
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
    return symbols


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {Path(sys.argv[0]).name} /path/to/rom /path/to/labels.json",
              file=sys.stderr)
        return 2
    source_dir = Path(sys.argv[1])
    labels_text = re.sub(r"(?<=\d)L\b", "", Path(sys.argv[2]).read_text())
    labels = ast.literal_eval(labels_text)
    if isinstance(labels, list) and len(labels) == 1 and isinstance(labels[0], dict):
        labels = labels[0]
    if not isinstance(labels, dict):
        print("assembled label export has an unknown format", file=sys.stderr)
        return 1
    required_labels = {
        ".uef_cmd", ".wicfs_state_load", ".host_select_tape", ".pi_wget_cmd",
        ".wicfs_reset_done", ".wicfs_load_pre_tape",
        ".wicfs_release_invalid_byte_trap", ".s_guard", ".e_guard",
    }
    missing = sorted(required_labels - labels.keys())
    if missing:
        print("assembled label export is incomplete: " + ", ".join(missing), file=sys.stderr)
        return 1

    # wicfs_reset_done is an eleven-byte register/flags restore epilogue ending
    # in RTS. A zero-context patch once placed wicfs_load_pre_tape at the same
    # address, so an inactive release fell into the helper with the reset frame
    # still on the stack. Keep this an assembled-symbol invariant: source patch
    # applicability alone cannot detect label aliasing after cumulative edits.
    if labels[".wicfs_load_pre_tape"] != labels[".wicfs_reset_done"] + 11:
        print(
            "WiCFS pre-TAPE helper does not follow the complete reset epilogue: "
            f"reset_done=&{labels['.wicfs_reset_done']:04X}, "
            f"helper=&{labels['.wicfs_load_pre_tape']:04X}",
            file=sys.stderr,
        )
        return 1
    if labels[".wicfs_load_pre_tape"] >= labels[".wicfs_release_invalid_byte_trap"]:
        print("WiCFS pre-TAPE helper overlaps the invalid-state handler", file=sys.stderr)
        return 1

    guard_size = labels[".e_guard"] - labels[".s_guard"]
    if not 0 < guard_size <= 0x80:
        print(f"WiCFS low-loader guard has invalid size: {guard_size}", file=sys.stderr)
        return 1

    symbols = source_symbols(source_dir)
    required_symbols = {"wicfs_state_ram", "wicfs_machine", "filev_x", "filev_y",
                        "notape", "romsel", "chain_exec",
                        "host_basic_pending"}
    missing = sorted(required_symbols - symbols.keys())
    if missing:
        print("combined RAM symbols are incomplete: " + ", ".join(missing), file=sys.stderr)
        return 1

    # UEF import counters are deliberately stack-local. Any fixed UEF length
    # symbol would recreate the cross-module alias this audit was added for.
    fixed_uef = sorted(name for name in symbols if name.startswith("uef_length_"))
    if fixed_uef:
        print("UEF length must remain stack-local: " + ", ".join(fixed_uef), file=sys.stderr)
        return 1

    expected = {
        "wicfs_state_ram": 0x0380,
        "wicfs_machine": 0x00C3,
        "filev_x": 0x0396,
        "filev_y": 0x0397,
        "notape": 0x0398,
        # The guard no longer lives in RAM: the Pi stamps it into the top of
        # every JIM page, where no cassette loader can reach it. Only its kind
        # byte stays in RAM, and only for the few instructions between the
        # guard's entry and its dispatch.
        "romsel": 0xFD97,
        "chain_exec": 0x03A0,
        "host_basic_pending": 0x03BD,
    }
    bad = [f"{name}=&{symbols[name]:04X}, expected &{address:04X}"
           for name, address in expected.items() if symbols[name] != address]
    if bad:
        print("combined RAM layout changed without review: " + "; ".join(bad), file=sys.stderr)
        return 1
    if symbols["romsel"] + guard_size > 0xFE00:
        print("WiCFS filing-vector guard crosses the JIM page top",
              file=sys.stderr)
        return 1

    print(f"Combined assembled RAM-symbol audit: OK ({source_dir})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
