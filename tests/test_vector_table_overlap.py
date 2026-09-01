import importlib.util
import struct
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "vector_table_overlap", ROOT / "scripts/vector_table_overlap.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def ssd(entries: list[tuple[bytes, int, int]], sectors: int = 800) -> bytes:
    """Build a DFS image from (name, load address, length) triples."""
    names = bytearray(b"\0" * 256)
    meta = bytearray(b"\0" * 256)
    names[0:8] = b"TEST    "
    meta[5] = len(entries) * 8
    meta[6] = (sectors >> 8) & 3
    meta[7] = sectors & 0xFF
    for index, (name, load, length) in enumerate(entries):
        at = 8 + index * 8
        names[at:at + 7] = name.ljust(7)[:7]
        names[at + 7] = ord("$")
        meta[at + 0] = load & 0xFF
        meta[at + 1] = (load >> 8) & 0xFF
        meta[at + 4] = length & 0xFF
        meta[at + 5] = (length >> 8) & 0xFF
        meta[at + 6] = (((length >> 16) & 3) << 4) | (((load >> 16) & 3) << 2)
    return bytes(names) + bytes(meta) + b"\0" * 256


class VectorTableOverlapTest(unittest.TestCase):
    def scan(self, image: bytes) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.ssd"
            path.write_bytes(image)
            return MODULE.scan_disc(path)

    def test_covers_table_spans_the_documented_range(self):
        self.assertTrue(MODULE.covers_table(0x0D00, 0x2300))   # Killer Gorilla
        self.assertTrue(MODULE.covers_table(0x0880, 0x4F80))   # Mineshaft
        self.assertTrue(MODULE.covers_table(0x0D9F, 1))        # first byte
        self.assertTrue(MODULE.covers_table(0x0DEF, 1))        # last byte

    def test_a_file_ending_below_the_table_does_not_cover_it(self):
        # Chuckulus loads $.Chuck at &08C0 for &0440, ending at exactly &0D00.
        self.assertFalse(MODULE.covers_table(0x08C0, 0x0440))

    def test_a_file_starting_above_the_table_does_not_cover_it(self):
        self.assertFalse(MODULE.covers_table(0x0DF0, 0x1000))

    def test_an_entry_without_a_fixed_load_address_is_excluded(self):
        # load=&0000 means the program places the file itself, so counting it
        # as loading from zero would inflate the measurement.
        self.assertFalse(MODULE.covers_table(0x0000, 0x2530))

    def test_reads_a_dfs_catalogue_and_reports_only_overlapping_files(self):
        image = ssd([
            (b"BOOT", 0x0000, 0x001E),
            (b"SAFE", 0x1900, 0x0400),
            (b"OVER", 0x0B00, 0x4CFF),
        ])
        self.assertEqual(self.scan(image), ["$.OVER"])

    def test_reports_nothing_for_an_image_which_stays_clear(self):
        self.assertEqual(self.scan(ssd([(b"SAFE", 0x1900, 0x0400)])), [])

    def test_rejects_a_catalogue_whose_length_is_not_whole_entries(self):
        image = bytearray(ssd([(b"A", 0x1900, 0x10)]))
        image[256 + 5] = 9
        with self.assertRaises(ValueError):
            self.scan(bytes(image))

    def test_rejects_an_image_shorter_than_its_catalogue(self):
        with self.assertRaises(ValueError):
            self.scan(b"\0" * 100)

    def test_survey_counts_unreadable_images_separately(self):
        with tempfile.TemporaryDirectory() as directory:
            good = Path(directory) / "good.ssd"
            good.write_bytes(ssd([(b"OVER", 0x0B00, 0x4CFF)]))
            bad = Path(directory) / "bad.ssd"
            bad.write_bytes(b"\0" * 16)
            report = MODULE.survey([good, bad])
        self.assertEqual(report["examined"], 1)
        self.assertEqual(len(report["unreadable"]), 1)
        self.assertEqual(len(report["overlapping"]), 1)


if __name__ == "__main__":
    unittest.main()
