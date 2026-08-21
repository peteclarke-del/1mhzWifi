"""Deterministic Elkulator runtime preparation shared by acceptance runners."""

from __future__ import annotations

from pathlib import Path
import shutil


def prepare_runtime(
    source: Path, destination: Path, pi1mhz_cfg: Path | None = None,
) -> Path:
    """Create a non-Turbo Electron profile without modifying its source tree."""
    destination.mkdir()
    roms = source / "roms"
    if not roms.is_dir():
        raise RuntimeError(f"Elkulator ROM directory not found: {roms}")
    (destination / "roms").symlink_to(roms.resolve(), target_is_directory=True)
    # Elkulator also resolves named OS images relative to its working
    # directory.  A raw build tree normally lacks these links, which used to
    # make catalogue tests fail before the guest booted.
    for rom in roms.iterdir():
        if rom.is_file():
            (destination / rom.name).symlink_to(rom.resolve())
    ddnoise = source / "ddnoise"
    if ddnoise.is_dir():
        (destination / "ddnoise").symlink_to(
            ddnoise.resolve(), target_is_directory=True,
        )
    source_cfg = source / "elk.cfg"
    if not source_cfg.is_file():
        raise RuntimeError(f"Elkulator configuration not found: {source_cfg}")
    overrides = {
        "plus1": "1",
        "plus3": "0",
        "dfsena": "0",
        "adfsena": "0",
        "turbo": "0",
        "enable_jim": "0",
    }
    seen: set[str] = set()
    configured: list[str] = []
    for line in source_cfg.read_text().splitlines():
        key, separator, _ = line.partition("=")
        name = key.strip()
        if separator and name in overrides:
            configured.append(f"{name} = {overrides[name]}")
            seen.add(name)
        else:
            configured.append(line)
    for name, value in overrides.items():
        if name not in seen:
            configured.append(f"{name} = {value}")
    (destination / "elk.cfg").write_text("\n".join(configured) + "\n")
    selected_pi_cfg = pi1mhz_cfg if pi1mhz_cfg is not None else source / "Pi1MHz.cfg"
    if selected_pi_cfg.is_file():
        shutil.copy2(selected_pi_cfg, destination / "Pi1MHz.cfg")
    return destination
