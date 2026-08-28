import ctypes
import gzip
import io
import os
import struct
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "pi-side/pi1mhz-516a267/overlay/src"
EMULATOR = ROOT / "emulator/pi1mhz-mailbox"
PUBLISH_BASE = 0x100
FLAT_WINDOW = 0xFE00
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
        cls.wicfs_length = ctypes.CDLL(str(library)).uef_legacy_trim_length
        cls.wicfs_length.argtypes = [
            ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t,
        ]
        cls.wicfs_length.restype = ctypes.c_size_t
        fixture_library = Path(cls._temporary.name) / "libfixture_normalize.so"
        subprocess.run(
            ["cc", "-std=c11", "-shared", "-fPIC", "-O2",
             "-D_POSIX_C_SOURCE=200809L", "-I", str(EMULATOR / "include"),
             str(EMULATOR / "src/pi1mhz_net_backend.c"),
             str(EMULATOR / "src/pi1mhz_ftp.c"), "-lz",
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

    def run_normalize_large(self, encoded: bytes) -> tuple[int, bytes]:
        capacity = 16 * 1024 * 1024
        window = (ctypes.c_uint8 * capacity)()
        scratch = (ctypes.c_uint8 * capacity)()
        window[:len(encoded)] = encoded
        length = ctypes.c_size_t(len(encoded))
        result = self.normalize(window, ctypes.byref(length), capacity,
                                scratch, capacity)
        return result, bytes(window[:length.value])

    def run_fixture_normalize(
        self, encoded: bytes, *, trim_tail: bool = False,
    ) -> tuple[str, bytes]:
        jim = (ctypes.c_uint8 * JIM_SIZE)()
        jim[:len(encoded)] = encoded
        jim[0xFFFE] = len(encoded) & 0xFF
        jim[0xFFFF] = len(encoded) >> 8
        jim[CONTROL] = 93
        previous = os.environ.get("PI1MHZ_UEF_TRIM_TAIL")
        if trim_tail:
            os.environ["PI1MHZ_UEF_TRIM_TAIL"] = "1"
        else:
            os.environ.pop("PI1MHZ_UEF_TRIM_TAIL", None)
        backend = self.fixture.pi1mhz_net_backend_create(b"fixture", None, 0)
        if previous is None:
            os.environ.pop("PI1MHZ_UEF_TRIM_TAIL", None)
        else:
            os.environ["PI1MHZ_UEF_TRIM_TAIL"] = previous
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

    def effective_length(self, raw: bytes) -> int:
        window = (ctypes.c_uint8 * len(raw)).from_buffer_copy(raw)
        return self.wicfs_length(window, len(raw))

    def run_incremental(self, encoded: bytes) -> tuple[bytes, list[int]]:
        jim = (ctypes.c_uint8 * JIM_SIZE)()
        backend = self.fixture.pi1mhz_net_backend_create(b"fixture", None, 0)
        self.assertTrue(backend)

        def request(operation: int, generation: int = 0) -> tuple[int, int, int]:
            jim[CONTROL:CONTROL + 32] = bytes(32)
            jim[CONTROL] = 93
            jim[CONTROL + 1:CONTROL + 5] = b"IUEF"
            jim[CONTROL + 5] = 1
            jim[CONTROL + 6] = operation
            jim[CONTROL + 11:CONTROL + 15] = generation.to_bytes(4, "little")
            result = self.fixture.pi1mhz_net_backend_dispatch(
                backend, 0xFF, CONTROL, jim, JIM_SIZE
            )
            self.assertEqual(result, 0)
            self.assertEqual(bytes(jim[CONTROL + 1:CONTROL + 5]), b"IUEF")
            return (
                int.from_bytes(bytes(jim[CONTROL + 10:CONTROL + 14]), "little"),
                int.from_bytes(bytes(jim[CONTROL + 14:CONTROL + 16]), "little"),
                jim[CONTROL + 16],
            )

        try:
            request(1)
            upload_generation = 0
            for offset in range(0, len(encoded), 0xFF00):
                part = encoded[offset:offset + 0xFF00]
                jim[:len(part)] = part
                jim[0xFFFE] = len(part) & 0xFF
                jim[0xFFFF] = len(part) >> 8
                next_generation, retry_length, retry_final = request(
                    2, upload_generation
                )
                retry = request(2, upload_generation)
                self.assertEqual(
                    retry, (next_generation, retry_length, retry_final)
                )
                upload_generation = next_generation
            generation, length, final = request(3)
            output = bytearray(jim[PUBLISH_BASE:PUBLISH_BASE + length])
            lengths = [length]
            while not final:
                previous_generation = generation
                generation, length, final = request(5, generation)
                window = bytes(jim[PUBLISH_BASE:PUBLISH_BASE + length])
                # A retry carrying the previous generation must republish the
                # same window, never advance and silently skip UEF bytes.
                retry_generation, retry_length, retry_final = request(
                    5, previous_generation
                )
                self.assertEqual(
                    (retry_generation, retry_length, retry_final),
                    (generation, length, final),
                )
                self.assertEqual(
                    bytes(jim[PUBLISH_BASE:PUBLISH_BASE + retry_length]), window
                )
                output.extend(window)
                lengths.append(length)
            return bytes(output), lengths
        finally:
            self.fixture.pi1mhz_net_backend_destroy(backend)

    def test_incremental_exact_window_boundaries(self) -> None:
        for size, expected_windows in (
            (FLAT_WINDOW, [FLAT_WINDOW]),
            (2 * FLAT_WINDOW, [FLAT_WINDOW, FLAT_WINDOW]),
            (2 * FLAT_WINDOW + 1, [FLAT_WINDOW, FLAT_WINDOW, 1]),
        ):
            raw = (b"UEF File!\0\x05\0" + bytes(range(256)) * 600)[:size]
            with self.subTest(size=size):
                output, windows = self.run_incremental(raw)
                self.assertEqual(output, raw)
                self.assertEqual(windows, expected_windows)

    def test_incremental_final_append_retry_at_exact_capacity(self) -> None:
        jim = (ctypes.c_uint8 * JIM_SIZE)()
        backend = self.fixture.pi1mhz_net_backend_create(b"fixture", None, 0)
        self.assertTrue(backend)

        def request(operation: int, generation: int, length: int = 0) -> int:
            jim[CONTROL:CONTROL + 32] = bytes(32)
            jim[CONTROL] = 93
            jim[CONTROL + 1:CONTROL + 5] = b"IUEF"
            jim[CONTROL + 5] = 1
            jim[CONTROL + 6] = operation
            jim[CONTROL + 11:CONTROL + 15] = generation.to_bytes(4, "little")
            jim[0xFFFE] = length & 0xFF
            jim[0xFFFF] = length >> 8
            result = self.fixture.pi1mhz_net_backend_dispatch(
                backend, 0xFF, CONTROL, jim, JIM_SIZE
            )
            self.assertEqual(result, 0)
            return int.from_bytes(
                bytes(jim[CONTROL + 10:CONTROL + 14]), "little"
            )

        try:
            generation = request(1, 0)
            remaining = 16 * 1024 * 1024
            last_generation = 0
            last_length = 0
            while remaining:
                length = min(0xFF00, remaining)
                jim[:length] = bytes((generation & 0xFF,)) * length
                last_generation = generation
                last_length = length
                generation = request(2, generation, length)
                remaining -= length
            self.assertEqual(last_length, 256)
            self.assertEqual(generation, 258)
            # No capacity remains, but acknowledging the identical final
            # sequence must not require capacity or append it twice.
            self.assertEqual(
                request(2, last_generation, last_length), generation
            )
        finally:
            self.fixture.pi1mhz_net_backend_destroy(backend)

    def test_incremental_raw_gzip_zip_and_zip_gzip_over_64k(self) -> None:
        raw = b"UEF File!\0\x05\0" + bytes(range(256)) * 600
        containers = [raw, gzip.compress(raw)]
        for payload in (raw, gzip.compress(raw)):
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
                output.writestr("game.uef", payload)
            containers.append(archive.getvalue())
        for encoded in containers:
            with self.subTest(signature=encoded[:4]):
                pi_result, pi_output = self.run_normalize_large(encoded)
                self.assertIn(pi_result, (0, 1, 2))
                self.assertEqual(pi_output, raw)
                output, windows = self.run_incremental(encoded)
                self.assertEqual(output, raw)
                self.assertEqual(
                    windows,
                    [FLAT_WINDOW, FLAT_WINDOW, len(raw) - 2 * FLAT_WINDOW],
                )

    def test_republish_repairs_a_window_a_service_reply_trod_on(self) -> None:
        """A reply written over the window must be repairable in place.

        The host keeps its service reply buffer in the first bytes of JIM page
        0, which is exactly where a published stream window starts, so any
        command that copies a reply while a stream is open overwrites the start
        of the stream. WiCFS then reads the reply text as UEF: an "ERR" reply
        is read as chunk type &5245. Operation 7 lays the window down again
        without moving the cursor or the generation, so the host can carry on
        from where it was rather than restarting the file.
        """
        USABLE = 0x68
        jim = (ctypes.c_uint8 * JIM_SIZE)()
        backend = self.fixture.pi1mhz_net_backend_create(b"fixture", None, 0)
        self.assertTrue(backend)

        def request(operation: int, generation: int = 0) -> tuple[int, int, int]:
            jim[CONTROL:CONTROL + 32] = bytes(32)
            jim[CONTROL] = 93
            jim[CONTROL + 1:CONTROL + 5] = b"IUEF"
            jim[CONTROL + 5] = 1
            jim[CONTROL + 6] = operation
            jim[CONTROL + 11:CONTROL + 15] = generation.to_bytes(4, "little")
            result = self.fixture.pi1mhz_net_backend_dispatch(
                backend, 0xFF, CONTROL, jim, JIM_SIZE
            )
            self.assertEqual(result, 0, f"operation {operation}")
            return (
                int.from_bytes(bytes(jim[CONTROL + 10:CONTROL + 14]), "little"),
                int.from_bytes(bytes(jim[CONTROL + 14:CONTROL + 16]), "little"),
                jim[CONTROL + 16],
            )

        raw = b"UEF File!\x00\x05\x00" + bytes(range(256)) * 40
        try:
            request(1)
            jim[:len(raw)] = raw
            jim[0xFFFE] = len(raw) & 0xFF
            jim[0xFFFF] = len(raw) >> 8
            generation, _, _ = request(2, 0)
            generation, length, _ = request(3)
            expected = bytes(jim[0x100:0x100 + min(length, USABLE)])

            # A service reply lands in JIM page 0, exactly as the ROM's reply
            # buffer does. These are the bytes that produced &5245 on hardware.
            # The stream starts at page 1, so this must not disturb it at all.
            jim[0:5] = b"ERR\r\x00"
            self.assertEqual(bytes(jim[0x100:0x100 + min(length, USABLE)]),
                             expected,
                             "a reply in page 0 reached the published stream")

            # The republish is still the recovery path if a window is ever
            # damaged, so corrupt one in-stream byte and prove it comes back.
            jim[0x100] = 0xFF
            self.assertNotEqual(bytes(jim[0x100:0x105]), expected[:5])

            before = (generation, length)
            generation, length, _ = request(7)
            self.assertEqual((generation, length), before,
                             "republish must not move the cursor or the"
                             " generation; the host has consumed nothing")
            self.assertEqual(bytes(jim[0x100:0x100 + min(length, USABLE)]),
                             expected,
                             "republish did not restore the damaged window")
        finally:
            self.fixture.pi1mhz_net_backend_destroy(backend)

    def test_incremental_stream_survives_public_jim_reuse(self) -> None:
        jim = (ctypes.c_uint8 * JIM_SIZE)()
        backend = self.fixture.pi1mhz_net_backend_create(b"fixture", None, 0)
        self.assertTrue(backend)

        def request(operation: int, generation: int = 0) -> tuple[int, int, int]:
            jim[CONTROL:CONTROL + 32] = bytes(32)
            jim[CONTROL] = 93
            jim[CONTROL + 1:CONTROL + 5] = b"IUEF"
            jim[CONTROL + 5] = 1
            jim[CONTROL + 6] = operation
            jim[CONTROL + 11:CONTROL + 15] = generation.to_bytes(4, "little")
            result = self.fixture.pi1mhz_net_backend_dispatch(
                backend, 0xFF, CONTROL, jim, JIM_SIZE
            )
            self.assertEqual(result, 0)
            self.assertEqual(bytes(jim[CONTROL + 1:CONTROL + 5]), b"IUEF")
            generation = int.from_bytes(
                bytes(jim[CONTROL + 10:CONTROL + 14]), "little"
            )
            length = int.from_bytes(
                bytes(jim[CONTROL + 14:CONTROL + 16]), "little"
            )
            final = jim[CONTROL + 16]
            return generation, length, final

        raw = b"UEF File!\0\x05\0" + bytes(range(256)) * 600
        try:
            request(1)  # BEGIN
            upload_generation = 0
            for offset in range(0, len(raw), 0xFF00):
                part = raw[offset:offset + 0xFF00]
                jim[:len(part)] = part
                jim[0xFFFE] = len(part) & 0xFF
                jim[0xFFFF] = len(part) >> 8
                upload_generation, _, _ = request(2, upload_generation)
            _, first_length, first_final = request(3)  # FINALIZE
            self.assertEqual(first_length, FLAT_WINDOW)
            self.assertEqual(first_final, 0)
            self.assertEqual(
                bytes(jim[PUBLISH_BASE:PUBLISH_BASE + first_length]),
                raw[:first_length],
            )

            rewind_generation, first_length, first_final = request(4)  # REWIND
            self.assertEqual((first_length, first_final), (FLAT_WINDOW, 0))
            self.assertEqual(
                bytes(jim[PUBLISH_BASE:PUBLISH_BASE + first_length]),
                raw[:first_length],
            )

            jim[PUBLISH_BASE:PUBLISH_BASE + FLAT_WINDOW] = (
                bytes([0xA5]) * FLAT_WINDOW
            )
            generation, second_length, second_final = request(
                5, rewind_generation
            )  # REFILL
            self.assertEqual(second_length, FLAT_WINDOW)
            self.assertEqual(second_final, 0)
            self.assertEqual(
                bytes(jim[PUBLISH_BASE:PUBLISH_BASE + second_length]),
                raw[FLAT_WINDOW:2 * FLAT_WINDOW],
            )
            _, last_length, last_final = request(5, generation)
            self.assertEqual(last_final, 1)
            self.assertEqual(
                bytes(jim[PUBLISH_BASE:PUBLISH_BASE + last_length]),
                raw[2 * FLAT_WINDOW:],
            )
        finally:
            self.fixture.pi1mhz_net_backend_destroy(backend)

    @staticmethod
    def chunk(chunk_type: int, payload: bytes) -> bytes:
        return struct.pack("<HI", chunk_type, len(payload)) + payload

    def test_terminal_timing_chunks_do_not_extend_the_wicfs_stream(self) -> None:
        header = b"UEF File!\0\x05\0"
        data = self.chunk(0x0100, b"cassette block")
        trailing = self.chunk(0x0110, b"\x58\x02") + self.chunk(0x0112, b"\x58\x02")
        raw = header + data + trailing
        expected = len(header + data)
        self.assertEqual(self.effective_length(raw), expected)
        fixture_format, fixture = self.run_fixture_normalize(raw)
        self.assertEqual(fixture_format, "RAW")
        self.assertEqual(fixture, raw)
        trimmed_format, trimmed = self.run_fixture_normalize(
            raw, trim_tail=True,
        )
        self.assertEqual(trimmed_format, "RAW")
        self.assertEqual(trimmed, raw[:expected])

    def test_wicfs_length_keeps_later_data_and_malformed_streams(self) -> None:
        header = b"UEF File!\0\x05\0"
        first = self.chunk(0x0100, b"one")
        gap = self.chunk(0x0112, b"\x01\0")
        second = self.chunk(0x0100, b"two")
        complete = header + first + gap + second
        self.assertEqual(self.effective_length(complete), len(complete))
        malformed = header + b"\x00\x01\xff\xff\xff\x7f"
        self.assertEqual(self.effective_length(malformed), len(malformed))

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
                    sample.read_bytes(), trim_tail=True,
                )
                self.assertEqual(fixture_result, result_names[pi_result])
                self.assertEqual(
                    fixture_bytes, pi_bytes[:self.effective_length(pi_bytes)]
                )


if __name__ == "__main__":
    unittest.main()
