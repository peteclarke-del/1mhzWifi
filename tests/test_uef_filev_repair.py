import ctypes
import importlib.util
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "pi-side/pi1mhz/overlay/src"
SPEC = importlib.util.spec_from_file_location(
    "uef_map", ROOT / "scripts/uef_map.py"
)
UEF_MAP = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(UEF_MAP)


class UefFilevRepairTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory()
        library = Path(cls._temporary.name) / "libmedia_catalogue.so"
        subprocess.run(
            ["cc", "-std=c11", "-shared", "-fPIC", "-O2", "-I", str(SOURCE),
             str(SOURCE / "media_catalogue.c"),
             "-o", str(library)],
            check=True,
        )
        decoder = ctypes.CDLL(str(library))
        cls.repair = decoder.uef_repair_filev_stamp
        cls.repair.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t]
        cls.repair.restype = ctypes.c_uint
        # The windowed form. The Pi streams a tape to the Beeb rather than
        # holding it, so it repairs a window at a time and needs to know
        # where the last complete chunk ended.
        cls.repair_span = decoder.uef_repair_filev_span
        cls.repair_span.argtypes = [
            ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t, ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_uint),
        ]
        cls.repair_span.restype = ctypes.c_size_t

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    @staticmethod
    def block(name: bytes, number: int, data: bytes, last: bool) -> bytes:
        descriptor = struct.pack(
            "<IIHHBI", 0x1900, 0x8023, number, len(data), 0x80 if last else 0, 0
        )
        header = name + b"\0" + descriptor
        payload = (b"*" + header +
                   UEF_MAP.tape_crc(header).to_bytes(2, "big") + data)
        if data:
            payload += UEF_MAP.tape_crc(data).to_bytes(2, "big")
        return payload

    def uef(self, blocks: list[bytes]) -> bytes:
        raw = b"UEF File!\0" + bytes([0, 10])
        for payload in blocks:
            raw += struct.pack("<HI", 0x0100, len(payload)) + payload
        return raw

    def run_repair(self, raw: bytes) -> tuple[bytes, int]:
        buffer = (ctypes.c_uint8 * len(raw)).from_buffer_copy(raw)
        count = self.repair(buffer, len(raw))
        return bytes(buffer), count

    def crcs_valid(self, raw: bytes) -> bool:
        position, index = 12, 0
        while position + 6 <= len(raw):
            chunk, length = struct.unpack_from("<HI", raw, position)
            start, end = position + 6, position + 6 + length
            if end > len(raw):
                return False
            if chunk == 0x0100:
                block = UEF_MAP.inspect_cfs_block(raw[start:end], index, position)
                if block is not None and not (block["header_crc_ok"]
                                              and block["data_crc_ok"]):
                    return False
                index += 1
            position = end
        return True

    def test_redirects_the_published_stamp_and_fixes_the_crc(self):
        loader = b"\r\x00\x1e A%=163:CALL&FFF4:?&212=&D6:?&213=&F1\r\xff"
        raw = self.uef([self.block(b"EXILE", 0, loader, True)])
        repaired, count = self.run_repair(raw)
        self.assertEqual(count, 2)
        self.assertIn(b"?&900=&D6:?&901=&F1", repaired)
        self.assertNotIn(b"?&212", repaired)
        self.assertEqual(len(repaired), len(raw))
        self.assertTrue(self.crcs_valid(repaired))

    def test_redirects_the_thirty_two_bit_indirection_form(self):
        raw = self.uef([self.block(b"L", 0, b"\r\x00\x0c !&212=&F1D6\r\xff", True)])
        repaired, count = self.run_repair(raw)
        self.assertEqual(count, 1)
        self.assertIn(b"!&900=&F1D6", repaired)
        self.assertTrue(self.crcs_valid(repaired))

    def test_leaves_a_longer_address_beginning_with_the_same_digits(self):
        # Blast! pokes &2110, &2127, &213C and &21F0. None is FILEV, and
        # rewriting three digits of a four-digit address would corrupt it.
        body = b"\r\x00\x2a ?&2110=?&81:?&213C=?&83:?&21F0=?&84\r\xff"
        raw = self.uef([self.block(b"BLAST", 0, body, True)])
        repaired, count = self.run_repair(raw)
        self.assertEqual(count, 0)
        self.assertEqual(repaired, raw)

    def test_ignores_an_address_which_is_not_an_indirection_target(self):
        raw = self.uef([self.block(b"L", 0, b"\r\x00\x0a X%=&212\r\xff", True)])
        repaired, count = self.run_repair(raw)
        self.assertEqual(count, 0)
        self.assertEqual(repaired, raw)

    def test_repairs_a_stamp_in_a_later_block_of_a_multi_block_file(self):
        first = self.block(b"BIG", 0, b"A" * 256, False)
        second = self.block(b"BIG", 1, b"?&212=&D6:?&213=&F1" + b"B" * 40, True)
        raw = self.uef([first, second])
        repaired, count = self.run_repair(raw)
        self.assertEqual(count, 2)
        self.assertTrue(self.crcs_valid(repaired))
        # The untouched block must keep its original bytes and CRC exactly.
        self.assertIn(b"A" * 256, repaired)

    def test_tolerates_a_zero_length_catalogue_marker(self):
        raw = self.uef([
            self.block(b"MARK", 0, b"", True),
            self.block(b"L", 0, b"\r\x00\x0e ?&212=&D6\r\xff", True),
        ])
        repaired, count = self.run_repair(raw)
        self.assertEqual(count, 1)
        self.assertTrue(self.crcs_valid(repaired))

    def test_leaves_a_uef_without_the_idiom_byte_for_byte_identical(self):
        raw = self.uef([self.block(b"CLEAN", 0, b"\r\x00\x0c MODE6\r\xff", True)])
        repaired, count = self.run_repair(raw)
        self.assertEqual(count, 0)
        self.assertEqual(repaired, raw)

    def test_ignores_a_truncated_trailing_chunk_rather_than_reading_past_it(self):
        raw = self.uef([self.block(b"L", 0, b"\r\x00\x0e ?&212=&D6\r\xff", True)])
        truncated = raw + struct.pack("<HI", 0x0100, 999) + b"*short"
        repaired, count = self.run_repair(truncated)
        self.assertEqual(count, 1)
        self.assertEqual(len(repaired), len(truncated))

    def run_span(self, raw: bytes, start: int) -> tuple[bytes, int, int]:
        buffer = (ctypes.c_uint8 * len(raw)).from_buffer_copy(raw)
        count = ctypes.c_uint(0)
        framed = self.repair_span(buffer, len(raw), start, ctypes.byref(count))
        return bytes(buffer), framed, count.value

    def test_the_windowed_form_matches_the_whole_image_form(self):
        raw = self.uef([
            self.block(b"L", 0, b"\r\x00\x0e ?&212=&D6\r\xff", False),
            self.block(b"L", 1, b"\r\x00\x0e !&213=&F1\r\xff", True),
        ])
        whole, whole_count = self.run_repair(raw)
        span, framed, span_count = self.run_span(raw, 12)
        self.assertEqual(span, whole)
        self.assertEqual(span_count, whole_count)
        self.assertEqual(framed, len(raw))

    def test_the_windowed_form_stops_at_the_last_complete_chunk(self):
        """A caller feeding it a stream has to hold the remainder back.

        The repair rewrites a block's payload and then the payload CRC that
        follows it, so a block split across two windows cannot be repaired
        from either half alone. Reporting where the last complete chunk ended
        is what lets the caller carry the rest into the next window.
        """
        raw = self.uef([self.block(b"L", 0, b"\r\x00\x0e ?&212=&D6\r\xff", True)])
        for cut in range(13, len(raw)):
            with self.subTest(cut=cut):
                _, framed, count = self.run_span(raw[:cut], 12)
                # Nothing past the truncation is ever framed, and the one
                # incomplete chunk is left for the next window rather than
                # being half repaired.
                self.assertLessEqual(framed, cut)
                self.assertEqual(framed, 12)
                self.assertEqual(count, 0)
        # The whole chunk present: framed to its end, and repaired.
        _, framed, count = self.run_span(raw, 12)
        self.assertEqual(framed, len(raw))
        self.assertEqual(count, 1)

    def test_the_windowed_form_starts_where_it_is_told(self):
        # Every window after the first begins on a chunk boundary, so the
        # walk starts at 0 rather than past the twelve byte file header.
        raw = self.uef([self.block(b"L", 0, b"\r\x00\x0e ?&212=&D6\r\xff", True)])
        body = raw[12:]
        repaired, framed, count = self.run_span(body, 0)
        self.assertEqual(framed, len(body))
        self.assertEqual(count, 1)
        self.assertNotIn(b"?&212", repaired)
        self.assertIn(b"?&900", repaired)


if __name__ == "__main__":
    unittest.main()
