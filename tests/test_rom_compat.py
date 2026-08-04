import hashlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROM_PATH = ROOT / "build" / "elkwifi_pi1mhz.rom"
ROM_SHA256 = "328a5d1191e59e5d147328ba4cbe480febbe76964d44ad29e826ec0381501601"


class RomCompatibilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM_PATH.read_bytes()

    def test_rom_identity_and_stock_header(self) -> None:
        self.assertEqual(len(self.rom), 16 * 1024)
        self.assertEqual(hashlib.sha256(self.rom).hexdigest(), ROM_SHA256)
        self.assertEqual(
            self.rom[:9], bytes((0, 0, 0, 0x4C, 0x35, 0x80, 0x82, 0x1B, 0))
        )
        self.assertEqual(self.rom[9:23], b"Electron Wifi\0")
        self.assertEqual(self.rom[23:28], b"0.23\0")

    def test_menu_catalogue_selector_is_present(self) -> None:
        helper = bytes.fromhex("A9 01 8D FE FC B9 00 FD 60")
        self.assertEqual(self.rom.count(helper), 1)
        self.assertEqual(self.rom.count(bytes.fromhex("A9 8C A2 00 A0 00 20 F4 FF")), 1)

    def test_wicfs_patches_the_copied_rom_switcher(self) -> None:
        self.assertEqual(self.rom.count(bytes.fromhex("A5 F4 8D C2 07")), 1)
        self.assertEqual(self.rom.count(bytes.fromhex("A9 00 85 F4 8D 05 FE")), 1)
        length_read = bytes.fromhex(
            "A9 FF 8D FF FC 20 FC 87 AD FE FD 85 F8 AD FF FD 85 F9"
        )
        self.assertEqual(self.rom.count(length_read), 1)
        self.assertNotIn(bytes.fromhex("AD FE FD 85 F8 20 FC 87"), self.rom)

    def test_stock_commands_additive_menusrc_and_osword_are_present(self) -> None:
        for command in (
            b"WGET", b"MENU", b"MENUSRC", b"WIFI", b"VERSION", b"LAPOPT",
            b"LAP", b"IFCFG", b"DATE", b"TIME", b"PRD", b"JOIN", b"LEAVE",
            b"PING", b"MODE", b"DISCONNECT", b"WICFS", b"REWIND", b"QUPCFS",
        ):
            self.assertIn(command, self.rom)
        for removed in (b"PRINTER", b"UPDATE", b"SETSERIAL", b"CRC error"):
            self.assertNotIn(removed, self.rom)
        self.assertIn(bytes((0xA5, 0xEF, 0xC9, 0x65)), self.rom)

    def test_services_use_ap5_fred_window_from_io_processor(self) -> None:
        self.assertIn(bytes((0x8D, 0xA6, 0xFC)), self.rom)  # STA &FCA6
        self.assertIn(bytes((0xAD, 0xAA, 0xFC)), self.rom)  # LDA &FCAA
        self.assertIn(b"Pi1MHz ElkWiFi service not responding", self.rom)
        self.assertNotIn(b"ACORNELECTRON.NL/uefarchive/MENU", self.rom)

    def test_join_uses_the_long_async_service_timeout(self) -> None:
        source = (ROOT / "rom-side/elkwifi-0.23/service_driver.asm").read_text()
        self.assertIn("cmp #drv_svc_join", source)

    def test_startup_does_not_probe_legacy_uart_or_reset_pi_service(self) -> None:
        # The original power-on path loaded reset function 1 from X and called
        # wifidriver.  The Pi1MHz build must start even when no kernel responds.
        self.assertNotIn(bytes((0x8A, 0x20, 0x5C, 0x82)), self.rom)
        # Pi1MHz reports WiFi enabled locally; startup must not read UART MCR
        # (&FC34), which AP5/PiTubeDirect does not forward as an ElkWiFi UART.
        self.assertIn(bytes((0xA9, 0x00, 0x29, 0x01, 0x60)), self.rom)

    def test_native_tcp_and_url_transports_are_present(self) -> None:
        self.assertIn(b"CONNECT\r\n\r\nOK", self.rom)
        self.assertIn(b"Network timeout", self.rom)
        self.assertIn(b"Network error &", self.rom)
        self.assertNotIn(b"www.acornelectron.nl", self.rom)


if __name__ == "__main__":
    unittest.main()
