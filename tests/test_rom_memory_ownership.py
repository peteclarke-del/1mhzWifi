"""The network ROM may only write memory a sideways ROM owns.

This ran nowhere until Pi1MHz V1.35. dp111 wrote the check against the copy of
this ROM he merged, and it found what nothing here had: the ROM kept its
scratch at &0900, &0A00 and &0D90. The first is the RS423 output buffer, the
second the CFS/RFS input buffer, and the third runs into the EXTENDED VECTOR
TABLE at &0D9F - `drv_uef_generation_hi` was being stored at &0DAF, four bytes
into it. Corrupting an extended vector kills the next OS call made through a
claimed vector, which is a hang on a Master with vector-claiming ROMs, and a
*FX3,1 serial redirect died as soon as any command ran.

The workspace now lives in the image, so these tests pin the property rather
than the addresses: the checker is the authority and this makes it run.
"""

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "rom-side/check_rom_memory.py"
SRC = ROOT / "rom-side/1mhz-wifi/src"


def run(root: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECKER), root],
        capture_output=True, text=True, cwd=ROOT,
    )


class RomMemoryOwnershipTest(unittest.TestCase):
    def test_the_network_rom_writes_only_memory_it_owns(self) -> None:
        result = run("1mhzwifi.asm")
        self.assertEqual(
            result.returncode, 0,
            f"{result.stdout}{result.stderr}",
        )
        self.assertIn("ROM MEMORY OK", result.stdout)

    def test_the_workspace_is_in_the_image_not_in_os_memory(self) -> None:
        machine = (SRC / "machine.asm").read_text()
        for name, address in (("heap", "&BE00"), ("strbuf", "&BF00"),
                              ("ws_base", "&BDDE")):
            self.assertRegex(machine, rf"{name}\s+= {address}")
        # The three addresses this used to use, each owned by the OS.
        for retired in ("= &900", "= &A00", "= &D90"):
            self.assertNotIn(retired, machine)

    def test_a_read_only_image_refuses_commands_instead_of_corrupting_ram(self) -> None:
        """The workspace is in the image, so a real ROM has nowhere to put it.

        Both roots probe the image at reset and record the answer; the command
        entry tests it and raises rather than writing into whatever the OS has
        at &BDDE in a real ROM, which is nothing it owns.
        """
        for root in ("1mhzwifi.asm", "1mhzwicfs.asm"):
            source = (SRC / root).read_text()
            with self.subTest(root=root):
                self.assertIn("bit ws_flag", source)
                self.assertIn("command_declined", source)
                # The probe writes both a value and its complement, so a bus
                # that floats high cannot pass it.
                self.assertIn("lda #&A5", source)
                self.assertIn("lda #&5A", source)

    def test_the_eprom_build_claims_its_workspace_and_owns_what_it_writes(self) -> None:
        """A real ROM has no writable image, so it asks the OS instead.

        WS_IN_IMAGE=0 builds the same sources with the three bases pointing at
        host RAM claimed at service call 1. The addresses stay assembly-time
        constants, which is what lets one set of sources serve both builds
        without reaching ninety-odd derived symbols through a pointer.
        """
        result = subprocess.run(
            [sys.executable, str(CHECKER), "1mhzwifi.asm", "--eprom"],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, f"{result.stdout}{result.stderr}")
        self.assertIn("ROM MEMORY OK", result.stdout)

        machine = (SRC / "machine.asm").read_text()
        self.assertIn("IF WS_IN_IMAGE", machine)
        self.assertIn("ws_base    = WS_HOST_PAGE * &100", machine)
        for root in ("1mhzwifi.asm", "1mhzwicfs.asm"):
            source = (SRC / root).read_text()
            with self.subTest(root=root):
                # Claims its pages by raising Y, and only when the range it
                # needs is still free.
                self.assertIn("cpy #WS_HOST_PAGE", source)
                self.assertIn("ldy #ws_host_end", source)
                # Claimed host RAM is not ours the way an image is, so the
                # command entry checks a signature as well as the flag.
                self.assertIn("ws_signature", source)
                self.assertIn("cmp #ws_signature_lo", source)
                # Nothing is written before the claim succeeds.
                self.assertIn("bcc autorun_claim_done", source)

    def test_the_two_eprom_images_claim_different_pages(self) -> None:
        """Both fitted together must not land on the same workspace.

        Each image's workspace is a fixed range, so two of them sharing a page
        would have the second silently writing over the first. The build gives
        them separate ranges; this pins that they stay separate and three
        pages apart.
        """
        build = (ROOT / "rom-side/build_rom.sh").read_text()
        pages = {}
        for name in ("ws_wifi_page", "ws_wicfs_page"):
            line = [l for l in build.splitlines() if l.startswith(f"{name}=")]
            self.assertEqual(len(line), 1, name)
            pages[name] = int(line[0].split("=", 1)[1], 16)
        self.assertGreaterEqual(
            abs(pages["ws_wicfs_page"] - pages["ws_wifi_page"]), 3,
            "each image claims three pages, so the two ranges would overlap",
        )

    def test_a_long_command_name_is_still_separated_from_its_help(self) -> None:
        """*DISCONNECT is ten characters and fills the description column.

        The walk pads a name out to column eleven and then prints the
        description. A name that already reaches that column was given no
        padding at all, so the emulator showed
        "DISCONNECTClose the connection". Names this long are rare, which is
        why the source list it replaced never hit it.
        """
        for root in ("1mhzwifi.asm", "1mhzwicfs.asm"):
            source = (SRC / root).read_text()
            with self.subTest(root=root):
                pad = source.split(".phd_pad", 1)[1].split(".phd_desc", 1)[0]
                self.assertIn("bcc phd_pad_one", pad)
                self.assertEqual(
                    pad.count("jsr OSWRCH"), 2,
                    "one space for a name that fills the column, and the "
                    "padding loop for one that does not",
                )

    def test_no_command_entry_raises_an_error_from_the_bank(self) -> None:
        """A BRK cannot carry its message inline in a sideways ROM.

        The MOS pages the ROM out before reading the error text back, so the
        message came from whatever ROM was paged in instead: on an Electron
        that is BASIC, and the screen filled with its keyword table. The entry
        declines the service call instead, which also stops it answering for
        every unrecognised command on the machine rather than only this ROM's.
        """
        for root in ("1mhzwifi.asm", "1mhzwicfs.asm"):
            source = (SRC / root).read_text()
            with self.subTest(root=root):
                self.assertNotIn("no_swr_error", source)
                entry = source.split("\n.command ", 1)[1].split(
                    ".command_have_ws", 1)[0]
                self.assertIn("command_declined", entry)
                self.assertNotRegex(entry, r"(?m)^\s+brk\b")
                declined = entry.split(".command_declined", 1)[1]
                self.assertIn("lda #4", declined)
                self.assertIn("rts", declined)
        # And the reason is stated once at reset, where the text is readable.
        wifi = (SRC / "1mhzwifi.asm").read_text()
        self.assertIn("needs sideways RAM", wifi)
        banner = wifi.split('equs "1MHz-WiFi 0.1.67"', 1)[1].split(
            ".autorun_ws_ready", 1)[0]
        self.assertIn("bit ws_flag", banner)

    def test_the_eprom_pages_ascend_in_service_call_order(self) -> None:
        """The MOS services bank 15 downwards, so the ranges must ascend.

        Each EPROM image claims a fixed range only if service call 1 says it
        is still free, so the image serviced first has to be the one wanting
        the lower pages. Measured on the emulator: PAGE is &0E00 with neither
        fitted, &1100 with the network image alone, and &1400 with both, but
        only when the network image sits in the higher bank. The other way
        round the filing system claims first, takes Y past &0E00, and the
        network image declines with the reason on screen.
        """
        build = (ROOT / "rom-side/build_rom.sh").read_text()
        pages = {}
        for name in ("ws_wifi_page", "ws_wicfs_page"):
            line = [l for l in build.splitlines() if l.startswith(f"{name}=")]
            self.assertEqual(len(line), 1, name)
            pages[name] = int(line[0].split("=", 1)[1], 16)
        # The network image is the one that must be serviced first, so it
        # takes the lower range.
        self.assertLess(pages["ws_wifi_page"], pages["ws_wicfs_page"])
        self.assertEqual(
            pages["ws_wicfs_page"] - pages["ws_wifi_page"], 3,
            "each image claims three pages, so they would overlap or leave a "
            "hole the other cannot claim across",
        )
        # And both images say so when the claim does not succeed, rather than
        # declining in silence.
        for root, who in (("1mhzwifi.asm", "1MHz-WiFi"),
                          ("1mhzwicfs.asm", "1MHz-WiCFS")):
            source = (SRC / root).read_text()
            with self.subTest(root=root):
                self.assertIn(f'"{who} needs sideways RAM"', source
                              .replace('equs " needs sideways RAM"',
                                       f'equs "{who} needs sideways RAM"'))

    def test_every_command_in_the_table_has_a_help_line(self) -> None:
        """*HELP is walked out of the command table, so it cannot drift.

        It used to be a hand-maintained list beside the table, and it had:
        *DISCONNECT was in the table with no help line, and the filing system
        ROM documented three of its eight commands.
        """
        for root in ("1mhzwifi.asm", "1mhzwicfs.asm"):
            source = (SRC / root).read_text()
            with self.subTest(root=root):
                table = source.split(".commandtable", 1)[1].split(
                    "command_x6", 1)[0]
                names = [line.split('"')[1] for line in table.splitlines()
                         if "equs" in line]
                descriptions = source.split(".help_descriptions", 1)[1].split(
                    ".print_help_end", 1)[0]
                lines = [line for line in descriptions.splitlines()
                         if "equs" in line]
                self.assertEqual(
                    len(names), len(lines),
                    f"{len(names)} commands but {len(lines)} help lines",
                )
                self.assertIn("help_descriptions", source)
                self.assertIn("lda #<commandtable", source)
                # A bare address ends the table, so an entry that loses its
                # name ends it early and every command after it becomes
                # unreachable while still being in the image. The last entry
                # is the only one allowed to be a bare address.
                entries = [line for line in table.splitlines() if line.strip()
                           and not line.lstrip().startswith("\\")]
                addresses = [line for line in entries if "equb >" in line]
                self.assertEqual(
                    len(addresses), len(names) + 1,
                    "every named entry needs one address, plus the bare "
                    "address that terminates the table",
                )


if __name__ == "__main__":
    unittest.main()
