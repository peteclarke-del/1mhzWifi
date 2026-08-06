import ctypes
import gzip
import io
import struct
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "pi-side/pi1mhz-v1.30/src"


class UefNormalizeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory()
        library = Path(cls._temporary.name) / "libuef_normalize.so"
        subprocess.run(
            ["cc", "-std=c11", "-shared", "-fPIC", "-O2", "-I", str(SOURCE),
             str(SOURCE / "uef_normalize.c"), str(SOURCE / "puff.c"),
             "-o", str(library)],
            check=True,
        )
        cls.normalize = ctypes.CDLL(str(library)).uef_normalize
        cls.normalize.argtypes = [
            ctypes.POINTER(ctypes.c_uint8), ctypes.POINTER(ctypes.c_size_t),
            ctypes.c_size_t, ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t,
        ]
        cls.normalize.restype = ctypes.c_int

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def run_normalize(self, encoded: bytes) -> tuple[int, bytes]:
        capacity = 0xFFFE
        window = (ctypes.c_uint8 * capacity)()
        scratch = (ctypes.c_uint8 * capacity)()
        window[:len(encoded)] = encoded
        length = ctypes.c_size_t(len(encoded))
        result = self.normalize(window, ctypes.byref(length), capacity,
                                scratch, capacity)
        return result, bytes(window[:length.value])

    def test_raw_gzip_zip_and_zip_containing_gzip(self) -> None:
        raw = b"UEF File!\0" + bytes(range(64))
        self.assertEqual(self.run_normalize(raw), (0, raw))
        self.assertEqual(self.run_normalize(gzip.compress(raw)), (1, raw))

        for payload in (raw, gzip.compress(raw)):
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
                output.writestr("game.uef", payload)
            self.assertEqual(self.run_normalize(archive.getvalue()), (2, raw))

    def test_invalid_and_oversized_inputs_are_rejected(self) -> None:
        self.assertEqual(self.run_normalize(b"not a UEF")[0], 3)
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
            output.writestr("one.uef", b"UEF File!\0one")
            output.writestr("two.uef", b"UEF File!\0two")
        self.assertEqual(self.run_normalize(archive.getvalue())[0], 3)
        oversized = gzip.compress(b"UEF File!\0" + bytes(0xFFFE))
        self.assertEqual(self.run_normalize(oversized)[0], 4)

    def test_local_deskdiary_hardware_sample_when_present(self) -> None:
        sample = ROOT / "samples/Acornsoft Desk Diary (198x)(Acornsoft).uef"
        if not sample.is_file():
            self.skipTest("local third-party DeskDiary sample is not installed")
        result, raw = self.run_normalize(sample.read_bytes())
        self.assertEqual(result, 1)
        self.assertEqual(len(raw), 20580)
        self.assertEqual(raw[:12], b"UEF File!\0\x05\0")
        offset = 12
        while offset < len(raw):
            self.assertLessEqual(offset + 6, len(raw))
            chunk_type, length = struct.unpack_from("<HI", raw, offset)
            self.assertTrue(chunk_type < 0x0500 or chunk_type >= 0xFF00)
            offset += 6 + length
            self.assertLessEqual(offset, len(raw))
        self.assertEqual(offset, len(raw))
        self.assertNotIn(b"\xD5\x5F", raw)
        self.assertNotIn(b"\x5F\xD5", raw)


if __name__ == "__main__":
    unittest.main()
