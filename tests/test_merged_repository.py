import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class MergedRepositoryTest(unittest.TestCase):
    def test_secure_command_allocation_is_consistent(self) -> None:
        asm = (ROOT / "host-tools/src/common/pi1mhz_secure.asm").read_text()
        backend = (
            ROOT / "emulator/pi1mhz-mailbox/src/pi1mhz_net_backend.c"
        ).read_text()
        header = (
            ROOT / "pi-side/pi1mhz-8468a38/overlay/src/secure_service_core.h"
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
        ]
        for relative in required:
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_release_bundle_pairs_host_tools_with_firmware(self) -> None:
        installer = (ROOT / "pi-side/install_bundle.sh").read_text()
        self.assertIn('make -C "$root_dir/host-tools" all', installer)
        self.assertIn('"$bundle/host-tools/nettools.ssd"', installer)

        bundled = ROOT / "build/pi1mhz-all/host-tools/nettools.ssd"
        built = ROOT / "host-tools/build/nettools.ssd"
        self.assertTrue(bundled.is_file())
        self.assertEqual(bundled.read_bytes(), built.read_bytes())

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
