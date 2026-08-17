from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BEmRunnerContractTests(unittest.TestCase):
    def test_minimum_model_b_profile_is_explicit_and_tube_free(self) -> None:
        source = (ROOT / "tests/bem/run_bem_hardware.py").read_text()
        self.assertIn("BBC B 32K Pi1MHz minimum", source)
        self.assertIn("fdc=none", source)
        self.assertIn("tube=none", source)
        self.assertIn("vdfsenable=false", source)
        self.assertIn("rom15=basic2", source)
        self.assertIn("rom14={wifi_rom.resolve()}", source)
        self.assertIn('"machine_profile": "bbc-model-b-32k-minimum"', source)

    def test_pass_requires_visual_output_trace_and_liveness(self) -> None:
        source = (ROOT / "tests/bem/run_bem_hardware.py").read_text()
        self.assertIn("alive and args.require_screen and not missing_screens", source)
        self.assertIn("not missing_events", source)
        self.assertIn('"still_running_at_deadline": alive', source)
        self.assertIn('"PI1MHZ_MAILBOX": "live"', source)
        self.assertIn("bem_paste(args.command)", source)

    def test_runner_records_current_binary_rom_and_configuration(self) -> None:
        source = (ROOT / "tests/bem/run_bem_hardware.py").read_text()
        self.assertIn('"bem": args.bem', source)
        self.assertIn('"wifi_rom": args.wifi_rom', source)
        self.assertIn('"config_before": config_before', source)
        self.assertIn('"config_after": snapshot', source)
        self.assertIn("output directory is not empty", source)


if __name__ == "__main__":
    unittest.main()
