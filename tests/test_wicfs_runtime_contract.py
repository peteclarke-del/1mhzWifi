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
RUN_RETURN = ROOT / "rom-side/elkwifi-0.23/patches/wicfs-run-return.patch"
CHAIN_TARGET = ROOT / "rom-side/elkwifi-0.23/patches/wicfs-chain-target.patch"
VECTOR_FLAGS = ROOT / "rom-side/elkwifi-0.23/patches/wicfs-vector-flags.patch"
MESSAGE_PRESERVE = ROOT / "rom-side/elkwifi-0.23/patches/wicfs-message-preserve.patch"
PAGE_SELECT_FAST = ROOT / "rom-side/elkwifi-0.23/patches/wicfs-page-select-fast.patch"
LOW_LOADER_GUARD = ROOT / "rom-side/elkwifi-0.23/patches/wicfs-low-loader-guard.patch"
BGET_REFILL_DETECTION = ROOT / "rom-side/elkwifi-0.23/patches/wicfs-bget-refill-detection.patch"
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
    def test_machine_detection_occurs_once_per_bget_buffer_refill(self) -> None:
        text = BGET_REFILL_DETECTION.read_text()
        bget, fill = text.split("@@ -2672", 1)
        self.assertIn("-    JSR wicfs_detect_machine", bget)
        self.assertIn("+\tJSR\twicfs_detect_machine", fill)
        self.assertIn("once per 256-byte refill", fill)

    def test_message_terminator_survives_osasci_register_clobber(self) -> None:
        text = MESSAGE_PRESERVE.read_text()
        loop = text.split(" .xmess_a1", 1)[1]
        self.assertIn(" \tLDA\ttxt0,X", loop)
        self.assertIn(" \tCMP\t#cr", loop)
        self.assertLess(loop.index("+\tPHA"), loop.index(" \tJSR\tOSASCI"))
        self.assertLess(loop.index(" \tJSR\tOSASCI"), loop.index("+\tPLA"))

        # Execute the emitted loop as well as checking its maintainable source.
        # OSASCI is a MOS call and does not promise to preserve A. Model the
        # hostile but valid case which made the old loop miss its CR and print
        # adjacent messages and ROM bytes.
        match = re.search(
            rb"\xBD(..)\x48\x20\xE3\xFF\x68\xE8\xC9\x0D\xD0\xF3\x60",
            self.rom,
            re.DOTALL,
        )
        self.assertIsNotNone(match, "assembled xmess loop not found")
        offset = match.start()

        mpu = MPU()
        mpu.memory[ROM_START:ROM_START + len(self.rom)] = self.rom
        mpu.pc = ROM_START + offset
        mpu.x = 0
        return_address = mpu.pc + len(match.group(0)) - 1
        printed = []
        for _ in range(256):
            if mpu.pc == return_address:
                break
            if mpu.pc == 0xFFE3:
                printed.append(mpu.a)
                low = mpu.memory[0x0100 + ((mpu.sp + 1) & 0xFF)]
                high = mpu.memory[0x0100 + ((mpu.sp + 2) & 0xFF)]
                mpu.sp = (mpu.sp + 2) & 0xFF
                mpu.pc = ((high << 8) | low) + 1
                mpu.a = 0x00
            else:
                mpu.step()
        else:
            self.fail("xmess did not stop at its first CR")

        self.assertEqual(bytes(printed), b"WiFi UEF FS    \r")
        self.assertEqual(mpu.x, 16)
        self.assertEqual(mpu.a, 0x0D)

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
        labels = [{
            ".uef_cmd": 0x8000,
            ".wicfs_state_load": 0x8001,
            ".host_select_tape": 0x8002,
            ".pi_wget_cmd": 0x8003,
            ".wicfs_reset_done": 0x8100,
            ".wicfs_load_pre_tape": 0x810B,
            ".wicfs_release_invalid_byte_trap": 0x8120,
            ".s_guard": 0x8200,
            ".e_guard": 0x8260,
        }]
        base = """
wicfs_state_ram = &0380
wicfs_machine = &C3
filev_x = &0396
filev_y = &0397
notape = &0398
romsel = &0780
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
            aliased = [dict(labels[0])]
            aliased[0][".wicfs_load_pre_tape"] = aliased[0][".wicfs_reset_done"]
            (root / "labels.txt").write_text(repr(aliased))
            bad_layout = subprocess.run(
                command, capture_output=True, text=True, check=False
            )
            self.assertNotEqual(bad_layout.returncode, 0)
            self.assertIn("complete reset epilogue", bad_layout.stderr)
            (root / "labels.txt").write_text(repr(labels))
            (root / "uef.asm").write_text("uef_length_hi = &0395\n")
            collision = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertNotEqual(collision.returncode, 0)
            self.assertIn("stack-local", collision.stderr)

    def test_tube_off_guard_survives_low_loader_vector_table_overwrite(self) -> None:
        text = LOW_LOADER_GUARD.read_text()
        self.assertIn("romsel\t=\t&0780", text)
        self.assertIn("loaders routinely overwrite &0900-&10FF", text)
        self.assertIn(".wicfs_publish_guards_if_host_only", text)
        self.assertIn("LDA\t#&EA", text)
        self.assertIn("CPX\t#&FF", text)
        self.assertIn(".guard_offsets", text)
        self.assertIn("equb\t27,33,42,45", text)
        self.assertIn("equb\t&1B,&21,&2A,&2D", text)
        self.assertIn("ASSERT romsel+(e_guard-s_guard) <= &0800", text)
        for entry in (".guard_file", ".guard_bget", ".guard_find", ".guard_fsc"):
            body = text.split(entry, 1)[1].split("LDA\t#", 1)[0]
            self.assertIn("PHP", body)
            self.assertIn("SEI", body)
        # Reset must first rebuild overwritten extended tuples and replace the
        # guard vectors with the normal MOS dispatchers. Otherwise the guard
        # would remain installed after stream retirement and a second MENU
        # invocation could re-enter stale WiCFS state.
        reset = text.split(".wicfs_reset_active", 1)[1]
        self.assertLess(reset.index("JSR\twicfs_publish_extended_vectors"),
                        reset.index(".wicfs_reset_vectors_ready"))
        for dispatcher in ("&FF1B", "&FF21", "&FF2A", "&FF2D"):
            self.assertIn(dispatcher, reset)

    def test_assembled_low_loader_guard_repairs_filev_tuple_and_preserves_call(self) -> None:
        match = self.find_rom_routine(
            rb"\x08\x48\x78\xA9\x00\x10.\x08\x48\x78\xA9\x01\x10."
            rb"\x08\x48\x78\xA9\x02\x10.\x08\x48\x78\xA9\x03"
        )
        template = self.rom[match.start():match.start() + 0x80]
        dispatch = template.find(b"\x1B\x21\x2A\x2D\x00\x00")
        self.assertGreater(dispatch, 0, "guard dispatch/slot table not found")

        mpu = MPU()
        mpu.memory[0x0780:0x0800] = template
        mpu.memory[0x0780 + dispatch + 4] = 3  # installed ROM slot
        # Simulate a cassette loader overwriting every extended tuple.
        mpu.memory[0x0400 + 27:0x0400 + 30] = [0xAA, 0xBB, 0xCC]
        mpu.pc = 0x0780
        mpu.a, mpu.x, mpu.y = 0xFF, 0x34, 0x12
        mpu.p = 0xA1  # normal IRQ-enabled caller
        mpu.sp = 0xFD
        sentinel = 0x0600
        return_address = sentinel - 1
        mpu.memory[0x01FE] = return_address & 0xFF
        mpu.memory[0x01FF] = return_address >> 8
        entered_dispatch = False

        def mos_return() -> None:
            low = mpu.memory[0x0100 + ((mpu.sp + 1) & 0xFF)]
            high = mpu.memory[0x0100 + ((mpu.sp + 2) & 0xFF)]
            mpu.sp = (mpu.sp + 2) & 0xFF
            mpu.pc = (((high << 8) | low) + 1) & 0xFFFF

        for _ in range(1000):
            if mpu.pc == sentinel:
                break
            if mpu.pc == 0xFFF4:
                self.assertEqual((mpu.a, mpu.x, mpu.y), (0xA8, 0, 0xFF))
                mpu.x, mpu.y = 0x00, 0x04
                mos_return()
            elif mpu.pc == 0xFF1B:
                entered_dispatch = True
                self.assertEqual((mpu.a, mpu.x, mpu.y), (0xFF, 0x34, 0x12))
                # PHP records the architecturally synthetic B flag. All real
                # caller flags must otherwise be unchanged at the dispatcher.
                self.assertEqual(mpu.p & 0xEF, 0xA1)
                repaired = bytes(mpu.memory[0x0400 + 27:0x0400 + 30])
                self.assertNotEqual(repaired[:2], b"\xAA\xBB")
                self.assertEqual(repaired[2], 3)
                mpu.a = 1
                mpu.p |= mpu.CARRY
                mos_return()
            else:
                mpu.step()
        else:
            self.fail("assembled FILEV guard did not return")

        self.assertTrue(entered_dispatch)
        self.assertEqual((mpu.a, mpu.x, mpu.y), (1, 0x34, 0x12))
        self.assertTrue(mpu.p & mpu.CARRY)

    def test_inactive_host_tape_transition_returns_with_balanced_stack(self) -> None:
        # Locate the assembled host transition by its four-call control-flow shape.
        # This executes the emitted ROM, so a source patch which aliases the
        # reset epilogue and helper cannot pass by textual inspection alone.
        match = self.find_rom_routine(
            rb"\x20..\xB0.\x20..\x20..\x90.\x20"
        )
        # 255 is the maximum capture-delay override accepted by the Elkulator
        # Pi1MHz integration. This makes the lifecycle path prove that every
        # private cursor access gets a complete quiet window, rather than only
        # passing the emulator's normal low-latency profile.
        memory = DelayedOneSlotMailbox(self.rom, delay_accesses=255)
        mpu = MPU(memory=memory)
        mpu.pc = ROM_START + match.start()
        mpu.sp = 0xFD
        sentinel = 0x0600
        return_address = sentinel - 1
        memory.ram[0x01FE] = return_address & 0xFF
        memory.ram[0x01FF] = return_address >> 8
        memory.ram[0x020A] = 0x34  # ordinary MOS BYTEV, no active WiCFS trap
        memory.ram[0x020B] = 0x12
        oscli_commands = []

        def mos_return() -> None:
            low = memory.ram[0x0100 + ((mpu.sp + 1) & 0xFF)]
            high = memory.ram[0x0100 + ((mpu.sp + 2) & 0xFF)]
            mpu.sp = (mpu.sp + 2) & 0xFF
            mpu.pc = (((high << 8) | low) + 1) & 0xFFFF

        for _ in range(300000):
            if mpu.pc == sentinel:
                break
            if mpu.pc == 0xFFF4:  # OSBYTE &A8: extended-vector table address
                self.assertEqual(mpu.a, 0xA8)
                mpu.x, mpu.y = 0x00, 0x04
                mos_return()
            elif mpu.pc == 0xFFF7:  # OSCLI TAPE
                address = mpu.x | mpu.y << 8
                command = bytearray()
                while memory.ram[address] != 0x0D:
                    command.append(memory.ram[address])
                    address += 1
                oscli_commands.append(bytes(command))
                mos_return()
            else:
                mpu.step()
        else:
            self.fail("inactive menu_select_tape did not return")

        self.assertEqual(oscli_commands, [b"TAPE"])
        self.assertEqual(mpu.sp, 0xFF)
        self.assertEqual(mpu.p & mpu.CARRY, 0)
        self.assertEqual(memory.collisions, 0)

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

    def test_page_selector_retains_proven_physical_settle_budget(self) -> None:
        text = PAGE_SELECT_FAST.read_text()
        self.assertNotIn("+\tLDA\t#16", text)
        self.assertIn("+.wicfs_select_public_page_a", text)

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
            rb"\x28\xba\xbd\x02\x01\x1d\x01\x01"
        )
        start = ROM_START + match.start()
        for value, expected_zero in (
            (0x0000, True),
            (0x0100, False),
            (0x01FF, False),
            (0xFFFE, False),
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
                # PLP, TSX, LDA high and ORA low. Inspect the result before
                # following either the legacy or negotiated-stream branch.
                for _ in range(4):
                    mpu.step()
                self.assertEqual(bool(mpu.p & mpu.ZERO), expected_zero)
                self.assertEqual(mpu.sp, 0xF0)

    def test_assembled_incremental_reply_parser_preserves_ff00_window(self) -> None:
        # Enter at the token-skip loop and replace only service_driver_read_a
        # with a deterministic reply source. This executes the assembled ROM
        # parser, so an extra or missing mailbox read cannot be hidden by a
        # source-level protocol model.
        match = self.find_rom_routine(
            rb"\xA2\x04\x20(..)\xCA\xD0\xFA\x20\1"
        )
        start = ROM_START + match.start()
        read_a = match.group(1)[0] | match.group(1)[1] << 8
        memory = bytearray(0x10000)
        memory[ROM_START:ROM_START + len(self.rom)] = self.rom
        mpu = MPU(memory=memory, pc=start)
        mpu.sp = 0xF0
        sentinel = 0x0600
        return_address = sentinel - 1
        memory[0x01F1] = return_address & 0xFF
        memory[0x01F2] = return_address >> 8

        # token, 32-bit generation, 16-bit length, final flag and format.
        reply = iter((0xA1, 0xB2, 0xC3, 0xD4,
                      0x34, 0x12, 0x78, 0x56,
                      0x00, 0xFF, 0x00, ord("G")))
        reads = 0
        for _ in range(5000):
            if mpu.pc == sentinel:
                break
            if mpu.pc == read_a:
                mpu.a = next(reply)
                reads += 1
                low = memory[0x0100 + ((mpu.sp + 1) & 0xFF)]
                high = memory[0x0100 + ((mpu.sp + 2) & 0xFF)]
                mpu.sp = (mpu.sp + 2) & 0xFF
                mpu.pc = ((high << 8) | low) + 1
            else:
                mpu.step()
        else:
            self.fail("incremental response parser did not return")

        self.assertEqual(reads, 12)
        self.assertEqual(memory[0x0DAE:0x0DB0], bytes((0x34, 0x12)))
        self.assertEqual(memory[0x00F8:0x00FA], bytes((0x00, 0xFF)))
        self.assertEqual(memory[0x00F5], 0x80)  # incremental, not final
        self.assertEqual(memory[0x0DAD], ord("G"))
        # The read cursor returns to the first byte of the window, which is
        # page 1 offset 0: JIM page 0 is the service reply buffer and the
        # stream is published above it so a reply cannot overwrite it.
        self.assertEqual(memory[0x00C7:0x00C9], bytes((0, 1)))
        self.assertEqual(mpu.p & mpu.CARRY, 0)
        with self.assertRaises(StopIteration):
            next(reply)

    def test_incremental_generation_survives_complete_loader_workspace_overwrite(self) -> None:
        load = self.find_rom_routine(
            rb"\x08\x78\x48\x8A\x48\xA2\x1A\x20..\xAD\xA9\xFC\x20..\x8D\xAE\x0D"
        )
        save = self.find_rom_routine(
            rb"\x08\x78\x48\x8A\x48\xA2\x1A\x20..\xAD\xAE\x0D\x8D\xA9\xFC"
        )
        memory = DelayedOneSlotMailbox(self.rom)

        def call(address: int) -> None:
            mpu = MPU(memory=memory, pc=address)
            mpu.sp = 0xFD
            sentinel = 0x0600
            return_address = sentinel - 1
            memory.ram[0x01FE] = return_address & 0xFF
            memory.ram[0x01FF] = return_address >> 8
            for _ in range(5000):
                if mpu.pc == sentinel:
                    return
                mpu.step()
            self.fail("generation persistence helper did not return")

        memory.ram[0x0DAE:0x0DB0] = bytes((0x34, 0x12))
        call(ROM_START + save.start())
        # This is the exact host-memory range occupied by the observed A-CODE
        # loader. It destroys netprt and the old generation scratch bytes.
        memory.ram[0x0900:0x1100] = b"\xA5" * 0x800
        self.assertEqual(memory.ram[0x0DAE:0x0DB0], b"\xA5\xA5")
        call(ROM_START + load.start())
        self.assertEqual(memory.ram[0x0DAE:0x0DB0], bytes((0x34, 0x12)))
        self.assertEqual(memory.collisions, 0)

    def test_assembled_first_file_classifier_obeys_basic_line_boundary(self) -> None:
        match = self.find_rom_routine(
            rb"\x20(..)\x20(..)\xA9\x00\x85.\x8D\xD2\x03"
            rb"\x20(..)\xB0.\x20(..)\xB0.\xF0.\x20(..)\xB0."
        )
        start = ROM_START + match.start()
        cfsinit = match.group(1)[0] | match.group(1)[1] << 8
        wsinit = match.group(2)[0] | match.group(2)[1] << 8
        newuef = match.group(3)[0] | match.group(3)[1] << 8
        findf = match.group(4)[0] | match.group(4)[1] << 8
        getbyte = match.group(5)[0] | match.group(5)[1] << 8
        chain = ROM_START + self.rom.index(b'*REWIND\rCHAIN ""\r\xff')
        run = ROM_START + self.rom.index(b'*REWIND\r*RUN ""\r\xff')

        def classify(first_file: bytes) -> tuple[bool, int]:
            memory = bytearray(0x10000)
            memory[ROM_START:ROM_START + len(self.rom)] = self.rom
            mpu = MPU(memory=memory, pc=start)
            mpu.sp = 0xFD
            sentinel = 0x0600
            return_address = sentinel - 1
            memory[0x01FE] = return_address & 0xFF
            memory[0x01FF] = return_address >> 8
            stream = iter(first_file)

            def return_from_stub() -> None:
                low = memory[0x0100 + ((mpu.sp + 1) & 0xFF)]
                high = memory[0x0100 + ((mpu.sp + 2) & 0xFF)]
                mpu.sp = (mpu.sp + 2) & 0xFF
                mpu.pc = (((high << 8) | low) + 1) & 0xFFFF

            for _ in range(20000):
                if mpu.pc == sentinel:
                    return bool(mpu.p & mpu.CARRY), mpu.a | mpu.x << 8
                if mpu.pc in (cfsinit, wsinit):
                    return_from_stub()
                elif mpu.pc == newuef:
                    mpu.p &= ~mpu.CARRY
                    return_from_stub()
                elif mpu.pc == findf:
                    mpu.a = 1
                    mpu.p &= ~(mpu.CARRY | mpu.ZERO)
                    return_from_stub()
                elif mpu.pc == getbyte:
                    try:
                        mpu.a = next(stream)
                        mpu.p &= ~mpu.CARRY
                    except StopIteration:
                        mpu.p |= mpu.CARRY
                    return_from_stub()
                else:
                    mpu.step()
            self.fail("assembled first-file classifier did not return")

        # Real BBC BASIC line shape: length &0B points at the CR at offset
        # &0B, not at the preceding byte. This is the boundary that exposed
        # the former SBC #4 off-by-one with Thrust and Desk Diary.
        basic = bytes((0x0D, 0x00, 0x0A, 0x0B,
                       0xF4, 0x20, 0x22, 0x58, 0x22, 0x3A, 0x40, 0x0D))
        self.assertEqual(classify(basic), (False, chain))

        # An early CR must not make arbitrary machine code look like BASIC.
        misleading_machine = bytes((0x0D, 0x00, 0x0A, 0x0B,
                                    0x0D, 0xA9, 0x00, 0x8D,
                                    0x00, 0x20, 0x60, 0xEA))
        self.assertEqual(classify(misleading_machine), (False, run))

        # Truncation before the declared boundary is a probe failure. It must
        # not queue either launch command from incomplete evidence.
        truncated = basic[:-1]
        failed, _ = classify(truncated)
        self.assertTrue(failed)

    @staticmethod
    def _trampoline_image(slot=3, preselect=12, sel=0xFE05,
                          handlers=(0x9000, 0x9100, 0x9200, 0x9300)):
        """The stub image the Pi mirrors into every JIM page.

        Built here to the same layout elkwifi_service.c uses, so this test
        exercises the real instruction sequence rather than a description of
        it. Offsets: four entries at 0/9/18/27, pager at 36, unpager at 95.
        """
        base = 0xFD00 + 0x68
        pager, unpager = base + 36, base + 95
        out = bytearray(143)
        for i, handler in enumerate(handlers):
            e = i * 9
            out[e:e + 9] = bytes((
                0x20, pager & 0xFF, pager >> 8,
                0x20, handler & 0xFF, handler >> 8,
                0x4C, unpager & 0xFF, unpager >> 8))
        q = bytearray()
        q += bytes((0x08, 0x78, 0x48, 0x8A, 0x48, 0x48, 0xBA))
        for src, dst in ((2, 1), (3, 2), (4, 3), (5, 4), (6, 5)):
            q += bytes((0xBD, src, 0x01, 0x9D, dst, 0x01))
        q += bytes((0xA5, 0xF4, 0x9D, 0x06, 0x01))
        q += bytes((0xA9, preselect, 0x8D, sel & 0xFF, sel >> 8))
        q += bytes((0xA9, slot, 0x85, 0xF4, 0x8D, sel & 0xFF, sel >> 8))
        q += bytes((0x68, 0xAA, 0x68, 0x28, 0x60))
        out[36:36 + len(q)] = q
        r = bytearray()
        r += bytes((0x08, 0x78, 0x48, 0x8A, 0x48, 0xBA))
        r += bytes((0xA9, preselect, 0x8D, sel & 0xFF, sel >> 8))
        r += bytes((0xBD, 0x04, 0x01, 0x85, 0xF4, 0x8D, sel & 0xFF, sel >> 8))
        for src, dst in ((3, 4), (2, 3), (1, 2)):
            r += bytes((0xBD, src, 0x01, 0x9D, dst, 0x01))
        r += bytes((0xE8, 0x9A, 0x68, 0xAA, 0x68, 0x28, 0x60))
        out[95:95 + len(r)] = r
        out[139:143] = b"WCFS"
        return bytes(out)

    def test_trampoline_survives_a_nested_filing_call(self) -> None:
        """A filing call inside a filing call must page the right ROM back.

        This is what `*/` does: FSCV reason 2 enters WiCFS, which calls OSFILE
        to load the next file, so FILEV is entered while WiCFS is already
        paged in. The displaced ROM number therefore differs between the two
        levels, and each exit has to restore its own. Getting this wrong pages
        the wrong bank back under the caller, which is why the trampoline
        builds the MOS frame rather than keeping one saved copy.
        """
        CALLER_ROM, OUR_SLOT = 0x0B, 0x03
        base, sentinel = 0xFD68, 0x0600
        memory = bytearray(0x10000)
        image = self._trampoline_image(slot=OUR_SLOT)
        memory[base:base + len(image)] = image

        # FILEV handler: record the frame's ROM and what is paged in.
        filev_stub = bytes((
            0x08, 0xBA, 0xBD, 0x04, 0x01, 0x85, 0x72,
            0xA5, 0xF4, 0x85, 0x73, 0x28, 0x60))
        memory[0x9000:0x9000 + len(filev_stub)] = filev_stub
        # FSCV handler: record its own frame, then nest a FILEV call.
        fscv_stub = bytes((
            0x85, 0x74, 0x86, 0x75, 0x84, 0x76,   # record the arguments
            0x08, 0xBA, 0xBD, 0x04, 0x01, 0x85, 0x70, 0x28,
            0x20, base & 0xFF, base >> 8,         # nested FILEV, as *\ does
            0xA5, 0xF4, 0x85, 0x71,
            0xA9, 0x99, 0xA2, 0x77, 0xA0, 0x55,   # hand back a known result
            0x60))
        memory[0x9300:0x9300 + len(fscv_stub)] = fscv_stub

        memory[0x00F4] = CALLER_ROM
        mpu = MPU(memory=memory, pc=base + 27)      # the FSCV entry
        mpu.sp = 0xF0
        memory[0x01F1] = (sentinel - 1) & 0xFF
        memory[0x01F2] = (sentinel - 1) >> 8
        mpu.a, mpu.x, mpu.y = 0x5A, 0xA5, 0x3C

        for _ in range(20000):
            if mpu.pc == sentinel:
                break
            mpu.step()
        else:
            self.fail("the trampoline did not return")

        self.assertEqual(memory[0x0070], CALLER_ROM,
                         "outer handler was not handed the caller's ROM")
        self.assertEqual(memory[0x0072], OUR_SLOT,
                         "nested handler was not handed the ROM that called it")
        self.assertEqual(memory[0x0073], OUR_SLOT,
                         "nested handler ran with the wrong ROM paged in")
        self.assertEqual(memory[0x0071], OUR_SLOT,
                         "our ROM was not paged back after the nested call")
        self.assertEqual(memory[0x00F4], CALLER_ROM,
                         "the caller's ROM was not paged back on exit")
        # 0xF0 plus the two bytes the final RTS consumes: balanced.
        self.assertEqual(mpu.sp, 0xF2, "the trampoline leaked stack")
        self.assertEqual(
            (memory[0x0074], memory[0x0075], memory[0x0076]),
            (0x5A, 0xA5, 0x3C),
            "the handler was not given the caller's A, X and Y")
        self.assertEqual(
            (mpu.a, mpu.x, mpu.y), (0x99, 0x77, 0x55),
            "the handler's result did not survive the exit")

    def _getbyte_symbols(self):
        match = self.find_rom_routine(
            rb"\xA5(.)\x05(.)\xD0\x05\x20(..)\xB0\x25"
            rb"\x08\x78\xA4(.)\xA5(.)\x20..\xB9\x00\xFD"
            rb".{25}\x38\x60"
        )
        return {
            "start": ROM_START + match.start(),
            "final_rts": ROM_START + match.end() - 1,
            "sbufl": match.group(1)[0], "sbufh": match.group(2)[0],
            "refill": match.group(3)[0] | match.group(3)[1] << 8,
            "pr_y": match.group(4)[0], "pr_r": match.group(5)[0],
        }

    def _drain(self, memory, sym, calls, on_refill=None):
        """Call the assembled getbyte `calls` times, returning what it read."""
        got = bytearray()
        refills = 0
        for _ in range(calls):
            mpu = MPU(memory=memory, pc=sym["start"])
            mpu.sp = 0xF0
            for _ in range(4000):
                if mpu.pc == sym["final_rts"]:
                    break
                if mpu.pc == sym["refill"]:
                    refills += 1
                    if on_refill is not None and on_refill():
                        mpu.p &= ~mpu.CARRY   # a window was published
                    else:
                        mpu.p |= mpu.CARRY    # nothing left: report EOF
                    low = memory[0x0100 + ((mpu.sp + 1) & 0xFF)]
                    high = memory[0x0100 + ((mpu.sp + 2) & 0xFF)]
                    mpu.sp = (mpu.sp + 2) & 0xFF
                    mpu.pc = ((high << 8) | low) + 1
                else:
                    mpu.step()
            else:
                self.fail("getbyte did not return")
            if mpu.p & mpu.CARRY:
                break
            got.append(mpu.a)
        return bytes(got), refills

    def _staged_window(self, memory, values, first_page=0):
        """Lay bytes out the way the Pi publishes them: a full JIM page each."""
        usable = 0x100
        for index, value in enumerate(values):
            page = (first_page + index // usable) & 0xFF
            memory.page_data[page, index % usable] = value

    def test_getbyte_reads_a_published_window_contiguously(self) -> None:
        """A full page per JIM page, then step the page.

        The reader must hand back the stream in order across a page boundary;
        a page step that fires early or late silently splices the window.
        """
        sym = self._getbyte_symbols()
        memory = DelayedOneSlotMailbox(self.rom, 1)
        memory.ram[0x00C3] = 1
        memory.ram[0x00F5] = 0x80
        window = bytes((i & 0xFF) for i in range(300))
        self._staged_window(memory, window)
        memory.ram[sym["sbufl"]] = len(window) & 0xFF
        memory.ram[sym["sbufh"]] = len(window) >> 8
        memory.ram[sym["pr_y"]] = 0
        memory.ram[sym["pr_r"]] = 0
        got, _ = self._drain(memory, sym, len(window) + 1)
        self.assertEqual(got, window)

    def test_getbyte_crosses_a_refill_without_losing_its_place(self) -> None:
        """A stream larger than one window is the case a third of the corpus hits.

        Above one window the Pi publishes more than one, so the host
        drains one, asks for a refill and carries on from the first byte of the
        next. WiCFS reported chunk type &5245 on exactly those titles, which is
        ASCII it read after losing its place, so walk the boundary byte by byte.
        """
        sym = self._getbyte_symbols()
        memory = DelayedOneSlotMailbox(self.rom, 1)
        memory.ram[0x00C3] = 1
        memory.ram[0x00F5] = 0x80
        first = bytes((i & 0xFF) for i in range(300))
        second = bytes(((300 + i) & 0xFF) for i in range(120))
        self._staged_window(memory, first)
        memory.ram[sym["sbufl"]] = len(first) & 0xFF
        memory.ram[sym["sbufh"]] = len(first) >> 8
        memory.ram[sym["pr_y"]] = 0
        memory.ram[sym["pr_r"]] = 0

        published = []

        def publish_second():
            if published:          # the second refill is the true end of stream
                return False
            published.append(True)
            self._staged_window(memory, second)
            memory.ram[sym["sbufl"]] = len(second) & 0xFF
            memory.ram[sym["sbufh"]] = len(second) >> 8
            memory.ram[sym["pr_y"]] = 0
            memory.ram[sym["pr_r"]] = 0
            return True

        got, refills = self._drain(
            memory, sym, len(first) + len(second) + 1, publish_second
        )
        self.assertEqual(refills, 2, "one refill for the window, one for EOF")
        self.assertEqual(got, first + second)

    def test_getbyte_survives_the_page_counter_wrapping(self) -> None:
        """A full window ends on page 255, so the counter wraps to zero there."""
        sym = self._getbyte_symbols()
        memory = DelayedOneSlotMailbox(self.rom, 1)
        memory.ram[0x00C3] = 1
        memory.ram[0x00F5] = 0x80
        window = bytes((i & 0xFF) for i in range(600))
        self._staged_window(memory, window, first_page=0xFE)
        memory.ram[sym["sbufl"]] = len(window) & 0xFF
        memory.ram[sym["sbufh"]] = len(window) >> 8
        memory.ram[sym["pr_y"]] = 0
        memory.ram[sym["pr_r"]] = 0xFE
        got, _ = self._drain(memory, sym, len(window) + 1)
        self.assertEqual(got, window)

    def test_assembled_getbyte_refills_without_resetting_parser_state(self) -> None:
        match = self.find_rom_routine(
            # The page-step is the natural wrap at 256: the Pi publishes a
            # whole JIM page of stream, so iny alone decides when to step.
            rb"\xA5(.)\x05(.)\xD0\x05\x20(..)\xB0\x25"
            rb"\x08\x78\xA4(.)\xA5(.)\x20..\xB9\x00\xFD"
            rb".{25}\x38\x60"
        )
        start = ROM_START + match.start()
        final_rts = ROM_START + match.end() - 1
        sbufl, sbufh = match.group(1)[0], match.group(2)[0]
        refill = match.group(3)[0] | match.group(3)[1] << 8
        pr_y, pr_r = match.group(4)[0], match.group(5)[0]

        memory = bytearray(0x10000)
        memory[ROM_START:ROM_START + len(self.rom)] = self.rom
        memory[0x00C3] = 1  # Electron/AP5 selector forwarding.
        memory[0x00F5] = 0x80  # incremental and not final
        memory[0xFD00] = 0xA7
        mpu = MPU(memory=memory, pc=start)
        mpu.sp = 0xF0
        refill_calls = 0

        for _ in range(20000):
            if mpu.pc == final_rts:
                break
            if mpu.pc == refill:
                refill_calls += 1
                memory[sbufl] = 2
                memory[sbufh] = 0
                memory[pr_y] = 0
                memory[pr_r] = 0
                mpu.p &= ~mpu.CARRY
                low = memory[0x0100 + ((mpu.sp + 1) & 0xFF)]
                high = memory[0x0100 + ((mpu.sp + 2) & 0xFF)]
                mpu.sp = (mpu.sp + 2) & 0xFF
                mpu.pc = ((high << 8) | low) + 1
            else:
                mpu.step()
        else:
            self.fail("getbyte did not return after publishing a refill")

        self.assertEqual(refill_calls, 1)
        self.assertEqual(mpu.a, 0xA7)
        self.assertEqual(memory[sbufl], 1)
        self.assertEqual(memory[sbufh], 0)
        self.assertEqual(memory[pr_y], 1)
        self.assertEqual(memory[pr_r], 0)
        self.assertEqual(mpu.p & mpu.CARRY, 0)
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

    def test_assembled_wget_file_sink_passes_each_byte_to_mos(self) -> None:
        match = self.find_rom_routine(
            rb"\x68\xac(..)\x20\xd4\xff\x4c(..)"
        )
        start = ROM_START + match.start()
        handle_address = match.group(1)[0] | match.group(1)[1] << 8
        copied = match.group(2)[0] | match.group(2)[1] << 8

        mpu = MPU()
        mpu.memory[ROM_START:ROM_START + len(self.rom)] = self.rom
        mpu.pc = start
        mpu.sp = 0xEF
        mpu.memory[0x01F0] = 0xA7
        mpu.memory[handle_address] = 0x35

        calls = []
        for _ in range(32):
            if mpu.pc == copied:
                break
            if mpu.pc == 0xFFD4:
                calls.append((mpu.a, mpu.y))
                low = mpu.memory[0x0100 + ((mpu.sp + 1) & 0xFF)]
                high = mpu.memory[0x0100 + ((mpu.sp + 2) & 0xFF)]
                mpu.sp = (mpu.sp + 2) & 0xFF
                mpu.pc = ((high << 8) | low) + 1
            else:
                mpu.step()
        else:
            self.fail("WGET file sink did not return from OSBPUT")

        self.assertEqual(calls, [(0xA7, 0x35)])
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
            # Both reply-copy paths are unchanged again: the reply buffer no
            # longer shares pages with the stream, so nothing has to be marked
            # or repaired here.
            rb"\x08\x78\x48\xad(..)\x20..\x68\x9d\x00\xfd\x20..\x28\x4c..",
            rb"\x08\x78\x48\xad(..)\x20..\x68\x9d\x00\xfd\x20..\x28\x60",
        )
        for pattern in write_patterns:
            with self.subTest(pattern=pattern):
                write = self.find_rom_routine(pattern)
                write_start = ROM_START + write.start()
                write_shadow = (
                    write.group(1)[0] | write.group(1)[1] << 8
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
        reset_service = text.split("@@ -138,7 +138,8 @@", 1)[1].split(
            "@@", 1
        )[0]
        self.assertNotIn("wicfs_any_vector_owned", reset_service)
        self.assertIn("bne autorun_wicfs_released", reset_service)
        self.assertIn("jsr release_owned_wicfs", reset_service)
        self.assertIn("cannot execute a partially rewritten handler", text)
        self.assertEqual(text.count("+\tJSR\tinstall_extended_vector"), 0)
        self.assertNotIn("+\tLDA\t#&8C", text)
        finish = text.split("+.wicfs_finish_if_exhausted", 1)[1].split(
            "+.wicfs_any_vector_owned", 1
        )[0]
        self.assertIn("+\tJMP\twicfs_reset", finish)
        self.assertIn("+.wicfs_install_invalid", text)
        uef = (ROOT / "rom-side/elkwifi-0.23/overlay/uef.asm").read_text()
        self.assertIn("jsr print_wicfs_power_cycle", uef)
        for vector, dispatcher in (
            ("OSFILEV", "&FF1B"),
            ("OSBGETV", "&FF21"),
            ("OSFINDV", "&FF2A"),
            ("OSFSCV", "&FF2D"),
        ):
            self.assertIn(f"+\tLDA\t{vector}", text)
            self.assertIn(f"+\tCMP\t#<{dispatcher}", text)
            self.assertIn(f"+\tCMP\t#>{dispatcher}", text)

    def test_final_bget_retires_the_complete_wicfs_installation(self) -> None:
        patch = (
            ROOT
            / "rom-side/elkwifi-0.23/patches/wicfs-bget-exhaustion.patch"
        ).read_text()
        self.assertIn("+.xbgetv\tPHP", patch)
        self.assertIn("+\tSTA\ttemp", patch)
        self.assertIn("+\tJSR\twicfs_finish_if_exhausted", patch)
        self.assertIn("+\tPLP", patch)
        self.assertLess(
            patch.index("JSR\twicfs_finish_if_exhausted"),
            patch.index("\n \tPLA\n"),
        )

    def test_stream_install_and_reset_are_transactional(self) -> None:
        text = STREAM_FINISH.read_text()
        self.assertIn("+.wicfs_install_check_partial", text)
        self.assertIn("+.wicfs_install_components_ok", text)
        self.assertIn("+.wicfs_release_invalid_byte_trap", text)
        self.assertIn("+                    bcs autorun_wicfs_abort", text)
        self.assertIn("+.autorun_wicfs_abort", text)
        uef = (ROOT / "rom-side/elkwifi-0.23/overlay/uef.asm").read_text()
        self.assertIn(".uef_run_failed", uef)
        self.assertIn("bcs uef_run_failed", uef)
        self.assertIn("+\tBCC\tbUPCFS_installed", text)
        self.assertIn("+\tLDX\t#(error_wicfs_state-error_table)", text)
        self.assertIn("+.bUPCFS_installed", text)
        self.assertIn("jsr print_wicfs_power_cycle", uef)
        host = (ROOT / "rom-side/elkwifi-0.23/overlay/host_launch.asm").read_text()
        self.assertEqual(host.count('equs "WiCFS state invalid; power cycle"'), 1)

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

        reset_service = text.split("@@ -138,7 +138,8 @@", 1)[1].split(
            "@@", 1
        )[0]
        self.assertEqual(reset_service.count("bne autorun_wicfs_released"), 1)
        self.assertIn("+                    bcs autorun_wicfs_abort", reset_service)
        self.assertNotIn("wicfs_any_vector_owned", reset_service)

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

    def test_tape_transition_preserves_the_real_filing_system_predecessor(self) -> None:
        patch = (
            ROOT
            / "rom-side/elkwifi-0.23/patches/wicfs-pre-tape-predecessor.patch"
        ).read_text()
        host_launch = (
            ROOT / "rom-side/elkwifi-0.23/overlay/host_launch.asm"
        ).read_text()
        uef = (ROOT / "rom-side/elkwifi-0.23/overlay/uef.asm").read_text()

        self.assertIn("+.wicfs_snapshot_pre_tape", patch)
        self.assertIn("+.wicfs_apply_pre_tape", patch)
        self.assertIn("private Pi JIM at &FFED00", patch)
        self.assertIn("+\tLDA\t#&ED", patch)
        self.assertNotIn("private Pi JIM at &FFEE00", patch)
        self.assertIn("+\tLDX\t#14", patch)
        self.assertIn("+\tLDA\tBYTEV\n+\tSTA\t&FCA9", patch)
        self.assertIn("+\tLDA\tBYTEV+1\n+\tSTA\t&FCA9", patch)

        retirement = (
            ROOT
            / "rom-side/elkwifi-0.23/patches/wicfs-dual-predecessor.patch"
        ).read_text()
        self.assertIn("+\tSTA\tbytev_rtn", retirement)
        self.assertIn("+\tSTA\tbytev_rtn+1", retirement)
        build = (ROOT / "rom-side/build_rom.sh").read_text()
        self.assertIn("retain the pre-\\*TAPE standard BYTEV as well", build)
        self.assertIn("STA\\tbytev_rtn+1", build)

        release = host_launch.index("jsr release_owned_wicfs")
        release_failed = host_launch.index("bcs host_tape_invalid", release)
        snapshot = host_launch.index("jsr wicfs_snapshot_pre_tape")
        select_tape = host_launch.index("jsr oscli", snapshot)
        self.assertLess(release, release_failed)
        self.assertLess(release_failed, snapshot)
        self.assertLess(release, snapshot)
        self.assertLess(snapshot, select_tape)
        self.assertLess(
            uef.index("jsr wicfs_install"),
            uef.index("jsr wicfs_apply_pre_tape"),
        )

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

        fast = PAGE_SELECT_FAST.read_text()
        helper = fast.split("+.wicfs_select_public_page_a", 1)[1].split(
            " .wicfs_state_address_x", 1
        )[0]
        self.assertIn("+\tLDX\twicfs_machine", helper)
        self.assertIn("+\tCPX\t#1", helper)
        self.assertIn("+\tSTA\t&FCFD", helper)
        self.assertIn("+\tSTA\t&FCFE", helper)
        self.assertIn("+\tSTA\tpagereg", helper)
        self.assertLess(helper.index("+\tSEI"), helper.index("+\tSTA\tpagereg"))
        self.assertLess(helper.index("+\tSTA\tpagereg"), helper.index("+\tPLP"))

    def test_assembled_fast_page_select_preserves_x_and_machine_decode(self) -> None:
        match = self.find_rom_routine(
            rb"\x08\x78\x48\x8A\x48\xA6.\xE0\x01\xF0."
            rb"\xA9\x00\x8D\xFD\xFC\x20..\x8D\xFE\xFC\x20.."
            rb"\x68\xAA\x68\x8D\xFF\xFC\x20..\x28\x60"
        )
        start = ROM_START + match.start()
        final_rts = ROM_START + match.end() - 1
        machine_address = self.rom[match.start() + 6]

        for machine, upper_value in ((1, 0xA5), (0, 0x00), (2, 0x00)):
            with self.subTest(machine=machine):
                memory = bytearray(0x10000)
                memory[ROM_START:ROM_START + len(self.rom)] = self.rom
                memory[machine_address] = machine
                memory[0xFCFD] = 0xA5
                memory[0xFCFE] = 0xA5
                mpu = MPU(memory=memory, pc=start)
                mpu.a = 0x37
                mpu.x = 0x91
                mpu.sp = 0xF0
                run_to(mpu, final_rts)
                self.assertEqual(mpu.x, 0x91)
                self.assertEqual(memory[0xFCFD], upper_value)
                self.assertEqual(memory[0xFCFE], upper_value)
                self.assertEqual(memory[0xFCFF], 0x37)

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
        # One commit publishes each full incremental source window; the
        # second checkpoints partial progress for the legacy path and Escape.
        self.assertEqual(read_loop.count("jsr uef_commit_length"), 2)
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
        text = PAGE_SELECT_FAST.read_text()
        getbyte = text.split("@@ -3013", 1)[1].split("@@ -3053", 1)[0]
        self.assertNotRegex(getbyte, r"(?m)^\+.*select the next physical page")
        self.assertIn("+    jsr wicfs_select_public_page_a", getbyte)
        self.assertNotIn("+    jsr wicfs_select_public_zero", getbyte)

    def test_starrun_filename_is_bounded(self) -> None:
        text = TRANSACTIONAL.read_text()
        starrun = text.split("@@ -1629", 1)[1].split("@@ -2346", 1)[0]
        self.assertIn("+\tCPX\t#10", starrun)
        self.assertIn("+\tBCS\tsr_a4", starrun)

    def test_host_transition_refuses_invalid_vector_record(self) -> None:
        host_launch = (
            ROOT / "rom-side/elkwifi-0.23/overlay/host_launch.asm"
        ).read_text()
        release = host_launch.split(".wicfs_release_tape_trap", 1)[1].split(
            ".host_basic_cmd", 1
        )[0]
        self.assertIn("jsr wicfs_state_load\n    bcs wicfs_release_tape_invalid", release)
        self.assertIn(".wicfs_release_tape_invalid\n    sec\n    rts", release)
        self.assertIn("WiCFS state invalid; power cycle", host_launch)

    def test_uef_tube_and_native_paths_share_host_tape_transition(self) -> None:
        uef = (ROOT / "rom-side/elkwifi-0.23/overlay/uef.asm").read_text()
        transition = uef.index("jsr host_select_tape")
        tube_query = uef.index("lda #&EA", transition)
        self.assertLess(transition, tube_query)
        launch = uef.split(".uef_launch", 1)[1].split(".uef_run_launch", 1)[0]
        self.assertNotIn("*TAPE", launch)
        host_launch = (
            ROOT / "rom-side/elkwifi-0.23/overlay/host_launch.asm"
        ).read_text()
        helper = host_launch.split(".host_select_tape", 1)[1].split(
            ".host_tape_command", 1
        )[0]
        self.assertIn("jsr oscli", helper)
        self.assertIn("clc\n    rts", helper)

    def test_wget_shared_uef_errors_do_not_pop_uef_stack_frame(self) -> None:
        uef = (ROOT / "rom-side/elkwifi-0.23/overlay/uef.asm").read_text()
        invalid = uef.split(".uef_invalid\n", 1)[1].split(
            ".uef_too_large_cleanup", 1
        )[0]
        too_large = uef.split(".uef_too_large\n", 1)[1].split(
            ".uef_stream_failed", 1
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
        run_return = RUN_RETURN.read_text()
        self.assertNotIn("+\tJMP\t(&03C2)", run_return)
        self.assertIn("+\tJSR\t&FFFF", run_return)
        self.assertIn("+\tRTS", run_return)

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

    def test_run_returns_through_the_intact_extended_vector_frame(self) -> None:
        text = RUN_RETURN.read_text()
        self.assertNotIn("+\tPLA", text)
        self.assertIn("+\tJSR\t&FFFF", text)
        self.assertIn("+\tRTS\t\t\t\\return through the intact MOS extended-vector frame", text)

    def test_cross_rom_vector_trampoline_uses_saved_handler_values(self) -> None:
        text = CHAIN_TARGET.read_text()
        for pointer in ("FILVRTN", "findv_rtn", "FSCVRTN"):
            self.assertIn(f"+\tLDA\t{pointer}", text)
            self.assertIn(f"+\tLDA\t{pointer}+1", text)
            self.assertNotIn(f"+\tLDA\t#<{pointer}", text)
            self.assertNotIn(f"+\tLDA\t#>{pointer}", text)

    def test_fscv_forwarding_preserves_entry_flags_and_stack(self) -> None:
        text = VECTOR_FLAGS.read_text()
        self.assertIn(".upfscv\n+\tPHP", text)
        self.assertIn("+\tLDA\t&0104,X", text)
        self.assertIn("+.chain_previous_rom_fscv", text)
        self.assertIn("+\tLDA\t#&28\t\t\t\\FSCV saved entry flags: patch PLP", text)
        self.assertIn("+\tLDA\t#&EA\t\t\t\\FILEV/FINDV have no saved entry flags: patch NOP", text)
        self.assertIn("+\tSTA\tchain_exec+(chain_entry_flags-chain_code)", text)
        self.assertIn("+\tJMP\tchain_previous_rom_fscv", text)
        self.assertIn("+\tPLP\n \tJMP\t(FSCVRTN)", text)
        self.assertIn("+\tPLP\t\t\t\\loaded code receives the native extended-vector stack", text)


if __name__ == "__main__":
    unittest.main()
