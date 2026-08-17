#!/usr/bin/env python3
"""Run the local *UEF LOAD acceptance fixture under the hardware ROM layout."""

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
from provenance import snapshot, sorted_screens, source_revision
from run_catalogue_differential import inject_x11_keys


KEY_SHIFT_DOWN = 2000
KEY_SHIFT_UP = 2001
KEY_QUOTE = 69
KEY_ENTER = 67
KEY_SPACE = 75


def command_events(profile: str) -> list[tuple[int, int]]:
    setup = (1, 4, 6, 19) if profile == "adfs-beebscsi" else (4, 9, 19, 3)
    events = [
        (300, KEY_SHIFT_DOWN), (1, KEY_QUOTE), (1, KEY_SHIFT_UP),
        *((2, key) for key in setup), (2, KEY_ENTER),
    ]
    if profile == "adfs-beebscsi":
        # The photographed hard-disc image stores its local fixtures in $.UEF.
        # Select that real directory before invoking the ROM command.
        events.extend([
            (300, KEY_SHIFT_DOWN), (1, KEY_QUOTE), (1, KEY_SHIFT_UP),
            (2, 4), (2, 9), (2, 18), (2, KEY_SPACE),
            (2, 21), (2, 5), (2, 6), (2, KEY_ENTER),
        ])
    events.extend([
        (300, KEY_SHIFT_DOWN), (1, KEY_QUOTE), (1, KEY_SHIFT_UP),
        (2, 21), (2, 5), (2, 6), (2, KEY_SPACE),
        (2, 12), (2, 15), (2, 1), (2, 4), (2, KEY_SPACE),
        (2, 20), (2, 8), (2, 18), (2, 21), (2, 19), (2, 20),
        (2, KEY_ENTER),
    ])
    return events


def command_script(events: list[tuple[int, int]]) -> str:
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


