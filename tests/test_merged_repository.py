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
            ROOT / "rom-side/1mhz-wifi/src",
            ROOT / "rom-side/inherited/patches",
            ROOT / "pi-side/pi1mhz/overlay",
            ROOT / "pi-side/pi1mhz/patches",
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
        patches = ROOT / "pi-side/pi1mhz/patches"
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
        # The pin has to be at or past the commit that carries upstream's fix.
        # Naming that commit exactly is what this used to do, and it then had
        # to be edited on every update, so it pins the release tag the fix
        # shipped in instead: install_bundle.sh refuses a checkout that does
        # not contain PI1MHZ_BASE_TAG, and dp111's fix predates V1.31.
        upstream_env = (ROOT / "pi-side/upstream.env").read_text()
        base_tag = next(
            line.split("=", 1)[1].strip()
            for line in upstream_env.splitlines()
            if line.startswith("PI1MHZ_BASE_TAG=")
        )
        self.assertRegex(base_tag, r"^V1\.\d+$")
        major, minor = base_tag[1:].split(".")
        self.assertEqual(major, "1")
        self.assertGreaterEqual(
            int(minor), 31,
            "the pin must include dp111's FIQ-masked adjacent-byte fix",
        )
        installer_text = (ROOT / "pi-side/install_bundle.sh").read_text()
        self.assertIn('merge-base --is-ancestor "$PI1MHZ_BASE_TAG" HEAD',
                      installer_text)

    def test_secure_command_allocation_is_consistent(self) -> None:
        asm = (ROOT / "host-tools/src/common/pi1mhz_secure.asm").read_text()
        backend = (
            ROOT / "emulator/pi1mhz-mailbox/src/pi1mhz_net_backend.c"
        ).read_text()
        # secure_service_core.h is Pi1MHz's now. The allocation it has to
        # agree with is the ROM's and the emulator's, which are both here, and
        # the 94..113 range upstream reserves for it in services.h - checked
        # against the real header by make test-pi-integration.
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
        self.assertEqual(min(expected.values()), 94)
        self.assertEqual(max(expected.values()), 113)
        self.assertIn("#define SEC_CMD_CAPS       94u", backend)
        self.assertIn("#define SEC_CMD_RANDOM     95u", backend)

    def test_the_secure_service_is_pi1mhz_s_to_maintain(self) -> None:
        """Its wrapper and ABI core were merged upstream by PR #20.

        They used to be overlay sources here and were checked by reading
        their text. Upstream's src/tests/secure drives the real dispatcher
        instead, and its copies have since gained bounds checks and a safe
        known_hosts write that these never got, so the right thing to assert
        now is that this package has stopped carrying them.
        """
        overlay = ROOT / "pi-side/pi1mhz/overlay/src"
        for merged in ("secure_service.c", "secure_service_core.c",
                       "secure_service_wolfssh.c"):
            self.assertFalse((overlay / merged).exists(), merged)
        installer = (ROOT / "pi-side/install_bundle.sh").read_text()
        # The build option that compiles them, which is OFF upstream because
        # Pi1MHz carries neither crypto library.
        self.assertIn("-DPI1MHZ_SSH=ON", installer)
        # Our fork of wolfSSH, and the fallback patches for a stock one.
        self.assertIn("peteclarke-del/wolfssh.git", installer)
        for patch in ("wolfssh-pi1mhz.patch", "wolfssh-sftp-client.patch"):
            self.assertTrue(
                (ROOT / "pi-side/pi1mhz/patches" / patch).is_file(), patch
            )

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

    def test_the_ftp_service_discards_an_abandoned_request_on_reset(self) -> None:
        """A host reset abandons the caller; the mailbox must not stay BUSY.

        The WiFi service's version of this went upstream with the service.
        The FTP service is still this package's, and has the same obligation:
        the Beeb that issued the command is gone, so anything latched has to
        be cleared rather than left for a machine that will never collect it.
        """
        service = (
            ROOT / "pi-side/pi1mhz/overlay/src/ftp_service.c"
        ).read_text()
        init = service.split("void ftp_service_init", 1)[1]
        self.assertIn("request_pending = false", init)
        self.assertIn("request_cancel = false", init)
        self.assertIn("services_register(FTP_CMD_FIRST, FTP_CMD_LAST", init)
        # And it has to be started, which the WiFi service's init now does.
        integration = (
            ROOT / "pi-side/pi1mhz/patches/services-integration.patch"
        ).read_text()
        self.assertIn("ftp_service_init();", integration)

    def test_merged_components_have_central_build_owners(self) -> None:
        required = [
            "host-tools/Makefile",
            "host-tools/src/ssh.asm",
            "host-tools/tests/test_emulated_clients.py",
            "emulator/pi1mhz-mailbox/Makefile",
            "emulator/pi1mhz-mailbox/integrations/elkulator/install.sh",
            "pi-side/tests/run_firmware_build.sh",
            "pi-side/upstream/1mhzwifi-pi1mhz.patch",
            "docs/nettools-merge.md",
            "rom-side/inherited/TECHNICAL.md",
            "pi-side/pi1mhz/TECHNICAL.md",
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
        # The trailing fingerprint hashes the overlay content, so pinning it in
        # full is what catches a kernel built before a Pi-side change. That is
        # not hypothetical: the bundle shipped kernels predating the FILEV
        # stamp repair, so a 0.1.67 ROM which expects the Pi to repair the
        # stream was packaged with kernels that could not, and every hash in
        # SHA256SUMS still verified because it pins whatever was committed.
        # A Pi-side change therefore requires a kernel rebuild before this
        # passes, which is the intended cost.
        pattern = re.compile(
            rb"Pi1MHz ElkWiFi 0\.1\.67, kernel "
            rb"(V1\.30-137-gd6ee4c3-dirty\.8aee109b)"
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
        # The two binaries a reviewer cannot rebuild from the patch text: the
        # host ROM the firmware has to match, and the pinned CYW43455 image.
        self.assertIn("firmware/Pi1MHz/1mhz-wifi.rom", patch)
        self.assertIn("firmware/Pi1MHz/wifi/brcmfmac43455-sdio.bin", patch)
        self.assertEqual(patch.count("GIT binary patch"), 2)

        # Everything else the patch should contain, and nothing it should
        # not. Pi1MHz V1.35 merged the WiFi, UEF and secure services, so a
        # patch still carrying their sources would be re-adding files that
        # are now upstream's, under older and less correct versions.
        touched = {
            line.split(" b/", 1)[1].strip()
            for line in patch.splitlines() if line.startswith("+++ b/")
        }
        for expected in (
            "src/ftp_service.c", "src/media_catalogue.c",
            "src/uef_service.c", "src/net_service.c", "src/services.h",
            "src/CMakeLists.txt", "src/wifi_service.c",
            "src/tests/uef/test_uef_filev.c",
            "firmware/Pi1MHz/Pi1MHz.cfg",
        ):
            self.assertIn(expected, touched, expected)
        for merged in (
            "src/elkwifi_service.c", "src/uef_normalize.c", "src/puff.c",
            "src/secure_service.c", "src/secure_service_core.c",
            "src/secure_service_wolfssh.c", "src/user_settings.h",
        ):
            self.assertNotIn(merged, touched, merged)
        self.assertNotIn("src/third_party", patch)

        # The configuration the host ROM cannot work without.
        self.assertIn("wifi_service_enable=1", patch)
        self.assertIn("net_enable=1", patch)


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
