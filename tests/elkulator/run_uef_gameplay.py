#!/usr/bin/env python3
"""Run the local *UEF LOAD acceptance fixture under the hardware ROM layout."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from provenance import bus_trace_summary, snapshot, sorted_screens, source_revision
from run_catalogue_differential import inject_x11_keys
from runtime import prepare_runtime


KEY_SHIFT_DOWN = 2000
KEY_SHIFT_UP = 2001
KEY_QUOTE = 69
KEY_ENTER = 67
KEY_SPACE = 75
KEY_DIGITS = {
    "1": 28, "2": 29, "3": 30, "4": 31, "5": 32,
    "6": 33, "7": 34, "8": 35, "9": 36, "0": 37,
}


def elkulator_text_events(text: str) -> list[tuple[int, int]]:
    events = []
    for character in text.upper():
        if "A" <= character <= "Z":
            key = ord(character) - ord("A") + 1
        elif character in KEY_DIGITS:
            key = KEY_DIGITS[character]
        elif character == " ":
            key = KEY_SPACE
        else:
            raise ValueError(f"unsupported Elkulator command character: {character!r}")
        events.append((2, key))
    return events


def command_events(profile: str, uef_file: str = "THRUST") -> list[tuple[int, int]]:
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
        *elkulator_text_events(f"UEF LOAD {uef_file}"),
        (2, KEY_ENTER),
    ])
    return events


def command_script(events: list[tuple[int, int]]) -> str:
    return ",".join(f"{delay}:{key}" for delay, key in events)


def native_tape_events() -> list[tuple[int, int]]:
    """Select the untouched cassette filing system and CHAIN the tape."""
    return [
        (300, KEY_SHIFT_DOWN), (1, KEY_QUOTE), (1, KEY_SHIFT_UP),
        *elkulator_text_events("TAPE"), (2, KEY_ENTER),
        *elkulator_text_events("CHAIN"),
        (2, KEY_SHIFT_DOWN), (1, KEY_DIGITS["2"]), (1, KEY_SHIFT_UP),
        (2, KEY_SHIFT_DOWN), (1, KEY_DIGITS["2"]), (1, KEY_SHIFT_UP),
        (2, KEY_ENTER),
    ]


def preloaded_wicfs_events() -> list[tuple[int, int]]:
    """Launch an already-normalised public-JIM UEF through stock WiCFS."""
    events = [
        (300, KEY_SHIFT_DOWN), (1, KEY_QUOTE), (1, KEY_SHIFT_UP),
        *elkulator_text_events("WICFS"), (2, KEY_ENTER),
        (300, KEY_SHIFT_DOWN), (1, KEY_QUOTE), (1, KEY_SHIFT_UP),
        *elkulator_text_events("REWIND"), (2, KEY_ENTER),
        *elkulator_text_events("CHAIN"),
        (2, KEY_SHIFT_DOWN), (1, KEY_DIGITS["2"]), (1, KEY_SHIFT_UP),
        (2, KEY_SHIFT_DOWN), (1, KEY_DIGITS["2"]), (1, KEY_SHIFT_UP),
        (2, KEY_ENTER),
    ]
    return events


def largest_window(tree: str, window_title: str) -> str | None:
    """Return the largest titled X11 window from an xwininfo tree."""
    candidates = []
    for line in tree.splitlines():
        match = re.match(
            rf'^\s+(0x[0-9a-f]+)\s+"{re.escape(window_title)}[^"\\]*".*?'
            rf'(\d+)x(\d+)\+',
            line, flags=re.IGNORECASE,
        )
        if match:
            candidates.append((int(match[2]) * int(match[3]), match[1]))
    return max(candidates)[1] if candidates else None


def capture(display: str, path: Path, window_title: str = "Elkulator") -> None:
    tree = subprocess.run(
        ["xwininfo", "-display", display, "-root", "-tree"],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    window = largest_window(tree.stdout, window_title)
    if window is None:
        raise RuntimeError(
            f"expected a {window_title} window on {display}, found none"
        )
    # B-Em creates a small companion window with the same title. Capturing the
    # largest matching top-level window selects the emulated display without
    # relying on creation order. Elkulator normally has one candidate.
    xwd = subprocess.run(
        ["xwd", "-display", display, "-id", window, "-silent"],
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
    """Compare guest pixels independently of X11 size and colour palette.

    The same Electron frame may be captured as indexed colour, greyscale, or
    at a different integer window scale.  NCC is unstable for these sparse
    screens and previously missed a visually identical Thrust title frame.
    Normalise both inputs to the Electron's 320x256 raster and compare their
    thresholded pixels instead.
    """
    result = subprocess.run(
        ["convert", str(left), str(right), "-resize", "320x256!",
         "-colorspace", "Gray", "-threshold", "50%", "-depth", "8",
         "gray:-"],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    pixels = 320 * 256
    if len(result.stdout) != pixels * 2:
        raise RuntimeError("ImageMagick returned an unexpected raster size")
    left_raster = result.stdout[:pixels]
    right_raster = result.stdout[pixels:]
    left_foreground = sum(bool(pixel) for pixel in left_raster)
    right_foreground = sum(bool(pixel) for pixel in right_raster)
    foreground = left_foreground + right_foreground
    if not foreground:
        return 1.0
    intersection = sum(
        bool(left_pixel) and bool(right_pixel)
        for left_pixel, right_pixel in zip(left_raster, right_raster)
    )
    return 2.0 * intersection / foreground


def binary_raster(path: Path) -> bytes:
    """Return one thresholded Electron raster at its native pixel geometry."""
    result = subprocess.run(
        ["convert", str(path), "-resize", "320x256!", "-colorspace", "Gray",
         "-threshold", "50%", "-depth", "8", "gray:-"],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if len(result.stdout) != 320 * 256:
        raise RuntimeError("ImageMagick returned an unexpected raster size")
    return result.stdout


def prompt_similarity(screen: Path, reference: Path) -> float:
    """Find the reference's final left-margin glyph at any screen row.

    MOS prompts move vertically as commands print output. Comparing a complete
    screen therefore rejects a valid prompt whenever the preceding text has a
    different height. The final occupied band in the reference's left margin
    is the reviewed prompt glyph. Match that small shape at any vertical
    position while retaining the real captured font and pixel geometry.
    """
    width = 320
    height = 256
    margin = 10
    reference_pixels = binary_raster(reference)
    screen_pixels = binary_raster(screen)
    occupied_rows = [
        y for y in range(height)
        if any(reference_pixels[y * width + x] for x in range(margin))
    ]
    if not occupied_rows:
        return 0.0
    band_end = occupied_rows[-1]
    band_start = band_end
    occupied = set(occupied_rows)
    while band_start - 1 in occupied:
        band_start -= 1
    template = [
        bool(reference_pixels[y * width + x])
        for y in range(band_start, band_end + 1)
        for x in range(margin)
    ]
    template_foreground = sum(template)
    if not template_foreground:
        return 0.0
    band_height = band_end - band_start + 1
    best = 0.0
    for top in range(height - band_height + 1):
        candidate = [
            bool(screen_pixels[y * width + x])
            for y in range(top, top + band_height)
            for x in range(margin)
        ]
        foreground = template_foreground + sum(candidate)
        if foreground:
            intersection = sum(a and b for a, b in zip(template, candidate))
            best = max(best, 2.0 * intersection / foreground)
    return best


def inject_elkulator_command(display: str, command: str) -> None:
    """Type one MOS command using Elkulator's physical @-for-* mapping."""
    keys = []
    for character in command:
        if character == "*":
            keys.append("at")
        elif character == " ":
            keys.append("space")
        elif character.isalpha():
            keys.append(character.lower())
        elif character.isdigit():
            keys.append(character)
        else:
            raise ValueError(f"unsupported recovery command character: {character!r}")
    inject_x11_keys(display, [*keys, "Return"])


