import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tests/elkulator/run_catalogue_differential.py"
SPEC = importlib.util.spec_from_file_location("catalogue_differential", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class CatalogueDifferentialTests(unittest.TestCase):
    def test_catalogue_matches_java_treeset_and_ignores_non_uef_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            index = Path(directory) / "index.txt"
            index.write_text(
                "./Zed/Second_E.uef\n"
                "./Docs/Codes.gif.gz\n"
                "./Alpha/First_RUN_BE.uef\n"
                "./Zed/Second_E.uef\n"
            )
            entries = MODULE.read_catalogue(index)
        self.assertEqual(
            [(entry["index"], entry["name"]) for entry in entries],
            [(0, "First"), (1, "Second")],
        )

    def test_key_script_uses_elkulator_star_and_selection_waits_for_titles(self):
        first_page = MODULE.key_script(5).split(",")
        self.assertEqual(first_page[:3], ["100:2000", "1:69", "1:2001"])
        self.assertEqual(first_page[-1], "1:67")
        self.assertEqual(MODULE.catalogue_selection_keys(5), ["f"])
        self.assertEqual(MODULE.catalogue_selection_keys(44),
                         ["Down", "Down", "c"])

    def test_exact_title_wins_over_substring_matches(self):
        catalogue = [
            {"index": 0, "name": "FrakV2"},
            {"index": 1, "name": "FrakV2-PIASRR"},
        ]
        args = type("Args", (), {
            "all": False, "title_range": None, "title": ["frakv2"]
        })()
        self.assertEqual(MODULE.select_titles(catalogue, args), [catalogue[0]])

    def test_trace_fingerprint_is_independent_of_read_chunking(self):
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / "trace"
            trace.write_text(
                "OPEN\t0\thttp://example.invalid/Publisher/Game_E.uef\n"
                "READ\t0\t0102\nREAD\t0\t03\n"
                "CLOSE\t0\thttp://example.invalid/Publisher/Game_E.uef\n"
            )
            opened, payload = MODULE.trace_payload(
                trace, "./Publisher/Game_E.uef"
            )
        self.assertEqual(opened, "http://example.invalid/Publisher/Game_E.uef")
        self.assertEqual(payload[0], "bytes=3")
        self.assertEqual(
            payload[1], "sha256=" + hashlib.sha256(b"\x01\x02\x03").hexdigest()
        )

    def test_trace_payload_is_bounded_to_matching_handle_and_close(self):
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / "trace"
            trace.write_text(
                "OPEN\t3\thttp://example.invalid/Publisher/Game_E.uef\n"
                "READ\t4\tdeadbeef\n"
                "READ\t3\t0102\n"
                "CLOSE\t3\thttp://example.invalid/Publisher/Game_E.uef\n"
                "READ\t3\tffff\n"
            )
            _, payload = MODULE.trace_payload(trace, "Publisher/Game_E.uef")
        self.assertEqual(payload[0], "bytes=2")
        self.assertEqual(
            payload[1], "sha256=" + hashlib.sha256(b"\x01\x02").hexdigest()
        )

    def test_animated_control_cannot_count_as_input_transition(self):
        self.assertFalse(MODULE.transitioned_to_gameplay(
            [0.82, 0.91, 0.86], [0.84, 0.92, 0.88], 0.80, 0.10
        ))
        self.assertTrue(MODULE.transitioned_to_gameplay(
            [0.20, 0.24, 0.22], [0.81, 0.91, 0.86], 0.80, 0.10
        ))


if __name__ == "__main__":
    unittest.main()
