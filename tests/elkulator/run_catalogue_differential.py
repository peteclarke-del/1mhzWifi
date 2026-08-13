#!/usr/bin/env python3
"""Compare WiCFS catalogue launches with the AP5 Tube disabled and enabled.

The no-Tube run is the behavioural reference.  Each selected title is fetched
again with the same ROM ordering and an enabled Tube.  The test compares the
network payload and a small set of post-launch screen samples.  It does not
contain title-specific launch rules.
"""

from __future__ import annotations

import argparse
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


SUFFIXES = (
    "_RUN_BE.uef", "_RUN_E.uef", "_E.hq.uef",
    "_BE.uef", "_E.uef", ".uef",
)
KEY_SHIFT_DOWN = 2000
KEY_SHIFT_UP = 2001
KEY_QUOTE = 69             # Shift+quote produces * in Elkulator's Elk map.
KEY_ENTER = 67
KEY_DOWN = 85


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
    parser.add_argument("--xvfb", type=Path,
                        default=Path("/tmp/elkulator-tools/usr/bin/Xvfb"))
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true")
    selection.add_argument("--range", dest="title_range", metavar="FIRST:LAST")
    selection.add_argument("--title", action="append", default=[],
                           help="exact name, or a case-insensitive substring; may be repeated")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--settle", type=float, default=8.0)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--sample-interval", type=float, default=1.0)
    parser.add_argument("--similarity", type=float, default=0.90)
    parser.add_argument("--display", type=int, default=119)
    parser.add_argument("--resume", action="store_true",
                        help="reuse complete trace and screenshot pairs")
    return parser.parse_args()


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


def key_script(index: int) -> str:
    page, position = divmod(index, 21)
    events = [
        (100, KEY_SHIFT_DOWN), (1, KEY_QUOTE), (1, KEY_SHIFT_UP),
        (1, 13), (1, 5), (1, 14), (1, 21), (1, KEY_ENTER),
    ]
    # MENU starts on page one.  Down is unambiguous for catalogues beyond the
    # single-digit direct page shortcuts.
    if page:
        events.append((1000, KEY_DOWN))
        events.extend((12, KEY_DOWN) for _ in range(page - 1))
        events.append((50, position + 1))
    else:
        events.append((1000, position + 1))
    return ",".join(f"{delay}:{key}" for delay, key in events)


def trace_payload(trace: Path, expected_path: str) -> tuple[str | None, list[str]]:
    opened_url = None
    events = []
    payload = bytearray()
    for line in trace.read_text(errors="replace").splitlines():
        fields = line.split("\t", 2)
        if len(fields) != 3:
            continue
        event, handle, detail = fields
        if event == "OPEN" and expected_path.lstrip("./") in detail:
            opened_url = detail
        if opened_url is None:
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


def has_frame_change(paths: list[str]) -> bool:
    return any(
        similarity(Path(left), Path(right)) < 0.99999
        for left, right in zip(paths, paths[1:])
    )


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
        "-autokeys", key_script(int(entry["index"])),
    ]
    if tube:
        command.extend(["-tube6502", str(roms / "6502tube_120.rom")])
    return command


