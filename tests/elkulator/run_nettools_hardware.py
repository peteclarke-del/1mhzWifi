#!/usr/bin/env python3
"""Run a NetTools command under the photographed Electron/AP5 ROM layout."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_uef_gameplay import capture
from provenance import snapshot, sorted_screens, source_revision


KEY_SHIFT_DOWN = 2000
KEY_SHIFT_UP = 2001
KEY_QUOTE = 69
KEY_ENTER = 67
KEY_SPACE = 75

KEYS = {
    "a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6, "g": 7,
    "h": 8, "i": 9, "j": 10, "k": 11, "l": 12, "m": 13,
    "n": 14, "o": 15, "p": 16, "q": 17, "r": 18, "s": 19,
    "t": 20, "u": 21, "v": 22, "w": 23, "x": 24, "y": 25,
    "z": 26, "0": 27, "1": 28, "2": 29, "3": 30, "4": 31,
    "5": 32, "6": 33, "7": 34, "8": 35, "9": 36, " ": KEY_SPACE,
}


def star_command(text: str, initial_delay: int) -> list[tuple[int, int]]:
    events = [
        (initial_delay, KEY_SHIFT_DOWN),
        (1, KEY_QUOTE),
        (1, KEY_SHIFT_UP),
    ]
    events.extend((2, KEYS[character]) for character in text.lower())
    events.append((2, KEY_ENTER))
    return events


def command_script(setup_commands: list[str], command: str) -> str:
    events: list[tuple[int, int]] = []
    delay = 300
    for setup in setup_commands:
        events.extend(star_command(setup, delay))
        delay = 300
    events.extend(star_command(command, delay))
    if command.split()[0].casefold() in ("hwd", "hwdtest"):
        events.append((300, KEY_SPACE))
        events.extend((100, KEY_SPACE) for _ in range(5))
    return ",".join(f"{delay}:{key}" for delay, key in events)


def ordered_trace_contains(rows: list[tuple[str, str]], required: list[str]) -> bool:
    position = 0
    for event, _ in rows:
        if position < len(required) and event == required[position]:
            position += 1
    return position == len(required)


def parse_slot_rom(value: str) -> tuple[int, Path]:
    slot_text, separator, path_text = value.partition("=")
    if not separator or not slot_text.isdigit() or not path_text:
        raise argparse.ArgumentTypeError("expected SLOT=ROM")
    slot = int(slot_text)
    if not 0 <= slot <= 15:
        raise argparse.ArgumentTypeError("ROM slot must be between 0 and 15")
    return slot, Path(path_text)


def similarity(left: Path, right: Path) -> float:
    result = subprocess.run(
        ["compare", "-colorspace", "Gray", "-metric", "NCC",
         str(left), str(right), "null:"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    return float(result.stderr.strip().split()[0])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--elkulator", type=Path, required=True)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument("--wifi-rom", type=Path, required=True)
    parser.add_argument("--disc", type=Path)
    parser.add_argument("--sd-image", type=Path,
                        help="Pi1MHz FAT image used by MMFS")
    parser.add_argument(
        "--profile", choices=("dfs", "mmfs", "adfs-beebscsi"),
    )
    parser.add_argument(
        "--beebscsi-lun", type=Path,
        help="raw BeebSCSI LUN 0 image mounted at &FC40 for adfs-beebscsi runs",
    )
    parser.add_argument("--beebscsi-dsc", type=Path,
                        help="optional 22-to-33-byte BeebSCSI geometry sidecar")
    parser.add_argument(
        "--extra-rom", action="append", type=parse_slot_rom, default=[],
        metavar="SLOT=ROM", help="replace a profile slot, for example 2=EMMFS.rom",
    )
    parser.add_argument(
        "--setup-command", action="append", default=[],
        help="filing-system setup command before the tested command; repeatable",
    )
    parser.add_argument("--command", default="hwdtest")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tube", action="store_true")
    parser.add_argument(
        "--fiq-delay", type=int,
        help=("override only the FIQ capture delay; omit this option to use "
              "the conservative fault-injection default"),
    )
    parser.add_argument("--display", type=int, default=133)
    parser.add_argument("--wait", type=float, default=25.0)
    parser.add_argument("--reject-header-screen", type=Path)
    parser.add_argument("--reject-memory-screen", type=Path)
    parser.add_argument(
        "--require-screen", action="append", type=Path, default=[],
        help="require similarity to a known-good emulator screen; repeatable",
    )
    parser.add_argument(
        "--hwd-pass-screen", type=Path,
        help="reviewed HWD D2 final screen containing HWDTEST RESULT PASS",
    )
    parser.add_argument("--reject-similarity", type=float, default=0.985)
    parser.add_argument(
        "--require-trace-event", action="append", default=[],
        help="require an exact event name in the Pi1MHz mailbox trace",
    )
    parser.add_argument(
        "--xvfb", type=Path,
        default=Path("/tmp/elkulator-tools/usr/bin/Xvfb"),
    )
    args = parser.parse_args()

    if args.profile is None:
        if args.beebscsi_lun is not None and args.disc is None and args.sd_image is None:
            args.profile = "adfs-beebscsi"
        else:
            args.profile = "mmfs" if args.sd_image is not None and args.disc is None else "dfs"
    if (args.disc is None and args.sd_image is None and
            args.profile != "adfs-beebscsi"):
        parser.error("one of --disc or --sd-image is required")
    if args.profile == "adfs-beebscsi" and args.beebscsi_lun is None:
        parser.error("--profile adfs-beebscsi requires --beebscsi-lun")
    if args.beebscsi_lun is not None and not args.beebscsi_lun.is_file():
        parser.error(f"BeebSCSI LUN not found: {args.beebscsi_lun}")
    if args.beebscsi_lun and args.beebscsi_dsc is None:
        candidate = args.beebscsi_lun.with_suffix(".dsc")
        if candidate.is_file():
            args.beebscsi_dsc = candidate
    if args.beebscsi_dsc is not None and not args.beebscsi_dsc.is_file():
        parser.error(f"BeebSCSI geometry not found: {args.beebscsi_dsc}")
    reference_paths = [
        path for path in (
            args.reject_header_screen, args.reject_memory_screen,
            args.hwd_pass_screen, *args.require_screen,
        ) if path is not None
    ]
    for path in reference_paths:
        if not path.is_file():
            parser.error(f"screen reference not found: {path}")
    setup_commands = args.setup_command or (
        ["adfs"] if args.profile == "adfs-beebscsi"
        else (["disc"] if args.disc else [])
    )

    args.output.mkdir(parents=True, exist_ok=True)
    display = f":{args.display}"
    roms = args.runtime_dir / "roms"
    profile_roms = {
        12: roms / "RHPLUS133.rom",
        11: roms / "electron-basic.rom",
        5: roms / "AFM1V09.rom",
        3: args.wifi_rom,
        2: roms / "dfs.rom",
        1: roms / "acorn-adfs.rom",
    }
    for slot, path in args.extra_rom:
        profile_roms[slot] = path
    immutable_inputs = {
        "elkulator": args.elkulator,
        "wifi_rom": args.wifi_rom,
        **{f"rom_slot_{slot}": path for slot, path in profile_roms.items()},
        **({"tube_rom": roms / "6502tube_120.rom"} if args.tube else {}),
    }
    media_inputs = {
        **({"disc": args.disc} if args.disc else {}),
        **({"sd_image": args.sd_image} if args.sd_image else {}),
        **({"beebscsi_lun": args.beebscsi_lun} if args.beebscsi_lun else {}),
        **({"beebscsi_dsc": args.beebscsi_dsc} if args.beebscsi_dsc else {}),
    }
    config_inputs = {
        name: path for name, path in {
            "elk_cfg": args.runtime_dir / "elk.cfg",
            "pi1mhz_cfg": args.runtime_dir / "Pi1MHz.cfg",
        }.items() if path.is_file()
    }
    immutable_provenance = snapshot(immutable_inputs)
    media_before = snapshot(media_inputs)
    config_before = snapshot(config_inputs)
    command = [
        str(args.elkulator.resolve()),
        "-ram", "7", "-ram", "6",
    ]
    for slot, path in sorted(profile_roms.items(), reverse=True):
        command.extend(["-rom", str(slot), str(path.resolve())])
    if args.disc:
        command.extend(["-disc", str(args.disc.resolve())])
    command.extend(["-autokeys", command_script(setup_commands, args.command)])
    if args.tube:
        command.extend(["-tube6502", str(roms / "6502tube_120.rom")])

    environment = os.environ.copy()
    environment.update({
        "DISPLAY": display,
        "PI1MHZ_MAILBOX": (
            "live" if args.profile == "adfs-beebscsi" else "fixture"
        ),
        "PI1MHZ_TRACE": str((args.output / "mailbox.trace").resolve()),
    })
    if args.fiq_delay is not None:
        environment["PI1MHZ_FIQ_DELAY_ACCESSES"] = str(args.fiq_delay)
    if args.sd_image:
        environment["PI1MHZ_SD_IMAGE"] = str(args.sd_image.resolve())
    if args.beebscsi_lun:
        environment["PI1MHZ_BEEBSCSI_LUN"] = str(args.beebscsi_lun.resolve())
        environment["PI1MHZ_BEEBSCSI_READ_ONLY"] = "1"
        environment["PI1MHZ_AP5_PROFILE"] = "full"
        environment["PI1MHZ_NOE"] = "1"
    if args.beebscsi_dsc:
        environment["PI1MHZ_BEEBSCSI_DSC"] = str(args.beebscsi_dsc.resolve())
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
            time.sleep(min(5.0, max(0.0, deadline - time.monotonic())))
            capture(display, args.output / f"screen-{number}.png")
            number += 1
        screenshots = sorted_screens(args.output)
        reject_references = {
            "header_only": args.reject_header_screen,
            "memory_envelope": args.reject_memory_screen,
        }
        rejected = []
        comparisons = {}
        for label, reference in reject_references.items():
            if reference is None:
                continue
            scores = [similarity(screen, reference) for screen in screenshots]
            comparisons[label] = scores
            if scores and max(scores) >= args.reject_similarity:
                rejected.append(label)
        required_screens = list(args.require_screen)
        if args.hwd_pass_screen:
            required_screens.append(args.hwd_pass_screen)
        required_screen_scores = {
            str(reference): [similarity(screen, reference)
                             for screen in screenshots]
            for reference in required_screens
        }
        missing_screens = [
            reference for reference, scores in required_screen_scores.items()
            if not scores or max(scores) < args.reject_similarity
        ]
        trace = args.output / "mailbox.trace"
        trace_events = []
        trace_rows = []
        if trace.exists():
            for line in trace.read_text(errors="replace").splitlines():
                fields = line.split("\t", 2)
                if fields:
                    trace_events.append(fields[0])
                    trace_rows.append((fields[0], fields[2] if len(fields) == 3 else ""))
        missing_events = [event for event in args.require_trace_event
                          if event not in trace_events]
        command_name = args.command.split()[0].lower()
        screen_success = not missing_screens and bool(required_screens)
        if command_name in ("hwdtest", "hwd"):
            hwd_scores = required_screen_scores.get(str(args.hwd_pass_screen), []) \
                if args.hwd_pass_screen else []
            command_success = bool(
                args.hwd_pass_screen and
                max(hwd_scores, default=0.0) >= args.reject_similarity
            )
            command_evidence = "required HWDTEST RESULT PASS reference"
        elif command_name == "ssh":
            command_success = ordered_trace_contains(
                trace_rows, ["SSH_OPEN", "SSH_USER", "CLOSE"]
            )
            command_evidence = "ordered SSH_OPEN, SSH_USER and CLOSE trace"
        elif command_name in ("telnet", "term"):
            command_success = ordered_trace_contains(trace_rows, ["OPEN", "CLOSE"])
            command_evidence = "ordered OPEN and CLOSE trace"
        elif command_name in ("nslook", "nslookup"):
            command_success = "DNS" in trace_events and screen_success
            command_evidence = "DNS trace plus required final address screen"
        else:
            command_success = screen_success
            command_evidence = "required command-specific final screen"
        alive_at_deadline = process.poll() is None
        if alive_at_deadline:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)
        media_after = snapshot(media_inputs)
        config_after = snapshot(config_inputs)
        elk_log.flush()
        log_text = (args.output / "elkulator.log").read_text(errors="replace")
        adfs_supported = bool(
            args.beebscsi_lun and
            "BeebSCSI: LUN 0 mounted at &FC40" in log_text
        )
        passed = (
            alive_at_deadline and command_success and not rejected and
            not missing_screens and not missing_events and
            (args.profile != "adfs-beebscsi" or adfs_supported)
        )
        report = {
            "tube": args.tube,
            "profile": args.profile,
            "adfs_beebscsi_supported": adfs_supported,
            "profile_note": (
                "BeebSCSI LUN 0 mounted through the full-decode AP5 profile"
                if args.profile == "adfs-beebscsi"
                else "DFS/MMFS approximation; BeebSCSI is not present"
            ),
            "timing_profile": (
                "conservative-fault-injection" if args.fiq_delay is None
                else f"capture-override-{args.fiq_delay}"
            ),
            "command": args.command,
            "setup_commands": setup_commands,
            "screenshots": [str(path) for path in screenshots],
            "still_running_at_deadline": alive_at_deadline,
            "provenance": {
                "immutable_inputs": immutable_provenance,
                "media_before": media_before,
                "media_after": media_after,
                "config_before": config_before,
                "config_after": config_after,
                "runtime_source": source_revision(args.runtime_dir),
                "integration_source": source_revision(Path(__file__).resolve().parents[2]),
            },
            "reject_comparisons": comparisons,
            "rejected_failures": rejected,
            "required_screen_comparisons": required_screen_scores,
            "missing_required_screens": missing_screens,
            "required_trace_events": args.require_trace_event,
            "missing_trace_events": missing_events,
            "command_success": command_success,
            "command_success_evidence": command_evidence,
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
        elk_log.close()
        xvfb_log.close()


if __name__ == "__main__":
    raise SystemExit(main())
