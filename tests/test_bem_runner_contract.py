from pathlib import Path
import unittest

from tests.bem.run_bem_hardware import config_text
from tests.elkulator.run_uef_gameplay import largest_window


ROOT = Path(__file__).resolve().parents[1]


class BEmRunnerContractTests(unittest.TestCase):
    def test_minimum_model_b_profile_is_explicit_and_tube_free(self) -> None:
        config = config_text(Path("/tmp/ElkWiFi.rom"), "bbc-b-32k")
        self.assertIn("name=BBC B 32K Pi1MHz minimum", config)
        self.assertIn("fdc=none", config)
        self.assertIn("tube=none", config)
        self.assertIn("vdfsenable=false", config)
        self.assertIn("rom15=basic2", config)
        self.assertIn("rom14=/tmp/ElkWiFi.rom", config)

    def test_b_plus_and_master_use_the_same_rom_image(self) -> None:
        rom = Path("/tmp/ElkWiFi.rom")
        b_plus = config_text(rom, "bbc-b-plus")
        master = config_text(rom, "master-128")
        self.assertIn("b+=true", b_plus)
        self.assertIn("os=bpos", b_plus)
        self.assertIn("rom14=/tmp/ElkWiFi.rom", b_plus)
        self.assertIn("master=true", master)
        self.assertIn("65c02=true", master)
        self.assertIn("os=mos320", master)
        self.assertIn("rom07=/tmp/ElkWiFi.rom", master)

    def test_capture_selects_main_bem_window_by_area(self) -> None:
        tree = '''
          0x200003 "B-Em 2.4": ("b-em" "B-Em") 1280x960+0+0 +0+0
          0x200004 "B-Em 2.4": ("b-em" "B-Em") 320x24+0+0 +0+0
        '''
        self.assertEqual(largest_window(tree, "B-Em"), "0x200003")

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
