#!/usr/bin/env python3
"""Run the local *UEF LOAD acceptance fixture under the hardware ROM layout."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time


KEY_SHIFT_DOWN = 2000
KEY_SHIFT_UP = 2001
KEY_QUOTE = 69
KEY_ENTER = 67
KEY_SPACE = 75


def command_script() -> str:
    events = [
        (300, KEY_SHIFT_DOWN), (1, KEY_QUOTE), (1, KEY_SHIFT_UP),
        (2, 4), (2, 9), (2, 19), (2, 3), (2, KEY_ENTER),
        (100, KEY_SHIFT_DOWN), (1, KEY_QUOTE), (1, KEY_SHIFT_UP),
        (2, 21), (2, 5), (2, 6), (2, KEY_SPACE),
        (2, 12), (2, 15), (2, 1), (2, 4), (2, KEY_SPACE),
        (2, 20), (2, 8), (2, 18), (2, 21), (2, 19), (2, 20),
        (2, KEY_ENTER),
        # Thrust's title screen requests Space. Allow the complete multi-file
        # cassette load to finish, then repeat the key so a slower host cannot
        # consume the only press while changing video mode.
        (2500, KEY_SPACE),
        (500, KEY_SPACE),
        (500, KEY_SPACE),
        (500, KEY_SPACE),
        (500, KEY_SPACE),
        (500, KEY_SPACE),
    ]
    return ",".join(f"{delay}:{key}" for delay, key in events)


def capture(display: str, path: Path) -> None:
    xwd = subprocess.run(
        ["xwd", "-display", display, "-root", "-silent"],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    subprocess.run(
        ["convert", "xwd:-", str(path)], input=xwd.stdout, check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )


def frame_changed(left: Path, right: Path) -> bool:
    result = subprocess.run(
        ["compare", "-colorspace", "Gray", "-metric", "NCC",
         str(left), str(right), "null:"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    return float(result.stderr.strip().split()[0]) < 0.99999


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--elkulator", type=Path, required=True)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument("--wifi-rom", type=Path, required=True)
    parser.add_argument("--disc", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tube", action="store_true")
    parser.add_argument("--display", type=int, default=123)
    parser.add_argument("--wait", type=float, default=70.0)
    parser.add_argument("--xvfb", type=Path,
                        default=Path("/tmp/elkulator-tools/usr/bin/Xvfb"))
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    display = f":{args.display}"
    roms = args.runtime_dir / "roms"
    command = [
        str(args.elkulator.resolve()),
        "-rom", "12", str(roms / "RHPLUS133.rom"),
        "-rom", "11", str(roms / "electron-basic.rom"),
        "-ram", "7", "-ram", "6",
        "-rom", "5", str(roms / "AFM1V09.rom"),
        "-rom", "3", str(args.wifi_rom.resolve()),
        "-rom", "2", str(roms / "dfs.rom"),
        "-rom", "1", str(roms / "acorn-adfs.rom"),
        "-disc", str(args.disc.resolve()),
        "-autokeys", command_script(),
    ]
    if args.tube:
        command.extend(["-tube6502", str(roms / "6502tube_120.rom")])

    environment = os.environ.copy()
    environment.update({"DISPLAY": display, "PI1MHZ_MAILBOX": "fixture"})
    xvfb_log = (args.output / "xvfb.log").open("wb")
    elk_log = (args.output / "elkulator.log").open("wb")
    xvfb = subprocess.Popen(
        [str(args.xvfb.resolve()), display, "-screen", "0", "1024x768x24"],
        stdout=xvfb_log, stderr=subprocess.STDOUT, start_new_session=True,
    )
    process = None
    try:
        time.sleep(1)
        if xvfb.poll() is not None:
            raise RuntimeError("Xvfb failed to start; inspect xvfb.log")
        process = subprocess.Popen(
            command, cwd=args.runtime_dir.resolve(), env=environment,
            stdout=elk_log, stderr=subprocess.STDOUT, start_new_session=True,
        )
        deadline = time.monotonic() + args.wait
        number = 0
        while time.monotonic() < deadline and process.poll() is None:
            time.sleep(min(10.0, max(0.0, deadline - time.monotonic())))
            capture(display, args.output / f"screen-{number}.png")
            number += 1
        screenshots = sorted(args.output.glob("screen-*.png"))
        moving = any(
            frame_changed(left, right)
            for left, right in zip(screenshots, screenshots[1:])
        )
        report = {
            "rom_sha256": hashlib.sha256(args.wifi_rom.read_bytes()).hexdigest(),
            "tube": args.tube,
            "screenshots": [str(path) for path in screenshots],
            "meaningful_frame_change": moving,
        }
        (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        return 0 if process.poll() is None and moving else 1
    finally:
        for child in (process, xvfb):
            if child is not None and child.poll() is None:
                try:
                    os.killpg(child.pid, signal.SIGTERM)
                    child.wait(timeout=5)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    if child.poll() is None:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait()
        elk_log.close()
        xvfb_log.close()


if __name__ == "__main__":
    raise SystemExit(main())
