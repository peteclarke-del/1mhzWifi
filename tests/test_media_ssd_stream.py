"""media_ssd_to_uef renders a DFS image as a cassette stream WiCFS can read.

*SSD LOAD adds no host filing code: the Pi presents the disc as the stream the
ROM already consumes. What has to hold is that the rendering is a valid UEF,
that every catalogue entry survives it, and that the two constraints WiCFS
imposes are met - !BOOT first, because that is what the command execs, and the
catalogue repeated, because WiCFS searches forward and never rewinds on a miss.
"""

import ctypes
import importlib.util
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "pi-side/pi1mhz-516a267/overlay/src"
SPEC = importlib.util.spec_from_file_location(
    "uef_loader_scan", ROOT / "scripts/uef_loader_scan.py"
)
SCAN = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(SCAN)
UEF_MAP = SCAN.uef_map

MEDIA_OK = 0


def ssd(entries):
    """A DFS image whose files hold recognisable data."""
    names = bytearray(256)
    meta = bytearray(256)
    names[0:8] = b"TESTDISC"
    meta[5] = len(entries) * 8
    meta[6] = 0x30            # *OPT 4,3, the EXEC boot every real disc uses
    data = bytearray()
    sector = 2
    payloads = {}
    for index, (name, load, length) in enumerate(entries):
        at = 8 + index * 8
        names[at:at + 7] = name.encode().ljust(7)[:7]
        names[at + 7] = ord("$")
        meta[at + 0] = load & 0xFF
        meta[at + 1] = (load >> 8) & 0xFF
        meta[at + 4] = length & 0xFF
        meta[at + 5] = (length >> 8) & 0xFF
        meta[at + 6] = ((length >> 16) & 3) << 4
        meta[at + 7] = sector
        payload = bytes(((index + 1) * 7 + i) & 0xFF for i in range(length))
        payloads[name] = payload
        sectors = max(1, (length + 255) // 256)
        block = bytearray(sectors * 256)
        block[0:length] = payload
        # Files are laid out from sector 2 in catalogue order.
        assert len(data) == (sector - 2) * 256
        data.extend(block)
        sector += sectors
    # The declared sector count has to match the image, or the decoder treats
    # it as malformed rather than as a disc.
    total_sectors = 2 + len(data) // 256
    meta[6] = (meta[6] & 0xFC) | ((total_sectors >> 8) & 3)
    meta[7] = total_sectors & 0xFF
    return bytes(names + meta + data), payloads


class MediaSsdStreamTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory()
        library = Path(cls._temporary.name) / "libmedia.so"
        subprocess.run(
            ["cc", "-std=c11", "-shared", "-fPIC", "-O2", "-Wall", "-Wextra",
             "-Werror", "-I", str(OVERLAY),
             str(OVERLAY / "media_catalogue.c"), "-o", str(library)],
            check=True, capture_output=True,
        )
        cls.lib = ctypes.CDLL(str(library))
        cls.lib.media_ssd_to_uef.argtypes = [
            ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t, ctypes.c_uint,
            ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_size_t),
        ]
        cls.lib.media_ssd_to_uef.restype = ctypes.c_int

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def convert(self, image: bytes, passes: int = 2):
        buffer = (ctypes.c_uint8 * len(image)).from_buffer_copy(image)
        needed = ctypes.c_size_t(0)
        status = self.lib.media_ssd_to_uef(buffer, len(image), passes, None, 0,
                                           ctypes.byref(needed))
        self.assertEqual(status, MEDIA_OK)
        out = (ctypes.c_uint8 * needed.value)()
        produced = ctypes.c_size_t(0)
        status = self.lib.media_ssd_to_uef(buffer, len(image), passes, out,
                                           needed.value,
                                           ctypes.byref(produced))
        self.assertEqual(status, MEDIA_OK)
        self.assertEqual(produced.value, needed.value)
        return bytes(out)[:produced.value]

    def files(self, stream: bytes):
        with tempfile.NamedTemporaryFile(suffix=".uef") as handle:
            handle.write(stream)
            handle.flush()
            path = Path(handle.name)
            report = UEF_MAP.inspect_uef(path)
            return report, SCAN.cassette_files(path)

    def test_renders_a_valid_uef_with_every_block_crc_correct(self):
        image, _ = ssd([("GAME", 0x1900, 300), ("!BOOT", 0x0000, 16)])
        report, _ = self.files(self.convert(image))
        blocks = report["cfs_blocks"]
        self.assertTrue(blocks)
        for block in blocks:
            self.assertTrue(block["header_crc_ok"], block["name"])
            self.assertTrue(block["data_crc_ok"], block["name"])

    def test_emits_boot_first_because_the_command_execs_it(self):
        image, _ = ssd([("GAME", 0x1900, 40), ("MENU", 0x1900, 40),
                        ("!BOOT", 0x0000, 16)])
        _, files = self.files(self.convert(image, passes=1))
        self.assertEqual(files[0]["name"], "!BOOT")

    def test_repeats_the_catalogue_so_a_backward_chain_still_resolves(self):
        # WiCFS searches forward and does not rewind when a name is not found.
        # !BOOT is emitted first, so a chain to a file behind it would fail on
        # a single pass; the file has to reappear ahead of the cursor.
        image, _ = ssd([("EARLY", 0x1900, 40), ("!BOOT", 0x0000, 16)])
        _, files = self.files(self.convert(image, passes=2))
        names = [entry["name"] for entry in files]
        self.assertEqual(names.count("EARLY"), 2)
        self.assertGreater(names.index("EARLY"), names.index("!BOOT"))

    def test_file_contents_survive_the_rendering(self):
        image, payloads = ssd([("!BOOT", 0x0000, 12), ("DATA", 0x0E00, 700)])
        _, files = self.files(self.convert(image, passes=1))
        recovered = {entry["name"]: bytes(entry["data"]) for entry in files}
        for name, payload in payloads.items():
            self.assertEqual(recovered[name], payload, name)

    def test_load_and_execution_addresses_survive(self):
        image, _ = ssd([("!BOOT", 0x0000, 8), ("CODE", 0x1234, 20)])
        _, files = self.files(self.convert(image, passes=1))
        code = next(entry for entry in files if entry["name"] == "CODE")
        self.assertEqual(code["load_address"] & 0xFFFF, 0x1234)

    def test_a_disc_without_a_boot_still_renders_every_file(self):
        image, _ = ssd([("ONE", 0x1900, 30), ("TWO", 0x1900, 30)])
        _, files = self.files(self.convert(image, passes=1))
        self.assertEqual([entry["name"] for entry in files], ["ONE", "TWO"])

    def test_measuring_pass_matches_the_written_length(self):
        image, _ = ssd([("!BOOT", 0x0000, 10), ("BIG", 0x0E00, 1000)])
        stream = self.convert(image, passes=3)
        self.assertGreater(len(stream), 3000)

    def test_rejects_a_zero_pass_request(self):
        image, _ = ssd([("!BOOT", 0x0000, 10)])
        buffer = (ctypes.c_uint8 * len(image)).from_buffer_copy(image)
        produced = ctypes.c_size_t(0)
        status = self.lib.media_ssd_to_uef(buffer, len(image), 0, None, 0,
                                           ctypes.byref(produced))
        self.assertNotEqual(status, MEDIA_OK)

    def test_a_truncated_image_is_refused_rather_than_half_rendered(self):
        # The decoder treats a catalogue declaring more sectors than the image
        # holds as malformed, which is the safe answer: better a clean refusal
        # than a stream built from whatever followed the buffer.
        image, _ = ssd([("!BOOT", 0x0000, 10), ("BIG", 0x0E00, 2000)])
        buffer = (ctypes.c_uint8 * len(image[:600])).from_buffer_copy(image[:600])
        produced = ctypes.c_size_t(0)
        status = self.lib.media_ssd_to_uef(buffer, 600, 1, None, 0,
                                           ctypes.byref(produced))
        self.assertNotEqual(status, MEDIA_OK)

    def test_truncations_never_read_outside_the_image(self):
        # Every container is untrusted input. Rebuild under AddressSanitizer
        # and sweep truncations, so a read past the buffer fails the test
        # rather than silently returning plausible bytes.
        image, _ = ssd([("!BOOT", 0x0000, 10), ("MID", 0x1900, 400),
                        ("BIG", 0x0E00, 2000)])
        with tempfile.TemporaryDirectory() as directory:
            harness = Path(directory) / "sweep.c"
            harness.write_text(
                "#include \"media_catalogue.h\"\n"
                "#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n"
                "int main(int argc, char **argv){\n"
                "  FILE *f = fopen(argv[1], \"rb\");\n"
                "  static unsigned char image[65536];\n"
                "  size_t n = fread(image, 1, sizeof image, f);\n"
                "  fclose(f);\n"
                "  for (size_t cut = 1; cut <= n; cut++) {\n"
                "    unsigned char *copy = malloc(cut);\n"
                "    memcpy(copy, image, cut);\n"
                "    size_t need = 0;\n"
                "    media_ssd_to_uef(copy, cut, 2, NULL, 0, &need);\n"
                "    if (need != 0 && need < (1u << 22)) {\n"
                "      unsigned char *out = malloc(need);\n"
                "      size_t got = 0;\n"
                "      media_ssd_to_uef(copy, cut, 2, out, need, &got);\n"
                "      free(out);\n"
                "    }\n"
                "    free(copy);\n"
                "  }\n"
                "  printf(\"swept\\n\");\n"
                "  return 0;\n"
                "}\n"
            )
            binary = Path(directory) / "sweep"
            sample = Path(directory) / "disc.ssd"
            sample.write_bytes(image)
            build = subprocess.run(
                ["cc", "-std=c11", "-g", "-fsanitize=address,undefined",
                 "-fno-sanitize-recover=all", "-I", str(OVERLAY),
                 str(harness), str(OVERLAY / "media_catalogue.c"),
                 "-o", str(binary)],
                capture_output=True, text=True,
            )
            if build.returncode != 0:
                self.skipTest("AddressSanitizer unavailable: " + build.stderr)
            run = subprocess.run([str(binary), str(sample)],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("swept", run.stdout)


if __name__ == "__main__":
    unittest.main()
