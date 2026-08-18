import hashlib
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROM_PATH = ROOT / "build" / "elkwifi_pi1mhz.rom"
ROM_SHA256 = "ea79352f49ebf986004050cc630452b795a6ca75fe5870c2c46980e49b4100fb"


class RomCompatibilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM_PATH.read_bytes()

    def test_rom_identity_and_stock_header(self) -> None:
        self.assertEqual(len(self.rom), 16 * 1024)
        self.assertEqual(hashlib.sha256(self.rom).hexdigest(), ROM_SHA256)
        self.assertEqual(
            self.rom[:9], bytes((0, 0, 0, 0x4C, 0x32, 0x80, 0x82, 0x18, 0x30))
        )
        copyright_offset = self.rom[7]
        self.assertEqual(self.rom[copyright_offset:copyright_offset + 4], b"\0(C)")
        self.assertEqual(self.rom[9:18], b"1MHzWifi\0")
        self.assertEqual(self.rom[18:25], b"0.1.55\0")
        self.assertIn(b"1MHzWifi 0.1.55 (C) 2026 Peter Clarke", self.rom)
        self.assertIn(b"Original elkWifi (C) 2020 Roland Leurs", self.rom)

    def test_menu_catalogue_selector_is_present(self) -> None:
        helper = bytes.fromhex("EA EA EA EA EA EA EA EA EA B9 00 FD 60")
        self.assertEqual(self.rom.count(helper), 1)
        self.assertIn(bytes.fromhex("20 C5 1F EA EA EA EA EA"), self.rom)
        self.assertRegex(
            self.rom,
            re.compile(bytes.fromhex("E0 01 F0") + b"."
                       + bytes.fromhex("8D FD FC 20") + b".."
                       + bytes.fromhex("8D FE FC 20"), re.S),
        )
        self.assertIn(b"TAPE\r", self.rom)

    def test_uef_file_handle_is_recovered_from_each_stack_context(self) -> None:
        # Inline read: TSX; LDY &0103,X; JSR OSBGET.
        self.assertEqual(
            self.rom.count(bytes.fromhex("BA BC 03 01 20 D7 FF")), 1
        )
        # Close helper: JSR has added its return address, so the saved OSFIND
        # handle is two bytes farther away: TSX; LDY &0105,X; LDA #0;
        # JSR OSFIND; RTS.
        self.assertEqual(
            self.rom.count(bytes.fromhex("BA BC 05 01 A9 00 20 CE FF 60")), 1
        )
        # WiCFS retains its original OSBYTE &8C trap so a protected loader's
        # internal *TAPE cannot disconnect a multi-stage virtual tape.
        self.assertIn(bytes.fromhex("C9 8C D0 01 60 4C 00 00 EA"), self.rom)

    def test_wicfs_uses_mos_vectors_and_host_only_osfile_transfer(self) -> None:
        # Test the cassette final-block flag before the loader-compatibility
        # helper can alter N/Z. A final block must call the helper and then
        # jump unconditionally to the completed OSFILE path.
        final_block = re.compile(
            re.escape(bytes.fromhex("AD CA 03 29 80 F0"))
            + b"."
            + re.escape(bytes.fromhex("20"))
            + b".."
            + re.escape(bytes.fromhex("4C"))
            + b"..",
            re.DOTALL,
        )
        self.assertEqual(len(final_block.findall(self.rom)), 1)
        # No ROM switcher may be copied into &07A4. Pages 4-7 belong to the
        # Tube host code whenever a parasite is active.
        self.assertNotIn(bytes.fromhex("A5 F4 8D C2 07"), self.rom)
        # WiCFS is an Electron-host filing system. It may query Tube presence
        # through OSBYTE &EA, but must never use Tube transfer registers or
        # copy a launcher into Tube host workspace.
        self.assertNotIn(bytes.fromhex("8D E4 FC"), self.rom)
        self.assertNotIn(bytes.fromhex("8D E5 FC"), self.rom)
        self.assertNotIn(bytes.fromhex("AD E4 FC"), self.rom)
        self.assertNotIn(bytes.fromhex("AD E5 FC"), self.rom)
        self.assertIn(bytes.fromhex("A9 EA A2 00 A0 FF 20 F4 FF"), self.rom)
        self.assertNotIn(bytes.fromhex("20 06 04"), self.rom)
        # Every UEF byte follows the normal host indirect-store path.
        self.assertIn(bytes.fromhex("A0 00 91 B0 E6 B0"), self.rom)
        # Extended vector entry points for FILEV/BGETV/FINDV/FSCV.
        for entry in (0x1B, 0x21, 0x2A, 0x2D):
            self.assertIn(bytes((0xA9, entry, 0x8D)), self.rom)
        # WiCFS reads the authoritative length trailer at rewind. The local
        # importer checkpoints a CPU-side count and reads the trailer only at
        # operation boundaries, so the retired per-byte byte pattern is not a
        # compatibility requirement.
        self.assertGreaterEqual(self.rom.count(bytes.fromhex("AD FE FD")), 1)
        self.assertGreaterEqual(self.rom.count(bytes.fromhex("AD FF FD")), 1)
        # &03E0-&03FF is the MOS keyboard input buffer containing MENU/UEF's
        # queued REWIND and CHAIN commands. The ROM must never mutate it. The
        # literal operand bytes may occur as data or instructions crossing a
        # ROM byte boundary, so inspect decoded absolute stores from a listing
        # in integration tests rather than rejecting arbitrary byte triples.
        self.assertNotIn(bytes.fromhex("8E DA 09 8C DB 09"), self.rom)
        self.assertNotIn(bytes.fromhex("8C DC 09"), self.rom)
        # Successful host OSFILE loads return the cassette catalogue metadata
        # which BASIC CHAIN needs to execute the loaded program.
        osfile_metadata = bytes.fromhex(
            "A0 02 A2 00 BD BE 03 91 B8 "
            "E8 C8 E0 08 D0 F5 A9 FF A0 04 91 B8 C8 91 B8 "
            "A0 08 91 B8 C8 91 B8 C8 A5 B5 91 B8 C8 AD C9 03 18 6D C6 03 "
            "91 B8 C8 A9 00 6D C7 03 91 B8 C8 A9 00 91 B8 A2 04 C8 91 B8 "
            "CA D0 FA A9 01 60"
        )
        self.assertEqual(self.rom.count(osfile_metadata), 1)
        # The UEF length remains authoritative in JIM. Do not reintroduce the
        # discarded cache in volatile &09D6/&09D7 host heap.
        self.assertNotIn(bytes.fromhex("A5 F8 8D D6 09 A5 F9 8D D7 09"), self.rom)
        self.assertIn(bytes.fromhex("0A 0A 0A 0A AA"), self.rom)
        self.assertNotIn(bytes.fromhex("0A AD D6 09"), self.rom)
        # The Zalaga compatibility guard contains both the complete vector
        # reset signature and its following TAPE command before patching RAM.
        loader_signature = bytes.fromhex(
            "AE B7 FF AC B8 FF 86 70 84 71 AC B6 FF 88 B1 70 "
            "99 00 02 98 D0 F7 A9 EA"
        )
        self.assertEqual(self.rom.count(loader_signature), 1)
        self.assertIn(b"TAPE\r", self.rom)

    def test_stock_commands_additive_menusrc_and_osword_are_present(self) -> None:
        for command in (
            b"WGET", b"MENU", b"MENUSRC", b"WIFI", b"VERSION", b"LAPOPT",
            b"LAP", b"IFCFG", b"DATE", b"TIME", b"PRD", b"JOIN", b"LEAVE",
            b"PING", b"MODE", b"ONLINE", b"DISCONNECT", b"UEF", b"WICFS",
            b"REWIND", b"QUPCFS", b"QUPRUN", b"PAGE=&E00\r*QR\r",
        ):
            self.assertIn(command, self.rom)
        for removed in (b"PRINTER", b"UPDATE", b"SETSERIAL", b"CRC error"):
            self.assertNotIn(removed, self.rom)
        self.assertIn(bytes((0xA5, 0xEF, 0xC9, 0x65)), self.rom)
        self.assertIn(b'*REWIND|MCHAIN ""|M\r', self.rom)
        self.assertNotIn(b'*RUN ""|M\r', self.rom)
        self.assertIn(b"Usage: *UEF LOAD <filename>", self.rom)
        self.assertIn(b"UEF ", self.rom)
        self.assertIn(b"RAW ", self.rom)
        self.assertIn(b"OK &", self.rom)
        self.assertIn(b"GZIP ", self.rom)
        self.assertIn(b"ZIP ", self.rom)
        self.assertIn(b"*QUPRUN\r", self.rom)
        self.assertIn(b"*REWIND\rCHAIN \"\"\r", self.rom)
        self.assertNotIn(b"*QUPRUN\r*REWIND", self.rom)

    def test_public_osword_driver_abi_reaches_single_socket_transport(self) -> None:
        # The emitted OSWORD &65 handler must unpack driver A/X/Y from the
        # caller's three-byte block before entering wifidriver.
        self.assertIn(bytes.fromhex(
            "A5 EF C9 65 F0 03 A9 08 60 98 48 8A 48 A0 00 B1 F0 48 "
            "C8 B1 F0 AA C8 B1 F0 A8 68 20"
        ), self.rom)

        driver = (ROOT / "rom-side/elkwifi-0.23/overlay/driver.asm").read_text()
        service = (ROOT / "rom-side/elkwifi-0.23/overlay/service_driver.asm").read_text()
        serial = (ROOT / "rom-side/elkwifi-0.23/overlay/serial.asm").read_text()
        self.assertIn("cmp #9\n bne service_driver_not_9\n jmp service_driver_cpmux", driver)
        self.assertIn("cmp #0\n bne service_driver_not_0\n jmp service_driver_init", driver)
        self.assertIn("cmp #1\n bne service_driver_not_1\n jmp service_driver_reset", driver)
        reset = service.split(".service_driver_init", 1)[1].split(
            ".service_driver_version", 1
        )[0]
        self.assertIn("jsr service_driver_net_close_silent", reset)
        self.assertIn("jmp service_driver_rom_response", reset)
        self.assertIn(".service_driver_cpmux", service)
        self.assertIn("cmp #'0'", service)
        self.assertIn("cmp #&0D", service)
        self.assertIn("driver_page_shadow = drv_svc_workspace+19", driver)
        common_entry = driver.split("jsr set_bank_0", 1)[1].split("lda save_a", 1)[0]
        self.assertIn("sta driver_page_shadow", common_entry)
        self.assertIn(".select_public_page_a", serial)
        self.assertIn("sta &FCFD\n jsr wicfs_bus_delay\n sta &FCFE", serial)
        self.assertIn("sta pagereg\n jsr wicfs_bus_delay", serial)
        self.assertGreaterEqual(driver.count("jsr select_public_page_a"), 5)
        self.assertIn("ldx driver_page_shadow", driver)
        self.assertNotIn("ldx pagereg", driver)
        self.assertNotIn("inc pagereg", service)
        self.assertGreaterEqual(service.count("stx driver_page_shadow"), 4)
        self.assertIn("inc driver_page_shadow", service)
        self.assertIn(".service_driver_wait_cursor", service)
        self.assertIn(".service_driver_read_a", service)
        self.assertGreaterEqual(service.count("jsr service_driver_read_a"), 3)
        self.assertGreaterEqual(service.count("jsr service_driver_wait_cursor"), 3)

        # Electron errorspace is &0100, the CPU hardware stack. A deep public
        # OSWORD caller such as ElkChat will have live return addresses there.
        # Error construction and driver state must remain in the retired
        # netprt block.
        ping = (ROOT / "rom-side/elkwifi-0.23/overlay/ping.asm").read_text()
        menusrc = (ROOT / "rom-side/elkwifi-0.23/overlay/menusrc.asm").read_text()
        errors = (ROOT / "rom-side/elkwifi-0.23/overlay/errors.asm").read_text()
        self.assertNotIn("errorspace+", service)
        self.assertNotIn("errorspace+", ping)
        self.assertNotIn("errorspace+", menusrc)
        self.assertNotIn("errorspace", errors)
        self.assertIn("error_workspace = netprt", errors)
        self.assertIn("drv_svc_workspace = netprt", service)
        self.assertIn("drv_net_ip = drv_svc_workspace+15", service)
        self.assertIn("driver_page_shadow = drv_svc_workspace+19", driver)
        self.assertIn("driver_machine = drv_svc_workspace+20", driver)

        transport = (ROOT / "rom-side/elkwifi-0.23/overlay/net_wget.asm").read_text()
        self.assertIn("net_cursor_lo = drv_svc_workspace+21", transport)
        self.assertIn("net_empty_lo = drv_svc_workspace+24", transport)
        self.assertIn(".net_wait_cursor", transport)
        self.assertGreaterEqual(transport.count("jsr net_wait_cursor"), 2)

        join = service.split(".service_driver_join", 1)[1].split(
            ".service_driver_leave", 1
        )[0]
        self.assertIn("lda (paramblok),y", join)
        self.assertNotIn("lda heap", join)

        open_tcp = service.split(".service_driver_cipstart", 1)[1].split(
            ".service_driver_cipsend", 1
        )[0]
        self.assertIn("sta drv_net_copy_count", open_tcp)
        self.assertIn("ldy drv_net_index", open_tcp)
        self.assertNotIn("sta drv_net_index\n.service_driver_copy_ip", open_tcp)

        selector = serial.split(".select_public_page_a", 1)[1].split(
            ".set_bank_1", 1
        )[0]
        self.assertIn("cpx #1\n beq set_bank_0_page", selector)
        self.assertIn("sta &FCFD\n jsr wicfs_bus_delay\n sta &FCFE", selector)

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
        source = (ROOT / "rom-side/elkwifi-0.23/overlay/service_driver.asm").read_text()
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
