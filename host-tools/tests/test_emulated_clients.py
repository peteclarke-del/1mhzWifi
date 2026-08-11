"""Execute the assembled clients on a real 6502 emulator.

The harness supplies the MOS entry points used by the programs and models the
Pi1MHz services registers/JIM ABI at &FCA6-&FCAA. Tests operate on build/TERM
and build/SSH, not reimplementations of their assembly logic.
"""

import pathlib
import unittest

from test_build import dfs_file

try:
    from py65.devices.mpu6502 import MPU
except ImportError as exc:  # Make a missing release-test dependency explicit.
    raise RuntimeError(
        "py65 1.2.0 is required for executable emulator tests; "
        "run 'make emulator-deps'"
    ) from exc


ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_START = 0x1900
RETURN_SENTINEL = 0x1234

OSASCI = 0xFFE3
OSNEWL = 0xFFE7
OSWRCH = 0xFFEE
OSARGS = 0xFFDA
OSBYTE = 0xFFF4

SERVICE_ADDR_LO = 0xFCA6
SERVICE_ADDR_MI = 0xFCA7
SERVICE_ADDR_HI = 0xFCA8
SERVICE_DATA = 0xFCA9
SERVICE_COMMAND = 0xFCAA

NET_OK = 0x00
NET_PENDING = 0x01
NET_EOF = 0x20
NET_ERR_NOTOPEN = 0x22


def ssh_plain_packet(payload, cookie_padding_start=0x80):
    padding = (8 - ((5 + len(payload)) % 8)) % 8
    if padding < 4:
        padding += 8
    packet_length = 1 + len(payload) + padding
    return (packet_length.to_bytes(4, "big") + bytes((padding,)) + payload +
            bytes((cookie_padding_start + i) & 0xFF for i in range(padding)))


def ssh_kexinit_packet(kex=b"curve25519-sha256"):
    names = (
        kex, b"ssh-ed25519",
        b"aes128-ctr", b"aes128-ctr",
        b"hmac-sha2-256", b"hmac-sha2-256",
        b"none", b"none", b"", b"",
    )
    payload = bytes((20,)) + bytes(range(0x10, 0x20))
    payload += b"".join(len(name).to_bytes(4, "big") + name for name in names)
    payload += b"\x00\x00\x00\x00\x00"
    return ssh_plain_packet(payload)


