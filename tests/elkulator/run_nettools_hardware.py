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
import re

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_uef_gameplay import capture
from provenance import snapshot, sorted_screens, source_revision


KEY_SHIFT_DOWN = 2000
KEY_SHIFT_UP = 2001
KEY_QUOTE = 69
KEY_STOP = 73
KEY_ENTER = 67
KEY_SPACE = 75
KEY_ESCAPE = 59

KEYS = {
    "a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6, "g": 7,
    "h": 8, "i": 9, "j": 10, "k": 11, "l": 12, "m": 13,
    "n": 14, "o": 15, "p": 16, "q": 17, "r": 18, "s": 19,
    "t": 20, "u": 21, "v": 22, "w": 23, "x": 24, "y": 25,
    "z": 26, "0": 27, "1": 28, "2": 29, "3": 30, "4": 31,
    "5": 32, "6": 33, "7": 34, "8": 35, "9": 36, " ": KEY_SPACE,
    "@": KEY_QUOTE, ".": KEY_STOP,
}

NAMED_KEYS = {
    "enter": KEY_ENTER,
    "escape": KEY_ESCAPE,
    "space": KEY_SPACE,
}


def star_command(text: str, initial_delay: int) -> list[tuple[int, int]]:
    events = [
        (initial_delay, KEY_SHIFT_DOWN),
        (1, KEY_QUOTE),
        (1, KEY_SHIFT_UP),
    ]
    for character in text.lower():
        if character == "!":
            events.extend(((2, KEY_SHIFT_DOWN), (1, KEYS["1"]),
                           (1, KEY_SHIFT_UP)))
        else:
            events.append((2, KEYS[character]))
    events.append((2, KEY_ENTER))
    return events


def parse_timed_key(value: str) -> tuple[int, int]:
    delay_text, separator, key_text = value.partition("=")
    if not separator or not delay_text.isdigit() or not key_text:
        raise argparse.ArgumentTypeError("expected DELAY=KEY")
    delay = int(delay_text)
    if delay < 1:
        raise argparse.ArgumentTypeError("key delay must be positive")
    key_name = key_text.casefold()
    if key_name in NAMED_KEYS:
        return delay, NAMED_KEYS[key_name]
    if len(key_name) == 1 and key_name in KEYS:
        return delay, KEYS[key_name]
    raise argparse.ArgumentTypeError(
        "KEY must be one alphanumeric key, space, enter or escape"
    )


def command_script(setup_commands: list[str], command: str,
                   escape_after: int | None = None,
                   command_delay: int = 300,
                   post_keys: list[tuple[int, int]] | None = None) -> str:
    events: list[tuple[int, int]] = []
    delay = command_delay
    for setup in setup_commands:
        events.extend(star_command(setup, delay))
        delay = command_delay
    events.extend(star_command(command, delay))
    if escape_after is not None:
        # Use Elkulator's ordinary six-frame key hold. This models a human
        # Escape press and gives MOS time to sample and acknowledge the key.
        events.append((escape_after, KEY_ESCAPE))
    events.extend(post_keys or [])
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


def parse_screen_region(value: str) -> tuple[str, Path]:
    geometry, separator, path_text = value.partition("=")
    if (not separator or
            not re.fullmatch(r"[1-9][0-9]*x[1-9][0-9]*\+[0-9]+\+[0-9]+",
                             geometry) or not path_text):
        raise argparse.ArgumentTypeError("expected WIDTHxHEIGHT+X+Y=IMAGE")
    return geometry, Path(path_text)


