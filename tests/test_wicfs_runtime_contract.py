import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
PATCH = ROOT / "rom-side/elkwifi-0.23/patches/wicfs-private-workspace.patch"


class WicfsRuntimeContractTest(unittest.TestCase):
    def test_rom_switchers_are_bounded_below_private_state(self) -> None:
        patch = (
            ROOT / "rom-side/elkwifi-0.23/patches/wicfs-rom-switch.patch"
        ).read_text()
        self.assertIn(
            "ASSERT chain_exec+(chain_code_end-chain_code) <= host_basic_pending",
            patch,
        )
        self.assertIn(
            "ASSERT chain_exec+(run_code_end-run_code) <= host_basic_pending",
            patch,
        )

    def test_private_state_never_uses_application_or_keyboard_ram(self) -> None:
        text = PATCH.read_text()
        definitions = dict(
            re.findall(r"^\+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*&([0-9A-Fa-f]+)", text, re.M)
        )
        for name in ("wicfs_state_ram", "filev_x", "filev_y", "bget_y",
                     "filev_source", "fscv_reason", "chain_rom"):
            self.assertIn(name, definitions)
            address = int(definitions[name], 16)
            self.assertLess(address, 0x0400, name)
            self.assertFalse(0x03E0 <= address <= 0x03FF, name)
        self.assertNotIn("+wicfs_state_ram = heap", text)
        self.assertIn("chain_exec     = &03A0", text)
        self.assertNotRegex(text, r"(?m)^\+(?:filev_x|filev_y|bget_y|filev_source|fscv_reason|chain_\w+)\s*=\s*heap")

    def test_stream_cursor_is_round_tripped_with_vector_state(self) -> None:
        text = PATCH.read_text()
        for field in ("pr_y", "pr_r", "sbuft", "sbufl", "sbufh"):
            self.assertRegex(text, rf"(?m)^\+\s*STA\s+{field}\b")
            self.assertRegex(text, rf"(?m)^\+\s*LDA\s+{field}\b")
        self.assertIn("+wicfs_state_size = 22", text)
        self.assertIn("persist authoritative initial cursor and length", text)
        self.assertIn("persist cursor consumed by this OSFILE load", text)
        self.assertIn("persist the completed unsuccessful search", text)

    def test_osfile_length_includes_full_final_block_and_carry(self) -> None:
        text = PATCH.read_text()
        for instruction in ("LDA\t&03C9", "ADC\t&03C6", "ADC\t&03C7"):
            self.assertIn(instruction, text)

        def returned_length(block: int, final_length: int) -> int:
            low = final_length & 0xFF
            middle_sum = ((final_length >> 8) & 0xFF) + (block & 0xFF)
            middle = middle_sum & 0xFF
            high = ((block >> 8) + (middle_sum >> 8)) & 0xFF
            return low | (middle << 8) | (high << 16)

        for block, final_length in ((0, 0), (0, 1), (0, 255), (34, 256),
                                    (0x01FF, 256)):
            self.assertEqual(returned_length(block, final_length),
                             block * 256 + final_length)

    def test_cfs_filenames_are_bounded_below_keyboard_buffer(self) -> None:
        text = PATCH.read_text()
        self.assertIn("CPX\t#10\t\t\\CFS filenames are at most ten characters", text)
        self.assertIn("CPX\t#11\t\t\\ten characters plus the terminating zero", text)

    def test_extended_vector_tail_call_discards_five_dispatcher_bytes(self) -> None:
        text = PATCH.read_text()
        tail = text.split("@@ -1150", 1)[1]
        # The base routine already contained three PLAs. This patch adds two,
        # giving the five-byte Electron extended-vector dispatcher unwind and
        # leaving the real caller return address on the stack.
        self.assertEqual(tail.count("+\tPLA"), 2)
        self.assertIn("\tJMP\t(&03C2)", tail)
        stack = [0x34, 0x12, 0x78, 0x56, 0x0B, 0x9A, 0xBC]
        for _ in range(5):
            stack.pop(0)
        self.assertEqual(stack, [0x9A, 0xBC])


if __name__ == "__main__":
    unittest.main()
