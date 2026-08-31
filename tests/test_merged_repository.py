import pathlib
import re
import unittest
import zipfile


ROOT = pathlib.Path(__file__).resolve().parents[1]


class MergedRepositoryTest(unittest.TestCase):
    def test_production_sources_do_not_contain_title_specific_workarounds(self) -> None:
        """WiCFS fixes must describe formats and MOS contracts, never titles."""
        title_names = (
            "arcadians", "bumblebee", "elite", "frak", "hopper", "mrwiz",
            "planb", "repton", "thrust", "zalaga",
        )
        source_suffixes = {".asm", ".c", ".h", ".py", ".sh"}
        roots = (
            ROOT / "rom-side/elkwifi-0.23/overlay",
            ROOT / "rom-side/elkwifi-0.23/patches",
            ROOT / "pi-side/pi1mhz-516a267/overlay",
            ROOT / "pi-side/pi1mhz-516a267/patches",
            ROOT / "emulator/pi1mhz-mailbox/src",
        )
        for source_root in roots:
            for path in source_root.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in source_suffixes:
                    continue
                text = path.read_text(errors="replace").lower()
                for title in title_names:
                    self.assertNotIn(title, text, f"{title} workaround in {path}")

    def test_adjacent_register_fix_is_taken_from_upstream(self) -> None:
        """The adjacent-byte guarantee is upstream's to keep, not ours.

        One VPU word holds two adjacent bus addresses, so writing one byte must
        not revert its neighbour: a reverted SCSI data byte corrupts a transfer
        and a reverted status byte leaves BSY set, which is the post-BREAK VFS
        wedge. This project carried its own fix, which rebuilt the neighbour by
        reading the live VPU window instead of the ARM shadow. dp111 then fixed
        the same defect differently, by masking FIQs around the compose so the
        read and the two stores cannot be split.

        Upstream's fix is sufficient: the FIQ handler in src/FIQ.s dispatches to
        callbacks that write through Pi1MHz_MemoryWrite, so the shadow is always
        maintained and only the interleaving was ever the hazard. Carrying a
        rival fix in a file upstream actively changes costs a conflict at every
        update, so ours was dropped. This test keeps that decision honest: it
        fails if a divergent fix reappears, or if the pin moves back before the
        commit that carries upstream's.
        """
        installer = (ROOT / "pi-side/install_bundle.sh").read_text()
        patches = ROOT / "pi-side/pi1mhz-516a267/patches"
        self.assertFalse(
            (patches / "bus-window-adjacent-preservation.patch").exists(),
            "the superseded local fix is back; upstream owns this function",
        )
        self.assertNotIn("bus-window-adjacent-preservation.patch", installer)
        for patch in sorted(patches.glob("*.patch")):
            self.assertNotIn(
                "Preserve the adjacent byte from the authoritative VPU bus",
                patch.read_text(errors="replace"),
                f"{patch.name} reintroduces the local adjacent-byte fix",
            )
        upstream_env = (ROOT / "pi-side/upstream.env").read_text()
        self.assertIn(
            "PI1MHZ_UPSTREAM_COMMIT=6b3b88df34172fbaeee927c24d9d5c937710400c",
            upstream_env,
            "the pin must include dp111's FIQ-masked adjacent-byte fix",
        )

    def test_secure_command_allocation_is_consistent(self) -> None:
        asm = (ROOT / "host-tools/src/common/pi1mhz_secure.asm").read_text()
        backend = (
            ROOT / "emulator/pi1mhz-mailbox/src/pi1mhz_net_backend.c"
        ).read_text()
        header = (
            ROOT / "pi-side/pi1mhz-516a267/overlay/src/secure_service_core.h"
        ).read_text()
        expected = {
            "CAPS": 94,
            "RANDOM": 95,
            "SSH_OPEN": 96,
            "SSH_READ": 97,
            "SSH_WRITE": 98,
            "SSH_CLOSE": 99,
            "SSH_PASSWORD": 100,
            "SFTP_OPEN": 101,
            "SFTP_PWD": 102,
            "SFTP_CD": 103,
            "SFTP_LS": 104,
            "SFTP_DELETE": 105,
            "SFTP_MKDIR": 106,
            "SFTP_RMDIR": 107,
            "SFTP_GET_OPEN": 108,
            "SFTP_GET_READ": 109,
            "SFTP_PUT_OPEN": 110,
            "SFTP_PUT_WRITE": 111,
            "SFTP_TRANSFER_CLOSE": 112,
            "SFTP_CLOSE": 113,
        }
        for name, command in expected.items():
            self.assertIn(f"SEC_CMD_{name} = {command}", asm)
            self.assertIn(f"SEC_CMD_{name}", backend)
            self.assertIn(f"NTS_SEC_{name}", header)
        self.assertIn("#define SEC_CMD_CAPS       94u", backend)
        self.assertIn("#define SEC_CMD_RANDOM     95u", backend)

    def test_secure_wrapper_cannot_strand_deferred_request_across_reset(self) -> None:
        wrapper = (
            ROOT / "pi-side/pi1mhz-516a267/overlay/src/secure_service.c"
        ).read_text()
        command = wrapper.split("void secure_service_command", 1)[1].split(
            "static void secure_poll", 1
        )[0]
        self.assertIn("NTS_SEC_CAPS", command)
        self.assertIn("Pi1MHz_MemoryWrite(addr, NTS_OK)", command)
        self.assertIn("Always latch the newest command", command)
        self.assertIn("pending_cp = command_pointer", command)
        self.assertIn("Pi1MHz_MemoryWrite(addr, SEC_BUSY)", command)

    def test_ftp_command_allocation_and_host_boundary_are_consistent(self) -> None:
        header = (
            ROOT / "pi-side/pi1mhz-516a267/overlay/src/ftp_service.h"
        ).read_text()
        service = (
            ROOT / "pi-side/pi1mhz-516a267/overlay/src/ftp_service.c"
        ).read_text()
        rom = (ROOT / "rom-side/elkwifi-0.23/overlay/ftp.asm").read_text()
        emulator = (
            ROOT / "emulator/pi1mhz-mailbox/src/pi1mhz_ftp.c"
        ).read_text()
        for name, number in {
            "OPEN": 114, "EXEC": 115, "READ": 116, "WRITE": 117,
            "CLOSE": 118, "CANCEL": 119,
        }.items():
            self.assertIn(f"FTP_CMD_{name}", header)
            self.assertRegex(
                rom,
                rf"ftp_cmd_{name.lower()}\s*=\s*{number}",
            )
        self.assertIn("FTP_SCRATCH_OFFSET 0xfff100u", service)
        self.assertIn("FTP_SCRATCH 0xfff100u", emulator)
        self.assertIn("ftp_OSFIND", rom)
        self.assertNotIn("Tube", "\n".join(
            line for line in rom.splitlines()
            if not line.lstrip().startswith("\\")
        ))

    def test_secure_capabilities_do_not_depend_on_poll_registration(self) -> None:
        wrapper = (
            ROOT / "pi-side/pi1mhz-516a267/overlay/src/secure_service.c"
        ).read_text()
        caps = wrapper.split("static void secure_write_capabilities", 1)[1]
        caps = caps.split("void secure_service_command", 1)[0]
        self.assertIn("command[1] = 1u", caps)
        self.assertIn("command[2] = 1u", caps)
        self.assertIn("command[3] = capability_features", caps)
        self.assertIn("command[6] = capability_managed_ssh", caps)
        command = wrapper.split("void secure_service_command", 1)[1].split(
            "static void secure_poll", 1
        )[0]
        capability_path = command.split("NTS_SEC_CAPS", 1)[1].split("return;", 1)[0]
        self.assertIn("secure_write_capabilities", capability_path)
        self.assertIn("Pi1MHz_MemoryWrite(addr, NTS_OK)", capability_path)
        self.assertNotIn("SEC_BUSY", capability_path)

    def test_fixed_services_replace_completed_selector_echo(self) -> None:
        patch = (
            ROOT / "pi-side/pi1mhz-516a267/patches/deterministic-service-dispatch.patch"
        ).read_text()
        installer = (ROOT / "pi-side/install_bundle.sh").read_text()
        fixed = patch.split("Built-in ABI ranges", 1)[1].split(
            "for (unsigned int i", 1
        )[0]
        self.assertIn("net_service_command(command_pointer, addr, data)", fixed)
        self.assertIn("elkwifi_service_command(command_pointer, addr, data)", fixed)
        self.assertIn("secure_service_command(command_pointer, addr, data)", fixed)
        self.assertIn("follow the standard selector echo", patch)
        self.assertNotIn("-   Pi1MHz_MemoryWrite(addr, data)", patch)
        self.assertIn("fixed_echo_seen[0]", patch)
        self.assertNotIn("!fixed_echo_seen[0]", patch)
        self.assertNotIn("services-result-publication.patch", installer)

    def test_host_nettools_mask_irq_while_using_shared_jim_cursor(self) -> None:
        net = (ROOT / "host-tools/src/common/pi1mhz_net.asm").read_text()
        secure = (ROOT / "host-tools/src/common/pi1mhz_secure.asm").read_text()
        ssh = (ROOT / "host-tools/src/ssh.asm").read_text()
        begin = net.split(".net_begin", 1)[1].split(".net_dispatch", 1)[0]
        dispatch = net.split(".net_dispatch_start", 1)[1].split("RTS", 1)[0]
        self.assertIn("SEI", begin)
        self.assertIn("STA net_saved_p", begin)
        self.assertIn("LDA net_saved_p", dispatch)
        self.assertIn("PLP", dispatch)
        for label in (".net_copy_rx_to_host", ".net_copy_selected_string"):
            block = net.split(label, 1)[1].split("RTS", 1)[0]
            self.assertIn("SEI", block)
            self.assertIn("PLP", block)
        for label in (
            ".secure_copy_url", ".secure_ssh_write", ".secure_ssh_password"
        ):
            block = secure.split(label, 1)[1]
            self.assertIn("SEI", block)
            self.assertIn("PLP", block)
        fingerprint = ssh.split(".ssh_confirm_host_key", 1)[1].split(
            ".ssh_print_fingerprint", 1
        )[0]
        self.assertIn("SEI", fingerprint)
        self.assertIn("JSR net_copy_selected_string", fingerprint)
        self.assertIn("PLP", fingerprint)

    def test_elkwifi_wrapper_discards_abandoned_request_on_reset(self) -> None:
        wrapper = (
            ROOT / "pi-side/pi1mhz-516a267/overlay/src/elkwifi_service.c"
        ).read_text()
        init = wrapper.split("void elkwifi_service_init", 1)[1]
        self.assertIn("request_pending = false", init)
        self.assertIn("request_cancel = false", init)
        self.assertIn("host reset abandons", init)
        self.assertIn("_disable_interrupts_cspr()", init)
        self.assertIn("_restore_cpsr(cpsr)", init)

    def test_merged_components_have_central_build_owners(self) -> None:
        required = [
            "host-tools/Makefile",
            "host-tools/src/ssh.asm",
            "host-tools/tests/test_emulated_clients.py",
            "emulator/pi1mhz-mailbox/Makefile",
            "emulator/pi1mhz-mailbox/integrations/elkulator/install.sh",
            "pi-side/tests/run_secure_build.sh",
            "pi-side/upstream/1mhzwifi-pi1mhz.patch",
            "docs/nettools-merge.md",
            "rom-side/elkwifi-0.23/TECHNICAL.md",
            "pi-side/pi1mhz-516a267/TECHNICAL.md",
            "emulator/pi1mhz-mailbox/integrations/elkulator/TECHNICAL.md",
            "scripts/package_patch_kits.sh",
        ]
        for relative in required:
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_each_upstream_patch_kit_is_self_describing(self) -> None:
        kits = (
            ROOT / "rom-side",
            ROOT / "pi-side",
            ROOT / "emulator/pi1mhz-mailbox",
        )
        for kit in kits:
            self.assertTrue((kit / "README.md").is_file(), kit)
        self.assertTrue((kits[0] / "build_rom.sh").is_file())
        self.assertTrue((kits[1] / "install_bundle.sh").is_file())
        self.assertTrue(
            (kits[2] / "integrations/elkulator/install.sh").is_file()
        )

        packager = (ROOT / "scripts/package_patch_kits.sh").read_text()
        for name in ("rom-side", "pi-side", "emulator/pi1mhz-mailbox"):
            self.assertIn(name, packager)

    def test_release_bundle_pairs_host_tools_with_firmware(self) -> None:
        installer = (ROOT / "pi-side/install_bundle.sh").read_text()
        self.assertIn('make -C "$root_dir/host-tools" all', installer)
        self.assertIn('"$bundle_staged/host-tools/nettools.ssd"', installer)
        self.assertIn('rm -rf -- "$bundle"', installer)
        self.assertIn('mv "$bundle_staged" "$bundle"', installer)

        bundled = ROOT / "build/pi1mhz-all/host-tools/nettools.ssd"
        built = ROOT / "host-tools/build/nettools.ssd"
        self.assertTrue(bundled.is_file())
        self.assertEqual(bundled.read_bytes(), built.read_bytes())
        bundled_rom = ROOT / "build/pi1mhz-all/Pi1MHz/1mhz-wifi.rom"
        compatibility_link = ROOT / "build/elkwifi_pi1mhz.rom"
        self.assertTrue(bundled_rom.is_file())
        self.assertTrue(compatibility_link.is_symlink())
        self.assertEqual(compatibility_link.resolve(), bundled_rom.resolve())
        with zipfile.ZipFile(ROOT / "build/pi1mhz-all-hardware-test.zip") as archive:
            self.assertEqual(
                archive.read("pi1mhz-all/Pi1MHz/1mhz-wifi.rom"),
                bundled_rom.read_bytes(),
            )

    def test_packaged_kernels_have_matching_recovery_revisions(self) -> None:
        pattern = re.compile(
            rb"Pi1MHz ElkWiFi 0\.1\.67, kernel "
            rb"(V1\.30-114-g6b3b88d-dirty\.[0-9a-f]{8})"
        )
        revisions = []
        for name in ("kernel.img", "kernel7.img"):
            image = (ROOT / "build/pi1mhz-all" / name).read_bytes()
            match = pattern.search(image)
            self.assertIsNotNone(match, name)
            revisions.append(match.group(1))
        self.assertEqual(revisions[0], revisions[1])

    def test_release_archive_has_one_installable_top_level(self) -> None:
        archive = ROOT / "build/pi1mhz-all-hardware-test.zip"
        with zipfile.ZipFile(archive) as bundle:
            names = bundle.namelist()
        self.assertTrue(names)
        self.assertTrue(all(name.startswith("pi1mhz-all/") for name in names))
        self.assertFalse(any(name.startswith("build/") for name in names))

    def test_maintainer_patch_embeds_the_matched_host_rom(self) -> None:
        patch = (ROOT / "pi-side/upstream/1mhzwifi-pi1mhz.patch").read_text(
            errors="replace"
        )
        self.assertIn("firmware/Pi1MHz/1mhz-wifi.rom", patch)
        self.assertIn("GIT binary patch", patch)
        self.assertIn("Pi1MHz ElkWiFi 0.1.67, kernel", patch)
        self.assertNotIn("Pi1MHz ElkWiFi 0.1.52, kernel", patch)
        # The RNG word wait is bounded by a named deadline rather than a
        # literal, so this pins the mechanism and not one magic number.
        self.assertIn("RNG_WORD_DEADLINE_US", patch)
        self.assertIn("RPI_GetSystemTime() - started_us >= RNG_WORD_DEADLINE_US", patch)
        self.assertIn("exact MENU TITLES transfer shape", patch)
        self.assertIn("TITLES reaches bounded EOF", patch)

    def test_fixed_service_children_cannot_consume_dynamic_slots(self) -> None:
        dispatch = (
            ROOT
            / "pi-side/pi1mhz-516a267/patches/deterministic-service-dispatch.patch"
        ).read_text()
        installer = (ROOT / "pi-side/install_bundle.sh").read_text()
        for symbol in ("net_service_init", "elkwifi_service_init", "secure_service_init"):
            self.assertIn(symbol, dispatch)
        self.assertIn("fixed_services_child", dispatch)
        self.assertIn("if (fixed_services_child)", dispatch)
        self.assertIn("grep -q 'fixed_services_child'", installer)

    def test_retired_layout_is_not_referenced(self) -> None:
        retired = (
            "patches/pi1mhz-firmware",
            "patches/pi1mhz-mailbox-emulator",
            "pi1mhz-v1.30",
        )
        scanned = [
            ROOT / "README.md",
            ROOT / "TODO.md",
            ROOT / "Makefile",
            *ROOT.joinpath("docs").glob("*.md"),
            *ROOT.joinpath("host-tools").rglob("*.md"),
            *ROOT.joinpath("host-tools").rglob("Makefile"),
            *ROOT.joinpath("pi-side").glob("*.sh"),
        ]
        for path in scanned:
            text = path.read_text()
            for value in retired:
                if path.name == "nettools-merge.md":
                    continue
                self.assertNotIn(value, text, f"{value} in {path}")

    def test_elkulator_rom_layout_support_is_generic(self) -> None:
        patch = (
            ROOT
            / "emulator/pi1mhz-mailbox/integrations/elkulator/elkulator.patch"
        ).read_text()
        installer = (
            ROOT
            / "emulator/pi1mhz-mailbox/integrations/elkulator/install.sh"
        ).read_text()
        autokeys = (
            ROOT
            / "emulator/pi1mhz-mailbox/integrations/elkulator/elkulator-autokeys.patch"
        ).read_text()
        elkwifi_main = (
            ROOT
            / "emulator/pi1mhz-mailbox/integrations/elkulator/elkulator-elkwifi-main.patch"
        ).read_text()
        tube_patch = (
            ROOT
            / "emulator/pi1mhz-mailbox/integrations/elkulator/elkulator-ap5-tube.patch"
        ).read_text()
        tube_elkwifi_patch = (
            ROOT
            / "emulator/pi1mhz-mailbox/integrations/elkulator/elkulator-ap5-tube-elkwifi.patch"
        ).read_text()
        tube_device = (
            ROOT
            / "emulator/pi1mhz-mailbox/integrations/elkulator/tube/ap5_tube.c"
        ).read_text()
        self.assertIn('printf("-ram number', patch)
        self.assertIn("if (bank >= 0 && bank < 16)", patch)
        self.assertIn("rombank_writable[rombank]", patch)
        self.assertIn("if (rombank_enabled[rombank])", patch)
        self.assertIn(
            "+                   legacy slot 0 and 1 cartridge mapping. */\n"
            "                 if (rombank_enabled[rombank])\n"
            "                     return rombanks[rombank][addr & 0x3fff];\n"
            "+                if (rombank==0) return cart0",
            patch,
        )
        self.assertIn('"$target/src/elk.h"', installer)
        self.assertIn("parse_scripted_keys", autokeys)
        self.assertIn("elkulator-autokeys.patch", installer)
        self.assertIn("elkulator-elkwifi-main.patch", installer)
        self.assertIn("reset6502() performs the MOS service-ROM scan", elkwifi_main)
        self.assertIn("if (rambanks[i]) enable_ram_n(i)", elkwifi_main)
        self.assertIn('printf("-tube6502 rom', tube_patch)
        self.assertIn("elkwifiname", tube_elkwifi_patch)
        self.assertIn("ap5_tube_sync_host_clock(cycles)", tube_patch)
        self.assertIn("address >= 0xfce0 && address <= 0xfcef", tube_device)
        self.assertIn("selected = value == 0 || value == 1", tube_device)
        self.assertIn("ula.host_status[0] &= FLOW_BOTH", tube_device)
        self.assertIn(
            "+                        ap5_tube_reset();\n"
            "                         reset6502();",
            tube_patch,
        )
        self.assertIn("elkulator-ap5-tube.patch", installer)
        self.assertIn("elkulator-ap5-tube-elkwifi.patch", installer)
        self.assertIn('ram[0x0d6d] |= 0x20', tube_device)
        self.assertIn("ap5_tube_prepare_cold_boot();", tube_patch)

    def test_emulator_preserves_pi1mhz_fat_service_for_mmfs(self) -> None:
        backend = (
            ROOT / "emulator/pi1mhz-mailbox/src/pi1mhz_net_backend.c"
        ).read_text()
        tests = (
            ROOT / "emulator/pi1mhz-mailbox/tests/test_live_backend.c"
        ).read_text()
        read_case = "command[0] == FAT_CMD_READ_SECTORS"
        write_case = "command[0] == FAT_CMD_WRITE_SECTORS"
        self.assertIn('#define FAT_CMD_READ_SECTORS  0u', backend)
        self.assertIn('#define FAT_CMD_WRITE_SECTORS 1u', backend)
        self.assertIn('getenv("PI1MHZ_SD_IMAGE")', backend)
        self.assertIn(read_case, backend)
        self.assertIn(write_case, backend)
        self.assertIn('setenv("PI1MHZ_SD_IMAGE"', tests)
        self.assertIn("Upstream MMFS uses commands 0/1", tests)

    def test_emulator_has_no_retired_menu_cache(self) -> None:
        backend = (
            ROOT / "emulator/pi1mhz-mailbox/src/pi1mhz_net_backend.c"
        ).read_text()
        tests = (
            ROOT / "emulator/pi1mhz-mailbox/tests/test_live_backend.c"
        ).read_text()
        self.assertNotIn("MENU_CACHE", backend)
        self.assertNotIn("PI1MHZ_MENU_CACHE_SECONDS", backend)
        self.assertNotIn('trace_line(backend, "CACHE_HIT"', backend)
        self.assertNotIn("opt-in MENU cache", tests)

    def test_release_artifacts_have_no_retired_menu_runtime(self) -> None:
        bundle = ROOT / "build/pi1mhz-all"
        rom = (bundle / "Pi1MHz/1mhz-wifi.rom").read_bytes()
        config = (bundle / "Pi1MHz/Pi1MHz.cfg").read_text().lower()
        for kernel_name in ("kernel.img", "kernel7.img"):
            kernel = (bundle / kernel_name).read_bytes().lower()
            self.assertNotIn(b"elkwifi_menu", kernel, kernel_name)
            self.assertNotIn(b"menu_cache", kernel, kernel_name)
        self.assertNotIn(b"menusrc", rom.lower())
        self.assertNotIn(b"acornelectron.nl/uefarchive/menu", rom.lower())
        self.assertNotIn("elkwifi_menu", config)

    def test_elkulator_exposes_opt_in_bus_evidence_trace(self) -> None:
        source = (
            ROOT
            / "emulator/pi1mhz-mailbox/integrations/elkulator/pi1mhz_elkulator.c"
        ).read_text()
        self.assertIn('getenv("PI1MHZ_BUS_TRACE")', source)
        self.assertIn("address >= 0xFEE0u && address <= 0xFEFFu", source)
        self.assertIn("address >= 0xFCFDu && address <= 0xFDFFu", source)
        self.assertIn("jim=%08X", source)
        self.assertIn("host_cycles += elapsed", source)


if __name__ == "__main__":
    unittest.main()
