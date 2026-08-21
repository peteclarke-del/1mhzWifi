import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tests" / "elkulator" / "run_nettools_hardware.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("nettools_hardware_runner", RUNNER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ElkulatorCommandTypingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = load_runner()

    def test_adfs_root_uses_shifted_four_for_dollar(self):
        events = self.runner.typed_command("dir $.utils", 100)
        dollar = events.index((2, self.runner.KEY_SHIFT_DOWN), 3)
        self.assertEqual(events[dollar:dollar + 3], [
            (2, self.runner.KEY_SHIFT_DOWN),
            (1, self.runner.KEY_4),
            (1, self.runner.KEY_SHIFT_UP),
        ])

    def test_raw_basic_command_has_no_star_prefix(self):
        events = self.runner.typed_command("print page", 100, star=False)
        self.assertEqual(events[0], (100, self.runner.KEYS["p"]))
        self.assertNotIn((1, self.runner.KEY_SHIFT_DOWN), events[:3])
        self.assertEqual(events[-1], (2, self.runner.KEY_ENTER))


if __name__ == "__main__":
    unittest.main()
