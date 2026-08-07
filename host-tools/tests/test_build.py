import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"


def catalogue(image: bytes):
    count = image[0x105] // 8
    entries = {}
    for index in range(count):
        name_at = 8 + index * 8
        meta_at = 0x108 + index * 8
        name = image[name_at:name_at + 7].decode("ascii").rstrip().upper()
        meta = image[meta_at:meta_at + 8]
        load = meta[0] | (meta[1] << 8) | (((meta[6] >> 2) & 3) << 16)
        execute = meta[2] | (meta[3] << 8) | (((meta[6] >> 6) & 3) << 16)
        length = meta[4] | (meta[5] << 8) | (((meta[6] >> 4) & 3) << 16)
        start_sector = meta[7] | ((meta[6] & 3) << 8)
        entries[name] = (load, execute, length, start_sector)
    return entries


def dfs_file(image: bytes, name: str) -> bytes:
    """Return a file's exact payload from a single-sided DFS image."""
    _, _, length, start_sector = catalogue(image)[name.upper()]
    start = start_sector * 256
    return image[start:start + length]


class BuildTests(unittest.TestCase):
    def test_ssd_shape_and_catalogue(self):
        image = (BUILD / "nettools.ssd").read_bytes()
        self.assertEqual(len(image), 204800)
        entries = catalogue(image)
        self.assertEqual(set(entries), {
            "!BOOT", "NETMENU", "TERM", "SSH", "PING", "NSLOOK", "FTP",
            "HGET", "VIEWDAT"
        })

    def test_executables_are_tagged_for_io_processor(self):
        entries = catalogue((BUILD / "nettools.ssd").read_bytes())
        for name in ("NETMENU", "TERM", "SSH", "PING", "NSLOOK", "FTP",
                     "HGET", "VIEWDAT"):
            load, execute, _, _ = entries[name]
            self.assertEqual(load, 0x31900, name)
            self.assertEqual(execute, 0x31900, name)

    def test_programs_fit_stock_electron_mode4_envelope(self):
        for name in ("NETMENU", "TERM", "SSH", "PING", "NSLOOK", "FTP",
                     "HGET", "VIEWDAT"):
            size = (BUILD / name).stat().st_size
            self.assertLessEqual(size, 0x5800 - 0x1900, name)

    def test_expected_protocol_markers_are_present(self):
        image = (BUILD / "nettools.ssd").read_bytes()
        term = dfs_file(image, "TERM")
        ssh = dfs_file(image, "SSH")
        self.assertIn(b"TELNET://", term)
        self.assertIn(b"Ctrl-] disconnects", term)
        self.assertIn(b"Usage: *SSH user@host", ssh)
        self.assertIn(b"Unknown host key", ssh)
        self.assertIn(b"Password: ", ssh)
        self.assertIn(b"Authenticating with password", ssh)

    def test_ssd_contains_the_assembled_programs_byte_for_byte(self):
        image = (BUILD / "nettools.ssd").read_bytes()
        for name in ("NETMENU", "TERM", "SSH", "PING", "NSLOOK", "FTP",
                     "HGET", "VIEWDAT"):
            self.assertEqual(dfs_file(image, name), (BUILD / name).read_bytes())


if __name__ == "__main__":
    unittest.main()