def beebscsi_read_count(log_path: Path) -> int:
    """Count completed READ(6) commands emitted by the BeebSCSI model."""
    if not log_path.exists():
        return 0
    return log_path.read_text(errors="replace").count("BeebSCSI trace: command 08")


def sustained_motion_by_epoch(
    screens: list[Path], times: list[float], start: float | None,
    end: float | None, threshold: int = 100,
) -> tuple[list[int], bool]:
    """Require late motion and motion in at least two gameplay epochs."""
    if start is None or end is None or end <= start:
        return [], False
    duration = end - start
    if duration < 6.0:
        return [], False
    maxima = []
    for epoch in range(3):
        lower = start + duration * epoch / 3.0
        upper = start + duration * (epoch + 1) / 3.0
        selected = [
            screen for screen, elapsed in zip(screens, times)
            if lower <= elapsed and
            (elapsed <= upper if epoch == 2 else elapsed < upper)
        ]
        changes = [frame_change_pixels(left, right)
                   for left, right in zip(selected, selected[1:])]
        maxima.append(max(changes, default=0))
    moving_epochs = sum(change >= threshold for change in maxima)
    return maxima, maxima[-1] >= threshold and moving_epochs >= 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--elkulator", type=Path, required=True)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument("--wifi-rom", type=Path, required=True)
    parser.add_argument(
        "--pi1mhz-cfg", type=Path,
        help=("Pi1MHz.cfg from the staged hardware image; recorded as immutable "
              "provenance even though Elkulator does not execute the Pi kernel"),
    )
    parser.add_argument("--disc", type=Path,
                        help="DFS fixture disc; required by the dfs profile")
    parser.add_argument("--sd-image", type=Path,
                        help="Pi1MHz SD image exposed to an installed MMFS ROM")
    parser.add_argument("--mmfs-rom", type=Path,
                        help="MMFS ROM loaded in writable sideways bank 7")
    parser.add_argument("--profile", choices=("dfs", "adfs-beebscsi"), default="dfs")
    parser.add_argument("--beebscsi-lun", type=Path)
    parser.add_argument(
        "--writable-beebscsi-copy", action="store_true",
        help=("allow filing-system writes to a caller-provided disposable LUN "
              "copy under /tmp; never use this with the staged hardware image"),
    )
    parser.add_argument("--beebscsi-dsc", type=Path,
                        help="optional 22-to-33-byte BeebSCSI geometry sidecar")
    parser.add_argument(
        "--uef-file", default="THRUST",
        help="UEF filename in the selected filing-system directory",
    )
    parser.add_argument(
        "--native-tape", type=Path,
        help=("load this UEF through Elkulator's untouched cassette path "
              "instead of installing WiCFS; used as a differential control"),
    )
    parser.add_argument(
        "--preloaded-jim", type=Path,
        help=("diagnostic 64 KiB public-JIM image containing a normalised UEF "
              "and its length trailer; bypasses only the local-file import"),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tube", action="store_true")
    parser.add_argument(
        "--no-bus-trace", action="store_true",
        help=("disable high-volume bus logging for Tube-off performance and "
              "gameplay runs; not permitted with --tube"),
    )
    parser.add_argument(
        "--recovery-check", action="store_true",
        help=("after sustained gameplay, press Break, reselect ADFS and load "
              "the same UEF a second time without restarting Elkulator"),
    )
    parser.add_argument(
        "--sustain-seconds", type=float, default=30.0,
        help="minimum first-run gameplay time before the recovery sequence",
    )
    parser.add_argument(
        "--without-dfs-rom", action="store_true",
        help="diagnostic only: omit bank 2 to isolate filing-system ROM interaction",
    )
    parser.add_argument(
        "--fiq-delay", type=int,
        help=("override only the FIQ capture delay; omit this option to use "
              "the conservative fault-injection default"),
    )
    parser.add_argument("--display", type=int, default=123)
    parser.add_argument("--wait", type=float, default=900.0)
    parser.add_argument("--sample-interval", type=float, default=5.0)
    parser.add_argument(
        "--gameplay-input", default="space,space",
        help=("comma-separated X11 keys sent after the reviewed title frame; "
              "Thrust requires one Space for the score screen and another "
              "for active play"),
    )
    parser.add_argument(
        "--gameplay-input-delay", type=float, default=2.0,
        help="minimum emulated wall time between gameplay input keys",
    )
    parser.add_argument("--title-reference", type=Path, required=True)
    parser.add_argument("--gameplay-reference", type=Path, required=True)
    parser.add_argument(
        "--prompt-reference", type=Path,
        help="reviewed MOS prompt used to gate each post-Break recovery command",
    )
    parser.add_argument(
        "--failure-reference", type=Path, action="append", required=True,
        help="known prompt or MOS-error screen; repeatable",
    )
    parser.add_argument("--title-similarity", type=float, default=0.90)
    parser.add_argument(
        "--gameplay-similarity", type=float, default=0.80,
        help="lower bound for a dynamic frame against the reviewed gameplay frame",
    )
    parser.add_argument("--failure-similarity", type=float, default=0.90)
    parser.add_argument("--xvfb", type=Path,
                        default=Path("/tmp/elkulator-tools/usr/bin/Xvfb"))
    args = parser.parse_args()
    if args.sample_interval <= 0:
        parser.error("--sample-interval must be positive")
    if args.gameplay_input_delay < 0:
        parser.error("--gameplay-input-delay must not be negative")
    if args.sustain_seconds < 6:
        parser.error("--sustain-seconds must be at least 6")
    if args.recovery_check and args.profile != "adfs-beebscsi":
        parser.error("--recovery-check currently requires --profile adfs-beebscsi")
    if args.recovery_check and args.prompt_reference is None:
        parser.error("--recovery-check requires --prompt-reference")
    if args.recovery_check and args.pi1mhz_cfg is None:
        parser.error("--recovery-check requires an explicit --pi1mhz-cfg")
    if args.writable_beebscsi_copy:
        if args.beebscsi_lun is None:
            parser.error("--writable-beebscsi-copy requires --beebscsi-lun")
        try:
            args.beebscsi_lun.resolve().relative_to(Path("/tmp").resolve())
        except ValueError:
            parser.error("writable BeebSCSI media must be a disposable copy under /tmp")
    gameplay_input = [key.strip() for key in args.gameplay_input.split(",")
                      if key.strip()]
    if not gameplay_input:
        parser.error("--gameplay-input must contain at least one key")
    for option in ("title_similarity", "gameplay_similarity",
                   "failure_similarity"):
        if not 0.5 <= getattr(args, option) <= 1.0:
            parser.error(f"--{option.replace('_', '-')} must be between 0.5 and 1.0")
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
    if args.pi1mhz_cfg is not None and not args.pi1mhz_cfg.is_file():
        parser.error(f"Pi1MHz configuration not found: {args.pi1mhz_cfg}")
    if args.native_tape is not None and not args.native_tape.is_file():
        parser.error(f"native tape not found: {args.native_tape}")
    if args.preloaded_jim is not None and not args.preloaded_jim.is_file():
        parser.error(f"preloaded JIM image not found: {args.preloaded_jim}")
    for path in (args.title_reference, args.gameplay_reference,
                 *([args.prompt_reference] if args.prompt_reference else []),
                 *args.failure_reference):
        if not path.is_file():
            parser.error(f"screen reference not found: {path}")

    if args.native_tape and args.preloaded_jim:
        parser.error("--native-tape and --preloaded-jim are mutually exclusive")
    if args.no_bus_trace and args.tube:
        parser.error("--no-bus-trace cannot be used with --tube")
    if args.preloaded_jim and args.preloaded_jim.stat().st_size != 65536:
        parser.error("--preloaded-jim must be exactly 65536 bytes")
    for attribute in ("sd_image", "mmfs_rom", "beebscsi_lun", "beebscsi_dsc",
                      "pi1mhz_cfg", "native_tape", "preloaded_jim"):
        path = getattr(args, attribute)
        if path is not None:
            setattr(args, attribute, path.resolve())

    if args.output.exists() and any(args.output.iterdir()):
        parser.error(f"output directory is not empty: {args.output}")
    args.output.mkdir(parents=True, exist_ok=True)
    display = f":{args.display}"
    test_runtime = prepare_runtime(
        args.runtime_dir.resolve(), args.output / "runtime", args.pi1mhz_cfg,
    )
    roms = test_runtime / "roms"
    try:
        events = (native_tape_events() if args.native_tape else
                  preloaded_wicfs_events() if args.preloaded_jim else
                  command_events(args.profile, args.uef_file))
    except ValueError as error:
        parser.error(str(error))
    command = [
        str(args.elkulator.resolve()),
        "-rom", "12", str(roms / "RHPLUS133.rom"),
        "-rom", "11", str(roms / "electron-basic.rom"),
        "-ram", "7", "-ram", "6",
        "-rom", "5", str(roms / "AFM1V09.rom"),
        "-rom", "3", str(args.wifi_rom.resolve()),
        "-rom", "1", str(roms / "acorn-adfs.rom"),
    ]
    if not args.without_dfs_rom:
        command.extend(["-rom", "2", str(roms / "dfs.rom")])
    if args.disc:
        command.extend(["-disc", str(args.disc.resolve())])
    if args.mmfs_rom:
        command.extend(["-rom", "7", str(args.mmfs_rom)])
    if args.native_tape:
        # Elkulator's legacy command-line parser stores tape names in a short
        # fixed buffer. Keep the emulator-facing path bounded while recording
        # the original file as immutable provenance above.
        runtime_tape = test_runtime / "tape.uef"
        shutil.copyfile(args.native_tape, runtime_tape)
        command.extend(["-tape", "tape.uef"])
    command.extend(["-autokeys", command_script(events)])
    if args.tube:
        command.extend(["-tube6502", str(roms / "6502tube_120.rom")])

    environment = {
        key: value for key, value in os.environ.items()
        if not key.startswith("PI1MHZ_")
    }
    environment.update({
        "DISPLAY": display,
        "PI1MHZ_MAILBOX": "fixture",
        "PI1MHZ_TRACE": str((args.output / "mailbox.trace").resolve()),
    })
    if not args.no_bus_trace:
        environment["PI1MHZ_BUS_TRACE"] = str(
            (args.output / "bus.trace").resolve()
        )
    if args.fiq_delay is not None:
        environment["PI1MHZ_FIQ_DELAY_ACCESSES"] = str(args.fiq_delay)
    if args.sd_image:
        environment["PI1MHZ_SD_IMAGE"] = str(args.sd_image)
    if args.beebscsi_lun:
        environment["PI1MHZ_BEEBSCSI_LUN"] = str(args.beebscsi_lun.resolve())
        environment["PI1MHZ_BEEBSCSI_READ_ONLY"] = (
            "0" if args.writable_beebscsi_copy else "1"
        )
        environment["PI1MHZ_BEEBSCSI_DEBUG"] = "1"
        environment["PI1MHZ_AP5_PROFILE"] = "full"
        environment["PI1MHZ_NOE"] = "1"
    if args.beebscsi_dsc:
        environment["PI1MHZ_BEEBSCSI_DSC"] = str(args.beebscsi_dsc.resolve())
    if args.preloaded_jim:
        environment["PI1MHZ_JIM_IMAGE"] = str(args.preloaded_jim)
        environment["PI1MHZ_JIM_IMAGE_ADDRESS"] = "0"
    immutable_inputs = {
        "acceptance_runner": Path(__file__).resolve(),
        "provenance_module": Path(__file__).resolve().parent / "provenance.py",
        "elkulator": args.elkulator,
        "wifi_rom": args.wifi_rom,
        "rom_12_rhplus": roms / "RHPLUS133.rom",
        "rom_11_os": roms / "electron-basic.rom",
        "rom_5_ap5": roms / "AFM1V09.rom",
        "rom_1_adfs": roms / "acorn-adfs.rom",
        "title_reference": args.title_reference,
        "gameplay_reference": args.gameplay_reference,
        **({"prompt_reference": args.prompt_reference}
           if args.prompt_reference else {}),
        **({"staged_pi1mhz_cfg": args.pi1mhz_cfg} if args.pi1mhz_cfg else {}),
        **({"native_tape": args.native_tape} if args.native_tape else {}),
        **({"preloaded_jim": args.preloaded_jim} if args.preloaded_jim else {}),
        **({"rom_7_mmfs": args.mmfs_rom} if args.mmfs_rom else {}),
        **{f"failure_reference_{number}": reference
           for number, reference in enumerate(args.failure_reference)},
        **({"tube_rom": roms / "6502tube_120.rom"} if args.tube else {}),
        **({"rom_2_dfs": roms / "dfs.rom"} if not args.without_dfs_rom else {}),
    }
    media_inputs = {
        **({"disc": args.disc} if args.disc else {}),
        **({"sd_image": args.sd_image} if args.sd_image else {}),
        **({"beebscsi_lun": args.beebscsi_lun} if args.beebscsi_lun else {}),
        **({"beebscsi_dsc": args.beebscsi_dsc} if args.beebscsi_dsc else {}),
    }
    config_inputs = {
        "source_elk_cfg": args.runtime_dir / "elk.cfg",
        "test_elk_cfg": test_runtime / "elk.cfg",
        "pi1mhz_cfg": test_runtime / "Pi1MHz.cfg",
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
            command, cwd=test_runtime, env=environment,
            stdout=elk_log, stderr=subprocess.STDOUT, start_new_session=True,
        )
        deadline = time.monotonic() + args.wait
        started = time.monotonic()
        number = 0
        capture_times = []
        first_game_input_seconds = None
        first_gameplay_seconds = None
        gameplay_input_index = 0
        next_game_input_at = None
        break_seconds = None
        recovery_commands_seconds = None
        recovery_title_seconds = None
        recovery_gameplay_seconds = None
        recovery_input_index = 0
        recovery_next_input_at = None
        recovery_commands = ["*ADFS", "*MOUNT", "*DIR UEF"]
        if args.native_tape is None:
            recovery_commands.append(f"*UEF LOAD {args.uef_file}")
        recovery_command_index = 0
        recovery_command_sent_at = None
        recovery_prompt_confirmations = 0
        beebscsi_reads_before_break = None
        captured_title_scores = []
        captured_gameplay_scores = []
        captured_failure_scores = {str(reference): []
                                   for reference in args.failure_reference}
        while time.monotonic() < deadline and process.poll() is None:
            time.sleep(min(args.sample_interval,
                           max(0.0, deadline - time.monotonic())))
            screenshot = args.output / f"screen-{number}.png"
            capture(display, screenshot)
            elapsed = time.monotonic() - started
            capture_times.append(elapsed)
            number += 1
            title_score = similarity(screenshot, args.title_reference)
            gameplay_score = similarity(screenshot, args.gameplay_reference)
            prompt_score = (prompt_similarity(screenshot, args.prompt_reference)
                            if args.prompt_reference else 0.0)
            captured_title_scores.append(title_score)
            captured_gameplay_scores.append(gameplay_score)
            for reference in args.failure_reference:
                captured_failure_scores[str(reference)].append(
                    similarity(screenshot, reference)
                )
            # Do not guess when cassette loading has finished. Start the game
            # only after the reviewed native title/instructions frame is
            # visible, using the same focused X11 injection as the catalogue
            # runner.
            if (first_game_input_seconds is None and
                    title_score >= args.title_similarity):
                first_game_input_seconds = elapsed
                inject_x11_keys(display, [gameplay_input[0]])
                gameplay_input_index = 1
                next_game_input_at = time.monotonic() + args.gameplay_input_delay
            elif (next_game_input_at is not None and
                    gameplay_input_index < len(gameplay_input) and
                    time.monotonic() >= next_game_input_at):
                inject_x11_keys(display, [gameplay_input[gameplay_input_index]])
                gameplay_input_index += 1
                next_game_input_at = time.monotonic() + args.gameplay_input_delay
            if (first_game_input_seconds is not None and
                    first_gameplay_seconds is None and
                    gameplay_score >= args.gameplay_similarity):
                first_gameplay_seconds = elapsed
            if (args.recovery_check and first_gameplay_seconds is not None and
                    gameplay_input_index == len(gameplay_input) and
                    break_seconds is None and
                    elapsed >= first_gameplay_seconds + args.sustain_seconds):
                inject_x11_keys(display, ["F12"])
                break_seconds = elapsed
                beebscsi_reads_before_break = beebscsi_read_count(
                    args.output / "elkulator.log"
                )
            elif (break_seconds is not None and recovery_commands_seconds is None):
                if recovery_command_sent_at is None:
                    if (elapsed >= break_seconds + 3.0 and
                            prompt_score >= args.failure_similarity):
                        inject_elkulator_command(
                            display, recovery_commands[recovery_command_index]
                        )
                        recovery_command_sent_at = elapsed
                        if recovery_command_index == len(recovery_commands) - 1:
                            recovery_commands_seconds = elapsed
                elif (elapsed >= recovery_command_sent_at + 1.0 and
                      prompt_score >= args.failure_similarity):
                    recovery_prompt_confirmations += 1
                    recovery_command_index += 1
                    recovery_command_sent_at = None
            elif (recovery_commands_seconds is not None and
                    recovery_title_seconds is None and
                    title_score >= args.title_similarity):
                recovery_title_seconds = elapsed
                inject_x11_keys(display, [gameplay_input[0]])
                recovery_input_index = 1
                recovery_next_input_at = time.monotonic() + args.gameplay_input_delay
            elif (recovery_next_input_at is not None and
                    recovery_input_index < len(gameplay_input) and
                    time.monotonic() >= recovery_next_input_at):
                inject_x11_keys(display, [gameplay_input[recovery_input_index]])
                recovery_input_index += 1
                recovery_next_input_at = time.monotonic() + args.gameplay_input_delay
            if (recovery_title_seconds is not None and
                    recovery_gameplay_seconds is None and
                    gameplay_score >= args.gameplay_similarity):
                recovery_gameplay_seconds = elapsed
            elif (recovery_gameplay_seconds is not None and
                  recovery_input_index == len(gameplay_input) and
                  elapsed >= recovery_gameplay_seconds + 8.0):
                break
            if (args.native_tape is not None and
                    recovery_commands_seconds is not None and
                    elapsed >= recovery_commands_seconds + 8.0):
                break
        screenshots = sorted_screens(args.output)
        pre_indexes = [index for index, elapsed in enumerate(capture_times)
                       if (first_game_input_seconds is None or
                           elapsed <= first_game_input_seconds)]
        post_indexes = [index for index, elapsed in enumerate(capture_times)
                        if (first_game_input_seconds is not None and
                            elapsed > first_game_input_seconds + 1.0 and
                            (break_seconds is None or elapsed < break_seconds))]
        pre_input = [screenshots[index] for index in pre_indexes]
        post_input = [screenshots[index] for index in post_indexes]
        title_scores = [captured_title_scores[index] for index in pre_indexes]
        gameplay_scores = [captured_gameplay_scores[index] for index in post_indexes]
        title_seen = max(title_scores, default=0.0) >= args.title_similarity
        gameplay_seen = max(gameplay_scores, default=0.0) >= args.gameplay_similarity
        gameplay_screens = [screen for screen, score in zip(post_input, gameplay_scores)
                            if score >= args.gameplay_similarity]
        gameplay_motion_pixels = [frame_change_pixels(left, right)
                                  for left, right in zip(
                                      gameplay_screens, gameplay_screens[1:])]
        gameplay_motion = max(gameplay_motion_pixels, default=0) >= 100
        epoch_motion_pixels, sustained_gameplay_motion = sustained_motion_by_epoch(
            screenshots, capture_times, first_gameplay_seconds, break_seconds,
        ) if args.recovery_check else ([], gameplay_motion)
        # The last frame before input is the causal baseline. Comparing every
        # earlier loader frame with every later frame is both weaker evidence
        # and quadratic when a large ADFS directory takes time to scan.
        correlated_changes = (
            [frame_change_pixels(pre_input[-1], after) for after in post_input]
            if pre_input else []
        )
        input_correlated_change = max(correlated_changes, default=0) >= 1000
        failure_scores = captured_failure_scores
        failure_seen = any(
            max(scores, default=0.0) >= args.failure_similarity
            for scores in failure_scores.values()
        )
        recovery_indexes = [
            index for index, elapsed in enumerate(capture_times)
            if (recovery_gameplay_seconds is not None and
                elapsed >= recovery_gameplay_seconds)
        ]
        recovery_screens = [screenshots[index] for index in recovery_indexes]
        recovery_motion_pixels = [
            frame_change_pixels(left, right)
            for left, right in zip(recovery_screens, recovery_screens[1:])
        ]
        recovery_motion = max(recovery_motion_pixels, default=0) >= 100
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
        beebscsi_reads_after = beebscsi_read_count(args.output / "elkulator.log")
        post_break_beebscsi_reads = (
            beebscsi_reads_after - beebscsi_reads_before_break
            if beebscsi_reads_before_break is not None else 0
        )
        tube_started = "AP5 Tube: external 3MHz 65C02 enabled" in log_text
        tube_requirement_satisfied = not args.tube or tube_started
        recovery_common = bool(
            break_seconds is not None and recovery_commands_seconds is not None and
            recovery_prompt_confirmations == len(recovery_commands) - 1 and
            post_break_beebscsi_reads > 0
        )
        recovery_reloaded = bool(
            recovery_title_seconds is not None and
            recovery_gameplay_seconds is not None and
            recovery_input_index == len(gameplay_input) and recovery_motion
        )
        recovery_passed = bool(
            not args.recovery_check or
            (recovery_common and
             (args.native_tape is not None or recovery_reloaded))
        )
        media_state_ok = media_unchanged or args.writable_beebscsi_copy
        passed = bool(
            alive_at_deadline and title_seen and gameplay_seen and
            gameplay_input_index == len(gameplay_input) and
            input_correlated_change and sustained_gameplay_motion and
            recovery_passed and
            media_state_ok and config_unchanged and
            tube_requirement_satisfied and not failure_seen and not mos_errors and
            (args.profile != "adfs-beebscsi" or adfs_supported)
        )
        report = {
            "argv": command,
            "hardware_environment": {
                key: environment[key]
                for key in sorted(environment)
                if key == "DISPLAY" or key.startswith("PI1MHZ_")
            },
            "profile": args.profile,
            "uef_file": args.uef_file,
            "stream_source": "native-cassette" if args.native_tape else "wicfs",
            "adfs_beebscsi_supported": adfs_supported,
            "profile_note": (
                "BeebSCSI LUN 0 mounted through the full-decode AP5 profile"
                if args.profile == "adfs-beebscsi"
                else "DFS approximation; BeebSCSI and MMFS are not present"
            ),
            "tube": args.tube,
            "bus_trace_enabled": not args.no_bus_trace,
            "dfs_rom_present": not args.without_dfs_rom,
            "tube_started": tube_started,
            "tube_requirement_satisfied": tube_requirement_satisfied,
            "timing_profile": (
                "conservative-fault-injection" if args.fiq_delay is None
                else f"capture-override-{args.fiq_delay}"
            ),
            "screenshots": [str(path) for path in screenshots],
            "capture_times_seconds": capture_times,
            "first_game_input_seconds": first_game_input_seconds,
            "first_gameplay_seconds": first_gameplay_seconds,
            "game_input_source": "reviewed-title-frame-triggered X11 sequence",
            "gameplay_input": gameplay_input,
            "gameplay_input_complete": gameplay_input_index == len(gameplay_input),
            "acceptance_thresholds": {
                "title_similarity": args.title_similarity,
                "gameplay_similarity": args.gameplay_similarity,
                "failure_similarity": args.failure_similarity,
                "input_change_pixels": 1000,
                "post_input_motion_pixels": 100,
            },
            "title_reference_scores": title_scores,
            "gameplay_reference_scores": gameplay_scores,
            "title_seen_before_input": title_seen,
            "gameplay_seen_after_input": gameplay_seen,
            "gameplay_motion_pixels": gameplay_motion_pixels,
            "gameplay_motion": gameplay_motion,
            "gameplay_epoch_motion_pixels": epoch_motion_pixels,
            "sustained_gameplay_motion": sustained_gameplay_motion,
            "input_correlated_change_pixels": correlated_changes,
            "input_correlated_change": input_correlated_change,
            "failure_reference_scores": failure_scores,
            "failure_seen": failure_seen,
            "mos_errors_in_log": mos_errors,
            "still_running_at_deadline": alive_at_deadline,
            "recovery": {
                "required": args.recovery_check,
                "break_seconds": break_seconds,
                "commands_seconds": recovery_commands_seconds,
                "commands": recovery_commands,
                "prompt_confirmations": recovery_prompt_confirmations,
                "beebscsi_reads_before_break": beebscsi_reads_before_break,
                "beebscsi_reads_after": beebscsi_reads_after,
                "post_break_beebscsi_reads": post_break_beebscsi_reads,
                "second_title_seconds": recovery_title_seconds,
                "second_gameplay_seconds": recovery_gameplay_seconds,
                "second_input_complete": recovery_input_index == len(gameplay_input),
                "second_gameplay_motion_pixels": recovery_motion_pixels,
                "second_gameplay_motion": recovery_motion,
                "passed": recovery_passed,
            },
            "stream_trace": {
                "available": bool(trace_lines),
                "lines": trace_lines,
                "note": "Local OSFIND/OSBGET UEF input may not produce backend stream events",
            },
            "bus_trace": bus_trace_summary(args.output / "bus.trace"),
            "provenance": {
                "immutable_inputs": immutable_provenance,
                "media_before": media_before,
                "media_after": media_after,
                "config_before": config_before,
                "config_after": config_after,
                "media_unchanged": media_unchanged,
                "media_mutation_allowed": args.writable_beebscsi_copy,
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
