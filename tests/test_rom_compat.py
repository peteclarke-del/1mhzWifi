import hashlib
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROM_PATH = ROOT / "build" / "elkwifi_pi1mhz.rom"
ROM_SHA256 = "dfed22515912be896a2e446d95c5f01d94b0ba0708eede4a6b09a56bdc34bca6"


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
        self.assertIn(b"TAPE\r", self.rom)
        self.assertNotIn(bytes.fromhex("A9 8C A2 00 A0 00 20 F4 FF"), self.rom)

    def test_wicfs_uses_mos_vectors_and_the_tube_transfer_abi(self) -> None:
        # No ROM switcher may be copied into &07A4. Pages 4-7 belong to the
        # Tube host code whenever a parasite is active.
        self.assertNotIn(bytes.fromhex("A5 F4 8D C2 07"), self.rom)
        # Whole-file parasite loads initialise operation 1 and stream bytes
        # through R3DATA. Successful parasite *RUN uses operation 4.
        self.assertGreaterEqual(self.rom.count(bytes.fromhex("20 06 04")), 1)
        self.assertEqual(self.rom.count(bytes.fromhex("8D E5 FE")), 1)
        self.assertEqual(self.rom.count(bytes.fromhex("4C 06 04")), 1)
        # Extended vector entry points for FILEV/BGETV/FINDV/FSCV.
        for entry in (0x1B, 0x21, 0x2A, 0x2D):
            self.assertIn(bytes((0xA9, entry, 0x8D)), self.rom)
        # The helper call address moves as dead legacy routines are removed.
        # Match the surrounding JIM length transaction, not a linker address.
        length_read = re.compile(
            bytes.fromhex("A9 FF 8D FF FC 20")
            + b".."
            + bytes.fromhex("AD FE FD 85 F8")
            + b".{0,12}"
            + bytes.fromhex("AD FF FD 85 F9"),
            re.DOTALL,
        )
        self.assertEqual(len(length_read.findall(self.rom)), 1)
        self.assertEqual(self.rom.count(bytes.fromhex("AD FE FD")), 1)
        self.assertEqual(self.rom.count(bytes.fromhex("AD FF FD")), 1)
        self.assertNotIn(bytes.fromhex("AD FE FD 85 F8 20 FC 87"), self.rom)
        self.assertEqual(self.rom.count(bytes.fromhex("8E DA 09 8C DB 09")), 1)
        self.assertGreaterEqual(self.rom.count(bytes.fromhex("AE DA 09 AC DB 09")), 1)
        self.assertEqual(self.rom.count(bytes.fromhex("8C DC 09")), 1)
        self.assertEqual(self.rom.count(bytes.fromhex("AC DC 09")), 1)
        osfile_metadata = bytes.fromhex(
            "AD DA 09 85 B8 AD DB 09 85 B9 A0 02 A2 00 BD BE 03 91 B8 "
            "E8 C8 E0 08 D0 F5 A5 B5 91 B8 C8 AD C6 03 91 B8 C8 A9 "
            "00 91 B8 C8 91 B8 A2 04 C8 91 B8 CA D0 FA A9 01 60"
        )
        self.assertEqual(self.rom.count(osfile_metadata), 1)

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

    def test_retired_cartridge_code_is_not_emitted(self) -> None:
        for legacy in (
            b"AT+", b"ESP8266", b"STATUS:3", b"115200", b"PRINTER",
            b"SETSERIAL", b"CRC error", b"WGET /",
        ):
            self.assertNotIn(legacy, self.rom)

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