def frame_change_pixels(left: Path, right: Path) -> int:
    result = subprocess.run(
        ["compare", "-colorspace", "Gray", "-metric", "AE",
         str(left), str(right), "null:"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    return int(result.stderr.strip().split()[0])


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
    parser.add_argument("--disc", type=Path,
                        help="DFS fixture disc; required by the dfs profile")
    parser.add_argument("--sd-image", type=Path,
                        help="Pi1MHz SD image exposed to an installed MMFS ROM")
    parser.add_argument("--mmfs-rom", type=Path,
                        help="MMFS ROM loaded in writable sideways bank 7")
    parser.add_argument("--profile", choices=("dfs", "adfs-beebscsi"), default="dfs")
    parser.add_argument("--beebscsi-lun", type=Path)
    parser.add_argument("--beebscsi-dsc", type=Path,
                        help="optional 22-to-33-byte BeebSCSI geometry sidecar")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tube", action="store_true")
    parser.add_argument(
        "--fiq-delay", type=int,
        help=("override only the FIQ capture delay; omit this option to use "
              "the conservative fault-injection default"),
    )
    parser.add_argument("--display", type=int, default=123)
    parser.add_argument("--wait", type=float, default=150.0)
    parser.add_argument("--sample-interval", type=float, default=2.0)
    parser.add_argument("--title-reference", type=Path, required=True)
    parser.add_argument("--gameplay-reference", type=Path, required=True)
    parser.add_argument(
        "--failure-reference", type=Path, action="append", required=True,
        help="known prompt or MOS-error screen; repeatable",
    )
    parser.add_argument("--similarity", type=float, default=0.90)
    parser.add_argument("--xvfb", type=Path,
                        default=Path("/tmp/elkulator-tools/usr/bin/Xvfb"))
    args = parser.parse_args()
    if args.sample_interval <= 0:
        parser.error("--sample-interval must be positive")
    if not 0.5 <= args.similarity <= 1.0:
        parser.error("--similarity must be between 0.5 and 1.0")
    if args.profile == "adfs-beebscsi" and args.beebscsi_lun is None:
        parser.error("--profile adfs-beebscsi requires --beebscsi-lun")
    if args.profile == "dfs" and args.disc is None:
        parser.error("--profile dfs requires --disc")
    if (args.sd_image is None) != (args.mmfs_rom is None):
        parser.error("--sd-image and --mmfs-rom must be supplied together")
    if args.beebscsi_lun is not None and not args.beebscsi_lun.is_file():
        parser.error(f"BeebSCSI LUN not found: {args.beebscsi_lun}")
    if args.beebscsi_lun and args.beebscsi_dsc is None:
        candidate = args.beebscsi_lun.with_suffix(".dsc")
        if candidate.is_file():
            args.beebscsi_dsc = candidate
    if args.beebscsi_dsc is not None and not args.beebscsi_dsc.is_file():
        parser.error(f"BeebSCSI geometry not found: {args.beebscsi_dsc}")
    for path in (args.title_reference, args.gameplay_reference, *args.failure_reference):
        if not path.is_file():
            parser.error(f"screen reference not found: {path}")

    for attribute in ("sd_image", "mmfs_rom", "beebscsi_lun", "beebscsi_dsc"):
        path = getattr(args, attribute)
        if path is not None:
            setattr(args, attribute, path.resolve())

    if args.output.exists() and any(args.output.iterdir()):
        parser.error(f"output directory is not empty: {args.output}")
    args.output.mkdir(parents=True, exist_ok=True)
    display = f":{args.display}"
    roms = args.runtime_dir / "roms"
    events = command_events(args.profile)
    command = [
        str(args.elkulator.resolve()),
        "-rom", "12", str(roms / "RHPLUS133.rom"),
        "-rom", "11", str(roms / "electron-basic.rom"),
        "-ram", "7", "-ram", "6",
        "-rom", "5", str(roms / "AFM1V09.rom"),
        "-rom", "3", str(args.wifi_rom.resolve()),
        "-rom", "2", str(roms / "dfs.rom"),
        "-rom", "1", str(roms / "acorn-adfs.rom"),
    ]
    if args.disc:
        command.extend(["-disc", str(args.disc.resolve())])
    if args.mmfs_rom:
        command.extend(["-rom", "7", str(args.mmfs_rom)])
    command.extend(["-autokeys", command_script(events)])
    if args.tube:
        command.extend(["-tube6502", str(roms / "6502tube_120.rom")])

    environment = os.environ.copy()
    environment.update({
        "DISPLAY": display,
        "PI1MHZ_MAILBOX": "fixture",
        "PI1MHZ_TRACE": str((args.output / "mailbox.trace").resolve()),
    })
    if args.fiq_delay is not None:
        environment["PI1MHZ_FIQ_DELAY_ACCESSES"] = str(args.fiq_delay)
    if args.sd_image:
        environment["PI1MHZ_SD_IMAGE"] = str(args.sd_image)
    if args.beebscsi_lun:
        environment["PI1MHZ_BEEBSCSI_LUN"] = str(args.beebscsi_lun.resolve())
        environment["PI1MHZ_BEEBSCSI_READ_ONLY"] = "1"
        environment["PI1MHZ_AP5_PROFILE"] = "full"
        environment["PI1MHZ_NOE"] = "1"
    if args.beebscsi_dsc:
        environment["PI1MHZ_BEEBSCSI_DSC"] = str(args.beebscsi_dsc.resolve())
    immutable_inputs = {
        "acceptance_runner": Path(__file__).resolve(),
        "provenance_module": Path(__file__).resolve().parent / "provenance.py",
        "elkulator": args.elkulator,
        "wifi_rom": args.wifi_rom,
        "rom_12_rhplus": roms / "RHPLUS133.rom",
        "rom_11_os": roms / "electron-basic.rom",
        "rom_5_ap5": roms / "AFM1V09.rom",
        "rom_2_dfs": roms / "dfs.rom",
        "rom_1_adfs": roms / "acorn-adfs.rom",
        "title_reference": args.title_reference,
        "gameplay_reference": args.gameplay_reference,
        **({"rom_7_mmfs": args.mmfs_rom} if args.mmfs_rom else {}),
        **{f"failure_reference_{number}": reference
           for number, reference in enumerate(args.failure_reference)},
        **({"tube_rom": roms / "6502tube_120.rom"} if args.tube else {}),
    }
    media_inputs = {
        **({"disc": args.disc} if args.disc else {}),
        **({"sd_image": args.sd_image} if args.sd_image else {}),
        **({"beebscsi_lun": args.beebscsi_lun} if args.beebscsi_lun else {}),
        **({"beebscsi_dsc": args.beebscsi_dsc} if args.beebscsi_dsc else {}),
    }
    config_inputs = {
        "elk_cfg": args.runtime_dir / "elk.cfg",
        "pi1mhz_cfg": args.runtime_dir / "Pi1MHz.cfg",
    }
    immutable_provenance = snapshot(immutable_inputs)
    media_before = snapshot(media_inputs)
    config_before = snapshot(config_inputs)
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
        started = time.monotonic()
        number = 0
        capture_times = []
        first_game_input_seconds = None
        while time.monotonic() < deadline and process.poll() is None:
            time.sleep(min(args.sample_interval,
                           max(0.0, deadline - time.monotonic())))
            screenshot = args.output / f"screen-{number}.png"
            capture(display, screenshot)
            elapsed = time.monotonic() - started
            capture_times.append(elapsed)
            number += 1
            # Do not guess when cassette loading has finished. Start the game
            # only after the reviewed native title/instructions frame is
            # visible, using the same focused X11 injection as the catalogue
            # runner.
            if (first_game_input_seconds is None and
                    similarity(screenshot, args.title_reference) >= args.similarity):
                first_game_input_seconds = elapsed
                inject_x11_keys(display, ["space"])
        screenshots = sorted_screens(args.output)
        pre_input = [screen for screen, elapsed in zip(screenshots, capture_times)
                     if (first_game_input_seconds is None or
                         elapsed <= first_game_input_seconds)]
        post_input = [screen for screen, elapsed in zip(screenshots, capture_times)
                      if (first_game_input_seconds is not None and
                          elapsed > first_game_input_seconds + 1.0)]
        title_scores = [similarity(screen, args.title_reference) for screen in pre_input]
        gameplay_scores = [similarity(screen, args.gameplay_reference)
                           for screen in post_input]
        title_seen = max(title_scores, default=0.0) >= args.similarity
        gameplay_seen = max(gameplay_scores, default=0.0) >= args.similarity
        gameplay_screens = [screen for screen, score in zip(post_input, gameplay_scores)
                            if score >= args.similarity]
        gameplay_motion_pixels = [frame_change_pixels(left, right)
                                  for left, right in zip(
                                      gameplay_screens, gameplay_screens[1:])]
        gameplay_motion = max(gameplay_motion_pixels, default=0) >= 100
        # The last frame before input is the causal baseline. Comparing every
        # earlier loader frame with every later frame is both weaker evidence
        # and quadratic when a large ADFS directory takes time to scan.
        correlated_changes = (
            [frame_change_pixels(pre_input[-1], after) for after in post_input]
            if pre_input else []
        )
        input_correlated_change = max(correlated_changes, default=0) >= 1000
        failure_scores = {
            str(reference): [similarity(screen, reference) for screen in screenshots]
            for reference in args.failure_reference
        }
        failure_seen = any(
            max(scores, default=0.0) >= args.similarity
            for scores in failure_scores.values()
        )
        alive_at_deadline = process.poll() is None
        if alive_at_deadline:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)
        elk_log.flush()
        log_text = (args.output / "elkulator.log").read_text(errors="replace")
        mos_errors = [text for text in ("Bad program", "Unexpected EOF", "Chunk type")
                      if text.casefold() in log_text.casefold()]
        trace = args.output / "mailbox.trace"
        trace_lines = trace.read_text(errors="replace").splitlines() if trace.exists() else []
        media_after = snapshot(media_inputs)
        config_after = snapshot(config_inputs)
        media_unchanged = media_before == media_after
        config_unchanged = config_before == config_after
        adfs_supported = bool(
            args.beebscsi_lun and
            "BeebSCSI: LUN 0 mounted at &FC40" in log_text
        )
        tube_started = bool(
            not args.tube or
            "AP5 Tube: external 3MHz 65C02 enabled" in log_text
        )
        passed = bool(
            alive_at_deadline and title_seen and gameplay_seen and
            input_correlated_change and gameplay_motion and
            media_unchanged and config_unchanged and
            tube_started and not failure_seen and not mos_errors and
            (args.profile != "adfs-beebscsi" or adfs_supported)
        )
        report = {
            "profile": args.profile,
            "adfs_beebscsi_supported": adfs_supported,
            "profile_note": (
                "BeebSCSI LUN 0 mounted through the full-decode AP5 profile"
                if args.profile == "adfs-beebscsi"
                else "DFS approximation; BeebSCSI and MMFS are not present"
            ),
            "tube": args.tube,
            "tube_started": tube_started,
            "timing_profile": (
                "conservative-fault-injection" if args.fiq_delay is None
                else f"capture-override-{args.fiq_delay}"
            ),
            "screenshots": [str(path) for path in screenshots],
            "capture_times_seconds": capture_times,
            "first_game_input_seconds": first_game_input_seconds,
            "game_input_source": "reviewed-title-frame-triggered X11 Space",
            "acceptance_thresholds": {
                "similarity": args.similarity,
                "input_change_pixels": 1000,
                "post_input_motion_pixels": 100,
            },
            "title_reference_scores": title_scores,
            "gameplay_reference_scores": gameplay_scores,
            "title_seen_before_input": title_seen,
            "gameplay_seen_after_input": gameplay_seen,
            "gameplay_motion_pixels": gameplay_motion_pixels,
            "gameplay_motion": gameplay_motion,
            "input_correlated_change_pixels": correlated_changes,
            "input_correlated_change": input_correlated_change,
            "failure_reference_scores": failure_scores,
            "failure_seen": failure_seen,
            "mos_errors_in_log": mos_errors,
            "still_running_at_deadline": alive_at_deadline,
            "stream_trace": {
                "available": bool(trace_lines),
                "lines": trace_lines,
                "note": "Local OSFIND/OSBGET UEF input may not produce backend stream events",
            },
            "provenance": {
                "immutable_inputs": immutable_provenance,
                "media_before": media_before,
                "media_after": media_after,
                "config_before": config_before,
                "config_after": config_after,
                "media_unchanged": media_unchanged,
                "config_unchanged": config_unchanged,
                "runtime_source": source_revision(args.runtime_dir),
                "integration_source": source_revision(Path(__file__).resolve().parents[2]),
            },
            "passed": passed,
        }
        (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
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
