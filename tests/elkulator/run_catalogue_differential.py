#!/usr/bin/env python3
"""Compare WiCFS catalogue launches with the AP5 Tube disabled and enabled.

The no-Tube run is the behavioural reference.  Each selected title is fetched
again with the same ROM ordering and an enabled Tube.  The test compares the
network payload and a small set of post-launch screen samples.  It does not
contain title-specific launch rules.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

# These runners are both executable scripts and are imported directly by the
# contract tests.  Make their sibling support module resolvable in both cases.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from provenance import snapshot, sorted_screens, source_revision


SUFFIXES = (
    "_RUN_BE.uef", "_RUN_E.uef", "_E.hq.uef",
    "_BE.uef", "_E.uef", ".uef",
)
KEY_SHIFT_DOWN = 2000
KEY_SHIFT_UP = 2001
KEY_QUOTE = 69             # Shift+quote produces * in Elkulator's Elk map.
KEY_ENTER = 67


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="batch Tube-on/off comparison of the published UEF catalogue"
    )
    parser.add_argument("--elkulator", type=Path, required=True)
    parser.add_argument(
        "--runtime-dir", type=Path, required=True,
        help="Elkulator working directory containing roms/ and elk.cfg",
    )
    parser.add_argument("--index", type=Path, required=True,
                        help="published menu data/index.txt")
    parser.add_argument("--wifi-rom", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", choices=("catalogue", "mmfs", "adfs-beebscsi"),
                        default="catalogue")
    parser.add_argument("--tube-mode", choices=("off", "both"), default="both",
                        help="use off while establishing the non-Tube baseline")
    parser.add_argument("--sd-image", type=Path,
                        help="raw Pi1MHz FAT image used by the MMFS profile")
    parser.add_argument("--mmfs-rom", type=Path,
                        help="SWMMFS ROM loaded into writable sideways bank 7")
    parser.add_argument("--beebscsi-lun", type=Path)
    parser.add_argument("--beebscsi-dsc", type=Path,
                        help="optional 22-to-33-byte BeebSCSI geometry sidecar")
    parser.add_argument(
        "--gameplay-reference", action="append", default=[], metavar="TITLE=IMAGE",
        help="reviewed gameplay frame for each selected title; repeatable",
    )
    parser.add_argument(
        "--ready-reference", action="append", default=[], metavar="TITLE=IMAGE",
        help="reviewed title or attract frame which is safe to receive input",
    )
    parser.add_argument(
        "--gameplay-input", action="append", default=[], metavar="TITLE=KEY[,KEY...]",
        help=("X11 key names injected after the UEF stream closes; every selected "
              "title requires an entry"),
    )
    parser.add_argument(
        "--failure-reference", type=Path, action="append", required=True,
        help="known prompt or MOS-error screen; repeatable",
    )
    parser.add_argument("--xvfb", type=Path,
                        default=Path("/tmp/elkulator-tools/usr/bin/Xvfb"))
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true")
    selection.add_argument("--range", dest="title_range", metavar="FIRST:LAST")
    selection.add_argument("--title", action="append", default=[],
                           help="exact name, or a case-insensitive substring; may be repeated")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--launch-timeout", type=float, default=180.0,
                        help="deadline after download close for the runnable title frame")
    parser.add_argument("--probe-interval", type=float, default=2.0)
    parser.add_argument("--settle", type=float, default=8.0)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--control-samples", type=int, default=5,
                        help="no-input frames recorded before gameplay input")
    parser.add_argument("--sample-interval", type=float, default=1.0)
    parser.add_argument("--similarity", type=float, default=0.90)
    parser.add_argument("--gameplay-similarity", type=float, default=0.80,
                        help="NCC floor for the reviewed post-input gameplay frame")
    parser.add_argument("--transition-margin", type=float, default=0.10,
                        help="required gameplay NCC increase over the no-input control")
    parser.add_argument("--display", type=int, default=119)
    parser.add_argument(
        "--fiq-delay", type=int,
        help=("override only the FIQ capture delay; omit this option to use "
              "the conservative fault-injection default"),
    )
    args = parser.parse_args()
    if not 0.5 <= args.similarity <= 1.0:
        parser.error("--similarity must be between 0.5 and 1.0")
    if not 0.5 <= args.gameplay_similarity <= 1.0:
        parser.error("--gameplay-similarity must be between 0.5 and 1.0")
    if not 0.0 < args.transition_margin <= 1.0:
        parser.error("--transition-margin must be greater than zero and at most one")
    if args.samples < 2 or args.control_samples < 2:
        parser.error("--samples and --control-samples must both be at least two")
    if args.profile == "adfs-beebscsi" and args.beebscsi_lun is None:
        parser.error("--profile adfs-beebscsi requires --beebscsi-lun")
    if args.profile == "mmfs":
        if args.sd_image is None or args.mmfs_rom is None:
            parser.error("--profile mmfs requires --sd-image and --mmfs-rom")
        if not args.sd_image.is_file():
            parser.error(f"Pi1MHz SD image not found: {args.sd_image}")
        if not args.mmfs_rom.is_file():
            parser.error(f"MMFS ROM not found: {args.mmfs_rom}")
    if args.beebscsi_lun is not None and not args.beebscsi_lun.is_file():
        parser.error(f"BeebSCSI LUN not found: {args.beebscsi_lun}")
    if args.beebscsi_lun and args.beebscsi_dsc is None:
        candidate = args.beebscsi_lun.with_suffix(".dsc")
        if candidate.is_file():
            args.beebscsi_dsc = candidate
    if args.beebscsi_dsc is not None and not args.beebscsi_dsc.is_file():
        parser.error(f"BeebSCSI geometry not found: {args.beebscsi_dsc}")
    return args


def named_references(values: list[str]) -> dict[str, Path]:
    references = {}
    for value in values:
        name, separator, path = value.partition("=")
        if not separator or not name or not path:
            raise ValueError("--gameplay-reference requires TITLE=IMAGE")
        references[name.casefold()] = Path(path).resolve()
    return references


def named_inputs(values: list[str]) -> dict[str, list[str]]:
    inputs = {}
    for value in values:
        name, separator, keys = value.partition("=")
        sequence = [key.strip() for key in keys.split(",") if key.strip()]
        if not separator or not name or not sequence:
            raise ValueError("--gameplay-input requires TITLE=KEY[,KEY...]")
        inputs[name.casefold()] = sequence
    return inputs


def inject_x11_keys(display: str, keys: list[str]) -> None:
    """Inject keys into the sole Elkulator window on the private Xvfb display."""
    x11 = ctypes.CDLL("libX11.so.6")
    xtst = ctypes.CDLL("libXtst.so.6")
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XStringToKeysym.argtypes = [ctypes.c_char_p]
    x11.XStringToKeysym.restype = ctypes.c_ulong
    x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    x11.XKeysymToKeycode.restype = ctypes.c_uint
    x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    x11.XDefaultRootWindow.restype = ctypes.c_ulong
    x11.XQueryTree.argtypes = [
        ctypes.c_void_p, ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
        ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)),
        ctypes.POINTER(ctypes.c_uint),
    ]
    x11.XQueryTree.restype = ctypes.c_int
    x11.XFree.argtypes = [ctypes.c_void_p]
    x11.XSetInputFocus.argtypes = [
        ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong,
    ]
    x11.XSetInputFocus.restype = ctypes.c_int
    x11.XRaiseWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                      ctypes.c_int, ctypes.c_ulong]
    handle = x11.XOpenDisplay(display.encode("ascii"))
    if not handle:
        raise RuntimeError(f"cannot open X display {display}")
    try:
        root = x11.XDefaultRootWindow(handle)
        root_return = ctypes.c_ulong()
        parent_return = ctypes.c_ulong()
        children = ctypes.POINTER(ctypes.c_ulong)()
        child_count = ctypes.c_uint()
        if not x11.XQueryTree(
            handle, root, ctypes.byref(root_return), ctypes.byref(parent_return),
            ctypes.byref(children), ctypes.byref(child_count),
        ):
            raise RuntimeError(f"cannot inspect X display {display}")
        try:
            if child_count.value != 1:
                raise RuntimeError(
                    f"expected one Elkulator window on {display}, found "
                    f"{child_count.value}"
                )
            window = children[0]
        finally:
            if children:
                x11.XFree(children)
        x11.XRaiseWindow(handle, window)
        # RevertToParent=2 and CurrentTime=0. Xvfb has no window manager to
        # assign focus, so XTest events otherwise go to the root and are lost.
        x11.XSetInputFocus(handle, window, 2, 0)
        x11.XSync(handle, 0)
        for name in keys:
            # XKeysymToKeycode("at") returns a layout-dependent number key and
            # does not add Shift.  Elkulator's default PC mapping assigns the
            # Electron @/* key to the host apostrophe key.  Send that physical
            # chord explicitly so MOS receives *, as it does for a user.
            chord = ("Shift_L", "apostrophe") if name == "at" else (name,)
            keycodes = []
            for chord_name in chord:
                keysym = x11.XStringToKeysym(chord_name.encode("ascii"))
                keycode = x11.XKeysymToKeycode(handle, keysym) if keysym else 0
                if not keycode:
                    raise ValueError(
                        f"unknown or unmapped X11 key name: {chord_name}"
                    )
                keycodes.append(keycode)
                if not xtst.XTestFakeKeyEvent(handle, keycode, 1, 0):
                    raise RuntimeError(f"XTest key-down failed for {chord_name}")
            x11.XSync(handle, 0)
            # Elkulator samples Allegro keyboard state. Keep the key down
            # across several 50 Hz samples instead of queueing down and up in
            # the same X server round trip.
            time.sleep(0.15)
            for chord_name, keycode in reversed(tuple(zip(chord, keycodes))):
                if not xtst.XTestFakeKeyEvent(handle, keycode, 0, 0):
                    raise RuntimeError(f"XTest key-up failed for {chord_name}")
            x11.XSync(handle, 0)
            time.sleep(0.25)
    finally:
        x11.XCloseDisplay(handle)


def title_name(path: str) -> str | None:
    filename = path.rsplit("/", 1)[-1]
    for suffix in SUFFIXES:
        if filename.endswith(suffix):
            return filename[:-len(suffix)]
    return None


def read_catalogue(path: Path) -> list[dict[str, object]]:
    # ProcessIndex.java uses TreeSet<String>, and the archive paths are ASCII.
    lines = sorted({line.strip() for line in path.read_text().splitlines()
                    if line.strip()})
    titles = []
    for line in lines:
        name = title_name(line)
        if name is not None:
            titles.append({"index": len(titles), "path": line, "name": name})
    return titles


def select_titles(catalogue: list[dict[str, object]], args: argparse.Namespace
                  ) -> list[dict[str, object]]:
    if args.all:
        return catalogue
    if args.title_range:
        match = re.fullmatch(r"(\d+):(\d+)", args.title_range)
        if not match:
            raise ValueError("--range must be FIRST:LAST, using zero-based indices")
        first, last = (int(value) for value in match.groups())
        if first > last or last >= len(catalogue):
            raise ValueError("--range lies outside the catalogue")
        return catalogue[first:last + 1]
    selected = []
    for query in args.title:
        matches = [entry for entry in catalogue
                   if query.casefold() == str(entry["name"]).casefold()]
        if not matches:
            matches = [entry for entry in catalogue
                       if query.casefold() in str(entry["name"]).casefold()]
        if not matches:
            raise ValueError(f"no catalogue title matches {query!r}")
        selected.extend(matches)
    unique = {int(entry["index"]): entry for entry in selected}
    return [unique[index] for index in sorted(unique)]


def star_command(text: str, delay: int) -> list[tuple[int, int]]:
    events = [
        (delay, KEY_SHIFT_DOWN), (1, KEY_QUOTE), (1, KEY_SHIFT_UP),
    ]
    for character in text.casefold():
        events.append((1, 75 if character == " " else ord(character) - ord("a") + 1
                       if "a" <= character <= "z" else ord(character) - ord("0") + 27))
    events.append((1, KEY_ENTER))
    return events


def key_script(index: int, mmfs: bool = False) -> str:
    events: list[tuple[int, int]] = []
    if mmfs:
        events.extend(star_command("disc", 250))
        events.extend(star_command("din 0", 250))
    events.extend([
        (100, KEY_SHIFT_DOWN), (1, KEY_QUOTE), (1, KEY_SHIFT_UP),
        (1, 13), (1, 5), (1, 14), (1, 21), (1, KEY_ENTER),
    ])
    return ",".join(f"{delay}:{key}" for delay, key in events)


def catalogue_selection_keys(index: int) -> list[str]:
    page, position = divmod(index, 21)
    return ["Down"] * page + [chr(ord("a") + position)]


def trace_payload(trace: Path, expected_path: str) -> tuple[str | None, list[str]]:
    opened_url = None
    expected_handle = None
    events = []
    payload = bytearray()
    for line in trace.read_text(errors="replace").splitlines():
        fields = line.split("\t", 2)
        if len(fields) != 3:
            continue
        event, handle, detail = fields
        if event == "OPEN" and expected_path.lstrip("./") in detail:
            opened_url = detail
            expected_handle = handle
            payload.clear()
            events.clear()
        if opened_url is None:
            continue
        if handle != expected_handle:
            continue
        if event == "READ":
            try:
                chunk = bytes.fromhex(detail)
            except ValueError:
                events.append("MALFORMED_READ")
                continue
            payload.extend(chunk)
            events.append(f"READ:{len(chunk)}")
        elif event in ("OPEN", "CLOSE"):
            events.append(f"{event}:{detail}")
            if event == "CLOSE":
                break
    return opened_url, [
        f"bytes={len(payload)}",
        f"sha256={hashlib.sha256(payload).hexdigest()}",
        *events,
    ]


def wait_for_game_close(trace: Path, expected_path: str, process: subprocess.Popen,
                        timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    needle = expected_path.lstrip("./")
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        if trace.exists():
            text = trace.read_text(errors="replace")
            if any(line.startswith("CLOSE\t") and needle in line
                   for line in text.splitlines()):
                return True
        time.sleep(0.1)
    return False


def capture(display: str, output: Path) -> None:
    xwd = subprocess.run(
        ["xwd", "-display", display, "-root", "-silent"],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    subprocess.run(
        ["convert", "xwd:-", str(output)], input=xwd.stdout,
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )


def similarity(left: Path, right: Path) -> float:
    result = subprocess.run(
        ["compare", "-colorspace", "Gray", "-metric", "NCC",
         str(left), str(right), "null:"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    value = result.stderr.strip().split()[0]
    return float(value)


def frame_change_pixels(left: Path, right: Path) -> int:
    result = subprocess.run(
        ["compare", "-colorspace", "Gray", "-metric", "AE",
         str(left), str(right), "null:"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    return int(result.stderr.strip().split()[0])


def transitioned_to_gameplay(control_scores: list[float], post_scores: list[float],
                             threshold: float, margin: float) -> bool:
    control_best = max(control_scores, default=0.0)
    post_best = max(post_scores, default=0.0)
    return post_best >= threshold and post_best - control_best >= margin


def emulator_command(args: argparse.Namespace, entry: dict[str, object],
                     tube: bool) -> list[str]:
    roms = args.runtime_dir / "roms"
    command = [
        str(args.elkulator),
        "-rom", "12", str(roms / "RHPLUS133.rom"),
        "-rom", "11", str(roms / "electron-basic.rom"),
        "-ram", "7", "-ram", "6",
        "-rom", "5", str(roms / "AFM1V09.rom"),
        "-rom", "3", str(args.wifi_rom),
        "-rom", "2", str(roms / "dfs.rom"),
        "-rom", "1", str(roms / "acorn-adfs.rom"),
        "-autokeys", key_script(int(entry["index"]), args.profile == "mmfs"),
    ]
    if args.mmfs_rom:
        command.extend(["-rom", "7", str(args.mmfs_rom)])
    if tube:
        command.extend(["-tube6502", str(roms / "6502tube_120.rom")])
    return command


def run_one(args: argparse.Namespace, entry: dict[str, object], tube: bool,
            display: str, gameplay_input: list[str], ready_reference: Path,
            gameplay_reference: Path) -> dict[str, object]:
    label = "tube-on" if tube else "tube-off"
    directory = args.output / f"{int(entry['index']):04d}-{entry['name']}" / label
    directory.mkdir(parents=True, exist_ok=True)
    trace = directory / "network.trace"
    log = directory / "elkulator.log"
    environment = {
        key: value for key, value in os.environ.items()
        if not key.startswith("PI1MHZ_")
    }
    environment.update({
        "DISPLAY": display,
        "PI1MHZ_MAILBOX": "live",
        "PI1MHZ_TRACE": str(trace),
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
    with log.open("wb") as output:
        process = subprocess.Popen(
            emulator_command(args, entry, tube), cwd=args.runtime_dir,
            env=environment, stdout=output, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        closed = False
        screenshots = []
        probe_screenshots = []
        control_screenshots = []
        ready_scores = []
        ready_seen = False
        try:
            menu_ready = wait_for_game_close(trace, "TITLES", process,
                                             args.timeout)
            if menu_ready:
                inject_x11_keys(display,
                                catalogue_selection_keys(int(entry["index"])))
            closed = bool(
                menu_ready and
                wait_for_game_close(trace, str(entry["path"]), process,
                                    args.timeout)
            )
            if closed:
                launch_deadline = time.monotonic() + args.launch_timeout
                while time.monotonic() < launch_deadline and process.poll() is None:
                    probe = directory / f"probe-{len(probe_screenshots)}.png"
                    capture(display, probe)
                    probe_screenshots.append(probe)
                    score = similarity(probe, ready_reference)
                    ready_scores.append(score)
                    if score >= args.similarity:
                        ready_seen = True
                        break
                    time.sleep(args.probe_interval)
                if ready_seen:
                    pre_input = directory / "screen-0.png"
                    shutil.copyfile(probe_screenshots[-1], pre_input)
                    screenshots.append(pre_input)
                    for number in range(args.control_samples):
                        control = directory / f"control-{number}.png"
                        capture(display, control)
                        control_screenshots.append(control)
                        if number + 1 < args.control_samples:
                            time.sleep(args.sample_interval)
                    inject_x11_keys(display, gameplay_input)
                    time.sleep(args.settle)
                    for number in range(args.samples):
                        screenshot = directory / f"screen-{number + 1}.png"
                        capture(display, screenshot)
                        screenshots.append(screenshot)
                        if number + 1 < args.samples:
                            time.sleep(args.sample_interval)
            alive_after_capture = process.poll() is None
        finally:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=5)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
    opened_url, payload = trace_payload(trace, str(entry["path"])) \
        if trace.exists() else (None, [])
    log_text = log.read_text(errors="replace") if log.exists() else ""
    mos_errors = [text for text in ("Bad program", "Unexpected EOF", "Chunk type")
                  if text.casefold() in log_text.casefold()]
    tube_started = bool(
        not tube or "AP5 Tube: external 3MHz 65C02 enabled" in log_text
    )
    correlated_changes = [frame_change_pixels(screenshots[0], screen)
                          for screen in screenshots[1:]] if screenshots else []
    post_motion_changes = [frame_change_pixels(left, right)
                           for left, right in zip(screenshots[1:], screenshots[2:])]
    control_gameplay_scores = [similarity(screen, gameplay_reference)
                               for screen in control_screenshots]
    post_gameplay_scores = [similarity(screen, gameplay_reference)
                            for screen in screenshots[1:]]
    gameplay_transition = transitioned_to_gameplay(
        control_gameplay_scores, post_gameplay_scores,
        args.gameplay_similarity, args.transition_margin,
    )
    return {
        "closed": closed,
        "menu_ready": menu_ready,
        "opened_url": opened_url,
        "payload": payload[:2],
        "screenshots": [str(path) for path in screenshots],
        "pre_input_screen": str(screenshots[0]) if screenshots else None,
        "post_input_screens": [str(path) for path in screenshots[1:]],
        "gameplay_input": gameplay_input,
        "probe_screenshots": [str(path) for path in probe_screenshots],
        "control_screenshots": [str(path) for path in control_screenshots],
        "control_gameplay_scores": control_gameplay_scores,
        "post_gameplay_scores": post_gameplay_scores,
        "gameplay_transition": gameplay_transition,
        "ready_reference_scores": ready_scores,
        "ready_seen": ready_seen,
        "input_correlated_change_pixels": correlated_changes,
        "input_correlated_change": max(correlated_changes, default=0) >= 1000,
        "post_input_motion_pixels": post_motion_changes,
        "post_input_motion": max(post_motion_changes, default=0) >= 100,
        "log": str(log),
        "alive_after_capture": alive_after_capture,
        "tube_started": tube_started,
        "mos_errors_in_log": mos_errors,
        "beebscsi_mounted": "BeebSCSI: LUN 0 mounted at &FC40" in log_text,
    }


def main() -> int:
    args = parse_arguments()
    args.elkulator = args.elkulator.resolve()
    args.runtime_dir = args.runtime_dir.resolve()
    args.index = args.index.resolve()
    args.wifi_rom = args.wifi_rom.resolve()
    args.output = args.output.resolve()
    args.xvfb = args.xvfb.resolve()
    for attribute in ("sd_image", "mmfs_rom", "beebscsi_lun", "beebscsi_dsc"):
        path = getattr(args, attribute)
        if path is not None:
            setattr(args, attribute, path.resolve())
    required = [str(args.elkulator), str(args.xvfb), "xwd", "convert",
                "compare", "montage"]
    for tool in required:
        resolved = Path(tool) if "/" in tool else Path(shutil.which(tool) or "/missing")
        if not resolved.is_file():
            raise SystemExit(f"required executable not found: {tool}")
    catalogue = read_catalogue(args.index)
    selected = select_titles(catalogue, args)
    gameplay_references = named_references(args.gameplay_reference)
    ready_references = named_references(args.ready_reference)
    gameplay_inputs = named_inputs(args.gameplay_input)
    for path in (*gameplay_references.values(), *ready_references.values(),
                 *args.failure_reference):
        if not path.is_file():
            raise SystemExit(f"screen reference not found: {path}")
    missing_reference_names = [str(entry["name"]) for entry in selected
                               if str(entry["name"]).casefold() not in gameplay_references]
    if missing_reference_names:
        raise SystemExit("missing reviewed gameplay reference for: " +
                         ", ".join(missing_reference_names))
    missing_ready_names = [str(entry["name"]) for entry in selected
                           if str(entry["name"]).casefold() not in ready_references]
    if missing_ready_names:
        raise SystemExit("missing reviewed ready reference for: " +
                         ", ".join(missing_ready_names))
    missing_input_names = [str(entry["name"]) for entry in selected
                           if str(entry["name"]).casefold() not in gameplay_inputs]
    if missing_input_names:
        raise SystemExit("missing gameplay input for: " +
                         ", ".join(missing_input_names))
    if args.output.exists() and any(args.output.iterdir()):
        parser.error(f"output directory is not empty: {args.output}")
    args.output.mkdir(parents=True, exist_ok=True)
    display = f":{args.display}"
    xvfb_log = (args.output / "xvfb.log").open("wb")
    xvfb = subprocess.Popen(
        [str(args.xvfb), display, "-screen", "0", "1024x768x24"],
        stdout=xvfb_log, stderr=subprocess.STDOUT, start_new_session=True,
    )
    time.sleep(1)
    roms = args.runtime_dir / "roms"
    immutable_inputs = {
        "acceptance_runner": Path(__file__).resolve(),
        "provenance_module": Path(__file__).resolve().parent / "provenance.py",
        "elkulator": args.elkulator, "wifi_rom": args.wifi_rom,
        "catalogue_index": args.index,
        "rom_12_rhplus": roms / "RHPLUS133.rom",
        "rom_11_os": roms / "electron-basic.rom",
        "rom_5_ap5": roms / "AFM1V09.rom",
        "rom_2_dfs": roms / "dfs.rom",
        "rom_1_adfs": roms / "acorn-adfs.rom",
        "tube_rom": roms / "6502tube_120.rom",
        **({"mmfs_rom": args.mmfs_rom} if args.mmfs_rom else {}),
    }
    for entry in selected:
        key = str(entry["name"]).casefold()
        immutable_inputs[f"ready_reference_{int(entry['index']):04d}"] = \
            ready_references[key]
        immutable_inputs[f"gameplay_reference_{int(entry['index']):04d}"] = \
            gameplay_references[key]
    for number, reference_path in enumerate(args.failure_reference):
        immutable_inputs[f"failure_reference_{number:02d}"] = reference_path
    media_inputs = {
        **({"sd_image": args.sd_image} if args.sd_image else {}),
        **({"beebscsi_lun": args.beebscsi_lun} if args.beebscsi_lun else {}),
        **({"beebscsi_dsc": args.beebscsi_dsc} if args.beebscsi_dsc else {}),
    }
    media_before = snapshot(media_inputs)
    report = {
        "catalogue_size": len(catalogue),
        "profile": args.profile,
        "tube_mode": args.tube_mode,
        "acceptance_policy": {
            "download_timeout_seconds": args.timeout,
            "launch_timeout_seconds": args.launch_timeout,
            "probe_interval_seconds": args.probe_interval,
            "post_input_settle_seconds": args.settle,
            "post_input_samples": args.samples,
            "control_samples": args.control_samples,
            "sample_interval_seconds": args.sample_interval,
            "ready_and_failure_ncc": args.similarity,
            "gameplay_ncc": args.gameplay_similarity,
            "transition_margin_ncc": args.transition_margin,
            "input_change_pixels": 1000,
            "post_input_motion_pixels": 100,
        },
        "adfs_beebscsi_supported": False,
        "timing_profile": (
            "conservative-fault-injection" if args.fiq_delay is None
            else f"capture-override-{args.fiq_delay}"
        ),
        "profile_note": (
            "BeebSCSI LUN 0 mounted through the full-decode AP5 profile"
            if args.profile == "adfs-beebscsi"
            else (
                "MMFS uses the Pi1MHz raw-sector SD backend and supplied MMFS ROM"
                if args.profile == "mmfs"
                else "Live catalogue approximation; BeebSCSI is not present"
            )
        ),
        "provenance": {
            "immutable_inputs": snapshot(immutable_inputs),
            "media_before": media_before,
            "config_before": snapshot({
                "elk_cfg": args.runtime_dir / "elk.cfg",
                "pi1mhz_cfg": args.runtime_dir / "Pi1MHz.cfg",
            }),
            "runtime_source": source_revision(args.runtime_dir),
            "integration_source": source_revision(Path(__file__).resolve().parents[2]),
        },
        "results": [],
    }
    failures = 0
    try:
        for entry in selected:
            print(f"[{int(entry['index']) + 1}/{len(catalogue)}] {entry['name']}",
                  flush=True)
            gameplay_input = gameplay_inputs[str(entry["name"]).casefold()]
            reference = gameplay_references[str(entry["name"]).casefold()]
            ready_reference = ready_references[str(entry["name"]).casefold()]
            off = run_one(args, entry, False, display, gameplay_input,
                          ready_reference, reference)
            on = (run_one(args, entry, True, display, gameplay_input,
                          ready_reference, reference)
                  if args.tube_mode == "both" else None)
            scores = []
            if on is not None:
                for left in off["screenshots"]:
                    for right in on["screenshots"]:
                        scores.append(similarity(Path(left), Path(right)))
            best = max(scores, default=0.0)
            payload_equal = bool(
                off["payload"] and
                (on is None or off["payload"] == on["payload"])
            )
            off_gameplay = max((similarity(Path(screen), reference)
                                for screen in off["post_input_screens"]), default=0.0)
            on_gameplay = (max((similarity(Path(screen), reference)
                                for screen in on["post_input_screens"]), default=0.0)
                           if on is not None else None)
            off_gameplay_screen = max(
                off["post_input_screens"],
                key=lambda screen: similarity(Path(screen), reference),
                default=None,
            )
            on_gameplay_screen = (max(
                on["post_input_screens"],
                key=lambda screen: similarity(Path(screen), reference),
                default=None,
            ) if on is not None else None)
            failure_scores = {
                str(reference_path): max(
                    (similarity(Path(screen), reference_path)
                     for screen in off["screenshots"] +
                     (on["screenshots"] if on is not None else [])),
                    default=0.0,
                )
                for reference_path in args.failure_reference
            }
            failure_seen = any(score >= args.similarity
                               for score in failure_scores.values())
            passed = bool(
                off["closed"] and payload_equal and off["menu_ready"] and
                off["alive_after_capture"] and
                off_gameplay >= args.gameplay_similarity and off["ready_seen"] and
                off["gameplay_transition"] and off["input_correlated_change"] and
                off["post_input_motion"] and not failure_seen and
                not off["mos_errors_in_log"] and
                (args.profile != "adfs-beebscsi" or off["beebscsi_mounted"])
            )
            if on is not None:
                passed = bool(
                    passed and on["closed"] and on["menu_ready"] and
                    on["alive_after_capture"] and on["tube_started"] and
                    on_gameplay is not None and
                    on_gameplay >= args.gameplay_similarity and on["ready_seen"] and
                    on["gameplay_transition"] and on["input_correlated_change"] and
                    on["post_input_motion"] and not on["mos_errors_in_log"] and
                    (args.profile != "adfs-beebscsi" or on["beebscsi_mounted"])
                )
            comparison = args.output / f"{int(entry['index']):04d}-{entry['name']}" / "comparison.png"
            if off_gameplay_screen and on_gameplay_screen:
                subprocess.run([
                    "montage", "-label", "Tube disabled", off_gameplay_screen,
                    "-label", "Tube enabled", on_gameplay_screen,
                    "-tile", "2x1", "-geometry", "+4+4", str(comparison),
                ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            failures += not passed
            result = {
                **entry, "tube_off": off, "tube_on": on,
                "payload_equal": payload_equal,
                "gameplay_reference": str(reference),
                "ready_reference": str(ready_reference),
                "tube_off_gameplay_ncc": off_gameplay,
                "tube_on_gameplay_ncc": on_gameplay,
                "tube_off_gameplay_screen": off_gameplay_screen,
                "tube_on_gameplay_screen": on_gameplay_screen,
                "failure_reference_scores": failure_scores,
                "failure_seen": failure_seen,
                "best_screen_ncc": best, "comparison": str(comparison),
                "passed": passed,
            }
            report["results"].append(result)
            (args.output / "report.json").write_text(
                json.dumps(report, indent=2) + "\n"
            )
            print(f"  {'PASS' if passed else 'FAIL'} payload={payload_equal} "
                  f"screen_ncc={best:.6f}", flush=True)
    finally:
        try:
            os.killpg(xvfb.pid, signal.SIGTERM)
            xvfb.wait(timeout=5)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            if xvfb.poll() is None:
                os.killpg(xvfb.pid, signal.SIGKILL)
                xvfb.wait()
        xvfb_log.close()
    report["failures"] = failures
    report["adfs_beebscsi_supported"] = bool(
        args.profile == "adfs-beebscsi" and report["results"] and
        all(result["tube_off"]["beebscsi_mounted"] and
            (result["tube_on"] is None or
             result["tube_on"]["beebscsi_mounted"])
            for result in report["results"])
    )
    report["provenance"]["media_after"] = snapshot(media_inputs)
    report["provenance"]["config_after"] = snapshot(
        {
            "elk_cfg": args.runtime_dir / "elk.cfg",
            "pi1mhz_cfg": args.runtime_dir / "Pi1MHz.cfg",
        }
    )
    report["provenance"]["media_unchanged"] = (
        report["provenance"]["media_before"] ==
        report["provenance"]["media_after"]
    )
    report["provenance"]["config_unchanged"] = (
        report["provenance"]["config_before"] ==
        report["provenance"]["config_after"]
    )
    if (not report["provenance"]["media_unchanged"] or
            not report["provenance"]["config_unchanged"]):
        for result in report["results"]:
            result["passed"] = False
        failures = len(report["results"])
        report["failures"] = failures
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"{len(selected) - failures} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