def run_one(args: argparse.Namespace, entry: dict[str, object], tube: bool,
            display: str) -> dict[str, object]:
    label = "tube-on" if tube else "tube-off"
    directory = args.output / f"{int(entry['index']):04d}-{entry['name']}" / label
    directory.mkdir(parents=True, exist_ok=True)
    trace = directory / "network.trace"
    log = directory / "elkulator.log"
    existing_screenshots = sorted(directory.glob("screen-*.png"))
    if args.resume and trace.exists() and len(existing_screenshots) == args.samples:
        opened_url, payload = trace_payload(trace, str(entry["path"]))
        closed = any(line.startswith("CLOSE\t") and
                     str(entry["path"]).lstrip("./") in line
                     for line in trace.read_text(errors="replace").splitlines())
        if closed:
            return {
                "closed": True,
                "opened_url": opened_url,
                "payload": payload[:2],
                "screenshots": [str(path) for path in existing_screenshots],
                "log": str(log),
            }
    environment = os.environ.copy()
    environment.update({
        "DISPLAY": display,
        "PI1MHZ_MAILBOX": "live",
        "PI1MHZ_TRACE": str(trace),
    })
    with log.open("wb") as output:
        process = subprocess.Popen(
            emulator_command(args, entry, tube), cwd=args.runtime_dir,
            env=environment, stdout=output, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        closed = False
        screenshots = []
        try:
            closed = wait_for_game_close(trace, str(entry["path"]), process,
                                         args.timeout)
            if closed:
                time.sleep(args.settle)
                for number in range(args.samples):
                    screenshot = directory / f"screen-{number}.png"
                    capture(display, screenshot)
                    screenshots.append(screenshot)
                    if number + 1 < args.samples:
                        time.sleep(args.sample_interval)
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
    return {
        "closed": closed,
        "opened_url": opened_url,
        "payload": payload[:2],
        "screenshots": [str(path) for path in screenshots],
        "log": str(log),
    }


def main() -> int:
    args = parse_arguments()
    args.elkulator = args.elkulator.resolve()
    args.runtime_dir = args.runtime_dir.resolve()
    args.index = args.index.resolve()
    args.wifi_rom = args.wifi_rom.resolve()
    args.output = args.output.resolve()
    args.xvfb = args.xvfb.resolve()
    required = [str(args.elkulator), str(args.xvfb), "xwd", "convert",
                "compare", "montage"]
    for tool in required:
        resolved = Path(tool) if "/" in tool else Path(shutil.which(tool) or "/missing")
        if not resolved.is_file():
            raise SystemExit(f"required executable not found: {tool}")
    catalogue = read_catalogue(args.index)
    selected = select_titles(catalogue, args)
    args.output.mkdir(parents=True, exist_ok=True)
    display = f":{args.display}"
    xvfb_log = (args.output / "xvfb.log").open("wb")
    xvfb = subprocess.Popen(
        [str(args.xvfb), display, "-screen", "0", "1024x768x24"],
        stdout=xvfb_log, stderr=subprocess.STDOUT, start_new_session=True,
    )
    time.sleep(1)
    report = {
        "catalogue_size": len(catalogue),
        "rom_sha256": hashlib.sha256(args.wifi_rom.read_bytes()).hexdigest(),
        "results": [],
    }
    failures = 0
    try:
        for entry in selected:
            print(f"[{int(entry['index']) + 1}/{len(catalogue)}] {entry['name']}",
                  flush=True)
            off = run_one(args, entry, False, display)
            on = run_one(args, entry, True, display)
            scores = []
            for left in off["screenshots"]:
                for right in on["screenshots"]:
                    scores.append(similarity(Path(left), Path(right)))
            best = max(scores, default=0.0)
            payload_equal = bool(off["payload"] and off["payload"] == on["payload"])
            off_changed = has_frame_change(off["screenshots"])
            on_changed = has_frame_change(on["screenshots"])
            passed = bool(off["closed"] and on["closed"] and payload_equal and
                          off_changed and on_changed and best >= args.similarity)
            comparison = args.output / f"{int(entry['index']):04d}-{entry['name']}" / "comparison.png"
            if off["screenshots"] and on["screenshots"]:
                subprocess.run([
                    "montage", "-label", "Tube disabled", off["screenshots"][0],
                    "-label", "Tube enabled", on["screenshots"][0],
                    "-tile", "2x1", "-geometry", "+4+4", str(comparison),
                ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            failures += not passed
            result = {
                **entry, "tube_off": off, "tube_on": on,
                "payload_equal": payload_equal,
                "tube_off_frame_change": off_changed,
                "tube_on_frame_change": on_changed,
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
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"{len(selected) - failures} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
