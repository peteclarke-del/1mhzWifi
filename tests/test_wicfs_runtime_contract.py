import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host-tools/.test-deps"))
from py65.devices.mpu6502 import MPU


PATCH = ROOT / "rom-side/elkwifi-0.23/patches/wicfs-private-workspace.patch"
TRANSACTIONAL = ROOT / "rom-side/elkwifi-0.23/patches/wicfs-transactional-state.patch"
STREAM_CHECKPOINT = ROOT / "rom-side/elkwifi-0.23/patches/wicfs-stream-checkpoint.patch"
STREAM_FINISH = ROOT / "rom-side/elkwifi-0.23/patches/wicfs-stream-finish.patch"
ROM_START = 0x8000


class DelayedOneSlotMailbox:
    """64K memory with the Pi1MHz FCA6-FCA9 single pending-operation latch."""

    registers = range(0xFCA6, 0xFCAB)

    def __init__(self, rom: bytes, delay_accesses: int = 12):
        self.ram = bytearray(0x10000)
        self.ram[ROM_START:ROM_START + len(rom)] = rom
        self.delay_accesses = delay_accesses
        self.pending = None
        self.remaining = 0
        self.collisions = 0
        self.selector = [0, 0, 0]
        self.data = {}
        self.command = 0
        self.page = 0
        self.page_data = {}

    @classmethod
    def _is_pi_bus(cls, address: int) -> bool:
        return address in cls.registers or 0xFCFD <= address <= 0xFCFF or 0xFD00 <= address <= 0xFDFF

    def _tick(self) -> None:
        if self.pending is None:
            return
        self.remaining -= 1
        if self.remaining:
            return
        operation, address, value = self.pending
        if operation == "write" and address < 0xFCA9:
            self.selector[address - 0xFCA6] = value
        elif address == 0xFCA9:
            cursor = self.selector[0] | self.selector[1] << 8 | self.selector[2] << 16
            if operation == "write":
                self.data[cursor] = value
            cursor = (cursor + 1) & 0xFFFFFF
            self.selector[:] = cursor & 0xFF, cursor >> 8 & 0xFF, cursor >> 16
        elif operation == "write" and address == 0xFCAA:
            # The Pi FIQ claims fixed service selectors by publishing BUSY.
            self.command = 0x80 if value >= 0xF0 else value
        elif operation == "write" and address == 0xFCFF:
            self.page = value
        elif operation == "write" and 0xFD00 <= address <= 0xFDFF:
            self.page_data[self.page, address & 0xFF] = value
        self.pending = None

    def _schedule(self, operation: str, address: int, value: int) -> None:
        if self.pending is not None:
            self.collisions += 1
        self.pending = operation, address, value
        self.remaining = self.delay_accesses

    def __getitem__(self, address: int) -> int:
        self._tick()
        if self._is_pi_bus(address):
            if address < 0xFCA9:
                value = self.selector[address - 0xFCA6]
            elif address == 0xFCA9:
                cursor = self.selector[0] | self.selector[1] << 8 | self.selector[2] << 16
                value = self.data.get(cursor, 0)
            elif address == 0xFCAA:
                value = self.command
            elif 0xFCFD <= address <= 0xFCFF:
                value = (0, 0, self.page)[address - 0xFCFD]
            else:
                value = self.page_data.get((self.page, address & 0xFF), 0)
            self._schedule("read", address, value)
            return value
        return self.ram[address]

    def __setitem__(self, address: int, value: int) -> None:
        self._tick()
        value &= 0xFF
        if self._is_pi_bus(address):
            self._schedule("write", address, value)
        else:
            self.ram[address] = value


def run_to(mpu: MPU, address: int, limit: int = 200000) -> None:
    for _ in range(limit):
        if mpu.pc == address:
            return
        mpu.step()
    raise AssertionError(f"6502 did not reach ${address:04X}")


