#!/usr/bin/env python3
"""Run a reviewed Pi1MHz command on a supported BBC-family host."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ELKULATOR_TESTS = Path(__file__).resolve().parents[1] / "elkulator"
sys.path.insert(0, str(ELKULATOR_TESTS))
from provenance import bus_trace_summary, snapshot, sorted_screens, source_revision
from run_uef_gameplay import capture


def similarity(left: Path, right: Path) -> float:
    result = subprocess.run(
        ["compare", "-colorspace", "Gray", "-metric", "NCC",
         str(left), str(right), "null:"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    return float(result.stderr.strip().split()[0])


def bem_paste(command: str) -> str:
    if "|" in command:
        raise ValueError("B-Em paste command must not contain '|'")
    return f"*{command.upper()}|M"


MACHINE_PROFILES = {
    "bbc-b-32k": {
        "name": "BBC B 32K Pi1MHz minimum",
        "os": "os12",
        "basic": "basic2",
        "fdc": "none",
        "65c02": "false",
        "b+": "false",
        "master": "false",
        "romsetup": "std",
        "romslot": 14,
    },
    "bbc-b-plus": {
        "name": "BBC B+ 64K Pi1MHz",
        "os": "bpos",
        "basic": "basic2",
        "fdc": "acorn",
        "65c02": "false",
        "b+": "true",
        "master": "false",
        "romsetup": "std",
        "romslot": 14,
    },
    "master-128": {
        "name": "BBC Master 128 Pi1MHz",
        "os": "mos320",
        "basic": None,
        "fdc": "master",
        "65c02": "true",
        "b+": "false",
        "master": "true",
        "romsetup": "master",
        "romslot": 7,
    },
}


def config_text(wifi_rom: Path, machine_profile: str) -> str:
    profile = MACHINE_PROFILES[machine_profile]
    basic = (f"rom15={profile['basic']}\n" if profile["basic"] else "")
    cmos = "cmos=cmos\n" if profile["master"] == "true" else ""
    return f"""model=0
tube=-1
key_as=false
key_logical=false
keypad=false
mouse_amx=false

[model_00]
name={profile['name']}
fdc={profile['fdc']}
65c02={profile['65c02']}
b+={profile['b+']}
master={profile['master']}
modela=false
os01=false
compact=false
os={profile['os']}
{cmos}tube=none
romsetup={profile['romsetup']}
{basic}rom{profile['romslot']:02d}={wifi_rom.resolve()}

[disc]
defaultwriteprotect=true
scsienable=false
ideenable=false
vdfsenable=false

[sound]
sndinternal=false
sndbeebsid=false
sndmusic5000=false
snddac=false
sndddnoise=false
sndtape=false

