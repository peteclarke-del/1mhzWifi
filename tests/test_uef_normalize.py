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
SOURCE = ROOT / "pi-side/pi1mhz-516a267/overlay/src"
EMULATOR = ROOT / "emulator/pi1mhz-mailbox"
JIM_SIZE = 3 << 24
SERVICE_BASE = JIM_SIZE - (2 << 24)
CONTROL = SERVICE_BASE + 0xFFFF00


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
        fixture_library = Path(cls._temporary.name) / "libfixture_normalize.so"
        subprocess.run(
            ["cc", "-std=c11", "-shared", "-fPIC", "-O2",
             "-D_POSIX_C_SOURCE=200809L", "-I", str(EMULATOR / "include"),
             str(EMULATOR / "src/pi1mhz_net_backend.c"), "-lz",
             "-o", str(fixture_library)],
            check=True,
        )
        cls.fixture = ctypes.CDLL(str(fixture_library))
        cls.fixture.pi1mhz_net_backend_create.argtypes = [
            ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int,
        ]
        cls.fixture.pi1mhz_net_backend_create.restype = ctypes.c_void_p
        cls.fixture.pi1mhz_net_backend_destroy.argtypes = [ctypes.c_void_p]
        cls.fixture.pi1mhz_net_backend_dispatch.argtypes = [
            ctypes.c_void_p, ctypes.c_uint8, ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t,
        ]
        cls.fixture.pi1mhz_net_backend_dispatch.restype = ctypes.c_uint8

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

    def run_fixture_normalize(self, encoded: bytes) -> tuple[str, bytes]:
        jim = (ctypes.c_uint8 * JIM_SIZE)()
        jim[:len(encoded)] = encoded
        jim[0xFFFE] = len(encoded) & 0xFF
        jim[0xFFFF] = len(encoded) >> 8
        jim[CONTROL] = 93
        backend = self.fixture.pi1mhz_net_backend_create(b"fixture", None, 0)
        self.assertTrue(backend)
        try:
            result = self.fixture.pi1mhz_net_backend_dispatch(
                backend, 0xFF, CONTROL, jim, JIM_SIZE
            )
            self.assertEqual(result, 0)
            length = jim[0xFFFE] | (jim[0xFFFF] << 8)
            response = bytes(jim[CONTROL + 1:CONTROL + 32]).split(b"\0", 1)[0]
            return response.decode("ascii").strip(), bytes(jim[:length])
        finally:
            self.fixture.pi1mhz_net_backend_destroy(backend)

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

    def test_emulator_and_pi_normalizers_match_real_corpus(self) -> None:
        samples = [
            ROOT / "samples/Thrust (1986)(Superior Software).uef",
            ROOT / "samples/Acornsoft Desk Diary (198x)(Acornsoft).uef",
        ]
        installed = [sample for sample in samples if sample.is_file()]
        if not installed:
            self.skipTest("local third-party UEF corpus is not installed")
        result_names = {0: "RAW", 1: "GZIP", 2: "ZIP", 3: "INVALID",
                        4: "TOO LARGE"}
        for sample in installed:
            with self.subTest(sample=sample.name):
                pi_result, pi_bytes = self.run_normalize(sample.read_bytes())
                fixture_result, fixture_bytes = self.run_fixture_normalize(
                    sample.read_bytes()
                )
                self.assertEqual(fixture_result, result_names[pi_result])
                self.assertEqual(fixture_bytes, pi_bytes)


if __name__ == "__main__":
    unittest.main()
