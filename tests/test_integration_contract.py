import hashlib
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class IntegrationContractTest(unittest.TestCase):
    def test_runtime_sources_do_not_special_case_software_titles(self) -> None:
        """Compatibility fixes must describe MOS/UEF state, never a title."""
        runtime_roots = (
            ROOT / "rom-side/elkwifi-0.23/overlay",
            ROOT / "rom-side/elkwifi-0.23/patches",
            ROOT / "pi-side/pi1mhz-516a267/overlay",
            ROOT / "pi-side/pi1mhz-516a267/patches",
            ROOT / "emulator/pi1mhz-mailbox/src",
        )
        fixture_titles = (
            "arcadians", "bumblebee", "frak", "mrwiz", "repton",
            "thrust", "zalaga",
        )
        offenders = []
        for runtime_root in runtime_roots:
            for path in runtime_root.rglob("*"):
                if not path.is_file():
                    continue
                text = path.read_text(errors="ignore").lower()
                for title in fixture_titles:
                    if title in text:
                        offenders.append(f"{path.relative_to(ROOT)}: {title}")
        self.assertEqual(offenders, [], "title-specific runtime logic: " + ", ".join(offenders))

    def test_every_overlay_source_and_patch_is_consumed_by_a_build(self) -> None:
        rom_installer = (ROOT / "rom-side/build_rom.sh").read_text()
        for patch in (ROOT / "rom-side/elkwifi-0.23/patches").glob("*.patch"):
            self.assertIn(patch.name, rom_installer, patch.name)
        for source in (ROOT / "rom-side/elkwifi-0.23/overlay").glob("*.asm"):
            self.assertIn(source.name, rom_installer, source.name)

        pi_installer = (ROOT / "pi-side/install_bundle.sh").read_text()
        for patch in (ROOT / "pi-side/pi1mhz-516a267/patches").glob("*.patch"):
            self.assertIn(patch.name, pi_installer, patch.name)
        for source in (ROOT / "pi-side/pi1mhz-516a267/overlay/src").iterdir():
            if source.is_file():
                self.assertIn(source.name, pi_installer, source.name)
        for source in (ROOT / "pi-side/firmware").iterdir():
            if source.is_file():
                self.assertIn(source.name, pi_installer, source.name)

        self.assertIn('rom_source=${ELKWIFI_ROM:-}', pi_installer)
        self.assertIn('rom_source=${ELKWIFI_ROM:-}', pi_installer)
        self.assertIn('if [ "$preset" != apply ]; then', pi_installer)
        self.assertIn('if [ -n "$rom_source" ] && [ "$(wc -c < "$rom_source")" -ne 16384 ]', pi_installer)
        self.assertIn('output_dir=${PI1MHZ_OUTPUT_DIR:-$root_dir/build}', pi_installer)
        self.assertIn("install_if_changed", pi_installer)
        self.assertIn("SOURCE_DATE_EPOCH", pi_installer)
        self.assertIn("TZ=UTC zip -Xqr", pi_installer)

        osfile_stack = (ROOT / "rom-side/elkwifi-0.23/patches/wicfs-osfile-stack.patch").read_text()
        self.assertIn("Keep the OSFILE control-block pointer below the active stack", osfile_stack)
        self.assertIn("LDA\t&0102,X", osfile_stack)
        self.assertIn("LDA\t&0101,X", osfile_stack)
        self.assertNotIn("+\tLDA\tfilev_x", osfile_stack)

    def test_beebscsi_assets_and_bus_contract_are_preserved(self) -> None:
        bundle = ROOT / "build/pi1mhz-all/Pi1MHz"
        expected_hashes = {
            "ADFS.rom": "4f785bb4572bde31a93f12687dec501c9005b6a0decc6ac943c657447095a563",
            "defscsi.cfg": "126d88b1923f5c71e48cff750f69a4ad42e657dbd885435534e51afb8aa9b864",
        }
        for name, expected in expected_hashes.items():
            self.assertEqual(hashlib.sha256((bundle / name).read_bytes()).hexdigest(), expected)

        config = (bundle / "Pi1MHz.cfg").read_text()
        active = dict(re.findall(r"^\s*([A-Za-z][A-Za-z0-9_]*)\s*=\s*([^#\r\n]+)",
                                 config, re.MULTILINE))
        self.assertEqual(active.get("SCSIJUKE", "").strip(), "0")
        self.assertEqual(active.get("SCSIID", "").strip(), "0")
        self.assertEqual(active.get("VFSJUKE", "").strip(), "0")
        self.assertEqual(active.get("Rampage_addr", "").strip(), "0xFD")
        self.assertNotIn("Harddisc_addr", active)
        self.assertEqual(active.get("Services_addr", "").strip(), "0xA6")

        integration = (ROOT / "pi-side/pi1mhz-516a267/patches/integration.patch").read_text()
        self.assertNotIn("harddisc_emulator", integration.lower())
        capacity_test = (ROOT / "pi-side/pi1mhz-516a267/patches/services-capacity-test.patch").read_text()
        self.assertIn("eighth range registers", capacity_test)
        self.assertIn("identical reset-time claim renews", capacity_test)

    def test_pi_zero_and_pi3_wifi_firmware_matrix_is_packaged(self) -> None:
        bundle = ROOT / "build/pi1mhz-all"
        self.assertTrue((bundle / "kernel.img").is_file())
        self.assertTrue((bundle / "kernel7.img").is_file())
        for chip in ("43430", "43436", "43436s", "43455"):
            stem = bundle / "Pi1MHz/wifi" / f"brcmfmac{chip}-sdio"
            for suffix in (".bin", ".clm_blob", ".txt"):
                self.assertTrue(stem.with_suffix(suffix).is_file(), f"{stem}{suffix}")
        calibrated = (bundle / "Pi1MHz/wifi/brcmfmac43430-sdio.txt").read_text()
        self.assertIn("Raspberry Pi 3 Model B", calibrated)
        self.assertIn("boardflags3=0x08000000", calibrated)
        bcm43455 = bundle / "Pi1MHz/wifi/brcmfmac43455-sdio.bin"
        self.assertEqual(
            hashlib.sha256(bcm43455.read_bytes()).hexdigest(),
            "8868b5420be1191355d62690da4d96d14d30c1b3899d02fd15e9d664596650f9",
        )
        installer = (ROOT / "pi-side/install_bundle.sh").read_text()
        upstream = (ROOT / "pi-side/upstream.env").read_text()
        self.assertIn("PI1MHZ_BCM43455_FIRMWARE_COMMIT", installer)
        self.assertIn("8468a38f63b25785007a50912a3b32a596db8ff9", upstream)

    def test_linux_bridge_scaffold_is_absent(self) -> None:
        for name in (
            "bridge_daemon.py", "bridge_protocol.py", "linux_network_backend.py",
            "pi_runtime.py", "pi_wifi_bridge.py", "run_bridge.sh",
        ):
            self.assertFalse(any(ROOT.rglob(name)), name)

    def test_kernel_revision_fingerprints_untracked_overlay_contents(self) -> None:
        installer = (ROOT / "pi-side/install_bundle.sh").read_text()
        version_patch = (
            ROOT / "pi-side/pi1mhz-516a267/patches/gitversion-untracked-content.patch"
        ).read_text()
        self.assertIn("gitversion-untracked-content.patch", installer)
        self.assertIn("ls-files --others --exclude-standard", version_patch)
        self.assertIn("file(SHA256", version_patch)
        self.assertIn("GIT_UNTRACKED_CONTENT", version_patch)

    def test_pi_overlay_uses_services_mailbox_not_fc30_uart(self) -> None:
        service = (ROOT / "pi-side/pi1mhz-516a267/overlay/src/elkwifi_service.c").read_text()
        service_header = (ROOT / "pi-side/pi1mhz-516a267/overlay/src/elkwifi_service.h").read_text()
        patch = (ROOT / "pi-side/pi1mhz-516a267/patches/integration.patch").read_text()
        self.assertIn("services_register", service)
        self.assertIn("elkwifi_service.c", patch)
        self.assertNotIn("elkwifi_emulator", patch)
        self.assertNotIn("0x30", patch)
        for source in (service, service_header):
            self.assertNotRegex(source.lower(), r"\btube\b|\bparasite\b")

    def test_secure_rng_startup_is_incremental_and_capabilities_are_live(self) -> None:
        source = (
            ROOT
            / "pi-side/pi1mhz-516a267/overlay/src/secure_service_wolfssh.c"
        ).read_text()
        service = (
            ROOT / "pi-side/pi1mhz-516a267/overlay/src/secure_service.c"
        ).read_text()
        self.assertIn("static void rng_begin(void)", source)
        self.assertIn("static void rng_poll(void)", source)
        self.assertIn("rng_sample_count == 8u", source)
        self.assertIn("nts_pi_wolfssh_random_ready", source)
        self.assertIn("nts_pi_wolfssh_poll();\n    secure_refresh_capabilities();", service)
        self.assertIn("static volatile uint8_t capability_features;", service)
        self.assertNotIn("static volatile uint8_t capability_features =", service)

    def test_wifi_credentials_persist_and_runtime_network_is_enabled(self) -> None:
        service = (ROOT / "pi-side/pi1mhz-516a267/overlay/src/elkwifi_service.c").read_text()
        service_header = (ROOT / "pi-side/pi1mhz-516a267/overlay/src/elkwifi_service.h").read_text()
        service_driver = (ROOT / "rom-side/elkwifi-0.23/overlay/service_driver.asm").read_text()
        uef = (ROOT / "rom-side/elkwifi-0.23/overlay/uef.asm").read_text()
        wget = (ROOT / "rom-side/elkwifi-0.23/overlay/net_wget.asm").read_text()
        installer = (ROOT / "pi-side/install_bundle.sh").read_text()
        security_patch = (ROOT / "pi-side/pi1mhz-516a267/patches/wifi-security.patch").read_text()
        network_tools_patch = (ROOT / "pi-side/pi1mhz-516a267/patches/wifi-network-tools.patch").read_text()
        net_copy_public_patch = (
            ROOT / "pi-side/pi1mhz-516a267/patches/net-copy-public.patch"
        ).read_text()
        secure_wolfssh = (
            ROOT / "pi-side/pi1mhz-516a267/overlay/src/secure_service_wolfssh.c"
        ).read_text()
        self.assertIn('WIFI_FILE "/Pi1MHz/ElkWiFi.wifi"', service)
        self.assertIn('WIFI_PROFILE_HEADER "ELKWIFI1"', service)
        self.assertIn("wifi_credentials_load", service)
        self.assertIn("Do not turn an already-live association into a full rejoin", service)
        self.assertIn("if (sdio_runtime_started())", service)
        self.assertIn("strcmp(current->ssid, ssid) == 0", service)
        self.assertIn("current->security == security", service)
        self.assertIn("wifi_disconnect", service)
        self.assertIn("wifi_profile_is_valid(ssid, password, security)", service)
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
        self.assertNotIn("+WIFI:LINK", service)
        self.assertIn('+CIFSR:STAIP,\\"%s\\"', service)
        self.assertIn('+CIFSR:STAMAC,\\"%02x:%02x:%02x:%02x:%02x:%02x\\"', service)
        ifcfg = service.split("static uint8_t wifi_ifcfg", 1)[1].split(
            "static uint8_t wifi_online", 1
        )[0]
        self.assertNotIn("+WIFI:", ifcfg)
        self.assertNotIn("GATEWAY", ifcfg)
        self.assertNotIn("NETMASK", ifcfg)
        longest_ifcfg = (
            '+CIFSR:STAIP,"255.255.255.255"\r\n'
            '+CIFSR:STAMAC,"FF:FF:FF:FF:FF:FF"\r\n\r\nOK\r\n'
        )
        self.assertLess(len(longest_ifcfg), 240)
        self.assertNotIn("wifi-rejoin-queue.patch", installer)
        self.assertFalse(
            (ROOT / "pi-side/pi1mhz-516a267/patches/wifi-rejoin-queue.patch").exists()
        )
        self.assertIn("Re-read the saved profile on every host reset", service)
        self.assertIn('LAPOPT_FILE "/Pi1MHz/ElkWiFi.lapopt"', service)
        self.assertIn("ELKWIFI_CMD_LAPOPT", service)
        self.assertIn("scan_fields == 7u", service)
        self.assertIn("ELKWIFI_CMD_PING", service)
        self.assertIn("raw_sendto", service)
        self.assertIn("ELKWIFI_CMD_DATETIME", service)
        self.assertIn("ELKWIFI_CMD_ONLINE", service)
        self.assertIn("ELKWIFI_CMD_ONLINE       92u", service_header)
        self.assertIn("ELKWIFI_CMD_UEF_NORMALIZE 93u", service_header)
        self.assertIn("ELKWIFI_CMD_LAST         ELKWIFI_CMD_UEF_NORMALIZE", service_header)
        self.assertIn("ELKWIFI_UEF_STREAM_CAPACITY (16u * 1024u * 1024u)", service)
        self.assertIn("uef_stream_publish_window", service)
        self.assertIn("ELKWIFI_UEF_OP_REFILL", service)
        self.assertIn("value + 1u == uef_window_generation", service)
        self.assertIn("value + 1u != uef_window_generation", service)
        self.assertIn("actual_crc != uef_last_append_crc", service)
        self.assertIn("drv_uef_generation_lo = drv_svc_workspace+30", service_driver)
        self.assertIn("drv_uef_generation_hi = drv_svc_workspace+31", service_driver)
        self.assertIn("drv_uef_generation_record_lo = 26", service_driver)
        self.assertIn("drv_uef_generation_record_hi = 27", service_driver)
        generation_load = service_driver.split(
            ".service_driver_uef_generation_load", 1
        )[1].split(".service_driver_uef_generation_save", 1)[0]
        generation_save = service_driver.split(
            ".service_driver_uef_generation_save", 1
        )[1].split(".service_driver_uef_stream_template", 1)[0]
        for helper in (generation_load, generation_save):
            self.assertIn("php\n sei", helper)
            self.assertIn("jsr wicfs_state_address_x", helper)
            self.assertIn("&FCA9", helper)
        self.assertIn("jsr service_driver_uef_generation_load", service_driver)
        self.assertIn("jsr service_driver_uef_generation_save", service_driver)
        self.assertIn("cmp #drv_svc_uef_op_refill", service_driver)
        self.assertIn("cmp #drv_svc_uef_op_append", service_driver)
        self.assertIn("lda #17\n sta drv_svc_cursor", service_driver)
        self.assertIn("jsr service_driver_uef_stream_close", uef)
        self.assertIn('response_printf(cp, "ONLINE %u.%u.%u.%u\\r\\n"', service)
        self.assertIn('response_string(cp, "OFFLINE CONNECTING\\r\\n")', service)
        self.assertIn('response_string(cp, "OFFLINE WIFI OFF\\r\\n")', service)
        self.assertIn('response_string(cp, "OFFLINE ERROR\\r\\n")', service)
        self.assertIn('dns_gethostbyname("pool.ntp.org"', service)
        self.assertIn("NTP_UNIX_EPOCH", service)
        self.assertIn("LWIP_RAW", network_tools_patch)
        self.assertIn("src/core/raw.c", network_tools_patch)
        self.assertIn("wifi-network-tools.patch", installer)
        self.assertIn("net-copy-public.patch", installer)
        self.assertIn("memmove(&Pi1MHz->JIM_ram\\[destination\\]", installer)
        self.assertIn("! grep -q 'JIM_ram\\[DISC_RAM_BASE + destination\\]'",
                      installer)
        self.assertIn("grep -q 'DISC_RAM_BASE + 0x01f0u'", installer)
        self.assertIn("grep -q 'COPY_PUBLIC_NONZERO_ONLY'", installer)
        self.assertIn("grep -q '#define TEST_JIM_SIZE 0x1100000u'", installer)
        self.assertIn("#define NET_CMD_COPY_PUBLIC  58u", net_copy_public_patch)
        self.assertIn("destination + count > 0x10000u", net_copy_public_patch)
        self.assertIn("JIM_ram[destination]", net_copy_public_patch)
        self.assertNotIn("JIM_ram[DISC_RAM_BASE + destination]",
                         net_copy_public_patch)
        # The copy-boundary test case moved upstream with the net test files,
        # so the patch no longer carries it; upstream owns that assertion now.
        self.assertIn("result == WS_EOF || result == WS_CHANNEL_CLOSED",
                      secure_wolfssh)
        self.assertIn("if (channel_finished(result)) return -(int)NTS_EOF;",
                      secure_wolfssh)
        self.assertIn("drv_net_copy_public = 58", service_driver)
        receive = service_driver.split(".service_driver_receive_ok", 1)[1].split(
            ".service_driver_receive_empty", 1
        )[0]
        self.assertIn("lda #drv_net_copy_public", receive)
        self.assertIn("cmp #drv_net_unsupported", receive)
        self.assertIn(".service_driver_receive_legacy_copy", receive)
        self.assertIn("jsr service_driver_write_paged", receive)
        paged_wget = wget.split(".pi_wget_have_bytes", 1)[1].split(
            ".pi_wget_copy_cancel", 1
        )[0]
        self.assertIn("lda #net_cmd_copy_public", paged_wget)
        self.assertIn("cmp #net_result_unsupported", paged_wget)
        self.assertIn("jsr net_scratch_address", paged_wget)
        self.assertIn("lda net_paged_offset", paged_wget)
        self.assertNotIn("lda #&FF\n sta pagereg", paged_wget)
        self.assertIn("ELKWIFI_JOIN_RADIO_OFF", service)
        self.assertIn("if (radio.link_up && live != NULL", service)
        init_body = service.split("void elkwifi_service_init", 1)[1]
        initial_once = init_body.split("if (!service_initialised)", 1)[1].split(
            "   }", 1
        )[0]
        self.assertNotIn("wifi_credentials_load();", initial_once)
        self.assertIn("   wifi_credentials_load();", init_body)
        self.assertIn('config_get("elkwifi_utc_offset_minutes")', service)
        self.assertIn('config_get("elkwifi_uef_trim_tail")', service)
        self.assertIn("if (uef_trim_tail)", service)
        self.assertIn("elkwifi_uef_trim_tail=0", installer)
        self.assertIn('bundle_stage_dir=$(mktemp -d', installer)
        self.assertIn('rm -rf -- "$bundle"', installer)
        self.assertIn('mv "$bundle_staged" "$bundle"', installer)
        emulator_backend = (
            ROOT / "emulator/pi1mhz-mailbox/src/pi1mhz_net_backend.c"
        ).read_text()
        self.assertIn("PI1MHZ_UEF_TRIM_TAIL", emulator_backend)
        self.assertIn("if (backend->uef_trim_tail)", emulator_backend)
        self.assertIn("Function 18 is a public ElkWiFi ABI", service)
        self.assertNotIn("+CIFSR:GATEWAY", service)
        self.assertNotIn("+CIFSR:NETMASK", service)
        self.assertIn('snprintf(response, sizeof response, "OK\\r\\n")', service)
        self.assertIn("ELKWIFI_ERR_NO_WIFI", service)
        self.assertIn("wifi_get_state() == WIFI_STATE_ERROR", service)
        self.assertIn("Pi1MHz->JIM_ram[cp] == ELKWIFI_CMD_STATUS", service)
        self.assertNotIn(
            "Pi1MHz->JIM_ram[cp] == ELKWIFI_CMD_STATUS\n       && wifi_get_state()",
            service,
        )
        status_case = service.split("case ELKWIFI_CMD_STATUS:", 1)[1].split(
            "case ELKWIFI_CMD_RADIO:", 1
        )[0]
        self.assertNotIn("wifi_get_state", status_case)
        self.assertIn("response_string(cp, ELKWIFI_VERSION_RESPONSE)", status_case)
        self.assertIn('"Pi1MHz ElkWiFi 0.1.67, kernel " GITVERSION', service)
        self.assertIn("drv_svc_radio = 91", service_driver)
        wifi_control = service_driver.split(".service_driver_wifi_control", 1)[1].split(
            ".service_driver_ping", 1
        )[0]
        self.assertIn("lda #drv_svc_radio\n jmp service_driver_begin", wifi_control)
        self.assertNotIn("jmp service_driver_version", wifi_control)
        self.assertIn("case ELKWIFI_CMD_RADIO:", service)
        self.assertIn("do not make the caller wait for firmware or association", service)
        self.assertEqual(service.count("response_string(cp, ELKWIFI_VERSION_RESPONSE)"), 2)
        self.assertIn("#define ELKWIFI_UEF_BASE 0u", service)
        self.assertIn("const uint32_t base = ELKWIFI_UEF_BASE", service)
        self.assertIn("const uint32_t trailer = ELKWIFI_UEF_BASE + 0xfffeu", service)
        self.assertNotIn("DISC_RAM_BASE + 0x10000u", service)
        self.assertIn("WLC_E_ESCAN_RESULT", security_patch)
        self.assertIn('memcpy(p, "escan", name_length)', security_patch)
        for mode in ("AUTO", "OPEN", "WEP", "WPA", "WPA2"):
            self.assertIn(f'"{mode}"', service)
        self.assertIn("WPA_AUTH_PSK | WPA2_AUTH_PSK", security_patch)
        self.assertIn("WIFI_SDIO_TX_PROBE_COMMAND_WEP_KEY", security_patch)
        self.assertIn("WSEC_KEY_PAYLOAD_LENGTH 164u", security_patch)
        self.assertIn("wifi-security.patch", installer)
        self.assertIn("net_enable=1", installer)
        self.assertIn("Services_addr=0xA6", installer)
        self.assertIn("ElkWiFi_addr=0x00", installer)
        self.assertIn("preset=${2:-all}", installer)
        self.assertIn('build.sh" rpi', installer)
        self.assertIn('build.sh" rpi3', installer)
        for key in ("SCSIJUKE", "SCSIID", "VFSJUKE"):
            self.assertIn(f"ensure_config_default {key} 0", installer)
        self.assertIn("ensure_config_default Rampage_addr 0xFD", installer)
        self.assertIn("must set Rampage_addr=0xFD", installer)

    def test_rom_routes_url_and_osword_tcp_through_pi_services(self) -> None:
        driver = (ROOT / "rom-side/elkwifi-0.23/overlay/service_driver.asm").read_text()
        wget = (ROOT / "rom-side/elkwifi-0.23/overlay/net_wget.asm").read_text()
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
        dispatch = (ROOT / "rom-side/elkwifi-0.23/overlay/driver.asm").read_text()
        wifi_response = (ROOT / "rom-side/elkwifi-0.23/overlay/wificmd.asm").read_text()
        table = dispatch.split(".public_driver_dispatch", 1)[1].split(
            "\\ Initialize the data buffer", 1
        )[0]
        self.assertEqual(table.count("equw service_driver_unsupported-1"), 4)
        self.assertIn("and #&1F\n asl a\n tax", dispatch)
        self.assertIn("and #&1F", dispatch)
        self.assertNotIn("service_driver_timeout_setting", dispatch)
        self.assertEqual(table.count("equw service_driver_connection_status-1"), 2)
        self.assertIn("equw service_driver_set_buffer-1", table)
        self.assertEqual(table.count("equw service_driver_baud_compat-1"), 3)
        self.assertIn(".service_driver_unsupported", driver)
        self.assertIn("jmp generic_cmd", wifi_response)
        self.assertIn("WIFI OFF/ready state and final OK", wifi_response)
        self.assertIn(".disconnect_cmd", wget)
        self.assertIn("lda #14\n jmp generic_cmd", wget)

    def test_wget_and_wicfs_use_the_pi_transport_and_jim_windows(self) -> None:
        wget = (ROOT / "rom-side/elkwifi-0.23/overlay/net_wget.asm").read_text()
        surface = (ROOT / "rom-side/elkwifi-0.23/patches/command-surface.patch").read_text()
        executable = "\n".join(
            line for line in wget.splitlines() if not line.lstrip().startswith("\\")
        )
        self.assertIn(".pi_wget_cmd", wget)
        self.assertIn("net_cmd_url_open = 60", wget)
        self.assertIn("net_cmd_url_read = 61", wget)
        self.assertIn("net_cmd_url_close = 63", wget)
        self.assertIn("jsr check_esc", wget)
        self.assertIn("cancelled: never masquerade as successful EOF", wget)
        self.assertIn("jsr pi_wget_store_paged", wget)
        self.assertIn("net_paged_page = heap+&E4", wget)
        self.assertIn("net_paged_offset = heap+&E5", wget)
        self.assertIn("sta net_primary_page", wget)
        self.assertIn("ldy net_paged_offset", wget)
        paged_store = wget.split(".pi_wget_store_paged", 1)[1].split(".pi_wget_close", 1)[0]
        self.assertIn("inc net_paged_page", paged_store)
        self.assertNotIn("lda pagereg", paged_store)
        self.assertNotIn("inc pagereg", paged_store)
        self.assertLess(paged_store.index("jsr set_bank_1"), paged_store.index("sta pagereg"))
        trailer = wget.split(".pi_wget_has_response", 1)[1].split(
            ".pi_wget_finish_close", 1
        )[0]
        self.assertLess(trailer.index("jsr set_bank_1"), trailer.index("sta pagereg"))
        self.assertNotIn(".pi_wget_store_paged\n pha\n jsr wget_context_switch_in", wget)
        self.assertNotIn("&FC30", executable)
        self.assertIn('equs "Usage: WGET <url> <file>"', wget)
        self.assertIn("lda #&80", wget)
        self.assertIn("jsr wget_OSFIND", wget)
        self.assertIn("jsr wget_OSBPUT", wget)
        self.assertIn("sta net_file_handle", wget)
        self.assertIn("sta net_file_mode", wget)
        self.assertNotIn("pi_wget_store_main", wget)
        file_store = wget.split(".pi_wget_store_file", 1)[1].split(
            ".pi_wget_copied", 1
        )[0]
        self.assertIn("ldy net_file_handle", file_store)
        self.assertIn("jsr wget_OSBPUT", file_store)

        ftp = (ROOT / "rom-side/elkwifi-0.23/overlay/ftp.asm").read_text()
        self.assertIn("ftp_cmd_open   = 114", ftp)
        self.assertIn("ftp_cmd_cancel = 119", ftp)
        self.assertIn("jsr ftp_OSBPUT", ftp)
        self.assertIn("jsr ftp_OSBGET", ftp)
        self.assertIn("jsr ftp_OSFIND", ftp)
        self.assertIn("jsr net_scratch_address", ftp)
        self.assertIn(".ftp_command_table", ftp)
        for row in (
            'equs "quit"', 'equs "bye"', 'equs "help"',
            'equs "get"', 'equs "put"', 'equs "dir"', 'equs "ls"',
        ):
            self.assertIn(row, ftp)
        self.assertIn("cmp (ftp_ptr_lo),y", ftp)
        self.assertIn("jmp ftp_exec_plain", ftp)
        self.assertIn("jsr check_esc", wget)
        self.assertNotIn("&FEE0", ftp.upper())
        self.assertNotIn("&FEE5", ftp.upper())
        close = wget.split(".pi_wget_close\n", 1)[1].split(
            ".pi_wget_usage", 1
        )[0]
        self.assertLess(close.index("jsr wget_OSFIND"), close.index("jsr net_dispatch_wait"))
        self.assertIn('equs "WICFS"', surface)
        self.assertIn('include "wicfs.asm"', surface)
        wicfs_patch = (ROOT / "rom-side/elkwifi-0.23/patches/wicfs-page-shadow.patch").read_text()
        self.assertIn("inc pr_r", wicfs_patch)
        self.assertIn("JSR set_bank_1", wicfs_patch)
        self.assertIn("pr_y    =   heap+&D8", wicfs_patch)
        self.assertIn("pr_r    =   heap+&D9", wicfs_patch)
        self.assertIn("LDA\t#vdu_on", wicfs_patch)
        self.assertIn("+    STA pagereg", wicfs_patch)
        self.assertIn("filev_x =   heap+&DA", wicfs_patch)
        self.assertIn("filev_y =   heap+&DB", wicfs_patch)
        self.assertIn("bget_y  =   heap+&DC", wicfs_patch)
        self.assertIn("+\tLDX\tfilev_x", wicfs_patch)
        self.assertIn("+\tLDY\tfilev_y", wicfs_patch)
        self.assertIn("+\tLDY\tbget_y", wicfs_patch)
        self.assertNotIn("+\tSTA\tslotid", wicfs_patch)
        self.assertIn("FCFF is write-only through AP5/Pi1MHz", wicfs_patch)
        self.assertNotIn("+    inc pagereg", wicfs_patch)

        cursor_patch = (
            ROOT / "rom-side/elkwifi-0.23/patches/wicfs-cursor-zp.patch"
        ).read_text()
        self.assertIn("pr_y    =   &C7", cursor_patch)
        self.assertIn("pr_r    =   &C8", cursor_patch)
        self.assertIn("fscv_x         = &C9", cursor_patch)
        self.assertIn("findv_rtn = &CB", cursor_patch)
        self.assertNotIn("+pr_y    =   heap+&D8", cursor_patch)
        self.assertNotIn("+pr_r    =   heap+&D9", cursor_patch)

        jim_state_patch = (
            ROOT / "rom-side/elkwifi-0.23/patches/wicfs-jim-state.patch"
        ).read_text()
        self.assertIn("MOS keyboard input buffer occupies &03E0-&03FF", jim_state_patch)
        self.assertIn("&FFEF00", jim_state_patch)
        self.assertIn("AP5 does not forward &FCFD/&FCFE", jim_state_patch)
        # The physical recovery baseline deliberately keeps WiCFS on its
        # original private FCA6-FCA9 cursor. Sharing net_cursor_* with WGET
        # was a 0.1.51 experiment which regressed MENU and local UEF loading.
        self.assertNotIn("net_cursor_lo", jim_state_patch)
        self.assertNotIn("net_cursor_mid", jim_state_patch)
        self.assertNotIn("net_cursor_hi", jim_state_patch)
        self.assertNotIn("net_read_a", jim_state_patch)
        self.assertNotIn("net_write_a", jim_state_patch)
        self.assertIn("+\tLDA\t&FCA9", jim_state_patch)
        self.assertIn("+\tSTA\t&FCA9", jim_state_patch)
        self.assertNotIn("+\tSTA\t&FCFD", jim_state_patch)
        self.assertNotIn("+\tSTA\t&FCFE", jim_state_patch)
        private_workspace = (
            ROOT / "rom-side/elkwifi-0.23/patches/wicfs-private-workspace.patch"
        ).read_text()
        self.assertIn("+wicfs_state_ram = &0380", private_workspace)
        self.assertIn(".wicfs_state_load", jim_state_patch)
        build_script = (ROOT / "rom-side/build_rom.sh").read_text()
        self.assertIn("check_wicfs_keyboard_buffer.py", build_script)
        self.assertIn('"$upstream/rom/wicfs.asm"', build_script)
        checker = (ROOT / "rom-side/check_wicfs_keyboard_buffer.py").read_text()
        self.assertIn("0x03E0 <= address <= 0x03FF", checker)
        self.assertIn("FILENAME_WRITE", checker)
        self.assertIn("FILENAME_LIMIT", checker)
        self.assertIn("-dd -labels", build_script)
        self.assertIn("check_combined_ram_layout.py", build_script)
        self.assertIn("symbols", checker)
        vector_entry_patch = (
            ROOT / "rom-side/elkwifi-0.23/patches/wicfs-vector-entry-state.patch"
        ).read_text()
        self.assertEqual(vector_entry_patch.count("JSR\twicfs_state_load"), 3)
        self.assertIn("JSR wicfs_state_load", vector_entry_patch)
        self.assertIn(".upfilev", vector_entry_patch)
        self.assertIn(".upfindv", vector_entry_patch)
        self.assertIn("STA\tfscv_reason", vector_entry_patch)

        patch_dir = ROOT / "rom-side/elkwifi-0.23/patches"
        opt_patch = (patch_dir / "wicfs-opt.patch").read_text()
        self.assertIn("FSCV reason 0 is *OPT", opt_patch)
        self.assertIn(".upv_opt_default", opt_patch)
        self.assertIn("equb\t&00,&22,&11", opt_patch)

        host_addresses = (patch_dir / "wicfs-host-addresses.patch").read_text()
        self.assertIn("portable host-memory representation", host_addresses)
        self.assertIn("\tLDY\t#8", host_addresses)
        self.assertIn(".upbgetv", vector_entry_patch)
        self.assertIn("chain_exec     = &03A0", vector_entry_patch)
        self.assertNotIn("+chain_exec     = heap+&B0", vector_entry_patch)
        self.assertIn(".wicfs_state_save", jim_state_patch)
        self.assertIn("pr_y    =   &C7", jim_state_patch)
        self.assertIn("pr_r    =   &C8", jim_state_patch)

        driver = (ROOT / "rom-side/elkwifi-0.23/overlay/driver.asm").read_text()
        service_driver = (
            ROOT / "rom-side/elkwifi-0.23/overlay/service_driver.asm"
        ).read_text()
        self.assertIn("driver_page_shadow = drv_svc_workspace+19", driver)
        self.assertNotIn("ldx pagereg", driver)
        self.assertNotIn("inc pagereg", service_driver)

        wget_helpers = (
            ROOT / "rom-side/elkwifi-0.23/overlay/wget_helpers.asm"
        ).read_text()
        self.assertNotRegex(wget_helpers, r"\blda\s+pagereg\b")
        self.assertNotRegex(wget_helpers, r"\binc\s+pagereg\b")
        self.assertIn("inc pr_r", wget_helpers)

        lifecycle_patch = (
            ROOT / "rom-side/elkwifi-0.23/patches/wicfs-lifecycle.patch"
        ).read_text()
        for symbol in (
            "BGETRTN", "bget_prev_rom", "bytev_rtn", "wicfs_magic",
            ".wicfs_reset",
        ):
            self.assertIn(symbol, lifecycle_patch)
        self.assertIn("jsr wicfs_reset", lifecycle_patch)
        self.assertIn("Restore BYTEV before using OSBYTE", lifecycle_patch)
        self.assertIn(".wicfs_restore_bget", lifecycle_patch)
        self.assertIn(".wicfs_restore_find", lifecycle_patch)
        self.assertIn(".wicfs_restore_fsc", lifecycle_patch)
        self.assertIn(".wicfs_restore_byte", lifecycle_patch)
        self.assertIn("+FILVRTN        = &03E8", lifecycle_patch)
        self.assertIn("+wicfs_magic    = &03F4", lifecycle_patch)
        self.assertIn("outside Tube and ADFS workspace", lifecycle_patch)
        self.assertNotRegex(lifecycle_patch, r"&D[0-9A-Fa-f]{2}")

        # Reset may release WiCFS only while its live BYTEV trap proves that
        # the saved predecessor set still belongs to this installation. Once
        # stream completion restores BYTEV, MOS owns reset-time vector rebuilds.
        reset_passive_patch = (
            ROOT / "rom-side/elkwifi-0.23/patches/wicfs-reset-passive.patch"
        ).read_text()
        self.assertIn("-                    jsr wicfs_reset", reset_passive_patch)
        self.assertIn("+                    jsr release_owned_wicfs", reset_passive_patch)
        self.assertIn("-                    stx pagereg", reset_passive_patch)
        self.assertIn("Do not touch the AP5 JIM selector", reset_passive_patch)
        self.assertIn("-                    stx uptype", reset_passive_patch)
        self.assertIn(
            "wicfs-reset-passive.patch",
            (ROOT / "rom-side/build_rom.sh").read_text(),
        )

        stream_finish_patch = (
            ROOT / "rom-side/elkwifi-0.23/patches/wicfs-stream-finish.patch"
        ).read_text()
        self.assertIn(".wicfs_any_vector_owned", stream_finish_patch)
        reset_service = stream_finish_patch.split(
            "@@ -138,7 +138,8 @@", 1
        )[1].split("@@", 1)[0]
        self.assertNotIn("wicfs_any_vector_owned", reset_service)
        self.assertIn("bne autorun_wicfs_released", reset_service)
        self.assertIn("cannot execute a partially rewritten handler", stream_finish_patch)
        self.assertEqual(stream_finish_patch.count("JSR\tinstall_extended_vector"), 0)
        self.assertNotIn("wicfs_reset_select_tape", stream_finish_patch)
        self.assertNotIn("LDA\t#&8C", stream_finish_patch)
        self.assertIn(".wicfs_install_byte_trap", stream_finish_patch)
        self.assertIn(".wicfs_install_invalid", stream_finish_patch)
        self.assertIn("JSR\twicfs_finish_if_exhausted", stream_finish_patch)
        self.assertIn("partially rewritten handler", stream_finish_patch)

        osfile_metadata_patch = (
            ROOT / "rom-side/elkwifi-0.23/patches/wicfs-osfile-metadata.patch"
        ).read_text()
        osfile_stack_patch = (
            ROOT / "rom-side/elkwifi-0.23/patches/wicfs-osfile-stack.patch"
        ).read_text()
        self.assertIn("OSFILE metadata return complete", osfile_metadata_patch)
        self.assertIn("JSR\tfilev_load_info", osfile_stack_patch)
        self.assertIn("LDA\t#1\t\t\t\\file found", osfile_stack_patch)

        jim_atomic_patch = (
            ROOT / "rom-side/elkwifi-0.23/patches/wicfs-jim-atomic.patch"
        ).read_text()
        self.assertIn("keep bank, page and data read one atomic transaction",
                      jim_atomic_patch)
        self.assertEqual(jim_atomic_patch.count("+    sei"), 3)
        self.assertEqual(jim_atomic_patch.count("+    plp"), 3)
        self.assertIn("leave the complete public JIM address at 00:00:00",
                      jim_atomic_patch)
        self.assertIn("recover data before the older saved flags below it",
                      jim_atomic_patch)
        self.assertLess(
            jim_atomic_patch.index("+    pla             \\recover data"),
            jim_atomic_patch.index("+    plp\n+    pha"),
        )

        host_patch = (
            ROOT / "rom-side/elkwifi-0.23/patches/wicfs-host-only.patch"
        ).read_text()
        self.assertIn("Use MOS extended vectors", host_patch)
        self.assertIn("LDY\t#27", host_patch)
        self.assertIn("LDY\t#33", host_patch)
        self.assertIn("LDY\t#42", host_patch)
        self.assertIn("LDY\t#45", host_patch)
        self.assertIn("1MHz-bus filing system", host_patch)
        self.assertIn("STA\t(CFSload),Y", host_patch)
        self.assertIn("JMP\t(&03C2)", host_patch)
        self.assertIn("INC\tCFSload+3", host_patch)
        self.assertIn("findv_rtn", host_patch)
        self.assertIn("fscv_reason", host_patch)
        self.assertIn("CMP\t#128\n+\tBEQ\tupf_a6", host_patch)
        self.assertIn("CMP\t#192\n+\tBEQ\tupf_a3", host_patch)
        self.assertNotIn("random access is unsupported", host_patch)
        self.assertNotIn("+romsel\t=\t&07A4", host_patch)
        for forbidden in ("&027A", "&0406", "&FCE4", "&FCE5", "&FEE4", "&FEE5", "tube_target"):
            self.assertNotIn(forbidden, host_patch)
        self.assertFalse(
            (ROOT / "rom-side/elkwifi-0.23/patches/wicfs-tube-osfile.patch").exists()
        )
        build_script = (ROOT / "rom-side/build_rom.sh").read_text()
        self.assertNotIn("wicfs-tube-osfile.patch", build_script)
        for forbidden in ("TubeCode", "TUBE_R3_STATUS", "TUBE_R3_DATA",
                          "tube_prepare", "tube_release", "tube_active"):
            self.assertNotIn(forbidden, build_script)

        host_launch = (
            ROOT / "rom-side/elkwifi-0.23/overlay/host_launch.asm"
        ).read_text()
        self.assertFalse(
            (ROOT / "rom-side/elkwifi-0.23/patches/menu-host-reset.patch").exists()
        )
        self.assertIn("host_return_addr = &1FD0", host_launch)
        self.assertIn(".host_select_tape", host_launch)
        self.assertIn(".host_enter_basic", host_launch)
        for forbidden in ("&FCE4", "&FCE5", "TubeCode",
                          "tube_prepare", "tube_release", "tube_active"):
            self.assertNotIn(forbidden, host_launch)
        self.assertNotIn("sta &FCE", host_launch)
        self.assertNotIn("lda &FCE", host_launch)
        uef = (ROOT / "rom-side/elkwifi-0.23/overlay/uef.asm").read_text()
        self.assertIn(".uef_select_launch", uef)
        self.assertIn("cmp #&0D", uef)
        self.assertIn("cmp #5", uef)
        self.assertIn("dec &0101,x", uef)
        self.assertIn("cmp #&0D                    \\ declared line boundary", uef)
        self.assertIn('equs "*RUN "', uef)
        self.assertIn('equs "CHAIN "', uef)
        self.assertIn(".uef_auto_cmd", uef)
        self.assertIn("lda #&EA", uef)
        self.assertIn('equs "*QUPRUN",&0D', uef)
        self.assertIn('equs "PAGE=&E00",&0D', host_launch)
        self.assertIn('equs "*QR",&0D', host_launch)
        self.assertIn("jmp host_basic_cmd", uef)
        command_patch = (
            ROOT / "rom-side/elkwifi-0.23/patches/uef-command.patch"
        ).read_text()
        self.assertIn('equs "QHOST"', command_patch)
        self.assertIn(".host_basic_cmd", host_launch)
        self.assertIn("jmp &8000", host_launch)
        for forbidden in ('equs "TUBE OFF"', "&FEE0", "&FEE1", "&FEE2", "&FEE3",
                          "&FEE4", "&FEE5", "&FEE6", "&FEE7"):
            self.assertNotIn(forbidden, host_launch)
            self.assertNotIn(forbidden, uef)

        vector_capture_patch = (
            ROOT / "rom-side/elkwifi-0.23/patches/wicfs-vector-chain.patch"
        ).read_text()
        self.assertIn("filev_prev_rom = &03A0", vector_capture_patch)
        self.assertIn("fscv_prev_rom  = &03A2", vector_capture_patch)
        self.assertIn("OSFSC may use B8/B9", vector_capture_patch)
        self.assertIn("CMP\t#>&FF2D", vector_capture_patch)
        self.assertIn("STA\tfscv_prev_rom", vector_capture_patch)
        self.assertIn("STX\tfscv_x", vector_capture_patch)
        self.assertIn("STY\tfscv_y", vector_capture_patch)
        reentry_patch = (
            ROOT / "rom-side/elkwifi-0.23/patches/wicfs-reentry-run.patch"
        ).read_text()
        self.assertIn("CMP\t#3\t\t\\unrecognised OSCLI command?", reentry_patch)
        self.assertIn("JSR\tcfsinit", reentry_patch)
        self.assertIn("LDA\t#0\t\t\\REWIND is not a pending *RUN", reentry_patch)
        self.assertIn("STA\tloadrun\t\t\\do not enter actioned's stale execution path", reentry_patch)
        self.assertIn("STA\tchain_exec,X", reentry_patch)
        self.assertNotIn("run_return_lo", reentry_patch)
        self.assertNotIn("run_return_hi", reentry_patch)
        self.assertIn("JMP\tchain_exec", reentry_patch)
        self.assertEqual(reentry_patch.count("\tPLA"), 2)
        tail_unwind = private_workspace.split("@@ -1150", 1)[1]
        self.assertEqual(tail_unwind.count("+\tPLA"), 4)
        self.assertNotIn("-BYTEV\t=", reentry_patch)
        self.assertNotIn("-.osb_s", reentry_patch)

        oscli_patch = (
            ROOT / "rom-side/elkwifi-0.23/patches/wicfs-oscli-prefix.patch"
        ).read_text()
        self.assertIn("CMP\t#8", oscli_patch)
        self.assertIn("BEQ\tupv_about_to_process", oscli_patch)
        self.assertIn(".upv_about_to_process", oscli_patch)
        self.assertIn("AND\t#&7F", oscli_patch)
        self.assertIn("JMP\tclfscv", oscli_patch)

        for tube_register in ("&FCE0", "&FCE1", "&FCE2", "&FCE3",
                              "&FCE4", "&FCE5", "&FCE6", "&FCE7"):
            self.assertNotIn(tube_register, host_launch)
        # Host entry avoids OSBYTE &8E, whose normal Tube-aware path copies
        # the language to the parasite. The Tube hardware remains untouched.
        self.assertIn("sta &028C", host_launch)
        self.assertIn("lda #&0C\n    sta &FE05", host_launch)
        self.assertIn("sta &025D", host_launch)
        self.assertNotIn("jmp &0400", host_launch.lower())
        self.assertIn("lda #&81", host_launch)
        self.assertIn("cpx #1", host_launch)
        self.assertIn("sta &FE05", host_launch)
        self.assertIn("sta &FE30", host_launch)

        rewind_patch = (
            ROOT / "rom-side/elkwifi-0.23/patches/wicfs-rewind.patch"
        ).read_text()
        wget = (ROOT / "rom-side/elkwifi-0.23/overlay/net_wget.asm").read_text()
        self.assertIn("jsr cfsinit", rewind_patch)
        self.assertIn("authoritative UEF length from Pi1MHz JIM", rewind_patch)
        self.assertNotIn("tape_len", rewind_patch)
        self.assertNotIn("tape_len", wget)
        self.assertIn("lda #&EA", uef)
        serial = (ROOT / "rom-side/elkwifi-0.23/overlay/serial.asm").read_text()
        self.assertIn("cpx #1\n beq set_bank_0_page", serial)
        self.assertIn("sta &FCFD\n jsr wicfs_bus_delay\n sta &FCFE", serial)
        self.assertIn(".detect_jim_machine", serial)
        self.assertNotIn("lda &FCFF", serial)
        self.assertIn("jsr set_bank_0             \\ ElkWiFi buffers are in JIM address 00:00:page", (ROOT / "rom-side/elkwifi-0.23/overlay/driver.asm").read_text())

    def test_rom_startup_and_absent_service_are_fail_safe(self) -> None:
        driver = (ROOT / "rom-side/elkwifi-0.23/overlay/service_driver.asm").read_text()
        serial = (ROOT / "rom-side/elkwifi-0.23/overlay/serial.asm").read_text()
        wifi = (ROOT / "rom-side/elkwifi-0.23/overlay/wificmd.asm").read_text()
        public_driver = (ROOT / "rom-side/elkwifi-0.23/overlay/driver.asm").read_text()
        rom_patch = (ROOT / "rom-side/elkwifi-0.23/patches/integration.patch").read_text()
        banner_patch = (ROOT / "rom-side/elkwifi-0.23/patches/banner-spacing.patch").read_text()
        self.assertIn("drv_svc_response_count = drv_svc_workspace+11", driver)
        self.assertIn("lda #240\n sta drv_svc_response_count", driver)
        self.assertIn("lda #100", driver)
        self.assertIn("lda #19", driver)
        self.assertIn("cmp #&21\n bcs service_driver_response_visible", driver)
        self.assertIn("cmp #&7F\n bcc service_driver_response_ascii", driver)
        self.assertIn("equw service_driver_version-1", public_driver)
        identity = (ROOT / "rom-side/elkwifi-0.23/patches/identity.patch").read_text()
        self.assertIn('romtitle           equs "1MHz-WiFi"', identity)
        self.assertIn('romversion         equs "0.1.67"', identity)
        version = (ROOT / "rom-side/elkwifi-0.23/overlay/version.asm").read_text()
        self.assertIn("1MHz-WiFi 0.1.67 (C) 2026 Peter Clarke", version)
        self.assertIn("+                    equb &D,&EA", banner_patch)
        self.assertIn("-                    equb &D,&D,&EA", banner_patch)
        self.assertIn("Parts from ElkWiFi (C) 2020 Roland Leurs", version)
        self.assertIn("cmp #&44\n beq service_driver_error_no_wifi", driver)
        self.assertIn(
            "lda &FC00+drv_svc_data\n cmp drv_svc_command_copy\n"
            " bne service_driver_port_missing_after_command",
            driver,
        )
        self.assertIn("jsr service_driver_wait_cursor", driver)
        wait = driver.split("\n.service_driver_wait\n", 1)[1].split(
            "\n.service_driver_timeout\n", 1
        )[0]
        self.assertNotIn("cmp #&FF", wait)
        timeout = driver.split("\n.service_driver_timeout\n", 1)[1].split(
            ".service_driver_result", 1
        )[0]
        self.assertIn(
            "cmp #&FF\n bne service_driver_timeout_claimed\n"
            " jmp service_driver_service_unclaimed",
            timeout,
        )
        self.assertIn("drv_svc_command_copy = drv_svc_workspace+13", driver)
        self.assertNotIn("cmp #drv_svc_status", driver.split(".service_driver_dispatch", 1)[1])
        self.assertIn("lda #8\n sta drv_svc_timeout_outer", driver)
        result = driver.split("\n.service_driver_result\n", 1)[1].split(
            "\n.service_driver_error\n", 1
        )[0]
        self.assertIn("php\n sei\n lda #&FF", result)
        self.assertIn("sta &FC00+drv_svc_addr_hi\n sta &FC00+drv_svc_addr_mid", result)
        self.assertIn(".service_driver_result_no_copy\n php\n sei", result)
        no_response = driver.split(".service_driver_no_response", 1)[1]
        self.assertIn("ldx #(error_no_response-error_table)\n jmp error", no_response)
        self.assertNotIn("stx pageram", no_response)
        self.assertIn("-                    jsr wifidriver", rom_patch)
        self.assertNotIn("test_wifi_ena", serial)
        self.assertNotIn("uart_mcr", serial)
        self.assertIn("                ldx #1", wifi)
        self.assertIn("+ lda #23", rom_patch)
        self.assertIn("+ lda #255", rom_patch)
        self.assertIn("- sta &60A0,x", rom_patch)

    def test_prd_uses_write_only_safe_jim_selection(self) -> None:
        pdump = (ROOT / "rom-side/elkwifi-0.23/overlay/pdump.asm").read_text()
        build = (ROOT / "rom-side/build_rom.sh").read_text()
        self.assertIn('install -m 0644 "$overlay_dir/pdump.asm"', build)
        self.assertNotRegex(pdump, r"(?im)^\s*lda\s+(?:&FCF[DEF]|pagereg)\s*$")
        read = pdump.split(".pdump_read_y", 1)[1]
        self.assertIn("sta &FCFD", read)
        self.assertIn("sta &FCFE", read)
        self.assertIn("sta pagereg", read)
        self.assertLess(read.index("sta pagereg"), read.index("lda pageram,y"))
        self.assertIn("cmp #1\n bne pdump_start\n jmp pdump_bad_bank", pdump)
        self.assertIn(".pdump_end\n jsr set_bank_0", pdump)

    def test_rom_reserves_space_for_the_next_feature(self) -> None:
        patch = (
            ROOT / "rom-side/elkwifi-0.23/patches/rom-headroom.patch"
        ).read_text()
        self.assertIn("rom_content_end = P%", patch)
        self.assertIn("ASSERT rom_content_end <= &BF00", patch)
        self.assertNotIn(b"This is the end!", (ROOT / "build/pi1mhz-all/Pi1MHz/1mhz-wifi.rom").read_bytes())

    def test_menu_surface_is_fully_retired(self) -> None:
        service = (
            ROOT / "pi-side/pi1mhz-516a267/overlay/src/elkwifi_service.c"
        ).read_text()
        service_header = (
            ROOT / "pi-side/pi1mhz-516a267/overlay/src/elkwifi_service.h"
        ).read_text()
        installer = (ROOT / "pi-side/install_bundle.sh").read_text()
        build_script = (ROOT / "rom-side/build_rom.sh").read_text()
        retirement = (
            ROOT / "rom-side/elkwifi-0.23/patches/menu-retirement.patch"
        ).read_text()
        wget = (
            ROOT / "rom-side/elkwifi-0.23/overlay/net_wget.asm"
        ).read_text()
        self.assertNotIn("ELKWIFI_CMD_MENU", service)
        self.assertNotIn("ELKWIFI_CMD_MENU", service_header)
        self.assertNotIn("elkwifi_menu", installer)
        self.assertNotIn("menu-cache.patch", installer)
        self.assertNotIn("overlay/menu.asm", build_script)
        self.assertNotIn("overlay/menusrc.asm", build_script)
        self.assertIn('equs "MENU"', retirement)
        self.assertIn('equs "MENUSRC"', retirement)
        self.assertNotIn("pi_wget_menu_cache", wget)
        self.assertNotIn("pi_wget_cached_paged", wget)
        self.assertNotIn("NET_OPEN_READ plus Pi MENU cache mode", wget)

    def test_ping_escape_dispatches_pi_cancellation(self) -> None:
        driver = (ROOT / "rom-side/elkwifi-0.23/overlay/service_driver.asm").read_text()
        ping = (ROOT / "rom-side/elkwifi-0.23/overlay/ping.asm").read_text()
        service = (ROOT / "pi-side/pi1mhz-516a267/overlay/src/elkwifi_service.c").read_text()
        header = (ROOT / "pi-side/pi1mhz-516a267/overlay/src/elkwifi_service.h").read_text()
        self.assertIn("drv_svc_cancel = 90", driver)
        self.assertIn("jsr check_esc", driver)
        self.assertIn("lda #drv_svc_cancel", driver)
        self.assertIn("lda drv_svc_cancelled", ping)
        self.assertIn("bcs ping_cancelled", ping)
        self.assertIn("ping_request_count = heap+&B1", ping)
        self.assertIn("stx ping_request_count", ping)
        self.assertIn("dec ping_request_count", ping)
        self.assertNotIn("stx size", ping)
        self.assertNotIn("dec size", ping)
        self.assertIn("ELKWIFI_CMD_CANCEL       90u", header)
        self.assertIn("if (request_cancel)", service)
        self.assertIn("ping_close();", service)
        self.assertIn("asynchronous_close();", service)
        self.assertIn("sdio_runtime_scan_cancel();", service)
        self.assertIn("ping_generation++", service)
        self.assertIn("time_generation++", service)
        self.assertIn("(uint32_t)(uintptr_t)arg != ping_generation", service)
        self.assertIn("(uint32_t)(uintptr_t)arg != time_generation", service)
        installer = (ROOT / "pi-side/install_bundle.sh").read_text()
        self.assertIn("service-range-online.patch", installer)
        range_patch = (
            ROOT / "pi-side/pi1mhz-516a267/patches/service-range-online.patch"
        ).read_text()
        self.assertIn("SERVICE_CMD_ELKWIFI_LAST  92u", range_patch)

    def test_installer_pins_reviewed_pi1mhz_commit(self) -> None:
        installer = (ROOT / "pi-side/install_bundle.sh").read_text()
        upstream = (ROOT / "pi-side/upstream.env").read_text()
        verifier = (ROOT / "pi-side/check_upstream.sh").read_text()
        self.assertIn("expected_upstream=$PI1MHZ_UPSTREAM_COMMIT", installer)
        self.assertIn("PI1MHZ_VERIFY_REMOTE:-1", installer)
        self.assertIn(
            "PI1MHZ_UPSTREAM_COMMIT=831b80675b2f4b2f10a85833fa807e4c572087c9",
            upstream,
        )
        self.assertIn("PI1MHZ_UPSTREAM_BRANCH=master", upstream)
        self.assertIn("PI1MHZ_UPSTREAM_VERIFIED=2026-08-31", upstream)
        self.assertIn("git ls-remote --symref", verifier)

        rom_installer = (ROOT / "rom-side/build_rom.sh").read_text()
        zero_length_patch = (
            ROOT / "rom-side/elkwifi-0.23/patches/wicfs-zero-length.patch"
        ).read_text()
        self.assertIn("zero-byte CFS files have no data byte to fetch", zero_length_patch)
        self.assertIn("JSR\tadjlen", zero_length_patch)
        self.assertIn("JSR\tchskip", zero_length_patch)
        self.assertIn('"$overlay_dir/uef.asm"', rom_installer)
        self.assertLess(
            rom_installer.index("wicfs-callable-init.patch"),
            rom_installer.index("wicfs-rewind.patch"),
        )
        self.assertLess(
            rom_installer.index("wicfs-private-workspace.patch"),
            rom_installer.index("wicfs-basic-host.patch"),
        )

    def test_local_uef_import_uses_current_filing_system_and_wicfs(self) -> None:
        source = (ROOT / "rom-side/elkwifi-0.23/overlay/uef.asm").read_text()
        command_patch = (
            ROOT / "rom-side/elkwifi-0.23/patches/uef-command.patch"
        ).read_text()
        callable_patch = (
            ROOT / "rom-side/elkwifi-0.23/patches/wicfs-callable-init.patch"
        ).read_text()
        self.assertIn('equs "UEF"', command_patch)
        self.assertIn('equs "QUPRUN"', command_patch)
        self.assertIn('equs "QR"', command_patch)
        self.assertIn('include "uef.asm"', command_patch)
        self.assertIn("OSFIND = &FFCE", source)
        self.assertIn("OSBGET = &FFD7", source)
        self.assertNotIn("read_cli_param", source)
        self.assertNotIn("strbuf", source)
        self.assertIn("lda (line),y", source)
        self.assertIn("lda #&40\n jsr OSFIND", source)
        self.assertIn("jsr OSBGET", source)
        self.assertIn("jsr uef_select_length", source)
        self.assertNotIn("sta &FCFD", source)
        self.assertNotIn("sta &FCFE", source)
        self.assertIn("sta pagereg", source)
        self.assertIn("sta &FDFE", source)
        self.assertIn("sta &FDFF", source)
        self.assertIn("cmp #&FE", source)
        self.assertIn("jsr check_esc", source)
        self.assertIn('equs "*QUPRUN",&0D', source)
        self.assertIn('equs "*REWIND",&0D', source)
        self.assertIn('equs "CHAIN "', source)
        self.assertLess(source.index(".uef_launch"), source.index(".uef_run_launch"))
        initial_launch = source.split(".uef_launch", 1)[1].split(
            ".uef_run_launch", 1
        )[0]
        self.assertNotIn('equs "REWIND"', initial_launch)
        self.assertIn('equs "PAGE=&0E00"', initial_launch)
        self.assertIn('equs "NEW"', initial_launch)
        self.assertIn("jsr wicfs_install", source)
        self.assertIn("JSR\twicfs_install", callable_patch)
        self.assertIn("JMP\tcall_claimed", callable_patch)
        self.assertIn("return to the command-specific wrapper", callable_patch)
        # OSBYTE &EA is only a Tube-presence query.  Loading remains entirely
        # host-side and must never touch the Tube data-transfer registers.
        self.assertIn("lda #&EA", source)
        self.assertIn("jmp host_basic_cmd", source)
        basic_host = (
            ROOT / "rom-side/elkwifi-0.23/patches/wicfs-basic-host.patch"
        ).read_text()
        self.assertIn(".upv_basic_match", basic_host)
        self.assertIn("JMP\thost_enter_basic", basic_host)
        self.assertNotIn('equs "TUBE OFF"', source)
        for register in range(0xFEE0, 0xFEE8):
            self.assertNotIn(f"&{register:04X}", source.upper())

    def test_date_time_and_ping_use_pi_network_services(self) -> None:
        driver = (ROOT / "rom-side/elkwifi-0.23/overlay/service_driver.asm").read_text()
        time_source = (ROOT / "rom-side/elkwifi-0.23/overlay/time.asm").read_text()
        self.assertIn("drv_svc_ping = 88", driver)
        self.assertIn("drv_svc_datetime = 89", driver)
        self.assertIn("service_driver_ping_copy", driver)
        self.assertIn("service_driver_datetime", driver)
        self.assertNotIn("acornelectron.nl", time_source)
        self.assertIn("jsr service_driver_time", time_source)
        self.assertIn("jsr service_driver_date", time_source)
        self.assertNotIn("drv_compat_timeout", driver)


if __name__ == "__main__":
    unittest.main()
