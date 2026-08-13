import pathlib
import unittest
import zipfile


ROOT = pathlib.Path(__file__).resolve().parents[1]


class MergedRepositoryTest(unittest.TestCase):
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
        }
        for name, command in expected.items():
            self.assertIn(f"SEC_CMD_{name} = {command}", asm)
            self.assertIn(f"SEC_CMD_{name}", backend)
            self.assertIn(f"NTS_SEC_{name}", header)
        self.assertIn("#define SEC_CMD_CAPS       94u", backend)
        self.assertIn("#define SEC_CMD_RANDOM     95u", backend)

    def test_secure_wrapper_cannot_strand_a_request_across_reset(self) -> None:
        wrapper = (
            ROOT / "pi-side/pi1mhz-516a267/overlay/src/secure_service.c"
        ).read_text()
        command = wrapper.split("void secure_service_command", 1)[1].split(
            "static void secure_poll", 1
        )[0]
        self.assertNotIn("if (pending)", command)
        self.assertIn("Always latch the newest command", command)
        self.assertIn("pending_cp = command_pointer", command)
        self.assertIn("Pi1MHz_MemoryWrite(addr, SEC_BUSY)", command)

    def test_secure_capabilities_complete_without_polling(self) -> None:
        wrapper = (
            ROOT / "pi-side/pi1mhz-516a267/overlay/src/secure_service.c"
        ).read_text()
        command = wrapper.split("void secure_service_command", 1)[1].split(
            "static void secure_poll", 1
        )[0]
        caps = command.split("if (Pi1MHz->JIM_ram[command_pointer] == NTS_SEC_CAPS)", 1)[1]
        caps = caps.split("pending_cp = command_pointer", 1)[0]
        self.assertIn("command[1] = 1u", caps)
        self.assertIn("command[2] = 1u", caps)
        self.assertIn("command[3] = capability_features", caps)
        self.assertIn("command[6] = capability_managed_ssh", caps)
        self.assertIn("Pi1MHz_MemoryWrite(addr, NTS_OK)", caps)
        self.assertIn("return", caps)

        init = wrapper.split("void secure_service_init", 1)[1]
        self.assertNotIn("pending = false", init)
        self.assertNotIn("pending_cp = 0u", init)
        self.assertNotIn("pending_addr = 0u", init)
        self.assertIn("Do not clear a", init)
        self.assertIn("reset_pending = true", init)
        self.assertIn("capability_features = 7u", wrapper)
        self.assertIn("capability_managed_ssh = 1u", wrapper)

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
        self.assertIn('"$bundle/host-tools/nettools.ssd"', installer)

        bundled = ROOT / "build/pi1mhz-all/host-tools/nettools.ssd"
        built = ROOT / "host-tools/build/nettools.ssd"
        self.assertTrue(bundled.is_file())
        self.assertEqual(bundled.read_bytes(), built.read_bytes())

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
        self.assertIn("firmware/Pi1MHz/ElkWiFi.rom", patch)
        self.assertIn("GIT binary patch", patch)

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
        self.assertIn("ap5_tube_run_host_cycles(oldcycs)", tube_patch)
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


if __name__ == "__main__":
    unittest.main()
