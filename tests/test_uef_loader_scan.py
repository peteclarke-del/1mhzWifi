import importlib.util
import struct
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "uef_loader_scan", ROOT / "scripts/uef_loader_scan.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
UEF_MAP = MODULE.uef_map


def cfs_block(name: bytes, block: int, data: bytes, last: bool) -> bytes:
    descriptor = struct.pack(
        "<IIHHBI", 0x1900, 0x8023, block, len(data), 0x80 if last else 0, 0
    )
    header = name + b"\0" + descriptor
    return (b"*" + header + UEF_MAP.tape_crc(header).to_bytes(2, "big") +
            data + UEF_MAP.tape_crc(data).to_bytes(2, "big"))


def build_uef(files: list[tuple[bytes, bytes]], block_size: int = 256) -> bytes:
    payload = b"UEF File!\0" + bytes([0, 10])
    for name, data in files:
        pieces = [data[at:at + block_size]
                  for at in range(0, max(len(data), 1), block_size)] or [b""]
        for number, piece in enumerate(pieces):
            block = cfs_block(name, number, piece, number == len(pieces) - 1)
            payload += struct.pack("<HI", 0x0100, len(block)) + block
    return payload


class UefLoaderScanTest(unittest.TestCase):
    def scan(self, files: list[tuple[bytes, bytes]], **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.uef"
            path.write_bytes(build_uef(files, **kwargs))
            return MODULE.scan(path)

    def test_reports_the_published_electron_filev_stamp(self):
        loader = b"\rd\x1f  A%=163:X%=128:Y%=1:CALL&FFF4:?&212=&D6:?&213=&F1\r\xff"
        report = self.scan([(b"EXILE", loader)])
        self.assertEqual(len(report["stamps"]), 1)
        stamp = report["stamps"][0]
        self.assertEqual(stamp["filev"], "&F1D6")
        self.assertTrue(stamp["mos_cassette_entry"])
        self.assertTrue(stamp["with_osbyte_163"])
        self.assertIn("?&212=&D6", stamp["text"])

    def test_accepts_the_decimal_spelling_of_the_same_stamp(self):
        report = self.scan([(b"LOADER", b"\r\x00\n\x10?&212=214:?&213=241\r\xff")])
        self.assertEqual(report["stamps"][0]["filev"], "&F1D6")
        self.assertTrue(report["stamps"][0]["mos_cassette_entry"])

    def test_records_a_stamp_to_some_other_address(self):
        report = self.scan([(b"LOADER", b"\r\x00\n\x10?&212=&00:?&213=&90\r\xff")])
        self.assertEqual(report["stamps"][0]["filev"], "&9000")
        self.assertFalse(report["stamps"][0]["mos_cassette_entry"])

    def test_records_an_unrecognised_stamp_form_rather_than_dropping_it(self):
        # A loader which writes only the low byte still disturbs FILEV, so it
        # must not be silently absent from the corpus measurement.
        report = self.scan([(b"LOADER", b"\r\x00\n\x10?&212=&D6\r\xff")])
        self.assertEqual(len(report["stamps"]), 1)
        self.assertIsNone(report["stamps"][0]["filev"])

    def test_ignores_a_loader_which_leaves_the_vector_alone(self):
        report = self.scan([(b"CLEAN", b"\r\x00\n\x0c MODE6:CHAIN\"\"\r\xff")])
        self.assertEqual(report["stamps"], [])

    def test_reassembles_a_file_split_across_blocks(self):
        body = b"?&212=&D6:?&213=&F1"
        data = b"A" * 250 + body + b"B" * 40
        report = self.scan([(b"SPLIT", data)], block_size=256)
        self.assertEqual(len(report["files"]), 1)
        self.assertEqual(report["files"][0]["length"], len(data))
        # The stamp straddles the 256-byte block boundary and is only visible
        # once the blocks are joined, which is the point of reassembling.
        self.assertEqual(report["stamps"][0]["filev"], "&F1D6")

    def test_separates_consecutive_files(self):
        report = self.scan([
            (b"FIRST", b"\r\x00\n\x08 END\r\xff"),
            (b"SECOND", b"\r\x00\n\x08 END\r\xff"),
        ])
        self.assertEqual([entry["name"] for entry in report["files"]],
                         ["FIRST", "SECOND"])


if __name__ == "__main__":
    unittest.main()