class Pi1MHzMemory:
    """64K host memory plus the Pi1MHz services-port/JIM behavior."""

    def __init__(self, service=True, incoming=b"", eof_after_data=False,
                 read_chunks=(1, 2, 7, 3, 31), host_known=True,
                 password_required=False, expected_password=b"secret",
                 dispatch_busy_reads=0):
        self.ram = bytearray(65536)
        self.jim = bytearray(1 << 24)
        self.service = service
        self.address = 0
        self.command_result = 0
        self.command_pending = False
        self.dispatch_busy_reads = dispatch_busy_reads
        self.busy_reads_left = 0
        self.open_polls = 0
        self.opened = False
        self.closed = False
        self.opened_url = None
        self.incoming = bytearray(incoming)
        self.eof_after_data = eof_after_data
        self.read_chunks = tuple(read_chunks)
        self.read_index = 0
        self.sent = bytearray()
        self.host_known = host_known
        self.ssh_username = None
        self.password_required = password_required
        self.expected_password = expected_password
        self.password_supplied = None
        self.password_jim_wiped = False

    def __len__(self):
        return 65536

    def __getitem__(self, address):
        address &= 0xFFFF
        if not self.service:
            if SERVICE_ADDR_LO <= address <= SERVICE_COMMAND:
                return 0xFF
            return self.ram[address]
        if address == SERVICE_ADDR_LO:
            return self.address & 0xFF
        if address == SERVICE_ADDR_MI:
            return (self.address >> 8) & 0xFF
        if address == SERVICE_ADDR_HI:
            return (self.address >> 16) & 0xFF
        if address == SERVICE_DATA:
            value = self.jim[self.address]
            self.address = (self.address + 1) & 0xFFFFFF
            return value
        if address == SERVICE_COMMAND:
            if self.command_pending:
                if self.busy_reads_left:
                    self.busy_reads_left -= 1
                    return 0x80
                self.command_pending = False
                self.command_result = self._dispatch()
            return self.command_result
        return self.ram[address]

    def __setitem__(self, address, value):
        address &= 0xFFFF
        value &= 0xFF
        if not self.service:
            self.ram[address] = value
            return
        if address == SERVICE_ADDR_LO:
            self.address = (self.address & 0xFFFF00) | value
            return
        if address == SERVICE_ADDR_MI:
            self.address = (self.address & 0xFF00FF) | (value << 8)
            return
        if address == SERVICE_ADDR_HI:
            self.address = (self.address & 0x00FFFF) | (value << 16)
            return
        if address == SERVICE_DATA:
            self.jim[self.address] = value
            self.address = (self.address + 1) & 0xFFFFFF
            return
        if address == SERVICE_COMMAND:
            self.command_result = 0x80
            self.command_pending = True
            self.busy_reads_left = self.dispatch_busy_reads
            return
        self.ram[address] = value

    def load(self, address, data):
        self.ram[address:address + len(data)] = data

    def _u24(self, address):
        return (self.jim[address] | self.jim[address + 1] << 8 |
                self.jim[address + 2] << 16)

    def _u32(self, address):
        return self._u24(address) | self.jim[address + 3] << 24

    def _set_u24(self, address, value):
        self.jim[address:address + 3] = bytes(
            (value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF)
        )

    def _dispatch(self):
        block = 0xFFF000
        command = self.jim[block]
        if command == 60:  # URL_OPEN
            end = self.jim.index(0, block + 2, block + 224)
            self.opened_url = bytes(self.jim[block + 2:end]).decode("ascii")
            self.open_polls += 1
            if self.open_polls == 1:
                return NET_PENDING
            self.opened = True
            return NET_OK
        if command in (61, 97):  # URL_READ / managed SSH read
            if not self.opened:
                return NET_ERR_NOTOPEN
            maximum = self._u24(block + 1)
            destination = self._u32(block + 4)
            if self.incoming:
                chunk_limit = self.read_chunks[
                    self.read_index % len(self.read_chunks)
                ]
                self.read_index += 1
                count = min(maximum, chunk_limit, len(self.incoming))
                self.jim[destination:destination + count] = self.incoming[:count]
                del self.incoming[:count]
                self._set_u24(block + 1, count)
                return NET_OK
            self._set_u24(block + 1, 0)
            return NET_EOF if self.eof_after_data else NET_OK
        if command in (62, 98):  # URL_WRITE / managed SSH write
            if not self.opened:
                return NET_ERR_NOTOPEN
            count = self._u24(block + 1)
            source = self._u32(block + 4)
            # Force partial writes to exercise the clients' retry paths.
            consumed = min(count, 5)
            self.sent.extend(self.jim[source:source + consumed])
            self._set_u24(block + 1, consumed)
            return NET_OK
        if command in (63, 99):  # URL_CLOSE / managed SSH close
            self.closed = True
            self.opened = False
            return NET_OK
        if command == 94:  # SEC_CAPS
            self.jim[block + 1:block + 11] = bytes(
                (1, 1, 7, 0xB8, 0x88, 1, 1, ord("N"), ord("T"), ord("S"))
            )
            return NET_OK
        if command == 95:  # SEC_RANDOM
            count = self.jim[block + 1] | self.jim[block + 2] << 8
            destination = self._u32(block + 4)
            self.jim[destination:destination + count] = bytes(
                (0xA0 + index) & 0xFF for index in range(count)
            )
            return NET_OK
        if command == 96:  # managed SSH open
            flags = self.jim[block + 1]
            url_address = self._u32(block + 2)
            user_address = self._u32(block + 6)
            url_end = self.jim.index(0, url_address)
            user_end = self.jim.index(0, user_address)
            self.opened_url = bytes(
                self.jim[url_address:url_end]
            ).decode("ascii")
            self.ssh_username = bytes(
                self.jim[user_address:user_end]
            ).decode("ascii")
            if not self.host_known and not flags & 1:
                fingerprint = b"SHA256:fixture-host-key\0"
                self.jim[0x020500:0x020500 + len(fingerprint)] = fingerprint
                return 0x2C
            if flags & 1:
                self.host_known = True
            self.open_polls += 1
            if self.open_polls == 1:
                return NET_PENDING
            if (self.password_required and
                    self.password_supplied != self.expected_password):
                self.open_polls = 0
                return 0x2D
            self.opened = True
            return NET_OK
        if command == 100:  # ephemeral SSH password
            count = self.jim[block + 1]
            source = self._u32(block + 4)
            self.password_supplied = bytes(self.jim[source:source + count])
            self.jim[source:source + count] = bytes(count)
            self.password_jim_wiped = True
            return NET_OK
        return 0x27


