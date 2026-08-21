import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def load_uef_runner():
    path = ROOT / "tests/elkulator/run_uef_gameplay.py"
    spec = importlib.util.spec_from_file_location("uef_gameplay_runner", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RunnerAcceptanceContractTests(unittest.TestCase):
    def test_recovery_prompt_match_is_independent_of_screen_row(self) -> None:
        runner = load_uef_runner()
        width, height = 320, 256

        def prompt_image(path: Path, top: int) -> None:
            pixels = bytearray(width * height)
            glyph = (
                "10000000",
                "01000000",
                "00100000",
                "00010000",
                "00100000",
                "01000000",
                "10000000",
            )
            for row, line in enumerate(glyph):
                for column, value in enumerate(line):
                    if value == "1":
                        pixels[(top + row) * width + column] = 255
            path.write_bytes(
                f"P5\n{width} {height}\n255\n".encode("ascii") + pixels
            )

        with tempfile.TemporaryDirectory() as temporary:
            reference = Path(temporary) / "reference.pgm"
            moved = Path(temporary) / "moved.pgm"
            prompt_image(reference, 220)
            prompt_image(moved, 40)
            self.assertGreaterEqual(
                runner.prompt_similarity(moved, reference), 0.9
            )

    def test_ping_requires_bounded_request_count_and_clean_prompt(self) -> None:
        source = (ROOT / "tests/elkulator/run_nettools_hardware.py").read_text()
        self.assertIn('ping_count = trace_events.count("PING")', source)
        self.assertIn("1 <= ping_count < 5 and screen_success", source)
        self.assertIn("ping_count == 5 and screen_success", source)
        self.assertNotIn('command_success = "CANCEL" in trace_events', source)

    def test_nettools_requires_liveness_and_command_completion(self):
        source = (ROOT / "tests/elkulator/run_nettools_hardware.py").read_text()
        self.assertIn("alive_at_deadline and command_success", source)
        self.assertIn('["SSH_OPEN", "SSH_USER", "CLOSE"]', source)
        self.assertIn('screen_success and ordered_trace_contains(', source)
        self.assertIn('plus required clean final screen', source)
        self.assertIn('["OPEN", "CLOSE"]', source)
        self.assertIn("DNS trace plus required final address screen", source)
        self.assertIn('"--hwd-pass-screen"', source)
        self.assertIn('"--expect"', source)
        self.assertIn('if args.expect == "auto" else args.expect', source)
        self.assertIn('"--require-trace-sequence"', source)
        self.assertIn("trace_sequence_found and", source)
        self.assertIn('events.extend((100, KEY_SPACE) for _ in range(5))', source)
        self.assertIn("adfs_beebscsi_supported", source)
        self.assertNotIn('"exact-hardware"', source)
        self.assertIn(
            '"live" if args.profile in ("bare", "adfs-beebscsi")', source
        )
        self.assertIn('choices=("typical-electron", "minimum-electron")', source)
        self.assertIn('"--wifi-rom-slot"', source)
        self.assertIn('choices=range(16)', source)
        self.assertIn('profile_roms[args.wifi_rom_slot] = args.wifi_rom', source)
        self.assertIn('"wifi_rom_slot": args.wifi_rom_slot', source)
        self.assertIn('if args.machine_profile == "typical-electron"', source)
        self.assertIn('command.extend(["-ram", "7", "-ram", "6"])', source)
        self.assertIn('"--require-screen-region"', source)
        self.assertIn("parse_screen_region", source)
        self.assertIn("similarity(screen, reference, geometry)", source)
        self.assertIn("not missing_screens and not missing_regions", source)
        self.assertIn("beebscsi_lun", source)
        self.assertIn("beebscsi_dsc", source)
        self.assertIn('"--ssh-dir"', source)
        self.assertIn('environment["PI1MHZ_SSH_DIR"]', source)
        self.assertIn('"known_hosts"', source)
        self.assertIn("output directory is not empty", source)

    def test_uef_requires_known_state_and_input_correlated_change(self):
        source = (ROOT / "tests/elkulator/run_uef_gameplay.py").read_text()
        self.assertIn('"--title-reference"', source)
        self.assertIn('"--gameplay-reference"', source)
        self.assertIn("title_seen and gameplay_seen", source)
        self.assertIn('profile == "adfs-beebscsi"', source)
        self.assertIn('"--sd-image"', source)
        self.assertIn('"--mmfs-rom"', source)
        self.assertIn('"-rom", "7", str(args.mmfs_rom)', source)
        self.assertIn("Select that real directory", source)
        self.assertIn("input_correlated_change", source)
        self.assertIn("frame_change_pixels(pre_input[-1], after)", source)
        self.assertIn("failure_seen", source)
        self.assertIn("still_running_at_deadline", source)
        self.assertIn('"--gameplay-input"', source)
        self.assertIn('"--uef-file"', source)
        self.assertIn('"--without-dfs-rom"', source)
        self.assertIn('"dfs_rom_present": not args.without_dfs_rom', source)
        self.assertIn('command_events(args.profile, args.uef_file)', source)
        self.assertIn('default="space,space"', source)
        self.assertIn("gameplay_input_index == len(gameplay_input)", source)
        self.assertIn("inject_x11_keys(display, [gameplay_input[0]])", source)
        self.assertIn("title_score = similarity(screenshot, args.title_reference)", source)
        self.assertNotIn("(2500, KEY_SPACE)", source)
        self.assertIn("sustained_gameplay_motion and", source)
        self.assertIn('"--recovery-check"', source)
        self.assertIn('inject_x11_keys(display, ["F12"])', source)
        self.assertIn('recovery_commands = ["*ADFS", "*MOUNT", "*DIR UEF"', source)
        self.assertIn('display, recovery_commands[recovery_command_index]', source)
        self.assertIn("recovery_passed and", source)
        self.assertIn('"--prompt-reference"', source)
        self.assertIn('"--recovery-check requires --prompt-reference"', source)
        self.assertIn('"--recovery-check requires an explicit --pi1mhz-cfg"', source)
        self.assertIn('environment["PI1MHZ_BEEBSCSI_DEBUG"] = "1"', source)
        self.assertIn("recovery_prompt_confirmations == len(recovery_commands) - 1", source)
        self.assertIn("post_break_beebscsi_reads > 0", source)
        self.assertIn('"post_break_beebscsi_reads"', source)
        self.assertIn('"second_gameplay_seconds"', source)
        self.assertIn("media_state_ok and config_unchanged", source)
        self.assertIn('"--writable-beebscsi-copy"', source)
        self.assertIn("writable BeebSCSI media must be a disposable copy under /tmp", source)
        self.assertIn("must be between 0.5 and 1.0", source)
        self.assertIn("--gameplay-similarity", source)
        self.assertIn("--failure-similarity", source)
        self.assertIn('"title_reference": args.title_reference', source)
        self.assertIn("output directory is not empty", source)
        self.assertIn('"acceptance_runner": Path(__file__).resolve()', source)
        self.assertIn('"AP5 Tube: external 3MHz 65C02 enabled"', source)
        self.assertIn("tube_requirement_satisfied and", source)
        self.assertIn('if not key.startswith("PI1MHZ_")', source)
        self.assertIn('"hardware_environment"', source)
        self.assertIn('"argv": command', source)
        self.assertIn("args.pi1mhz_cfg", source)
        self.assertIn('"PI1MHZ_BUS_TRACE"', source)
        self.assertIn('"bus_trace": bus_trace_summary', source)
        self.assertIn('"tube_requirement_satisfied"', source)

    def test_bus_trace_summary_preserves_failure_boundary(self):
        runner = load_uef_runner()
        with tempfile.TemporaryDirectory() as temporary:
            trace = Path(temporary) / "bus.trace"
            trace.write_text(
                "# cycle op address value selected-page mapped-jim\n"
                "10 W FCFF 02 page=000001\n"
                "20 R FD05 AA page=000002 jim=00000205\n"
                "30 R FEE0 -- page=000002\n"
            )
            summary = runner.bus_trace_summary(trace)
        self.assertEqual(summary["event_count"], 3)
        self.assertEqual(summary["tube_access_count"], 1)
        self.assertEqual(summary["jim_access_count"], 1)
        self.assertEqual(summary["last_jim_access"].split()[2], "FD05")

    def test_uef_sustained_motion_rejects_a_late_freeze(self):
        runner = load_uef_runner()
        screens = [Path(f"frame-{number}") for number in range(6)]
        times = [0.0, 1.0, 3.0, 4.0, 6.0, 7.0]
        with mock.patch.object(
            runner, "frame_change_pixels", side_effect=[200, 0, 0],
        ):
            maxima, passed = runner.sustained_motion_by_epoch(
                screens, times, 0.0, 9.0,
            )
        self.assertEqual(maxima, [200, 0, 0])
        self.assertFalse(passed)

    def test_uef_runtime_profile_disables_ambient_turbo_and_plus3(self):
        runner = load_uef_runner()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "roms").mkdir()
            (source / "roms/os").write_bytes(b"os")
            (source / "roms/sndrom").write_bytes(b"sound")
            original = "plus1 = 0\nplus3 = 1\nturbo = 1\nadfsena = 1\n"
            (source / "elk.cfg").write_text(original)
            runtime = runner.prepare_runtime(source, root / "runtime")
            configured = (runtime / "elk.cfg").read_text()
            self.assertIn("plus1 = 1", configured)
            self.assertIn("plus3 = 0", configured)
            self.assertIn("turbo = 0", configured)
            self.assertIn("adfsena = 0", configured)
            self.assertEqual((source / "elk.cfg").read_text(), original)
            self.assertTrue((runtime / "roms").is_symlink())
            self.assertTrue((runtime / "os").is_symlink())
            self.assertTrue((runtime / "sndrom").is_symlink())

    def test_provenance_separates_mutable_media_snapshots(self):
        for filename in (
            "run_nettools_hardware.py", "run_uef_gameplay.py",
            "run_catalogue_differential.py",
        ):
            source = (ROOT / "tests/elkulator" / filename).read_text()
            self.assertIn('"media_before"', source, filename)
            self.assertIn('"media_after"', source, filename)
            self.assertIn('"immutable_inputs"', source, filename)

    def test_catalogue_requires_per_title_gameplay_evidence(self):
        source = (ROOT / "tests/elkulator/run_catalogue_differential.py").read_text()
        self.assertIn('"--gameplay-reference"', source)
        self.assertIn('off_gameplay >= args.gameplay_similarity', source)
        self.assertIn('on_gameplay >= args.gameplay_similarity', source)
        self.assertIn('off["alive_after_capture"]', source)
        self.assertIn('"--gameplay-input"', source)
        self.assertIn('"--ready-reference"', source)
        self.assertIn('off["input_correlated_change"]', source)
        self.assertIn('on["input_correlated_change"]', source)
        self.assertIn('off["post_input_motion"]', source)
        self.assertIn('on["post_input_motion"]', source)
        self.assertIn('off["gameplay_transition"]', source)
        self.assertIn('on["gameplay_transition"]', source)
        self.assertIn('off["menu_ready"]', source)
        self.assertIn('on["menu_ready"]', source)
        self.assertIn('on["tube_requirement_satisfied"]', source)
        self.assertIn('"tube_started": tube_started', source)
        self.assertIn('"--tube-mode"', source)
        self.assertIn('args.tube_mode == "both"', source)
        self.assertIn('"--profile mmfs requires --sd-image and --mmfs-rom"', source)
        self.assertIn('(\"sd_image\", \"mmfs_rom\", \"beebscsi_lun\", \"beebscsi_dsc\")', source)
        self.assertIn('"control_gameplay_scores"', source)
        self.assertIn('"tube_off_gameplay_screen"', source)
        self.assertIn("XSetInputFocus", source)
        self.assertIn("time.sleep(0.15)", source)
        self.assertIn('failure_seen', source)
        self.assertIn('"media_unchanged"', source)
        self.assertIn('"config_unchanged"', source)
        self.assertIn("output directory is not empty", source)

    def test_hwdtest_has_a_structured_terminal_result(self):
        source = (ROOT / "host-tools/src/hwdtest.asm").read_text()
        self.assertIn('EQUS "HWDTEST RESULT "', source)
        self.assertIn('EQUS "PASS",13,0', source)
        self.assertIn('EQUS "FAIL",13,0', source)

    def test_real_ssh_runner_is_bounded_and_retains_failures(self):
        source = (
            ROOT / "host-tools/tests/run_elkulator_ssh_real.sh"
        ).read_text()
        self.assertIn("ELKULATOR_SSH_TIMEOUT:-90", source)
        self.assertIn('timeout "${elkulator_timeout}s"', source)
        self.assertIn("Elkulator SSH diagnostics retained", source)
        self.assertIn('test_passed=1', source)


if __name__ == "__main__":
    unittest.main()