def similarity(left: Path, right: Path, geometry: str | None = None) -> float:
    command = ["compare", "-colorspace", "Gray", "-metric", "NCC"]
    if geometry:
        command.extend(["-extract", geometry])
    command.extend([str(left), str(right), "null:"])
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    return float(result.stderr.strip().split()[0])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--elkulator", type=Path, required=True)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument("--wifi-rom", type=Path, required=True)
    parser.add_argument(
        "--wifi-rom-slot", type=int, choices=range(16), default=3,
        metavar="BANK",
        help=("sideways bank containing 1MHzWifi; defaults to 3. A profile "
              "ROM displaced from that bank can be relocated with --extra-rom"),
    )
    parser.add_argument("--disc", type=Path)
    parser.add_argument("--sd-image", type=Path,
                        help="Pi1MHz FAT image used by MMFS")
    parser.add_argument(
        "--profile", choices=("bare", "dfs", "mmfs", "adfs-beebscsi"),
    )
    parser.add_argument(
        "--machine-profile",
        choices=("typical-electron", "minimum-electron"),
        default="typical-electron",
        help=("physical Electron expansion profile, independent of the "
              "selected filing system"),
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
    parser.add_argument(
        "--expect", choices=("auto", "hwd", "ssh", "telnet", "nslook", "ping"),
        default="auto",
        help="command outcome expected when a !BOOT or *EXEC wrapper launches it",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--escape-after", type=int,
        help="inject Escape this many emulator frames after the tested command",
    )
    parser.add_argument(
        "--post-key", action="append", type=parse_timed_key, default=[],
        metavar="DELAY=KEY",
        help=("inject an application key after the preceding event; repeat "
              "for interactive programs"),
    )
    parser.add_argument("--tube", action="store_true")
    parser.add_argument(
        "--fiq-delay", type=int,
        help=("override only the FIQ capture delay; omit this option to use "
              "the conservative fault-injection default"),
    )
    parser.add_argument(
        "--service-delay", type=int,
        help="override foreground Pi service latency in emulated host cycles",
    )
    parser.add_argument(
        "--wifi-profile", type=Path,
        help="persistent ElkWiFi profile used by the emulated Pi boot path",
    )
    parser.add_argument(
        "--ssh-dir", type=Path,
        help="managed SSH key and known-host directory exposed by the Pi service",
    )
    parser.add_argument("--wifi-associate-ms", type=int)
    parser.add_argument("--wifi-dhcp-ms", type=int)
    parser.add_argument(
        "--wifi-absent", action="store_true",
        help="model a Pi without WiFi hardware",
    )
    parser.add_argument("--display", type=int, default=133)
    parser.add_argument(
        "--x11-transport", choices=("unix", "tcp"), default="unix",
        help=("Xvfb transport; tcp is useful when the host /tmp/.X11-unix "
              "directory is not owned by root"),
    )
    parser.add_argument(
        "--command-delay", type=int, default=300,
        help="emulator frames before each scripted star command",
    )
    parser.add_argument("--wait", type=float, default=25.0)
    parser.add_argument("--reject-header-screen", type=Path)
    parser.add_argument("--reject-memory-screen", type=Path)
    parser.add_argument(
        "--require-screen", action="append", type=Path, default=[],
        help="require similarity to a known-good emulator screen; repeatable",
    )
    parser.add_argument(
        "--require-screen-region", action="append", type=parse_screen_region,
        default=[], metavar="WIDTHxHEIGHT+X+Y=IMAGE",
        help="compare only a stable application region; repeatable",
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
        "--require-trace-sequence", action="append", default=[],
        help="require these event names in order; repeat for each event",
    )
    parser.add_argument(
        "--xvfb", type=Path,
        default=Path("/tmp/elkulator-tools/usr/bin/Xvfb"),
    )
    args = parser.parse_args()

    if args.command_delay < 1:
        parser.error("--command-delay must be positive")
    for name, value in (("--wifi-associate-ms", args.wifi_associate_ms),
                        ("--wifi-dhcp-ms", args.wifi_dhcp_ms)):
        if value is not None and not 0 <= value <= 60000:
            parser.error(f"{name} must be between 0 and 60000")

    if args.profile is None:
        if args.beebscsi_lun is not None and args.disc is None and args.sd_image is None:
            args.profile = "adfs-beebscsi"
        else:
            args.profile = "mmfs" if args.sd_image is not None and args.disc is None else "dfs"
    if (args.disc is None and args.sd_image is None and
            args.profile not in ("bare", "adfs-beebscsi")):
        parser.error("one of --disc or --sd-image is required")
    if args.profile == "bare" and (args.disc is not None or args.sd_image is not None):
        parser.error("--profile bare does not accept filing-system media")
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
    if args.ssh_dir is not None and not args.ssh_dir.is_dir():
        parser.error(f"managed SSH directory not found: {args.ssh_dir}")
    reference_paths = [
        path for path in (
            args.reject_header_screen, args.reject_memory_screen,
            args.hwd_pass_screen, *args.require_screen,
            *(path for _, path in args.require_screen_region),
        ) if path is not None
    ]
    for path in reference_paths:
        if not path.is_file():
            parser.error(f"screen reference not found: {path}")
    setup_commands = args.setup_command or (
        ["adfs"] if args.profile == "adfs-beebscsi"
        else (["disc"] if args.disc else [])
    )

    if args.output.exists() and any(args.output.iterdir()):
        parser.error(f"output directory is not empty: {args.output}")
    args.output.mkdir(parents=True, exist_ok=True)
    display = (f"127.0.0.1:{args.display}.0"
               if args.x11_transport == "tcp" else f":{args.display}")
    roms = args.runtime_dir / "roms"
    profile_roms = {
        11: roms / "electron-basic.rom",
        5: roms / "AFM1V09.rom",
    }
    if args.machine_profile == "typical-electron":
        profile_roms[12] = roms / "RHPLUS133.rom"
    if args.profile == "dfs" or args.machine_profile == "typical-electron":
        profile_roms[2] = roms / "dfs.rom"
    if (args.profile == "adfs-beebscsi" or
            args.machine_profile == "typical-electron"):
        profile_roms[1] = roms / "acorn-adfs.rom"
    for slot, path in args.extra_rom:
        profile_roms[slot] = path
    # Apply this last so the requested test bank is authoritative. This also
    # permits tests of every bank: relocate any displaced profile ROM with an
    # explicit --extra-rom assignment.
    profile_roms[args.wifi_rom_slot] = args.wifi_rom
    immutable_inputs = {
        "elkulator": args.elkulator,
        "wifi_rom": args.wifi_rom,
        **{f"rom_slot_{slot}": path for slot, path in profile_roms.items()},
        **({"tube_rom": roms / "6502tube_120.rom"} if args.tube else {}),
        **({f"ssh_{name}": args.ssh_dir / name
            for name in ("id_ed25519", "id_ed25519.pub", "known_hosts")}
           if args.ssh_dir else {}),
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
    if args.wifi_profile is not None:
        config_inputs["wifi_profile"] = args.wifi_profile
    immutable_provenance = snapshot(immutable_inputs)
    media_before = snapshot(media_inputs)
    config_before = snapshot(config_inputs)
    command = [str(args.elkulator.resolve())]
    if args.machine_profile == "typical-electron":
        command.extend(["-ram", "7", "-ram", "6"])
    for slot, path in sorted(profile_roms.items(), reverse=True):
        command.extend(["-rom", str(slot), str(path.resolve())])
    if args.disc:
        command.extend(["-disc", str(args.disc.resolve())])
    command.extend(["-autokeys", command_script(
        setup_commands, args.command, args.escape_after, args.command_delay,
        args.post_key,
    )])
    if args.tube:
        command.extend(["-tube6502", str(roms / "6502tube_120.rom")])

    environment = os.environ.copy()
    environment.update({
        "DISPLAY": display,
        "PI1MHZ_MAILBOX": (
            "live" if args.profile in ("bare", "adfs-beebscsi") else "fixture"
        ),
        "PI1MHZ_TRACE": str((args.output / "mailbox.trace").resolve()),
    })
    if args.fiq_delay is not None:
        environment["PI1MHZ_FIQ_DELAY_ACCESSES"] = str(args.fiq_delay)
    if args.service_delay is not None:
        environment["PI1MHZ_SERVICE_DELAY_CYCLES"] = str(args.service_delay)
    if args.wifi_profile is not None:
        environment["PI1MHZ_WIFI_PROFILE"] = str(args.wifi_profile.resolve())
    if args.ssh_dir is not None:
        environment["PI1MHZ_SSH_DIR"] = str(args.ssh_dir.resolve())
    if args.wifi_associate_ms is not None:
        environment["PI1MHZ_WIFI_ASSOCIATE_MS"] = str(args.wifi_associate_ms)
    if args.wifi_dhcp_ms is not None:
        environment["PI1MHZ_WIFI_DHCP_MS"] = str(args.wifi_dhcp_ms)
    if args.wifi_absent:
        environment["PI1MHZ_WIFI_PRESENT"] = "0"
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
    xvfb_command = [
        str(args.xvfb.resolve()), f":{args.display}",
        "-screen", "0", "1024x768x24",
    ]
    if args.x11_transport == "tcp":
        xvfb_command.extend(["-nolisten", "unix", "-listen", "tcp"])
    xvfb = subprocess.Popen(
        xvfb_command,
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
        required_region_scores = {
            f"{geometry}={reference}": [
                similarity(screen, reference, geometry) for screen in screenshots
            ]
            for geometry, reference in args.require_screen_region
        }
        missing_regions = [
            key for key, scores in required_region_scores.items()
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
        trace_sequence_found = ordered_trace_contains(
            trace_rows, args.require_trace_sequence
        )
        command_name = (args.command.split()[0].lower()
                        if args.expect == "auto" else args.expect)
        screen_success = bool(
            not missing_screens and not missing_regions and
            (required_screens or args.require_screen_region)
        )
        if command_name in ("hwdtest", "hwd"):
            hwd_scores = required_screen_scores.get(str(args.hwd_pass_screen), []) \
                if args.hwd_pass_screen else []
            command_success = bool(
                args.hwd_pass_screen and
                max(hwd_scores, default=0.0) >= args.reject_similarity
            )
            command_evidence = "required HWDTEST RESULT PASS reference"
        elif command_name == "ssh":
            command_success = screen_success and ordered_trace_contains(
                trace_rows, ["SSH_OPEN", "SSH_USER", "CLOSE"]
            )
            command_evidence = (
                "ordered SSH_OPEN, SSH_USER and CLOSE trace plus required "
                "clean final screen"
            )
        elif command_name in ("telnet", "term"):
            command_success = screen_success and ordered_trace_contains(
                trace_rows, ["OPEN", "CLOSE"]
            )
            command_evidence = (
                "ordered OPEN and CLOSE trace plus required clean final screen"
            )
        elif command_name in ("nslook", "nslookup"):
            command_success = "DNS" in trace_events and screen_success
            command_evidence = "DNS trace plus required final address screen"
        elif command_name == "ping":
            ping_count = trace_events.count("PING")
            if args.escape_after is not None:
                command_success = 1 <= ping_count < 5 and screen_success
                command_evidence = (
                    "fewer than five PING requests after Escape plus required "
                    "clean MOS prompt screen"
                )
            else:
                command_success = ping_count == 5 and screen_success
                command_evidence = (
                    "exactly five PING requests plus required clean MOS prompt "
                    "screen"
                )
        else:
            command_success = screen_success
            command_evidence = "required command-specific final screen"
        process_status = process.poll()
        alive_at_deadline = process_status is None
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
            not missing_screens and not missing_regions and not missing_events and
            trace_sequence_found and
            (args.profile != "adfs-beebscsi" or adfs_supported)
        )
        report = {
            "tube": args.tube,
            "machine_profile": args.machine_profile,
            "wifi_rom_slot": args.wifi_rom_slot,
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
            "post_keys": args.post_key,
            "screenshots": [str(path) for path in screenshots],
            "still_running_at_deadline": alive_at_deadline,
            "emulator_returncode": process_status,
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
            "required_screen_region_comparisons": required_region_scores,
            "missing_required_screen_regions": missing_regions,
            "required_trace_events": args.require_trace_event,
            "missing_trace_events": missing_events,
            "required_trace_sequence": args.require_trace_sequence,
            "trace_sequence_found": trace_sequence_found,
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