class TextScreen:
    """Small MOS VDU model sufficient to assert visible client behavior."""

    def __init__(self, width=40, height=32):
        self.width = width
        self.height = height
        self.cells = [[" "] * width for _ in range(height)]
        self.x = 0
        self.y = 0
        self.pending = None
        self.params = []
        self.raw = bytearray()

    def emit(self, value):
        value &= 0xFF
        self.raw.append(value)
        if self.pending is not None:
            self.params.append(value)
            needed = 2 if self.pending == 31 else 1
            if len(self.params) == needed:
                if self.pending == 31:
                    self.x = min(self.params[0], self.width - 1)
                    self.y = min(self.params[1], self.height - 1)
                self.pending = None
                self.params.clear()
            return
        if value in (17, 31):
            self.pending = value
        elif value == 12:
            self.cells = [[" "] * self.width for _ in range(self.height)]
            self.x = self.y = 0
        elif value == 13:
            self.x = 0
        elif value == 10:
            self.y = min(self.y + 1, self.height - 1)
        elif value == 11:
            self.y = max(self.y - 1, 0)
        elif value == 8:
            self.x = max(self.x - 1, 0)
        elif value == 9:
            self.x = min(self.x + 1, self.width - 1)
        elif 32 <= value < 127:
            self.cells[self.y][self.x] = chr(value)
            self.x += 1
            if self.x == self.width:
                self.x = 0
                self.y = min(self.y + 1, self.height - 1)

    def text(self):
        return "\n".join("".join(row).rstrip() for row in self.cells)


class ClientMachine:
    def __init__(self, binary, arguments, *, service=True, incoming=b"",
                 eof_after_data=False, keys=(), host_known=True,
                 password_required=False, expected_password=b"secret",
                 dispatch_busy_reads=0):
        self.memory = Pi1MHzMemory(
            service=service, incoming=incoming, eof_after_data=eof_after_data,
            host_known=host_known, password_required=password_required,
            expected_password=expected_password,
            dispatch_busy_reads=dispatch_busy_reads,
        )
        self.memory.load(APP_START, binary)
        self.argument_address = 0x1000
        self.memory.load(self.argument_address, arguments.encode("ascii") + b"\r")
        self.screen = TextScreen()
        self.keys = list(keys)
        self.keyboard_polls = 0
        self.mpu = MPU(memory=self.memory, pc=APP_START)
        self.mpu.sp = 0xFF
        self.mpu.stPushWord(RETURN_SENTINEL - 1)
        self.mpu.x = self.argument_address & 0xFF
        self.mpu.y = self.argument_address >> 8

    def _return_from_jsr(self):
        self.mpu.pc = (self.mpu.stPopWord() + 1) & 0xFFFF

    def _mos_call(self):
        pc = self.mpu.pc
        if pc in (OSWRCH, OSASCI):
            value = self.mpu.a
            self.screen.emit(value)
            if pc == OSASCI and value == 13:
                self.screen.emit(10)
            self._return_from_jsr()
            return True
        if pc == OSNEWL:
            self.screen.emit(13)
            self.screen.emit(10)
            self._return_from_jsr()
            return True
        if pc == 0xFFE0:  # OSRDCH, used only by the host-key trust prompt
            self.mpu.a = self.keys.pop(0) if self.keys else ord("N")
            self._return_from_jsr()
            return True
        if pc == OSARGS:
            if self.mpu.a != 1 or self.mpu.y != 0:
                raise AssertionError(
                    f"unsupported OSARGS A={self.mpu.a} Y={self.mpu.y}"
                )
            block = self.mpu.x
            pointer = self.argument_address
            self.memory.ram[block:block + 4] = bytes(
                (pointer & 0xFF, pointer >> 8, 0, 0)
            )
            self._return_from_jsr()
            return True
        if pc == OSBYTE:
            reason = self.mpu.a
            if reason == 0x81:
                self.keyboard_polls += 1
                # Let network/parser work before delivering scripted keys.
                if self.keyboard_polls > 8 and self.keys:
                    self.mpu.x = self.keys.pop(0)
                    self.mpu.y = 0
                else:
                    self.mpu.y = 0xFF
            elif reason == 0x86:
                self.mpu.x = self.screen.x
                self.mpu.y = self.screen.y
            # Other calls configure keyboard state or wait for VSync. Their
            # old-value result is zero in this deterministic MOS fixture.
            else:
                self.mpu.x = 0
                self.mpu.y = 0
            self._return_from_jsr()
            return True
        return False

    def run(self, instruction_limit=2_000_000):
        for _ in range(instruction_limit):
            if self.mpu.pc == RETURN_SENTINEL:
                return
            if not self._mos_call():
                self.mpu.step()
        self.fail_state = (self.mpu.pc, self.mpu.a, self.mpu.x, self.mpu.y)
        raise AssertionError(f"client did not return; CPU={self.fail_state!r}")


class EmulatedClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        image = (ROOT / "build" / "nettools.ssd").read_bytes()
        # Execute the exact file payloads distributed on the DFS image.
        cls.term = dfs_file(image, "TERM")
        cls.ssh = dfs_file(image, "SSH")

    def test_term_connects_renders_fragmented_vt100_and_sends_keys(self):
        incoming = (
            b"discarded\x1b[2J"       # prove ED2 clears earlier text
            b"\x1b[2;3HOK"            # row 2, column 3 (one based)
            b"\x1b[7mI\x1b[0m"       # supported SGR paths
            b"\x1b]0;ignored title\x07"
        )
        machine = ClientMachine(
            self.term, "bbs.example 2323", incoming=incoming,
            keys=(0x8B, ord("x"), 29)
        )
        machine.run()
        self.assertEqual(machine.memory.opened_url,
                         "TELNET://bbs.example:2323/")
        self.assertTrue(machine.memory.closed)
        self.assertEqual(bytes(machine.memory.sent), b"\x1b[Ax")
        self.assertIn("OKI", machine.screen.text())
        self.assertNotIn("discarded", machine.screen.text())
        self.assertIn("Disconnected.", machine.screen.text())

    def test_term_reports_absent_pi_service_without_touching_network(self):
        machine = ClientMachine(self.term, "bbs.example", service=False)
        machine.run()
        self.assertIn("Pi1MHz net service not found", machine.screen.text())
        self.assertIsNone(machine.memory.opened_url)

    def test_term_renders_top_style_home_ed0_and_el0_without_erasing_text(self):
        incoming = (
            b"stale screen"
            b"\x1b[H\x1b[J"          # top clears from home with default ED0
            b"\x1b[?25l"             # cursor visibility mode is safely consumed
            b"top - 12:34:56\x1b[K\r\n"
            b"Tasks: 3 total\x1b[K"
            b"\x1b[?25h"
        )
        machine = ClientMachine(
            self.term, "bbs.example 2323", incoming=incoming,
            keys=(ord("q"), 29)
        )
        machine.run()
        visible = machine.screen.text()
        self.assertNotIn("stale screen", visible)
        self.assertIn("top - 12:34:56", visible)
        self.assertIn("Tasks: 3 total", visible)
        self.assertEqual(bytes(machine.memory.sent), b"q")

    def test_term_vt100_cursor_motion_clamps_and_ed2_preserves_cursor(self):
        incoming = (
            b"\x1b[2;3H\x1b[2JX"     # ED2 clears but does not home the cursor
            b"\x1b[99CY"              # CUF clamps at the right edge
            b"\x1b[99BZ"              # CUD clamps at the bottom edge
        )
        machine = ClientMachine(
            self.term, "bbs.example", incoming=incoming, eof_after_data=True
        )
        machine.run()
        self.assertEqual(machine.screen.cells[1][2], "X")
        self.assertEqual(machine.screen.cells[1][39], "Y")
        self.assertEqual(machine.screen.cells[23][0], "Z")

    def test_term_consumes_charset_and_control_strings_and_uses_tab_stops(self):
        incoming = (
            b"\x1b[2J\x1b[H"
            b"A\tB"                  # HT advances to the next 8-column stop
            b"\x1b(B"                # ASCII character-set designation
            b"\x1bPignored DCS\x1b\\"
            b"C"
        )
        machine = ClientMachine(
            self.term, "bbs.example", incoming=incoming, eof_after_data=True
        )
        machine.run()
        self.assertEqual(machine.screen.cells[0][0], "A")
        self.assertEqual(machine.screen.cells[0][8], "B")
        self.assertEqual(machine.screen.cells[0][9], "C")
        self.assertNotIn("ignored DCS", machine.screen.text())

    def test_term_remaining_vt100_scaffolds_consume_complete_sequences(self):
        incoming = (
            b"\x1b[2J\x1b[HA"
            b"\x1b[2@\x1b[2L\x1b[2M\x1b[2P\x1b[2X"
            b"\x1b[2S\x1b[2T\x1b[?25h\x1b[?25l\x1b[1;24r"
            b"\x1b[6n\x1b[c\x1b[3g\x1b[1 qB"
        )
        machine = ClientMachine(
            self.term, "bbs.example", incoming=incoming, eof_after_data=True
        )
        machine.run()
        self.assertEqual(machine.screen.cells[0][0:2], ["A", "B"])

    def test_ssh_managed_session_renders_vt100_and_sends_keys(self):
        incoming = (b"discarded\x1b[2J\x1b[2;3HSSH OK\r\n" +
                    b"\x1b[7mready\x1b[0m")
        machine = ClientMachine(
            self.ssh, "alice@shell.example", incoming=incoming,
            keys=(0x8B, ord("x"), 29)
        )
        machine.run()
        self.assertEqual(machine.memory.opened_url,
                         "TCP://shell.example:22/")
        self.assertEqual(machine.memory.ssh_username, "alice")
        self.assertEqual(bytes(machine.memory.sent), b"\x1b[Ax")
        self.assertTrue(machine.memory.closed)
        self.assertIn("SSH OK", machine.screen.text())
        self.assertNotIn("discarded", machine.screen.text())
        self.assertIn("Disconnected", machine.screen.text())

    def test_ssh_waits_for_deferred_pi_firmware_poll(self):
        machine = ClientMachine(
            self.ssh, "alice@shell.example", incoming=b"delayed OK\r\n",
            keys=(29,), dispatch_busy_reads=20
        )
        machine.run()
        self.assertEqual(machine.memory.opened_url,
                         "TCP://shell.example:22/")
        self.assertIn("delayed OK", machine.screen.text())
        self.assertNotIn("ABI 1 required", machine.screen.text())

    def test_ssh_prompts_for_unknown_host_and_persists_acceptance(self):
        machine = ClientMachine(
            self.ssh, "bob@new.example 2222", incoming=b"welcome\r\n",
            keys=(ord("Y"), 29), host_known=False
        )
        machine.run()
        self.assertEqual(machine.memory.opened_url,
                         "TCP://new.example:2222/")
        self.assertTrue(machine.memory.host_known)
        self.assertIn("SHA256:fixture-host-ke", machine.screen.text())

    def test_ssh_rejects_target_without_explicit_username(self):
        machine = ClientMachine(
            self.ssh, "missing-user.example"
        )
        machine.run()
        self.assertIn("Usage: *SSH user@host", machine.screen.text())
        self.assertIsNone(machine.memory.opened_url)

    def test_ssh_falls_back_to_hidden_password_and_wipes_mailbox(self):
        machine = ClientMachine(
            self.ssh, "alice@password.example", incoming=b"password OK\r\n",
            keys=tuple(map(ord, "secret\r")) + (29,),
            password_required=True
        )
        machine.run()
        self.assertEqual(machine.memory.password_supplied, b"secret")
        self.assertTrue(machine.memory.password_jim_wiped)
        self.assertIn("Password:", machine.screen.text())
        self.assertNotIn("secret", machine.screen.text())
        self.assertIn("password OK", machine.screen.text())


if __name__ == "__main__":
    unittest.main()
