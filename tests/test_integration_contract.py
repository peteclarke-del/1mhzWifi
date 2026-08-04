import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class IntegrationContractTest(unittest.TestCase):
    def test_linux_bridge_scaffold_is_absent(self) -> None:
        for name in (
            "bridge_daemon.py", "bridge_protocol.py", "linux_network_backend.py",
            "pi_runtime.py", "pi_wifi_bridge.py", "run_bridge.sh",
        ):
            self.assertFalse(any(ROOT.rglob(name)), name)

    def test_pi_overlay_uses_services_mailbox_not_fc30_uart(self) -> None:
        service = (ROOT / "pi-side/pi1mhz-v1.30/src/elkwifi_service.c").read_text()
        patch = (ROOT / "pi-side/pi1mhz-current/integration.patch").read_text()
        self.assertIn("services_register", service)
        self.assertIn("elkwifi_service.c", patch)
        self.assertNotIn("elkwifi_emulator", patch)
        self.assertNotIn("0x30", patch)

    def test_wifi_credentials_persist_and_runtime_network_is_enabled(self) -> None:
        service = (ROOT / "pi-side/pi1mhz-v1.30/src/elkwifi_service.c").read_text()
        installer = (ROOT / "pi-side/install_bundle.sh").read_text()
        security_patch = (ROOT / "pi-side/pi1mhz-current/wifi-security.patch").read_text()
        radio_patch = (ROOT / "pi-side/pi1mhz-current/wifi-radio.patch").read_text()
        mac_patch = (ROOT / "pi-side/pi1mhz-current/wifi-mac-fallback.patch").read_text()
        radio_setup_patch = (ROOT / "pi-side/pi1mhz-current/wifi-radio-setup.patch").read_text()
        join_diagnostics_patch = (ROOT / "pi-side/pi1mhz-current/wifi-join-diagnostics.patch").read_text()
        join_reference_patch = (ROOT / "pi-side/pi1mhz-current/wifi-join-reference.patch").read_text()
        leave_patch = (ROOT / "pi-side/pi1mhz-current/wifi-leave.patch").read_text()
        network_tools_patch = (ROOT / "pi-side/pi1mhz-current/wifi-network-tools.patch").read_text()
        self.assertIn('WIFI_FILE "Pi1MHz/ElkWiFi.wifi"', service)
        self.assertIn('WIFI_PROFILE_HEADER "ELKWIFI1"', service)
        self.assertIn("wifi_credentials_load", service)
        self.assertIn("wifi_disconnect", service)
        self.assertIn("wifi_enable_radio", service)
        self.assertIn("sdio_runtime_scan_start", service)
        self.assertIn("sdio_runtime_scan_busy", service)
        self.assertIn("sdio_runtime_link_is_up", service)
        self.assertIn("wifi_lwip_get_context", service)
        self.assertIn("netif_ip4_addr", service)
        self.assertIn('response_string(cp, "No AP\\r\\n\\r\\nOK\\r\\n")', service)
        self.assertIn("sdio_runtime_rejoin_busy", service)
        self.assertIn("operation == (uint8_t)'?'", service)
        self.assertIn("Never keep the shared ElkWiFi command page", service)
        self.assertIn("+WIFI:LINK", service)
        self.assertIn("last_event_reason", join_diagnostics_patch)
        self.assertIn("wifi-join-diagnostics.patch", installer)
        self.assertIn("wifi-join-reference.patch", installer)
        self.assertIn("always send the canonical 36 bytes", join_reference_patch)
        self.assertIn("WIFI_SDIO_TX_PROBE_COMMAND_MFP", join_reference_patch)
        self.assertIn("WIFI_SDIO_TX_PROBE_COMMAND_DISASSOC", leave_patch)
        self.assertIn("g_runtime_rejoin_allowed = false", leave_patch)
        self.assertIn("wifi-leave.patch", installer)
        self.assertIn('LAPOPT_FILE "Pi1MHz/ElkWiFi.lapopt"', service)
        self.assertIn("ELKWIFI_CMD_LAPOPT", service)
        self.assertIn("scan_fields == 7u", service)
        self.assertIn("ELKWIFI_CMD_PING", service)
        self.assertIn("raw_sendto", service)
        self.assertIn("ELKWIFI_CMD_DATETIME", service)
        self.assertIn('dns_gethostbyname("pool.ntp.org"', service)
        self.assertIn("NTP_UNIX_EPOCH", service)
        self.assertIn("LWIP_RAW", network_tools_patch)
        self.assertIn("src/core/raw.c", network_tools_patch)
        self.assertIn("wifi-network-tools.patch", installer)
        self.assertIn('config_get("elkwifi_utc_offset_minutes")', service)
        self.assertIn('"+WIFI:STATE,\\"%s\\",\\"%.48s\\"\\r\\n"', service)
        self.assertIn('snprintf(response, sizeof response, "OK\\r\\n")', service)
        self.assertIn("ELKWIFI_ERR_NO_WIFI", service)
        self.assertIn("wifi_get_state() == WIFI_STATE_ERROR", service)
        self.assertIn("Pi1MHz->JIM_ram[cp] == ELKWIFI_CMD_STATUS", service)
        self.assertIn('response_string(cp, "Pi1MHz ElkWiFi\\r\\n\\r\\nOK\\r\\n")', service)
        self.assertIn("WLC_E_ESCAN_RESULT", security_patch)
        self.assertIn('memcpy(p, "escan", name_length)', security_patch)
        for mode in ("AUTO", "OPEN", "WEP", "WPA", "WPA2"):
            self.assertIn(f'"{mode}"', service)
        self.assertIn("WPA_AUTH_PSK | WPA2_AUTH_PSK", security_patch)
        self.assertIn("WIFI_SDIO_TX_PROBE_COMMAND_WEP_KEY", security_patch)
        self.assertIn("WSEC_KEY_PAYLOAD_LENGTH 164u", security_patch)
        self.assertIn("wifi-security.patch", installer)
        self.assertIn("wifi-radio.patch", installer)
        self.assertIn("bool wifi_enable_radio(void)", radio_patch)
        self.assertIn("if (sdio_runtime_ready())", radio_patch)
        self.assertIn("wifi-radio-setup.patch", installer)
        self.assertIn("Radio-only startup still needs the complete CLM/country", radio_setup_patch)
        self.assertIn("config->ssid[0] != '\\0'", radio_setup_patch)
        self.assertIn("g_runtime_step_deadline_us = now + 250000u", mac_patch)
        self.assertIn("if (g_runtime_desired_mac_valid)", mac_patch)
        self.assertIn("net_enable=1", installer)
        self.assertIn("Services_addr=0xA6", installer)
        self.assertIn("ElkWiFi_addr=0x00", installer)
        self.assertIn("preset=${2:-all}", installer)
        self.assertIn('build.sh" rpi', installer)
        self.assertIn('build.sh" rpi3', installer)
        for key in ("SCSIJUKE", "SCSIID", "VFSJUKE"):
            self.assertIn(f"ensure_config_default {key} 0", installer)

    def test_rom_routes_url_and_osword_tcp_through_pi_services(self) -> None:
        driver = (ROOT / "rom-side/elkwifi-0.23/service_driver.asm").read_text()
        wget = (ROOT / "rom-side/elkwifi-0.23/net_wget.asm").read_text()
        for operation in ("cipstart", "cipsend", "receive", "cipclose"):
            self.assertIn(f"service_driver_{operation}", driver)
        self.assertIn("net_cmd_url_open = 60", wget)
        self.assertIn("net_svc_command = &AA", wget)
        executable_lines = "\n".join(
            line for line in wget.splitlines() if not line.lstrip().startswith("\\")
        )
        self.assertNotIn("&FC30", executable_lines)
        self.assertIn("sta &FC00+drv_svc_command", driver)
        self.assertIn("lda &FC00+drv_svc_command", driver)
        self.assertNotIn("lda #&92", driver)
        self.assertNotIn("lda #&93", driver)
        surface = (ROOT / "rom-side/elkwifi-0.23/command-surface.patch").read_text()
        self.assertIn("+.service_driver_not_30\n+ jmp service_driver_unsupported", surface)
        self.assertIn(".service_driver_unsupported", driver)

    def test_wget_and_wicfs_use_the_pi_transport_and_jim_windows(self) -> None:
        wget = (ROOT / "rom-side/elkwifi-0.23/net_wget.asm").read_text()
        surface = (ROOT / "rom-side/elkwifi-0.23/command-surface.patch").read_text()
        executable = "\n".join(
            line for line in wget.splitlines() if not line.lstrip().startswith("\\")
        )
        self.assertIn(".pi_wget_cmd", wget)
        self.assertIn("net_cmd_url_open = 60", wget)
        self.assertIn("net_cmd_url_read = 61", wget)
        self.assertIn("net_cmd_url_close = 63", wget)
        self.assertIn("jsr check_esc", wget)
        self.assertIn("cancelled: never masquerade as successful EOF", wget)
        self.assertIn("jsr wget_context_switch_in", wget)
        self.assertIn("jsr pi_wget_store_paged", wget)
        self.assertNotIn("&FC30", executable)
        self.assertIn('equs "WICFS"', surface)
        self.assertIn('include "wicfs.asm"', surface)
        self.assertIn("sta &FCFE", surface)

    def test_rom_startup_and_absent_service_are_fail_safe(self) -> None:
        driver = (ROOT / "rom-side/elkwifi-0.23/service_driver.asm").read_text()
        menusrc = (ROOT / "rom-side/elkwifi-0.23/menusrc.asm").read_text()
        rom_patch = (ROOT / "rom-side/elkwifi-0.23/integration.patch").read_text()
        self.assertIn("drv_svc_response_count = errorspace+14", driver)
        self.assertIn("lda #240\n sta drv_svc_response_count", driver)
        self.assertIn("lda #100", driver)
        self.assertIn("lda #19", driver)
        self.assertIn("cmp #&21\n bcc service_driver_no_response", driver)
        self.assertIn("cmp #&7F\n bcs service_driver_no_response", driver)
        self.assertIn("jmp service_driver_version", driver)
        self.assertIn("cmp #&44\n beq service_driver_error_no_wifi", driver)
        self.assertIn("cmp &FC00+drv_svc_data\n bne service_driver_port_missing_near", driver)
        self.assertIn("cmp #&FF\n bne service_driver_wait_claimed\n jmp service_driver_service_unclaimed", driver)
        self.assertIn("drv_svc_command_copy = errorspace+16", driver)
        self.assertIn("cmp #drv_svc_status", driver)
        self.assertIn("lda #8\n sta drv_svc_timeout_outer", driver)
        no_response = driver.split(".service_driver_no_response", 1)[1]
        self.assertIn("ldx #(error_no_response-error_table)\n jmp error", no_response)
        self.assertNotIn("stx pageram", no_response)
        self.assertIn("lda #240\n sta menusrc_index", menusrc)
        self.assertIn("-                    jsr wifidriver", rom_patch)
        self.assertIn("report enabled without touching unforwarded &FC34", rom_patch)
        self.assertIn("+                ldx #1", rom_patch)
        self.assertIn("+ lda #23", rom_patch)
        self.assertIn("+ lda #255", rom_patch)
        self.assertIn("- sta &60A0,x", rom_patch)

    def test_menu_source_is_persistent_and_used_by_menu(self) -> None:
        service = (ROOT / "pi-side/pi1mhz-v1.30/src/elkwifi_service.c").read_text()
        rom_patch = (ROOT / "rom-side/elkwifi-0.23/integration.patch").read_text()
        self.assertIn('MENU_FILE "Pi1MHz/ElkWiFi.menu"', service)
        self.assertIn("filesystemWriteFile", service)
        self.assertIn("menusrc_make_wget", rom_patch)
        self.assertIn('config_get("elkwifi_menu_url")', service)
        self.assertIn("if (valid_menu_url(configured))", service)
        self.assertLess(service.index("filesystemReadFile(MENU_FILE"),
                        service.index('config_get("elkwifi_menu_url")'))
        # The matcher claims a command as soon as the table spelling ends.
        # MENUSRC therefore has to precede its MENU prefix.
        self.assertLess(rom_patch.index('+                    equs "MENUSRC"'),
                        rom_patch.index('+                    equs "MENU"'))
        self.assertIn("sta net_transfer_ok", rom_patch)
        self.assertIn("beq mquit", rom_patch)
        wget = (ROOT / "rom-side/elkwifi-0.23/net_wget.asm").read_text()
        self.assertIn("net_transfer_ok = heap+&EF", wget)
        self.assertIn("net_received = heap+&F0", wget)
        self.assertIn('equs "Empty response"', wget)
        menu = (ROOT / "rom-side/elkwifi-0.23/menu.asm").read_text()
        menusrc = (ROOT / "rom-side/elkwifi-0.23/menusrc.asm").read_text()
        self.assertIn("sta &0E00", menu)
        self.assertIn("lda &0E00", menu)
        self.assertIn("jsr menusrc_patch_menu", menu)
        self.assertIn('equs "Menu download failed"', menu)
        self.assertIn("equb &AD,&34,&FC,&09,&08,&8D,&34,&FC", menusrc)
        self.assertIn("equb &A9,&01,&EA,&EA,&EA,&8D,&FE,&FC", menusrc)
        menu_doc = (ROOT / "docs/menu-runtime-patch.md").read_text()
        self.assertIn("AD 34 FC", menu_doc)
        self.assertIn("8D 34 FC", menu_doc)
        self.assertIn("A9 01", menu_doc)
        self.assertIn("8D FE FC", menu_doc)
        self.assertIn("&0E00-&1FFF", menu_doc)

    def test_ping_escape_dispatches_pi_cancellation(self) -> None:
        driver = (ROOT / "rom-side/elkwifi-0.23/service_driver.asm").read_text()
        ping = (ROOT / "rom-side/elkwifi-0.23/ping.asm").read_text()
        service = (ROOT / "pi-side/pi1mhz-v1.30/src/elkwifi_service.c").read_text()
        header = (ROOT / "pi-side/pi1mhz-v1.30/src/elkwifi_service.h").read_text()
        self.assertIn("drv_svc_cancel = 90", driver)
        self.assertIn("jsr check_esc", driver)
        self.assertIn("lda #drv_svc_cancel", driver)
        self.assertIn("lda drv_svc_cancelled", ping)
        self.assertIn("bcs ping_cancelled", ping)
        self.assertIn("ELKWIFI_CMD_CANCEL       90u", header)
        self.assertIn("if (request_cancel)", service)
        self.assertIn("ping_close();", service)

    def test_installer_pins_reviewed_pi1mhz_commit(self) -> None:
        installer = (ROOT / "pi-side/install_bundle.sh").read_text()
        self.assertIn(
            "expected_upstream=83bca4922955e28e2f95122d71d631cce813d467",
            installer,
        )

    def test_date_time_and_ping_use_pi_network_services(self) -> None:
        driver = (ROOT / "rom-side/elkwifi-0.23/service_driver.asm").read_text()
        time_source = (ROOT / "rom-side/elkwifi-0.23/time.asm").read_text()
        self.assertIn("drv_svc_ping = 88", driver)
        self.assertIn("drv_svc_datetime = 89", driver)
        self.assertIn("service_driver_ping_copy", driver)
        self.assertIn("service_driver_datetime", driver)
        self.assertNotIn("acornelectron.nl", time_source)
        self.assertIn("lda #30", time_source)
        self.assertIn("lda #29", time_source)


if __name__ == "__main__":
    unittest.main()
