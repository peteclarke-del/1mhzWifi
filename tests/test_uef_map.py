import gzip
import importlib.util
import io
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "uef_map", ROOT / "scripts/uef_map.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class UefMapTest(unittest.TestCase):
    @staticmethod
    def chunk(chunk_type: int, payload: bytes) -> bytes:
        return struct.pack("<HI", chunk_type, len(payload)) + payload

    def inspect_bytes(self, encoded: bytes):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.uef"
            path.write_bytes(encoded)
            return MODULE.inspect_uef(path)

    @staticmethod
    def cfs_block(name: bytes, block: int, data: bytes,
                  flags: int = 0) -> bytes:
        descriptor = struct.pack(
            "<IIHHBI", 0x1900, 0x8023, block, len(data), flags, 0
        )
        header = name + b"\0" + descriptor
        return (b"*" + header + MODULE.tape_crc(header).to_bytes(2, "big") +
                data + MODULE.tape_crc(data).to_bytes(2, "big"))

    def test_maps_offsets_and_reports_legacy_firmware_trim(self):
        header = b"UEF File!\0\x05\0"
        first = self.chunk(0x0100, b"ABC")
        tail = self.chunk(0x0110, b"\x58\x02")
        report = self.inspect_bytes(header + first + tail)
        self.assertEqual(report["chunks"][0]["offset"], 12)
        self.assertEqual(report["chunks"][0]["end"], 21)
        self.assertEqual(report["last_0100_end"], 21)
        self.assertEqual(report["compatibility_length"], len(header + first + tail))
        self.assertEqual(report["legacy_trim_length"], 21)
        self.assertEqual(report["legacy_trimmed_bytes"], len(tail))

    def test_distinguishes_other_data_chunks_from_firmware_0100_rule(self):
        header = b"UEF File!\0\x05\0"
        implicit = self.chunk(0x0100, b"one")
        explicit = self.chunk(0x0102, b"two")
        report = self.inspect_bytes(header + implicit + explicit)
        self.assertEqual(report["last_data_end"], len(header + implicit + explicit))
        self.assertEqual(report["legacy_trim_length"], len(header + implicit))

    def test_decodes_gzip_and_single_entry_zip_gzip(self):
        raw = b"UEF File!\0\x05\0" + self.chunk(0x0100, b"data")
        compressed = gzip.compress(raw)
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
            output.writestr("game.uef.gz", compressed)
        report = self.inspect_bytes(archive.getvalue())
        self.assertEqual(report["container_chain"], ["zip", "gzip", "raw"])
        self.assertEqual(report["zip_member"], "game.uef.gz")
        self.assertEqual(report["decoded_length"], len(raw))

    def test_decodes_and_validates_cfs_blocks(self):
        header = b"UEF File!\0\x05\0"
        first = self.cfs_block(b"GAME", 0, b"abc")
        last = self.cfs_block(b"GAME", 1, b"de", flags=0x81)
        report = self.inspect_bytes(
            header + self.chunk(0x0100, first) + self.chunk(0x0100, last)
        )
        self.assertEqual([block["name"] for block in report["cfs_blocks"]],
                         ["GAME", "GAME"])
        self.assertEqual(report["cfs_blocks"][1]["block_number"], 1)
        self.assertTrue(report["cfs_blocks"][1]["last_block"])
        self.assertTrue(report["cfs_blocks"][1]["locked"])
        self.assertEqual(report["cfs_issues"], [])

    def test_reports_bad_crc_and_block_sequence(self):
        header = b"UEF File!\0\x05\0"
        broken = bytearray(self.cfs_block(b"GAME", 2, b"abc"))
        broken[-1] ^= 1
        report = self.inspect_bytes(header + self.chunk(0x0100, broken))
        self.assertTrue(any("starts at block" in issue
                            for issue in report["cfs_issues"]))
        self.assertTrue(any("bad data CRC" in issue
                            for issue in report["cfs_issues"]))
        self.assertTrue(any("without a final-block flag" in issue
                            for issue in report["cfs_issues"]))

    def test_accepts_zero_byte_marker_without_data_crc(self):
        header = b"UEF File!\0\x05\0"
        block = self.cfs_block(b"V1", 0, b"", flags=0x80)[:-2]
        report = self.inspect_bytes(header + self.chunk(0x0100, block))
        self.assertEqual(report["cfs_blocks"][0]["data_length"], 0)
        self.assertIsNone(report["cfs_blocks"][0]["data_crc"])
        self.assertEqual(report["cfs_issues"], [])

    def test_rejects_truncated_chunks_and_multi_entry_zip(self):
        raw = b"UEF File!\0\x05\0" + struct.pack("<HI", 0x0100, 99) + b"x"
        with self.assertRaisesRegex(MODULE.UefError, "declares 99 bytes"):
            self.inspect_bytes(raw)
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr("one.uef", b"one")
            output.writestr("two.uef", b"two")
        with self.assertRaisesRegex(MODULE.UefError, "exactly one file"):
            self.inspect_bytes(archive.getvalue())

    def test_local_samples_are_structurally_complete_when_installed(self):
        samples = sorted((ROOT / "samples").glob("*.uef"))
        if not samples:
            self.skipTest("local third-party UEF corpus is not installed")
        for sample in samples:
            with self.subTest(sample=sample.name):
                report = MODULE.inspect_uef(sample)
                self.assertEqual(report["chunks"][-1]["end"],
                                 report["decoded_length"])


if __name__ == "__main__":
    unittest.main()
