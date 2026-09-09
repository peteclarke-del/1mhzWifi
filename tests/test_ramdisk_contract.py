"""Structural checks on the RAM disk, from defects that reached the emulator.

Every one of these was found by running the ROM on a BBC B and a Master under
B-Em rather than by reading it, so each test names the symptom it prevents.
"""

import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "rom-side/1mhz-wifi/src/ramdisk.asm"
NET_ROOT = ROOT / "rom-side/1mhz-wifi/src/1mhzwifi.asm"


class RamDiskContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE.read_text()

    def equate(self, name: str) -> str:
        match = re.search(rf"^{name}\s*=\s*(\S+)", self.source, re.M)
        self.assertIsNotNone(match, f"{name} is not defined")
        return match.group(1)

    def test_entry_fields_are_contiguous_and_ordered(self) -> None:
        """The catalogue entry is read and written as one six byte run.

        rd_len was once placed well away from rd_load, so the run copied
        rd_start and rd_index instead and every file recorded a length of
        zero. The catalogue looked plausible and no file could be loaded.
        """
        offsets = {}
        for name in ("rd_load", "rd_exec", "rd_len"):
            value = self.equate(name)
            match = re.fullmatch(r"heap\+&([0-9A-F]+)", value)
            self.assertIsNotNone(match, f"{name} is not a heap offset: {value}")
            offsets[name] = int(match.group(1), 16)
        self.assertEqual(offsets["rd_exec"], offsets["rd_load"] + 2)
        self.assertEqual(offsets["rd_len"], offsets["rd_exec"] + 2)

    def test_window_access_preserves_the_command_line_pointer(self) -> None:
        """Y is the MOS command line pointer.

        rd_read indexes the window with Y, and every command reads the
        catalogue before it has finished parsing. When it did not restore Y,
        *RDSAVE rejected its own valid arguments with a usage message.
        """
        for routine in ("rd_read", "rd_write"):
            body = self.source.split(f".{routine}", 1)[1].split("\n.rd_", 1)[0]
            self.assertIn("tya", body, f"{routine} must save Y")
            self.assertIn("tay", body, f"{routine} must restore Y")

    def test_entry_is_recorded_before_the_copy_consumes_the_length(self) -> None:
        """rd_copy_in counts rd_len down to zero as it stores.

        Writing the entry afterwards therefore recorded a zero length. The
        entry is written first, which is safe because rd_count is only raised
        once the copy has reported success.
        """
        store = self.source.split(".rd_save_store", 1)[1].split(".rd_usage_save", 1)[0]
        self.assertLess(store.index("rd_entry_write"), store.index("rd_copy_in"))
        self.assertLess(store.index("rd_copy_in"), store.index("inc rd_count"))

    def test_optional_exec_address_does_not_fall_into_the_usage_message(self) -> None:
        """The usage trampoline sits between the parser and the store.

        Supplying an execution address parsed it correctly and then fell
        straight through into the usage text instead of saving.
        """
        parse = self.source.split("sta rd_exec+1", 1)[1].split(".rd_save_store", 1)[0]
        self.assertIn("jmp rd_save_store", parse)

    def test_bulk_copies_select_the_window_page_once_per_page(self) -> None:
        """Selecting per byte costs two selector writes and three bus delays.

        On a BBC family host that is far longer than moving the data, and a
        sixteen kilobyte file would spend seconds settling the bus.
        """
        for routine in ("rd_copy_out", "rd_copy_in"):
            body = self.source.split(f".{routine}", 1)[1]
            body = body.split("\n\\ ", 1)[0]
            self.assertEqual(
                body.count("jsr select_public_page_a"), 1,
                f"{routine} must select once per page, not per byte",
            )

    def test_ram_disk_stays_in_the_bank_every_machine_forwards(self) -> None:
        """An unmodified Electron AP5 forwards only bank 0.

        Anything reaching for &FCFD or &FCFE would work on the BBC family and
        silently not on the Electron, which the ROM must support equally.
        """
        code = "\n".join(
            line for line in self.source.splitlines()
            if not line.lstrip().startswith("\\")
        )
        self.assertNotIn("&FCFD", code)
        self.assertNotIn("&FCFE", code)

    def test_commands_are_reachable_from_the_network_rom(self) -> None:
        table = NET_ROOT.read_text()
        for command, handler in (
            ("RDINIT", "rd_init_cmd"), ("RDCAT", "rd_cat_cmd"),
            ("RDLOAD", "rd_load_cmd"), ("RDSAVE", "rd_save_cmd"),
            ("RDRUN", "rd_run_cmd"),
        ):
            self.assertIn(f'equs "{command}"', table)
            self.assertIn(f"equb >{handler}, <{handler}", table)


if __name__ == "__main__":
    unittest.main()
