from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RunnerAcceptanceContractTests(unittest.TestCase):
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
        self.assertIn('default="space,space"', source)
        self.assertIn("gameplay_input_index == len(gameplay_input)", source)
        self.assertIn("inject_x11_keys(display, [gameplay_input[0]])", source)
        self.assertIn("similarity(screenshot, args.title_reference)", source)
        self.assertNotIn("(2500, KEY_SPACE)", source)
        self.assertIn("gameplay_motion and", source)
        self.assertIn("media_unchanged and config_unchanged", source)
        self.assertIn("--similarity must be between 0.5 and 1.0", source)
        self.assertIn('"title_reference": args.title_reference', source)
        self.assertIn("output directory is not empty", source)
        self.assertIn('"acceptance_runner": Path(__file__).resolve()', source)
        self.assertIn('"AP5 Tube: external 3MHz 65C02 enabled"', source)
        self.assertIn("tube_started and", source)

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
        self.assertIn('on["tube_started"]', source)
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
