from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RunnerAcceptanceContractTests(unittest.TestCase):
    def test_nettools_requires_liveness_and_command_completion(self):
        source = (ROOT / "tests/elkulator/run_nettools_hardware.py").read_text()
        self.assertIn("alive_at_deadline and command_success", source)
        self.assertIn('["SSH_OPEN", "SSH_USER", "CLOSE"]', source)
        self.assertIn('["OPEN", "CLOSE"]', source)
        self.assertIn("DNS trace plus required final address screen", source)
        self.assertIn('"--hwd-pass-screen"', source)
        self.assertIn('events.extend((100, KEY_SPACE) for _ in range(5))', source)
        self.assertIn("adfs_beebscsi_supported", source)
        self.assertNotIn('"exact-hardware"', source)
        self.assertIn('"live" if args.profile == "adfs-beebscsi"', source)
        self.assertIn("beebscsi_lun", source)
        self.assertIn("beebscsi_dsc", source)

    def test_uef_requires_known_state_and_input_correlated_change(self):
        source = (ROOT / "tests/elkulator/run_uef_gameplay.py").read_text()
        self.assertIn('"--title-reference"', source)
        self.assertIn('"--gameplay-reference"', source)
        self.assertIn("title_seen and gameplay_seen", source)
        self.assertIn('profile == "adfs-beebscsi"', source)
        self.assertIn("Select that real directory", source)
        self.assertIn("input_correlated_change", source)
        self.assertIn("frame_change_pixels(pre_input[-1], after)", source)
        self.assertIn("failure_seen", source)
        self.assertIn("still_running_at_deadline", source)
        self.assertIn('inject_x11_keys(display, ["space"])', source)
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
        self.assertIn('off["tube_started"]', source)
        self.assertIn('on["tube_started"]', source)
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


if __name__ == "__main__":
    unittest.main()
