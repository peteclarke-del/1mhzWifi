"""Stable provenance capture shared by Elkulator acceptance runners."""

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def snapshot(paths: dict[str, Path]) -> dict[str, dict[str, object]]:
    result = {}
    for name, path in paths.items():
        resolved = path.resolve()
        result[name] = {
            "path": str(resolved),
            "exists": resolved.is_file(),
            "sha256": sha256(resolved) if resolved.is_file() else None,
            "size": resolved.stat().st_size if resolved.is_file() else None,
        }
    return result


def source_revision(path: Path) -> dict[str, object]:
    result = {"path": str(path.resolve()), "git_commit": None, "git_dirty": None}
    probe = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
    )
    if probe.returncode == 0:
        result["git_commit"] = probe.stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", str(path), "status", "--porcelain"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        )
        result["git_dirty"] = bool(dirty.stdout.strip())
    return result


def sorted_screens(directory: Path) -> list[Path]:
    """Sort screen-10 after screen-9 rather than after screen-1."""
    return sorted(
        directory.glob("screen-*.png"),
        key=lambda path: int(path.stem.rsplit("-", 1)[1]),
    )


def bus_trace_summary(path: Path) -> dict[str, object]:
    """Summarise bounded JIM and Tube evidence from an emulator bus trace."""
    if not path.exists():
        return {"available": False}
    lines = [line for line in path.read_text(errors="replace").splitlines()
             if line and not line.startswith("#")]
    tube = [line for line in lines
            if len(line.split()) >= 4 and
            0xFEE0 <= int(line.split()[2], 16) <= 0xFEFF]
    jim = [line for line in lines if " jim=" in line]
    selectors = [line for line in lines
                 if len(line.split()) >= 4 and line.split()[2] == "FCFF"]
    return {
        "available": True,
        "event_count": len(lines),
        "tube_access_count": len(tube),
        "jim_access_count": len(jim),
        "selector_write_count": sum(" W FCFF " in f" {line} "
                                    for line in selectors),
        "last_jim_access": jim[-1] if jim else None,
        "last_selector_access": selectors[-1] if selectors else None,
        "tail": lines[-64:],
    }
