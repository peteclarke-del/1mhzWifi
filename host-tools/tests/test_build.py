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
        self.assertEqual(
            set(entries),
            {
                "!BOOT", "NETMENU", "TELNET", "SSH", "PING", "NSLOOK", "HWDTEST",
                "NTMENU", "NTTEL", "NTSSH", "NTPING", "NTNSLK", "NTHWD",
            },
        )

    def test_executables_are_tagged_for_io_processor(self):
        entries = catalogue((BUILD / "nettools.ssd").read_bytes())
        for name in ("NETMENU", "TELNET", "SSH", "PING", "NSLOOK", "HWDTEST"):
            load, execute, _, _ = entries[name]
            self.assertEqual(load, 0x32000, name)
            self.assertEqual(execute, 0x32000, name)
        for name in ("NTMENU", "NTTEL", "NTSSH", "NTPING", "NTNSLK", "NTHWD"):
            load, execute, _, _ = entries[name]
            self.assertEqual(load, 0x32200, name)
            self.assertEqual(execute, 0x32200, name)

    def test_public_loaders_select_mode_before_nested_host_run(self):
        image = (BUILD / "nettools.ssd").read_bytes()
        targets = {
            "NETMENU": b"NTMENU ", "TELNET": b"NTTEL ", "SSH": b"NTSSH ",
            "PING": b"NTPING ", "NSLOOK": b"NTNSLK ", "HWDTEST": b"NTHWD ",
        }
        for public, target in targets.items():
            loader = dfs_file(image, public)
            self.assertLessEqual(len(loader), 0x200, public)
            self.assertIn(target, loader, public)
            self.assertIn(b"requires OSHWM <= &2000", loader, public)
            self.assertIn(bytes.fromhex("A9 16 20 EE FF A9 04 20 EE FF"), loader, public)

    def test_programs_fit_stock_electron_mode4_envelope(self):
        for name in ("NETMENU", "TELNET", "SSH", "PING", "NSLOOK", "HWDTEST"):
            size = (BUILD / name).stat().st_size
            self.assertLessEqual(size, 0x5800 - 0x2200, name)

    def test_expected_protocol_markers_are_present(self):
        image = (BUILD / "nettools.ssd").read_bytes()
        telnet = dfs_file(image, "NTTEL")
        ssh = dfs_file(image, "NTSSH")
        self.assertIn(b"TELNET://", telnet)
        self.assertIn(b"Ctrl-] disconnects", telnet)
        self.assertIn(b"Usage: *SSH user@host", ssh)
        self.assertIn(b"Unknown host key", ssh)
        self.assertIn(b"Password: ", ssh)
        self.assertIn(b"Authenticating with password", ssh)
        self.assertIn(b"SSH 0.1.54 error &", ssh)
        self.assertIn(b"Usage: *PING host", dfs_file(image, "NTPING"))
        self.assertIn(b"Usage: *NSLOOK host", dfs_file(image, "NTNSLK"))
        nslook = dfs_file(image, "NTNSLK")
        self.assertIn(b"Address: ", nslook)
        self.assertIn(b"NetTools 0.1.54 network error &", nslook)
        hwdtest = dfs_file(image, "NTHWD")
        self.assertIn(b"1MHzWifi HWDTEST D2", hwdtest)
        self.assertIn(b"Loader OSHWM=&", hwdtest)
        self.assertIn(b"HIMEM=&", hwdtest)
        self.assertIn(b"Before OSBYTE &82", hwdtest)
        self.assertIn(b"After OSBYTE &82 high=&", hwdtest)
        self.assertIn(b"Before OSBYTE &81", hwdtest)
        self.assertIn(b"After OSBYTE &81 X=&", hwdtest)
        self.assertIn(b"FCA9 req 00 F0 FF <= 5E", hwdtest)
        self.assertIn(b"FCA6-9 after", hwdtest)
        self.assertIn(b"Addressed JIM block", hwdtest)
        self.assertIn(b"Secure CAPS result", hwdtest)
        self.assertIn(b"CAPS 1-5", hwdtest)
        self.assertIn(b"CAPS 6-10", hwdtest)
        self.assertIn(b"HWDTEST RESULT ", hwdtest)
        self.assertIn(b"PASS\r\x00", hwdtest)
        self.assertIn(b"FAIL\r\x00", hwdtest)

    def test_transient_tools_return_through_oscli(self):
        image = (BUILD / "nettools.ssd").read_bytes()
        # Re-entering a language with OSBYTE &8E from an active OSCLI frame can
        # turn an ordinary tool error into BASIC's `Bad program` diagnostic.
        bad_sequence = bytes.fromhex("A9 8E 4C F4 FF")
        for name in (
            "NETMENU", "TELNET", "SSH", "PING", "NSLOOK", "HWDTEST",
            "NTMENU", "NTTEL", "NTSSH", "NTPING", "NTNSLK", "NTHWD",
        ):
            self.assertNotIn(bad_sequence, dfs_file(image, name), name)
        application = (ROOT / "src/common/application.asm").read_text()
        exit_block = application.split(".application_exit", 1)[1]
        self.assertNotIn("OSBYTE", exit_block)
        self.assertNotIn("STA ", exit_block)
        self.assertIn("RTS", exit_block)

    def test_transient_tools_validate_runtime_memory_envelope(self):
        application = (ROOT / "src/common/application.asm").read_text()
        self.assertIn("LDA #&83", application)
        self.assertIn("LDA #&84", application)
        self.assertIn("LDA #&EA", application)
        self.assertIn("LDA LOADER_COOKIE", application)
        self.assertIn("CPY #HI(APP_START)", application)
        self.assertIn("CPY #HI(end)", application)
        for source in ("netmenu.asm", "telnet.asm", "ssh.asm", "ping.asm", "nslook.asm", "hwdtest.asm"):
            text = (ROOT / "src" / source).read_text()
            entry = text.split(".start", 1)[1].split("\n", 6)[:6]
            self.assertIn("JSR application_check_workspace", "\n".join(entry), source)

    def test_bus_settle_has_no_mailbox_or_jim_access(self):
        source = (ROOT / "src/common/pi1mhz_net.asm").read_text()
        settle = source.split(".net_bus_settle\n", 1)[1].split("\n.net_copy_rx_to_host", 1)[0]
        for forbidden in ("SERVICE_", "&FCA", "&FCF", "&FD"):
            self.assertNotIn(forbidden, settle)
        self.assertIn("NOP", settle)
        self.assertIn("DEX", settle)

    def test_ssd_contains_the_assembled_programs_byte_for_byte(self):
        image = (BUILD / "nettools.ssd").read_bytes()
        files = {
            "NETMENU": "NETMENUL", "TELNET": "TELNETL", "SSH": "SSHL",
            "PING": "PINGL", "NSLOOK": "NSLOOKL", "HWDTEST": "HWDTESTL",
            "NTMENU": "NETMENU", "NTTEL": "TELNET", "NTSSH": "SSH",
            "NTPING": "PING", "NTNSLK": "NSLOOK", "NTHWD": "HWDTEST",
        }
        for disc_name, build_name in files.items():
            self.assertEqual(
                dfs_file(image, disc_name), (BUILD / build_name).read_bytes(),
                disc_name,
            )


if __name__ == "__main__":
    unittest.main()