[video]
fullborders=1
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bem", type=Path, required=True)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument("--wifi-rom", type=Path, required=True)
    parser.add_argument(
        "--machine-profile", choices=tuple(MACHINE_PROFILES),
        default="bbc-b-32k",
    )
    parser.add_argument("--command", default="version")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-screen", type=Path, action="append", default=[])
    parser.add_argument("--require-trace-event", action="append", default=[])
    parser.add_argument("--wifi-profile", type=Path)
    parser.add_argument("--display", type=int, default=220)
    parser.add_argument("--wait", type=float, default=20.0)
    parser.add_argument("--similarity", type=float, default=0.985)
    parser.add_argument(
        "--xvfb", type=Path,
        default=Path("/tmp/elkulator-tools/usr/bin/Xvfb"),
    )
    args = parser.parse_args()
    if not 0.5 <= args.similarity <= 1.0:
        parser.error("--similarity must be between 0.5 and 1.0")
    for path in (args.bem, args.wifi_rom, *args.require_screen):
        if not path.is_file():
            parser.error(f"required file not found: {path}")

    if args.output.exists() and any(args.output.iterdir()):
        parser.error(f"output directory is not empty: {args.output}")
    args.output.mkdir(parents=True, exist_ok=True)
    cfg = args.output / "b-em.cfg"
    cfg.write_text(config_text(args.wifi_rom, args.machine_profile))
    trace = args.output / "mailbox.trace"
    bus_trace = args.output / "bus.trace"
    log = args.output / "b-em.log"
    xdg = args.output / "xdg"
    xdg.mkdir(exist_ok=True)
    display = f":{args.display}"
    selected_profile = MACHINE_PROFILES[args.machine_profile]
    immutable_paths = {
        "bem": args.bem,
        "wifi_rom": args.wifi_rom,
        "os_rom": args.runtime_dir / f"roms/os/{selected_profile['os']}.rom",
    }
    if selected_profile["basic"]:
        immutable_paths["basic_rom"] = (
            args.runtime_dir / f"roms/general/{selected_profile['basic']}.rom"
        )
    if selected_profile["master"] == "true":
        immutable_paths["cmos"] = args.runtime_dir / "cmos.bin"
    immutable = snapshot(immutable_paths)
    config_before = snapshot({"generated_cfg": cfg})
    environment = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "DISPLAY": display,
        "XDG_CONFIG_HOME": str(xdg.resolve()),
        "ALSOFT_DRIVERS": "null",
        "PI1MHZ_MAILBOX": "live",
        "PI1MHZ_TRACE": str(trace.resolve()),
        "PI1MHZ_BUS_TRACE": str(bus_trace.resolve()),
    }
    if args.wifi_profile:
        environment["PI1MHZ_WIFI_PROFILE"] = str(args.wifi_profile.resolve())
        environment["PI1MHZ_WIFI_ASSOCIATE_MS"] = "0"
        environment["PI1MHZ_WIFI_DHCP_MS"] = "0"

    xvfb_log = (args.output / "xvfb.log").open("wb")
    bem_log = log.open("wb")
    xvfb = subprocess.Popen(
        [str(args.xvfb.resolve()), display, "-screen", "0", "1024x768x24"],
        stdout=xvfb_log, stderr=subprocess.STDOUT, start_new_session=True,
        env=environment,
    )
    process = None
    try:
        time.sleep(1)
        if xvfb.poll() is not None:
            raise RuntimeError("Xvfb failed to start")
        process = subprocess.Popen(
            [str(args.bem.resolve()), "-cfg", str(cfg.resolve()), "-m0",
             "-paste", bem_paste(args.command), "-F1"],
            cwd=args.runtime_dir.resolve(), env=environment,
            stdout=bem_log, stderr=subprocess.STDOUT, start_new_session=True,
        )
        deadline = time.monotonic() + args.wait
        number = 0
        while time.monotonic() < deadline and process.poll() is None:
            time.sleep(min(5.0, max(0.0, deadline - time.monotonic())))
            capture(display, args.output / f"screen-{number}.png", "B-Em")
            number += 1
        screens = sorted_screens(args.output)
        scores = {
            str(reference): [similarity(screen, reference) for screen in screens]
            for reference in args.require_screen
        }
        missing_screens = [
            reference for reference, values in scores.items()
            if max(values, default=0.0) < args.similarity
        ]
        trace_events = []
        if trace.is_file():
            trace_events = [
                line.split("\t", 1)[0]
                for line in trace.read_text(errors="replace").splitlines()
            ]
        missing_events = [
            event for event in args.require_trace_event
            if event not in trace_events
        ]
        alive = process.poll() is None
        passed = bool(
            alive and args.require_screen and not missing_screens and
            not missing_events
        )
        report = {
            "machine_profile": args.machine_profile,
            "tube": False,
            "command": args.command,
            "still_running_at_deadline": alive,
            "required_screen_scores": scores,
            "missing_required_screens": missing_screens,
            "required_trace_events": args.require_trace_event,
            "missing_trace_events": missing_events,
            "bus_trace": bus_trace_summary(bus_trace),
            "provenance": {
                "immutable_inputs": immutable,
                "config_before": config_before,
                "config_after": snapshot({"generated_cfg": cfg}),
                "runtime_source": source_revision(args.runtime_dir),
                "integration_source": source_revision(
                    Path(__file__).resolve().parents[2]
                ),
            },
            "passed": passed,
        }
        (args.output / "report.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        return 0 if passed else 1
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
        bem_log.close()
        xvfb_log.close()


if __name__ == "__main__":
    raise SystemExit(main())