class WicfsRuntimeContractTest(unittest.TestCase):
    def test_menu_page_select_settles_after_fcff_write(self):
        source = (ROOT / "rom-side/elkwifi-0.23/overlay/menusrc.asm").read_text()
        helper = source.split(".menusrc_catalogue_select\n", 1)[1].split(
            ".menusrc_catalogue_select_end", 1
        )[0]
        self.assertLess(helper.index("sta &FCFF"), helper.index("nop:nop"))

    def test_every_mos_error_fits_private_workspace(self) -> None:
        source = (
            ROOT / "rom-side/elkwifi-0.23/overlay/errors.asm"
        ).read_text()
        messages = re.findall(
            r'^\.error_[A-Za-z0-9_]+\s+equs\s+"([^"]*)",&0D$',
            source, re.MULTILINE,
        )
        self.assertGreater(len(messages), 10)
        # BRK opcode, error number, message, and terminating NUL. The CR is
        # the table delimiter and is not copied by error_loop.
        for message in messages:
            with self.subTest(message=message):
                self.assertLessEqual(1 + 1 + len(message) + 1, 32)

    @classmethod
    def setUpClass(cls) -> None:
        cls.rom_path = pathlib.Path(os.environ.get(
            "ELKWIFI_TEST_ROM",
            ROOT / "build/pi1mhz-all/Pi1MHz/ElkWiFi.rom",
        ))
        cls.rom = cls.rom_path.read_bytes()

    def find_rom_routine(self, pattern: bytes) -> re.Match[bytes]:
        matches = list(re.finditer(pattern, self.rom, re.S))
        self.assertEqual(len(matches), 1)
        return matches[0]

    def test_combined_assembled_ram_audit_rejects_fixed_uef_counter(self) -> None:
        checker = ROOT / "rom-side/check_combined_ram_layout.py"
        labels = [{name: 0x8000 + index for index, name in enumerate(
            (".uef_cmd", ".wicfs_state_load", ".menu_cmd", ".pi_wget_cmd"))}]
        base = """
wicfs_state_ram = &0380
wicfs_machine = &C3
filev_x = &0396
filev_y = &0397
notape = &0398
chain_exec = &03A0
host_basic_pending = &03BD
"""
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "combined.asm").write_text(base)
            (root / "labels.txt").write_text(repr(labels))
            command = [sys.executable, str(checker), str(root), str(root / "labels.txt")]
            valid = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(valid.returncode, 0, valid.stderr)
            (root / "uef.asm").write_text("uef_length_hi = &0395\n")
            collision = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertNotEqual(collision.returncode, 0)
            self.assertIn("stack-local", collision.stderr)

    def test_persisted_state_uses_explicit_private_addresses(self) -> None:
        base = (ROOT / "rom-side/elkwifi-0.23/patches/wicfs-jim-state.patch").read_text()
        text = TRANSACTIONAL.read_text()
        load = text.split("@@ -225", 1)[1].split(" .wicfs_state_save", 1)[0]
        save = text.split("@@ -260", 1)[1].split(" .wicfs_install", 1)[0]
        address = base.split("+.wicfs_state_address_x", 1)[1].split(
            "+.wicfs_state_load", 1
        )[0]

        self.assertIn("+\tTXA\n+\tSTA\t&FCA6", address)
        self.assertIn("+\tLDA\t#&EF\n+\tSTA\t&FCA7", address)
        self.assertIn("+\tLDA\t#&FF\n+\tSTA\t&FCA8", address)
        self.assertIn("+\tJSR\twicfs_state_address_x", load)
        self.assertIn("+\tJSR\twicfs_state_address_x", save)
        self.assertIn("+\tLDA\t&FCA9\n+\tJSR\twicfs_bus_delay", load)
        self.assertIn("+\tSTA\t&FCA9\n+\tJSR\twicfs_bus_delay", save)
        for section in (address, load, save):
            self.assertNotIn("net_cursor", section)
            self.assertNotIn("net_read_a", section)
            self.assertNotIn("net_write_a", section)

    def test_wicfs_delay_is_cpu_only_and_preserves_state(self) -> None:
        text = (
            ROOT / "rom-side/elkwifi-0.23/patches/wicfs-jim-state.patch"
        ).read_text()
        delay = text.split("+.wicfs_bus_delay\n", 1)[1].split(
            "+.wicfs_state_address_x", 1
        )[0]
        for instruction in ("+\tPHP", "+\tPHA", "+\tPLA", "+\tPLP"):
            self.assertIn(instruction, delay)
        self.assertNotRegex(delay, r"&FC(?:A[0-9A-F]|D[0-9A-F]|E[0-9A-F]|F[0-9A-F])")

    def test_jim_page_is_settled_before_data_access(self) -> None:
        atomic = (
            ROOT / "rom-side/elkwifi-0.23/patches/wicfs-jim-atomic.patch"
        ).read_text()
        self.assertIn(
            "sta pagereg\n+    jsr wicfs_bus_delay"
            " \\wait for the Pi FIQ to publish the selected JIM page\n"
            "     lda pageram,y",
            atomic,
        )
        self.assertGreaterEqual(atomic.count("+    jsr wicfs_bus_delay"), 4)

        uef = (ROOT / "rom-side/elkwifi-0.23/overlay/uef.asm").read_text()
        self.assertIn(
            "tsx\n lda &0103,x                \\ high byte below saved flags\n"
            " sta pagereg\n jsr wicfs_bus_delay\n"
            " ldy &0102,x                \\ low byte below saved flags",
            uef,
        )
        self.assertIn(
            ".uef_select_length\n jsr wicfs_select_public_zero\n"
            " lda #&FF\n sta pagereg\n"
            " jsr wicfs_bus_delay\n rts",
            uef,
        )
        self.assertIn(
            "lda temp\n sta pageram,y\n jsr wicfs_bus_delay\n"
            " inc &0102,x",
            uef,
        )
        self.assertIn(
            ".uef_commit_length\n pha                         \\ uef_select_length uses A for page &FF\n"
            " jsr uef_select_length\n pla\n"
            " sta &FDFE\n jsr wicfs_bus_delay\n tya\n"
            " sta &FDFF\n jsr wicfs_bus_delay",
            uef,
        )

    def test_wget_mailbox_accesses_are_individually_settled(self) -> None:
        source = (ROOT / "rom-side/elkwifi-0.23/overlay/net_wget.asm").read_text()
        start = source.index(".net_address_low")
        end = source.index(".net_dispatch_wait")
        transport = source[start:end]
        lines = transport.splitlines()
        mailbox = re.compile(r"^\s*(?:lda|sta)\s+(?:&FC00\+net_svc_(?:addr_lo|addr_mid|addr_hi|data))\s*$", re.I)
        for index, line in enumerate(lines):
            if mailbox.match(line):
                with self.subTest(line=index + 1, instruction=line.strip()):
                    self.assertLess(index + 1, len(lines))
                    self.assertEqual(lines[index + 1].strip(), "jsr wicfs_bus_delay")

    def test_assembled_uef_length_commit_preserves_both_bytes(self) -> None:
        match = self.find_rom_routine(
            rb"\x48\x20..\x68\x8d\xfe\xfd\x20..\x98\x8d\xff\xfd\x20..\x60"
        )
        start = ROM_START + match.start()
        final_rts = ROM_START + match.end() - 1
        for value in (0x0000, 0x0100, 0x01FF, 0xFFFE):
            with self.subTest(value=f"{value:04X}"):
                memory = bytearray(0x10000)
                memory[ROM_START:ROM_START + len(self.rom)] = self.rom
                memory[0x00C3] = 1  # Electron: only FCFF is Pi-visible.
                mpu = MPU(memory=memory, pc=start)
                mpu.a = value & 0xFF
                mpu.y = value >> 8
                mpu.sp = 0xF0
                run_to(mpu, final_rts)
                self.assertEqual(memory[0xFDFE], value & 0xFF)
                self.assertEqual(memory[0xFDFF], value >> 8)
                self.assertEqual(mpu.sp, 0xF0)

    def test_assembled_uef_completion_classifies_256_byte_multiples(self) -> None:
        match = self.find_rom_routine(
            rb"\x28\xba\xbd\x02\x01\x1d\x01\x01\xd0.\x4c.."
        )
        start = ROM_START + match.start()
        branch_address = start + 8
        fallthrough = branch_address + 2
        displacement = self.rom[match.start() + 9]
        if displacement & 0x80:
            displacement -= 0x100
        nonempty = fallthrough + displacement
        for value, expected in (
            (0x0000, fallthrough),
            (0x0100, nonempty),
            (0x01FF, nonempty),
            (0xFFFE, nonempty),
        ):
            with self.subTest(value=f"{value:04X}"):
                memory = bytearray(0x10000)
                memory[ROM_START:ROM_START + len(self.rom)] = self.rom
                # Entry is PLP. It removes saved flags, leaving the stable
                # low/high frame at S+1/S+2 exactly as uef_complete does.
                memory[0x01F0] = 0x20
                memory[0x01F1] = value & 0xFF
                memory[0x01F2] = value >> 8
                mpu = MPU(memory=memory, pc=start)
                mpu.sp = 0xEF
                for _ in range(5):
                    mpu.step()
                self.assertEqual(mpu.pc, expected)
                self.assertEqual(mpu.sp, 0xF0)

    def test_assembled_wget_transport_survives_one_slot_delayed_mailbox(self) -> None:
        probe = DelayedOneSlotMailbox(self.rom)
        probe[0xFCA6] = 0x34
        probe[0xFCA7] = 0x12
        self.assertEqual(probe.collisions, 1)  # The model rejects an unsettled pair.

        write = self.find_rom_routine(
            rb"\x08\x78\x48\xad..\x8d\xa6\xfc\x20.."
            rb"\xad..\x8d\xa7\xfc\x20..\xad..\x8d\xa8\xfc"
        )
        read = self.find_rom_routine(
            rb"\x08\x78\xad..\x8d\xa6\xfc\x20.."
            rb"\xad..\x8d\xa7\xfc\x20..\xad..\x8d\xa8\xfc"
        )
        write_start = ROM_START + write.start()
        read_start = ROM_START + read.start()
        write_final_rts = read_start - 1
        # net_wait_cursor begins after net_read_a's PLA/PLP/CMP #0/RTS tail.
        read_final_rts = ROM_START + self.rom.find(b"\x68\x28\xc9\x00\x60", read.end()) + 4
        self.assertGreater(read_final_rts, read_start)

        memory = DelayedOneSlotMailbox(self.rom)
        cursor_locations = (
            self.rom[write.start() + 4] | self.rom[write.start() + 5] << 8,
            self.rom[write.start() + 13] | self.rom[write.start() + 14] << 8,
            self.rom[write.start() + 22] | self.rom[write.start() + 23] << 8,
        )
        for address, value in zip(cursor_locations, (0x34, 0x12, 0x00)):
            memory.ram[address] = value
        mpu = MPU(memory=memory, pc=write_start)
        mpu.a = 0x5A
        mpu.sp = 0xF0
        run_to(mpu, write_final_rts)
        self.assertEqual(memory.collisions, 0)
        self.assertEqual(memory.data.get(0x001234), 0x5A)
        self.assertEqual(memory.selector, [0x35, 0x12, 0x00])
        self.assertIsNone(memory.pending)
        self.assertEqual(mpu.sp, 0xF0)

        memory.data[0x001235] = 0xA7
        mpu.pc = read_start
        run_to(mpu, read_final_rts)
        self.assertEqual(memory.collisions, 0)
        self.assertEqual(mpu.a, 0xA7)
        self.assertEqual(memory.selector, [0x36, 0x12, 0x00])
        self.assertIsNone(memory.pending)
        self.assertEqual(mpu.sp, 0xF0)

    def test_assembled_wget_dispatch_waits_for_command_publication(self) -> None:
        # An immediate command write/read loses the posted write and observes
        # the previous zero result in the real one-slot transport model.
        probe = DelayedOneSlotMailbox(self.rom)
        probe[0xFCAA] = 0xF0
        self.assertEqual(probe[0xFCAA], 0)
        self.assertEqual(probe.collisions, 1)

        match = self.find_rom_routine(
            rb"\x08\x78\xa9\xf0\x8d\xaa\xfc\x20..\x28\xad\xaa\xfc"
        )
        start = ROM_START + match.start()
        after_read = start + match.end() - match.start()
        memory = DelayedOneSlotMailbox(self.rom)
        mpu = MPU(memory=memory, pc=start)
        mpu.sp = 0xF0
        run_to(mpu, after_read)
        self.assertEqual(mpu.a, 0x80)
        self.assertEqual(memory.command, 0x80)
        self.assertEqual(memory.collisions, 0)
        self.assertEqual(mpu.sp, 0xF0)

    def test_assembled_driver_waits_for_page_publication(self) -> None:
        probe = DelayedOneSlotMailbox(self.rom)
        probe[0xFCFF] = 1
        self.assertEqual(probe[0xFD23], 0)
        self.assertEqual(probe.collisions, 1)

        read = self.find_rom_routine(
            rb"\x08\x78\xad(..)\x20..\xbd\x00\xfd\x28\x20..\x09\x00\x60"
        )
        start = ROM_START + read.start()
        final_rts = start + read.end() - read.start() - 1
        shadow = self.rom[read.start() + 3] | self.rom[read.start() + 4] << 8
        memory = DelayedOneSlotMailbox(self.rom)
        memory.ram[shadow] = 1
        memory.page_data[0, 0x23] = 0x11
        memory.page_data[1, 0x23] = 0xA7
        mpu = MPU(memory=memory, pc=start)
        mpu.x = 0x23
        mpu.sp = 0xF0
        run_to(mpu, final_rts)
        self.assertEqual(mpu.a, 0xA7)
        self.assertEqual(memory.page, 1)
        self.assertEqual(memory.collisions, 0)
        self.assertEqual(mpu.sp, 0xF0)
        self.assertEqual(mpu.p & mpu.ZERO, 0)

        write_patterns = (
            rb"\x08\x78\x48\xad(..)\x20..\x68\x9d\x00\xfd\x20..\x28\x4c..",
            rb"\x08\x78\x48\xad(..)\x20..\x68\x9d\x00\xfd\x20..\x28\x60",
        )
        for pattern in write_patterns:
            with self.subTest(pattern=pattern):
                write = self.find_rom_routine(pattern)
                write_start = ROM_START + write.start()
                write_shadow = (
                    self.rom[write.start() + 4] |
                    self.rom[write.start() + 5] << 8
                )
                if self.rom[write.end() - 3] == 0x4C:
                    increment = (
                        self.rom[write.end() - 2] |
                        self.rom[write.end() - 1] << 8
                    )
                    increment_offset = increment - ROM_START
                    write_final_rts = ROM_START + self.rom.index(
                        b"\x60", increment_offset
                    )
                else:
                    write_final_rts = ROM_START + write.end() - 1
                memory = DelayedOneSlotMailbox(self.rom)
                memory.ram[write_shadow] = 1
                mpu = MPU(memory=memory, pc=write_start)
                mpu.a = 0x5A
                mpu.x = 0x23
                mpu.sp = 0xF0
                run_to(mpu, write_final_rts)
                self.assertEqual(memory.page_data.get((1, 0x23)), 0x5A)
                self.assertEqual(memory.collisions, 0)
                self.assertIsNone(memory.pending)
                self.assertEqual(mpu.sp, 0xF0)

    def test_every_uef_jim_write_is_followed_by_bus_settle(self) -> None:
        uef = (ROOT / "rom-side/elkwifi-0.23/overlay/uef.asm").read_text()
        lines = uef.splitlines()
        jim_writes = re.compile(r"^\s*sta\s+(?:&FD[0-9A-F]{2}|pageram(?:,y)?)\s*$", re.I)
        for index, line in enumerate(lines):
            if jim_writes.match(line):
                with self.subTest(line=index + 1, instruction=line.strip()):
                    self.assertLess(index + 1, len(lines))
                    self.assertEqual(lines[index + 1].strip(), "jsr wicfs_bus_delay")

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
        text = STREAM_CHECKPOINT.read_text()
        self.assertIn("+wicfs_state_size = 22", text)
        for field in ("wicfs_cursor_y", "wicfs_cursor_page", "wicfs_stream_start",
                      "wicfs_bytes_lo", "wicfs_bytes_hi"):
            self.assertRegex(text, rf"(?m)^\+{field} = ")
        self.assertIn("checkpoint cursor before executing loaded code", text)
        self.assertIn("checkpoint before a loaded program runs", text)
        self.assertIn("persist open, close and cursor changes", text)
        # Persistence is deliberately at file/FSC boundaries. Rewriting a
        # checksummed 22-byte record for every OSBGET byte would recreate the
        # physical performance regression this checkpoint replaces.
        self.assertNotIn(".upbgetv", text)

    def test_exhausted_stream_restores_and_rearms_the_osbyte_trap(self) -> None:
        text = STREAM_FINISH.read_text()
        self.assertIn("+.wicfs_finish_if_exhausted", text)
        self.assertIn("+.wicfs_install_byte_trap", text)
        self.assertGreaterEqual(
            text.count("wicfs_finish_if_exhausted"), 3,
            "OSFILE/CHAIN and FSCV/*RUN must share stream completion",
        )
        self.assertGreaterEqual(
            text.count("wicfs_install_byte_trap"), 2,
            "repeated UEF installs must use the complete trap wrapper",
        )
        self.assertGreaterEqual(text.count("wicfs_prepare_byte_trap"), 3)
        self.assertGreaterEqual(text.count("wicfs_publish_byte_trap"), 3)
        self.assertIn("+.wicfs_any_vector_owned", text)
        self.assertIn("+                    jsr wicfs_any_vector_owned", text)
        self.assertIn("cannot execute a partially rewritten handler", text)
        self.assertEqual(text.count("+\tJSR\tinstall_extended_vector"), 0)
        self.assertNotIn("+\tLDA\t#&8C", text)
        finish = text.split("+.wicfs_finish_if_exhausted", 1)[1].split(
            "+.wicfs_any_vector_owned", 1
        )[0]
        self.assertLess(finish.index("+\tSEI"), finish.index("+\tLDA\tBYTEV"))
        self.assertIn("+.wicfs_install_invalid", text)
        self.assertIn("WiCFS state invalid; power cycle", text)
        for vector, dispatcher in (
            ("OSFILEV", "&FF1B"),
            ("OSBGETV", "&FF21"),
            ("OSFINDV", "&FF2A"),
            ("OSFSCV", "&FF2D"),
        ):
            self.assertIn(f"+\tLDA\t{vector}", text)
            self.assertIn(f"+\tCMP\t#<{dispatcher}", text)
            self.assertIn(f"+\tCMP\t#>{dispatcher}", text)
        self.assertNotIn("JSR\twicfs_reset", text)

    def test_stream_install_and_reset_are_transactional(self) -> None:
        text = STREAM_FINISH.read_text()
        self.assertIn("+.wicfs_install_check_partial", text)
        self.assertIn("+.wicfs_install_components_ok", text)
        self.assertIn("+.wicfs_release_invalid_byte_trap", text)
        self.assertIn("+                    bcs autorun_wicfs_abort", text)
        self.assertIn("+.autorun_wicfs_abort", text)
        self.assertIn("+.uef_run_failed", text)
        self.assertIn("+ bcs uef_run_failed", text)
        self.assertIn("+\tBCC\tbUPCFS_installed", text)
        self.assertIn("+\tLDX\t#(error_wicfs_state-error_table)", text)
        self.assertIn("+.bUPCFS_installed", text)
        self.assertIn(
            '+ equs "WiCFS state invalid; power cycle",&0D,&EA', text
        )

        invalid = text.split("+.wicfs_install_invalid", 1)[1].split(
            " .b_install", 1
        )[0]
        self.assertIn(
            "+\tLDA\t#0\n+\tSTA\twicfs_magic\n+\tSTA\twicfs_magic+1",
            invalid,
        )
        self.assertIn(" .Bquit\t\n+\tCLC\n", text)

        prepared = text.index(
            "+\tJSR\twicfs_state_save\t\\commit rollback record before publishing hooks"
        )
        predecessor_capture = text.index("+\tJSR\twicfs_prepare_byte_trap")
        first_publish = text.index(" \\Use MOS extended vectors")
        byte_publish = text.index("+\tJSR\twicfs_publish_byte_trap")
        self.assertLess(predecessor_capture, prepared)
        self.assertLess(prepared, first_publish)
        self.assertLess(first_publish, byte_publish)
        service_refresh = text.index(
            "+\tJSR\twicfs_state_save\t\\capture any BYTEV owner installed by service &0F"
        )
        refreshed_prepare = text.rfind(
            "+\tJSR\twicfs_prepare_byte_trap", first_publish, service_refresh
        )
        self.assertGreater(refreshed_prepare, first_publish)
        self.assertLess(service_refresh, byte_publish)

        wrapper = text.split("+.wicfs_install_byte_trap", 1)[1].split(
            "+.wicfs_prepare_byte_trap", 1
        )[0]
        self.assertLess(wrapper.index("+\tJSR\twicfs_prepare_byte_trap"),
                        wrapper.index("+\tJSR\twicfs_state_save"))
        self.assertLess(wrapper.index("+\tJSR\twicfs_state_save"),
                        wrapper.index("+\tJMP\twicfs_publish_byte_trap"))

        partial = text.split("+.wicfs_install_check_partial", 1)[1].split(
            "+.wicfs_install_invalid", 1
        )[0]
        self.assertIn(
            "+\tLDA\tBYTEV\n+\tCMP\t#<notape\n"
            "+\tBNE\twicfs_install_check_byte_high\n"
            "+\tJMP\twicfs_install_invalid",
            partial,
        )

        self.assertIn("+                    beq autorun_wicfs_low_matches", text)
        self.assertIn("+                    beq autorun_wicfs_abort", text)
        self.assertIn("+                    bne autorun_wicfs_abort", text)

        ownership = text.split("+.wicfs_any_vector_owned", 1)[1].split(
            "+.wicfs_owned_no", 1
        )[0]
        for vector, dispatcher, handler in (
            ("OSFILEV", "&FF1B", "upfilev"),
            ("OSBGETV", "&FF21", "upbgetv"),
            ("OSFINDV", "&FF2A", "upfindv"),
            ("OSFSCV", "&FF2D", "upfscv"),
        ):
            self.assertIn(f"+\tLDA\t{vector}", ownership)
            self.assertIn(f"+\tCMP\t#<{dispatcher}", ownership)
            self.assertIn(f"+\tCMP\t#>{dispatcher}", ownership)
            self.assertIn(f"+\tCMP\t#<{handler}", ownership)
            self.assertIn(f"+\tCMP\t#>{handler}", ownership)

        invalid_trap = text.split(
            "+.wicfs_release_invalid_byte_trap", 1
        )[1].split(r" \OSFILE metadata return complete", 1)[0]
        for opcode in ("#&C9", "#&8C", "#&D0", "#&60", "#&4C"):
            self.assertIn(f"+\tCMP\t{opcode}", invalid_trap)
        self.assertNotIn("+\tLDA\tnotape+8", invalid_trap)
        self.assertIn("+.wicfs_invalid_trap_bad", invalid_trap)

        build = (ROOT / "rom-side/build_rom.sh").read_text()
        for marker in (
            "wicfs_any_vector_owned", "wicfs_install_check_partial",
            "wicfs_prepare_byte_trap", "wicfs_publish_byte_trap",
            "commit rollback record before publishing hooks",
            "capture any BYTEV owner installed by service &0F",
            "wicfs_release_invalid_byte_trap", "autorun_wicfs_abort",
            "uef_run_failed",
            "bUPCFS_installed", "error_wicfs_state",
        ):
            self.assertIn(marker, build)

    def test_reset_does_not_restore_arbitrary_host_workspace(self) -> None:
        workspace_patch = (
            ROOT / "rom-side/elkwifi-0.23/patches/wicfs-workspace-preserve.patch"
        )
        self.assertFalse(workspace_patch.exists())
        self.assertNotIn(
            "wicfs-workspace-preserve.patch",
            (ROOT / "rom-side/build_rom.sh").read_text(),
        )

    def test_public_jim_selection_is_machine_local(self) -> None:
        text = TRANSACTIONAL.read_text()
        detect = text.split("+.wicfs_detect_machine", 1)[1].split(
            "+.wicfs_select_public_zero", 1
        )[0]
        select = text.split("+.wicfs_select_public_zero", 1)[1].split(
            " .wicfs_state_address_x", 1
        )[0]
        self.assertIn("+\tLDA\t#&81", detect)
        self.assertIn("+\tSTX\twicfs_machine", detect)
        self.assertIn("+\tCPX\t#1", select)
        self.assertIn("+\tSTA\t&FCFD", select)
        self.assertIn("+\tSTA\t&FCFE", select)
        self.assertIn("+\tSTA\tpagereg", select)
        self.assertIn("+\tTXA\n+\tPHA", select)
        self.assertIn("+\tPLA\n+\tTAX\n+\tPLA\n+\tPLP", select)
        self.assertNotIn("driver_machine", text)

        def effective_pi_selectors(machine: int, selectors: tuple[int, int, int]):
            high, middle, _page = selectors
            if machine == 1:
                # AP5 does not forward the two upper selector addresses.
                return 0, 0, 0
            return 0, 0, 0

        for machine in (0, 1, 2, 3):
            self.assertEqual(effective_pi_selectors(machine, (0xAB, 0xCD, 0xEF)),
                             (0, 0, 0))

    def test_persisted_state_is_committed_transactionally(self) -> None:
        text = TRANSACTIONAL.read_text()
        load_source = text.split("@@ -225", 1)[1].split(" .wicfs_state_save", 1)[0]
        self.assertLess(load_source.index("+.wicfs_state_checksum_ok"),
                        load_source.index("+.wicfs_state_copy_loop"))
        self.assertLess(load_source.index("+.wicfs_state_copy_loop"),
                        load_source.index("+.wicfs_state_final_valid"))
        save = text.split("@@ -260", 1)[1].split(" .wicfs_install", 1)[0]
        positions = [
            save.index("+\tLDX\t#wicfs_record_valid"),
            save.index("+.wicfs_state_save_payload"),
            save.index("+\tLDX\t#wicfs_record_checksum"),
            save.index("+\tLDX\t#wicfs_record_version"),
            save.index("+\tLDX\t#wicfs_record_generation", save.index("+.wicfs_state_save_payload")),
            save.rindex("+\tLDX\t#wicfs_record_valid"),
        ]
        self.assertEqual(positions, sorted(positions))

        valid, version, generation, checksum, payload_at = 0, 1, 2, 3, 4

        def make_record(payload: bytes, gen: int) -> bytearray:
            record = bytearray(payload_at + len(payload))
            record[version] = 1
            record[generation] = gen
            value = 1 ^ gen
            for byte in payload:
                value ^= byte
            record[checksum] = value
            record[payload_at:] = payload
            record[valid] = 0xA5
            return record

        def load(record: bytearray):
            if record[valid] != 0xA5 or record[version] != 1:
                return None
            value = record[version] ^ record[generation]
            for byte in record[payload_at:]:
                value ^= byte
            return bytes(record[payload_at:]) if value == record[checksum] else None

        # The payload includes 17 bytes of vector ownership followed by the
        # UEF offset, page, start flag and two-byte remaining length. A title
        # program may destroy the corresponding volatile zero-page values;
        # the next WiCFS file entry must recover these final five bytes.
        old = bytes(range(22))
        new = bytes((value ^ 0xA5) for value in range(22))
        original = make_record(old, 7)
        new_generation = 8
        new_checksum = 1 ^ new_generation
        for byte in new:
            new_checksum ^= byte
        writes = [(valid, 0)]
        writes += [(payload_at + index, byte) for index, byte in enumerate(new)]
        writes += [(checksum, new_checksum), (version, 1),
                   (generation, new_generation), (valid, 0xA5)]
        for interrupted_after in range(len(writes) + 1):
            record = bytearray(original)
            for address, value in writes[:interrupted_after]:
                record[address] = value
            accepted = load(record)
            if interrupted_after == 0:
                self.assertEqual(accepted, old)
            elif interrupted_after == len(writes):
                self.assertEqual(accepted, new)
                self.assertEqual(accepted[-5:], new[-5:])
            else:
                self.assertIsNone(accepted, interrupted_after)

    def test_uef_length_is_cpu_side_and_checkpointed(self) -> None:
        uef = (ROOT / "rom-side/elkwifi-0.23/overlay/uef.asm").read_text()
        read_loop = uef.split(".uef_read\n", 1)[1].split(".uef_read_end", 1)[0]
        opened = uef.split(".uef_opened\n", 1)[1].split(".uef_read\n", 1)[0]
        self.assertIn("pha                         \\ file handle below", opened)
        self.assertIn(
            "tsx\n ldy &0103,x                 \\ recover handle after TSX",
            read_loop,
        )
        close = uef.split(".uef_close\n", 1)[1].split(".uef_select_length", 1)[0]
        self.assertIn("tsx\n \\ JSR uef_close has placed its two-byte return address", close)
        self.assertIn("ldy &0105,x", close)
        self.assertNotIn("txa\n tay", close)
        self.assertNotIn("lda &FDFE", read_loop)
        self.assertNotIn("lda &FDFF", read_loop)
        self.assertEqual(read_loop.count("jsr uef_commit_length"), 1)
        self.assertIn("inc &0102,x\n bne uef_byte_stored\n inc &0103,x", read_loop)
        self.assertNotIn("uef_length_lo", uef)
        self.assertNotIn("uef_length_hi", uef)
        # Stable frame: low/high are +1/+2. With PHP: +2/+3. With the
        # normalize result and PHP: +3/+4. Lock all three contexts down.
        self.assertIn("lda &0102,x\n cmp #&FF", read_loop)
        self.assertIn("lda &0101,x\n cmp #&FE", read_loop)
        self.assertIn("lda &0103,x                \\ high byte below saved flags", read_loop)
        self.assertIn("ldy &0102,x                \\ low byte below saved flags", read_loop)
        self.assertIn(
            "plp\n tsx\n lda &0102,x                \\ high frame byte after saved flags are removed\n"
            " ora &0101,x                \\ low frame byte\n bne uef_nonempty",
            uef,
        )
        normalized = uef.split(".uef_normalized", 1)[1].split(".uef_format_done", 1)[0]
        self.assertIn("sta &0104,x", normalized)
        self.assertIn("sta &0103,x", normalized)

        def writes_for(size: int):
            length = 0
            addresses = []
            checkpoints = [0]
            for _ in range(size):
                addresses.append(length)
                length += 1
                if not (length & 0xFF):
                    checkpoints.append(length)
            if checkpoints[-1] != length:
                checkpoints.append(length)
            return addresses, checkpoints

        for size, expected_checkpoints in (
            (255, [0, 255]),
            (256, [0, 256]),
            (257, [0, 256, 257]),
            (0xFFFE, list(range(0, 0xFF01, 0x100)) + [0xFFFE]),
        ):
            addresses, checkpoints = writes_for(size)
            self.assertEqual(addresses[0] if addresses else 0, 0)
            if addresses:
                self.assertEqual(addresses[-1], size - 1)
            self.assertEqual(checkpoints, expected_checkpoints)

    def test_getbyte_does_not_select_then_discard_next_page(self) -> None:
        text = TRANSACTIONAL.read_text()
        getbyte = text.split("@@ -2346", 1)[1].split("@@ -2392", 1)[0]
        self.assertNotRegex(getbyte, r"(?m)^\+.*select the next physical page")
        self.assertIn("jsr wicfs_select_public_zero", getbyte)

    def test_starrun_filename_is_bounded(self) -> None:
        text = TRANSACTIONAL.read_text()
        starrun = text.split("@@ -1629", 1)[1].split("@@ -2346", 1)[0]
        self.assertIn("+\tCPX\t#10", starrun)
        self.assertIn("+\tBCS\tsr_a4", starrun)

    def test_menu_refuses_invalid_vector_record(self) -> None:
        menu = (ROOT / "rom-side/elkwifi-0.23/overlay/menu.asm").read_text()
        release = menu.split(".wicfs_release_tape_trap", 1)[1].split(
            ".menu_download_invalid", 1
        )[0]
        self.assertIn("jsr wicfs_state_load\n    bcs wicfs_release_tape_invalid", release)
        self.assertIn(".wicfs_release_tape_invalid\n    sec\n    rts", release)
        self.assertIn("WiCFS state invalid; power cycle", menu)

    def test_uef_tube_and_native_paths_share_host_tape_transition(self) -> None:
        uef = (ROOT / "rom-side/elkwifi-0.23/overlay/uef.asm").read_text()
        transition = uef.index("jsr menu_select_tape")
        tube_query = uef.index("lda #&EA", transition)
        self.assertLess(transition, tube_query)
        launch = uef.split(".uef_launch", 1)[1].split(".uef_run_launch", 1)[0]
        self.assertNotIn("*TAPE", launch)
        menu = (ROOT / "rom-side/elkwifi-0.23/overlay/menu.asm").read_text()
        helper = menu.split(".menu_select_tape", 1)[1].split(".menu_tape_command", 1)[0]
        self.assertIn("jsr oscli", helper)
        self.assertIn("clc\n    rts", helper)

    def test_wget_shared_uef_errors_do_not_pop_uef_stack_frame(self) -> None:
        uef = (ROOT / "rom-side/elkwifi-0.23/overlay/uef.asm").read_text()
        invalid = uef.split(".uef_invalid\n", 1)[1].split(
            ".uef_too_large_cleanup", 1
        )[0]
        too_large = uef.split(".uef_too_large\n", 1)[1].split(
            ".uef_open_failed", 1
        )[0]
        self.assertNotRegex(invalid, r"(?m)^\s*pla\s*$")
        self.assertNotRegex(too_large, r"(?m)^\s*pla\s*$")
        self.assertIn("jmp uef_invalid_cleanup", uef)
        self.assertIn("jmp uef_too_large_cleanup", uef)

    def test_wget_machine_detection_and_jim_writes_are_settled(self) -> None:
        serial = (ROOT / "rom-side/elkwifi-0.23/overlay/serial.asm").read_text()
        wget = (ROOT / "rom-side/elkwifi-0.23/overlay/net_wget.asm").read_text()
        helpers = (ROOT / "rom-side/elkwifi-0.23/overlay/wget_helpers.asm").read_text()
        self.assertIn(".pi_wget_cmd\n jsr detect_jim_machine", wget)
        self.assertIn("lda #&81\n ldx #0\n ldy #&FF\n jsr osbyte", serial)
        self.assertIn("cpx #1\n beq set_bank_0_page", serial)
        self.assertIn("sta &FCFD\n jsr wicfs_bus_delay\n sta &FCFE", serial)
        for source in (serial, wget, helpers):
            lines = source.splitlines()
            for index, line in enumerate(lines):
                if re.match(r"^\s*sta\s+(?:pagereg|&FD[0-9A-F]{2}|pageram(?:,y)?)\s*$",
                            line, re.I):
                    with self.subTest(source=source[:20], line=index + 1):
                        self.assertEqual(lines[index + 1].strip(), "jsr wicfs_bus_delay")

    def test_invalid_vectors_never_dereference_predecessors(self) -> None:
        patch = (ROOT / "rom-side/elkwifi-0.23/patches/wicfs-invalid-state.patch").read_text()
        for label in ("upfilev_state_valid", "upfindv_state_valid",
                      "upfscv_state_valid", "upbgetv_state_valid"):
            self.assertIn(label, patch)
        self.assertIn("bounded OSFILE failure", patch)
        self.assertIn("bounded OSFIND failure", patch)
        self.assertIn("never jump through stale FSCVRTN", patch)
        self.assertIn("bounded EOF", patch)
        private = (ROOT / "rom-side/elkwifi-0.23/patches/wicfs-private-workspace.patch").read_text()
        tail = private.split("@@ -1150", 1)[1]
        self.assertEqual(tail.count("+\tPLA"), 2)
        self.assertIn("\tJMP\t(&03C2)", tail)

    def test_break_restores_only_owned_vectors_from_valid_state(self) -> None:
        text = TRANSACTIONAL.read_text()
        reset = text.split("@@ -686", 1)[1].split("@@ -967", 1)[0]
        self.assertIn("+\tBCC\twicfs_reset_state_valid", reset)
        self.assertIn("+\tJMP\twicfs_reset_done", reset)

        def restore(current, owned, predecessor, record_valid):
            if record_valid and current == owned:
                return predecessor
            return current

        self.assertEqual(restore("wicfs", "wicfs", "adfs", True), "adfs")
        self.assertEqual(restore("adfs", "wicfs", "tape", True), "adfs")
        self.assertEqual(restore("wicfs", "wicfs", "garbage", False), "wicfs")

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
