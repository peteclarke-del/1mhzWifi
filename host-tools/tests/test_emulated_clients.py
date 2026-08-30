"""Execute the assembled clients on a real 6502 emulator.

The harness supplies the MOS entry points used by the programs and models the
Pi1MHz services registers/JIM ABI at &FCA6-&FCAA. Tests operate on the internal
main images extracted from the SSD, not reimplementations of their logic. The
public relocation loaders have separate assembled-code and Elkulator tests.
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
APP_START = 0x2200
LOADER_START = 0x2000
RETURN_SENTINEL = 0x1234

OSASCI = 0xFFE3
OSNEWL = 0xFFE7
OSWRCH = 0xFFEE
OSARGS = 0xFFDA
OSBYTE = 0xFFF4
OSCLI = 0xFFF7

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
                 dispatch_busy_reads=0, auto_increment=True,
                 delayed_selector_accesses=0, secure_features=7,
                 secure_ready=1):
        self.ram = bytearray(65536)
        self.jim = bytearray(1 << 24)
        self.service = service
        self.address = 0
        self.data_address = 0
        self.command_result = 0
        self.command_pending = False
        self.dispatch_busy_reads = dispatch_busy_reads
        self.auto_increment = auto_increment
        self.delayed_selector_accesses = delayed_selector_accesses
        self.pending_selector = None
        self.pending_selector_count = 0
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
        self.raw_opened = False
        self.dns_polls = 0
        self.ping_count = 0
        self.secure_features = secure_features
        self.secure_ready = secure_ready
        self.extended_vector_table = 0x0400

    def _select_address(self):
        if self.delayed_selector_accesses:
            self.pending_selector = self.address
            self.pending_selector_count = self.delayed_selector_accesses
        else:
            self.data_address = self.address

    def tick_fiq(self):
        if self.pending_selector is None:
            return
        self.pending_selector_count -= 1
        if self.pending_selector_count <= 0:
            self.data_address = self.pending_selector
            self.pending_selector = None

    def __len__(self):
        return 65536

    def __getitem__(self, address):
        address &= 0xFFFF
        if not self.service:
            if SERVICE_ADDR_LO <= address <= SERVICE_COMMAND:
                return 0xFF
            return self.ram[address]
        if address == SERVICE_ADDR_LO:
            value = self.address & 0xFF
            return value
        if address == SERVICE_ADDR_MI:
            return (self.address >> 8) & 0xFF
        if address == SERVICE_ADDR_HI:
            return (self.address >> 16) & 0xFF
        if address == SERVICE_DATA:
            value = self.jim[self.data_address]
            if self.auto_increment:
                self.address = (self.address + 1) & 0xFFFFFF
                self.data_address = self.address
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
            self._select_address()
            return
        if address == SERVICE_ADDR_MI:
            self.address = (self.address & 0xFF00FF) | (value << 8)
            self._select_address()
            return
        if address == SERVICE_ADDR_HI:
            self.address = (self.address & 0x00FFFF) | (value << 16)
            self._select_address()
            return
        if address == SERVICE_DATA:
            self.jim[self.data_address] = value
            if self.auto_increment:
                self.address = (self.address + 1) & 0xFFFFFF
                self.data_address = self.address
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
        if command == 45:  # raw socket OPEN
            self.raw_opened = True
            return NET_OK
        if command == 46:  # DNS
            if not self.raw_opened:
                return NET_ERR_NOTOPEN
            self.dns_polls += 1
            if self.dns_polls == 1:
                return NET_PENDING
            self.jim[block + 4:block + 8] = bytes((192, 0, 2, 42))
            return NET_OK
        if command == 53:  # raw socket CLOSE
            self.raw_opened = False
            return NET_OK
        if command == 88:  # ICMP ping compatibility service
            self.ping_count += 1
            response = f"+{10 + self.ping_count}\r\n\0".encode("ascii")
            self.jim[block + 1:block + 1 + len(response)] = response
            return NET_OK
        if command == 90:  # cancel asynchronous ElkWiFi operation
            return NET_OK
        if command == 80:  # ElkWiFi status/version
            response = b"Pi1MHz ElkWiFi 0.1.59, kernel fixture\r\n\r\nOK\r\n\0"
            self.jim[block + 1:block + 1 + len(response)] = response
            return NET_OK
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
                (1, 1, self.secure_features, 0xB8, 0x88,
                 self.secure_ready, 1, ord("N"), ord("T"), ord("S"))
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

    def set_geometry(self, width, height):
        self.width = width
        self.height = height
        self.cells = [[" "] * width for _ in range(height)]
        self.x = self.y = 0
        self.pending = None
        self.params.clear()

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
                 dispatch_busy_reads=0, tube=False, auto_increment=True,
                 delayed_selector_accesses=0,
                 oshwm=0x0E00, himem=0x5800, load_address=APP_START,
                 mode4_himem=0x5800, secure_features=7, secure_ready=1,
                 screen_width=40, screen_height=32):
        self.memory = Pi1MHzMemory(
            service=service, incoming=incoming, eof_after_data=eof_after_data,
            host_known=host_known, password_required=password_required,
            expected_password=expected_password,
            dispatch_busy_reads=dispatch_busy_reads,
            auto_increment=auto_increment,
            delayed_selector_accesses=delayed_selector_accesses,
            secure_features=secure_features, secure_ready=secure_ready,
        )
        self.memory.load(load_address, binary)
        self.argument_address = 0x1000
        self.memory.load(self.argument_address, arguments.encode("ascii") + b"\r")
        self.screen = TextScreen(screen_width, screen_height)
        self.screen_captures = []
        self.keys = list(keys)
        self.keyboard_polls = 0
        self.oscli_commands = []
        self.tube = tube
        self.oshwm = oshwm
        self.himem = himem
        self.mode4_himem = mode4_himem
        self.mode_changes = []
        self.mode_pending = False
        self.mpu = MPU(memory=self.memory, pc=load_address)
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
            if pc == OSWRCH:
                if self.mode_pending:
                    self.mode_changes.append(value)
                    if value == 4:
                        self.himem = self.mode4_himem
                        self.screen.set_geometry(40, 32)
                    self.mode_pending = False
                elif value == 22:
                    self.mode_pending = True
            self.screen.emit(value)
            # The services/JIM byte-address cursor is global hardware state.
            # A MOS call may enter another filing-system or expansion ROM, so
            # clients must not retain a selected cursor across OS calls.
            self.memory.address = 0x012345
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
            self.screen_captures.append(self.screen.text())
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
            elif reason == 0x87:
                self.mpu.x = ord(self.screen.cells[self.screen.y][self.screen.x])
                self.mpu.y = 0
            elif reason == 0xA0:
                self.mpu.x = {
                    8: 0,
                    9: self.screen.height - 1,
                    10: self.screen.width - 1,
                    11: 0,
                }.get(self.mpu.x, 0)
                self.mpu.y = 0
            elif reason == 0x83:
                self.mpu.x = self.oshwm & 0xFF
                self.mpu.y = self.oshwm >> 8
            elif reason == 0x84:
                self.mpu.x = self.himem & 0xFF
                self.mpu.y = self.himem >> 8
            elif reason == 0xA8:
                self.mpu.x = self.memory.extended_vector_table & 0xFF
                self.mpu.y = self.memory.extended_vector_table >> 8
            elif reason == 0xEA:
                self.mpu.x = 0xFF if self.tube else 0
                self.mpu.y = 0
            elif reason == 0xFC:
                self.mpu.x = 10
                self.mpu.y = 0
            elif reason == 0x8E:
                # A real MOS does not return: it re-enters the selected
                # language. End the fixture at the equivalent boundary.
                self.mpu.pc = RETURN_SENTINEL
                return True
            # Other calls configure keyboard state or wait for VSync. Their
            # old-value result is zero in this deterministic MOS fixture.
            else:
                self.mpu.x = 0
                self.mpu.y = 0
            self._return_from_jsr()
            return True
        if pc == OSCLI:
            pointer = self.mpu.x | (self.mpu.y << 8)
            end = self.memory.ram.index(13, pointer)
            self.oscli_commands.append(
                bytes(self.memory.ram[pointer:end]).decode("ascii")
            )
            self._return_from_jsr()
            return True
        return False

    def run(self, instruction_limit=2_000_000):
        for _ in range(instruction_limit):
            if self.mpu.pc == RETURN_SENTINEL:
                return
            if not self._mos_call():
                self.mpu.step()
            self.memory.tick_fiq()
        self.fail_state = (self.mpu.pc, self.mpu.a, self.mpu.x, self.mpu.y)
        raise AssertionError(f"client did not return; CPU={self.fail_state!r}")


class EmulatedClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        image = (ROOT / "build" / "nettools.ssd").read_bytes()
        # Execute the exact file payloads distributed on the DFS image.
        cls.telnet = dfs_file(image, "NTTEL")
        cls.ssh = dfs_file(image, "NTSSH")
        cls.hwdtest = dfs_file(image, "NTHWD")
        cls.ssh_loader = dfs_file(image, "SSH")
        cls.hwdtest_loader = dfs_file(image, "HWDTEST")

    def test_public_loader_falls_back_to_mode4_then_runs_host_main(self):
        for tube, oshwm in ((False, 0x0800), (True, 0x0800), (False, 0x1F00)):
            with self.subTest(tube=tube, oshwm=oshwm):
                machine = ClientMachine(
                    self.ssh_loader, "alice@example.test 2222",
                    load_address=LOADER_START, oshwm=oshwm, himem=0x1D00,
                    tube=tube,
                )
                machine.run()
                self.assertEqual(machine.himem, 0x5800)
                self.assertEqual(bytes(machine.memory.ram[0x21F0:0x21F2]), b"NT")
                self.assertEqual(
                    bytes(machine.memory.ram[0x21F2:0x21F6]),
                    bytes((oshwm & 0xFF, oshwm >> 8, 0x00, 0x1D)),
                )
                self.assertEqual(
                    machine.oscli_commands, ["NTSSH alice@example.test 2222"],
                )

    def test_public_loader_preserves_a_suitable_host_display_mode(self):
        machine = ClientMachine(
            self.ssh_loader, "alice@example.test 2222",
            load_address=LOADER_START, oshwm=0x0800, himem=0x7000,
            mode4_himem=0x5800, tube=False,
        )
        machine.run()
        self.assertEqual(machine.himem, 0x7000)
        self.assertEqual(
            machine.oscli_commands, ["NTSSH alice@example.test 2222"],
        )

    def test_public_loader_rejects_unmeasured_higher_oshwm(self):
        machine = ClientMachine(
            self.ssh_loader, "alice@example.test",
            load_address=LOADER_START, oshwm=0x2100, himem=0x5800,
        )
        machine.run()
        self.assertIn("requires OSHWM <= &2000", machine.screen.text())
        self.assertEqual(machine.oscli_commands, [])

    def test_public_loader_requires_only_its_exact_main_image(self):
        exact_end = APP_START + len(self.hwdtest)
        machine = ClientMachine(
            self.hwdtest_loader, "", load_address=LOADER_START,
            oshwm=0x1F00, himem=0x1D00, mode4_himem=exact_end,
        )
        machine.run()
        self.assertEqual(machine.himem, exact_end)
        self.assertEqual(machine.oscli_commands, ["NTHWD "])

    def test_tube_loader_ignores_parasite_memory_boundaries(self):
        # Acorn's Tube contract makes &83/&84 language-processor values. They
        # are not the MODE 4 host screen boundary for an &FFFFxxxx utility.
        loader = ClientMachine(
            self.hwdtest_loader, "", load_address=LOADER_START,
            oshwm=0x8000, himem=0x0800, mode4_himem=0x0800, tube=True,
        )
        loader.run()
        self.assertEqual(loader.oscli_commands, ["NTHWD "])
        self.assertNotIn("could not obtain MODE 4 RAM", loader.screen.text())

    def test_hardware_diagnostic_matches_emulated_services_contract(self):
        machine = ClientMachine(self.hwdtest, "")
        machine.memory.ram[0x21F0:0x21F6] = b"NT\x00\x08\x00\x1d"
        machine.memory.ram[0x020A:0x020C] = b"\x34\x12"
        machine.memory.ram[0x0212:0x0214] = b"\x78\x56"
        machine.memory.ram[0x0216:0x0218] = b"\xBC\x9A"
        machine.memory.ram[0x021C:0x0220] = b"\xF0\xDE\x57\x13"
        extended = machine.memory.extended_vector_table
        for offset, entry in (
            (27, b"\x11\x22\x03"),
            (33, b"\x44\x55\x06"),
            (42, b"\x77\x88\x09"),
            (45, b"\xAA\xBB\x0C"),
        ):
            machine.memory.ram[extended + offset:extended + offset + 3] = entry
        wicfs_state = bytes(range(26))
        machine.memory.jim[0xFFEF00:0xFFEF1A] = wicfs_state
        machine.run()
        visible = "\n".join(machine.screen_captures + [machine.screen.text()])
        self.assertIn("Loader OSHWM=&0800 HIMEM=&1D00", visible)
        self.assertIn("Entry/opcode: &2200 20", visible)
        self.assertIn("Before OSBYTE &82", visible)
        self.assertIn("After OSBYTE &81 X=&00", visible)
        self.assertIn("V BYTE FILE BGET: 1234 5678 9ABC", visible)
        self.assertIn("V FIND FSC: DEF0 1357", visible)
        self.assertIn("E FILE BGET (addr/rom): 2211/03 5544/06", visible)
        self.assertIn("E FIND FSC (addr/rom): 8877/09 BBAA/0C", visible)
        self.assertIn("Capture machine/vectors. Press a key.", visible)
        self.assertIn("WSTATE 00-03: 00 01 02 03", visible)
        self.assertIn("WSTATE 17-21: 11 12 13 14 15", visible)
        self.assertIn("WSTATE 22-25: 16 17 18 19", visible)
        self.assertIn("FCA9 req 00 F0 FF <= 5E", visible)
        self.assertIn("FCA6-9 after: 01 F0 FF 5E PASS", visible)
        self.assertIn("Addressed JIM block: PASS", visible)
        self.assertIn("Secure CAPS result=&00", visible)
        self.assertIn("CAPS 1-5: 01 01 07 B8 88", visible)
        self.assertIn("CAPS 6-10: 01 01 4E 54 53", visible)
        self.assertIn("HWDTEST RESULT PASS", visible)
        self.assertEqual(machine.memory.jim[0xFFEF00:0xFFEF1A], wicfs_state)
        self.assertEqual(
            machine.memory.jim[0xFFEE00:0xFFEE10],
            bytes((0x00, 0xFF, 0x55, 0xAA, 0x01, 0xFE, 0x10, 0xEF,
                   0x5A, 0xA5, 0x33, 0xCC, 0x0F, 0xF0, 0x69, 0x96)),
        )
        self.assertEqual(machine.oscli_commands, ["ROMS"])
        self.assertIn("Pi1MHz ElkWiFi 0.1.59", visible)

    def test_hardware_diagnostic_fails_when_managed_ssh_is_not_ready(self):
        machine = ClientMachine(
            self.hwdtest, "", secure_features=1, secure_ready=0,
        )
        machine.memory.ram[0x21F0:0x21F6] = b"NT\x00\x08\x00\x1d"
        machine.run()
        visible = "\n".join(machine.screen_captures + [machine.screen.text()])
        self.assertIn("CAPS 1-5: 01 01 01 B8 88", visible)
        self.assertIn("CAPS 6-10: 00 01 4E 54 53", visible)
        self.assertIn("HWDTEST RESULT FAIL", visible)

    def test_clients_do_not_depend_on_immediate_hardware_auto_increment(self):
        # Real Pi1MHz services callbacks are asynchronous to the 6502. Model
        # the strongest safe case: FCA9 read-back never advances before the
        # next host access. Explicit per-byte addressing must still work.
        ssh = ClientMachine(
            self.ssh, "test@example.test", incoming=b"safe path\r\n",
            keys=(29,), auto_increment=False,
        )
        ssh.run()
        self.assertEqual(ssh.memory.opened_url, "TCP://example.test:22/")
        self.assertTrue(ssh.memory.closed)

    def test_clients_wait_for_selector_data_publication(self):
        # The real handler has one pending FIQ slot. A second mailbox access
        # before the scheduled event runs replaces it. Advance publication by
        # CPU instructions, never by another read of a service register.
        for tube in (False, True):
            with self.subTest(client="ssh", tube=tube):
                ssh = ClientMachine(
                    self.ssh, "test@example.test", incoming=b"settled path\r\n",
                    keys=(29,), delayed_selector_accesses=5, tube=tube,
                )
                ssh.run()
                self.assertEqual(ssh.memory.opened_url, "TCP://example.test:22/")
                self.assertTrue(ssh.memory.closed)

            with self.subTest(client="telnet", tube=tube):
                telnet = ClientMachine(
                    self.telnet, "example.test", incoming=b"ready\r\n",
                    eof_after_data=True, delayed_selector_accesses=5, tube=tube,
                )
                telnet.run()
                self.assertIn("ready", telnet.screen.text())

            with self.subTest(client="hwdtest", tube=tube):
                hwdtest = ClientMachine(
                    self.hwdtest, "", delayed_selector_accesses=5, tube=tube,
                )
                hwdtest.run()
                visible = "\n".join(
                    hwdtest.screen_captures + [hwdtest.screen.text()]
                )
                self.assertIn("FCA9 callback ACK: PASS", visible)
                self.assertIn("CAPS 6-10: 01 01 4E 54 53", visible)

    def test_client_refuses_workspace_above_its_fixed_load_address(self):
        machine = ClientMachine(
            self.ssh, "test@example.test", oshwm=APP_START + 0x100,
        )
        machine.run()
        self.assertIn("OSHWM=&2300", machine.screen.text())
        self.assertIn("HIMEM=&5800", machine.screen.text())
        self.assertIn("image=&2200-", machine.screen.text())
        self.assertEqual(machine.memory.dns_polls, 0)

    def test_client_refuses_display_boundary_below_its_image_end(self):
        machine = ClientMachine(
            self.ssh, "test@example.test", himem=APP_START + 0x100,
            mode4_himem=APP_START + 0x100,
        )
        machine.run()
        self.assertIn("OSHWM=&0E00", machine.screen.text())
        self.assertIn("HIMEM=&2300", machine.screen.text())
        self.assertIn("image=&2200-", machine.screen.text())
        self.assertIsNone(machine.memory.opened_url)

    def test_telnet_connects_renders_fragmented_vt100_and_sends_keys(self):
        incoming = (
            b"discarded\x1b[2J"       # prove ED2 clears earlier text
            b"\x1b[2;3HOK"            # row 2, column 3 (one based)
            b"\x1b[7mI\x1b[0m"       # supported SGR paths
            b"\x1b]0;ignored title\x07"
        )
        machine = ClientMachine(
            self.telnet, "bbs.example 2323", incoming=incoming,
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

    def test_telnet_reports_absent_pi_service_without_touching_network(self):
        machine = ClientMachine(self.telnet, "bbs.example", service=False)
        machine.run()
        self.assertIn("Pi1MHz net service not found", machine.screen.text())
        self.assertIsNone(machine.memory.opened_url)

    def test_telnet_renders_top_style_home_ed0_and_el0_without_erasing_text(self):
        incoming = (
            b"stale screen"
            b"\x1b[H\x1b[J"          # top clears from home with default ED0
            b"\x1b[?25l"             # cursor visibility mode is safely consumed
            b"top - 12:34:56\x1b[K\r\n"
            b"Tasks: 3 total\x1b[K"
            b"\x1b[?25h"
        )
        machine = ClientMachine(
            self.telnet, "bbs.example 2323", incoming=incoming,
            keys=(ord("q"), 29)
        )
        machine.run()
        visible = machine.screen.text()
        self.assertNotIn("stale screen", visible)
        self.assertIn("top - 12:34:56", visible)
        self.assertIn("Tasks: 3 total", visible)
        self.assertEqual(bytes(machine.memory.sent), b"q")

    def test_telnet_vt100_cursor_motion_clamps_and_ed2_preserves_cursor(self):
        incoming = (
            b"\x1b[2;3H\x1b[2JX"     # ED2 clears but does not home the cursor
            b"\x1b[99CY"              # CUF clamps at the right edge
            b"\x1b[99BZ"              # CUD clamps at the bottom edge
        )
        machine = ClientMachine(
            self.telnet, "bbs.example", incoming=incoming, eof_after_data=True
        )
        machine.run()
        self.assertEqual(machine.screen.cells[1][2], "X")
        self.assertEqual(machine.screen.cells[1][39], "Y")
        self.assertEqual(machine.screen.cells[23][0], "Z")

    def test_telnet_consumes_charset_and_control_strings_and_uses_tab_stops(self):
        incoming = (
            b"\x1b[2J\x1b[H"
            b"A\tB"                  # HT advances to the next 8-column stop
            b"\x1b(B"                # ASCII character-set designation
            b"\x1bPignored DCS\x1b\\"
            b"C"
        )
        machine = ClientMachine(
            self.telnet, "bbs.example", incoming=incoming, eof_after_data=True
        )
        machine.run()
        self.assertEqual(machine.screen.cells[0][0], "A")
        self.assertEqual(machine.screen.cells[0][8], "B")
        self.assertEqual(machine.screen.cells[0][9], "C")
        self.assertNotIn("ignored DCS", machine.screen.text())

    def test_telnet_vt100_editing_operations_modify_the_screen(self):
        incoming = (
            b"\x1b[2J\x1b[HABCDE"
            b"\x1b[1;2H\x1b[2@XY"  # AXYBCDE
            b"\x1b[1;4H\x1b[2P"    # AXYDE
            b"\x1b[1;2H\x1b[2X"    # A  DE
            b"\x1b[10;1Hsecond"
            b"\x1b[10;1H\x1b[2L"   # insert two blank lines before second
        )
        machine = ClientMachine(
            self.telnet, "bbs.example", incoming=incoming, eof_after_data=True
        )
        machine.run()
        self.assertEqual("".join(machine.screen.cells[0][:5]), "A  DE")
        self.assertEqual("".join(machine.screen.cells[9][:6]), "      ")
        self.assertEqual("".join(machine.screen.cells[11][:6]), "second")

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

    def test_ssh_password_session_preserves_suitable_80_column_mode(self):
        machine = ClientMachine(
            self.ssh, "alice@password.example",
            incoming=b"\x1b[1;80HX\r\n", eof_after_data=True,
            keys=tuple(map(ord, "secret\r")), password_required=True,
            himem=0x5800, screen_width=80, screen_height=32,
        )
        machine.run()
        self.assertEqual(machine.mode_changes, [])
        self.assertEqual(machine.screen.width, 80)
        self.assertEqual(machine.screen.cells[0][79], "X")

    def test_ssh_uses_single_entry_fallback_when_mode_has_insufficient_ram(self):
        machine = ClientMachine(
            self.ssh, "alice@password.example", incoming=b"OK\r\n",
            eof_after_data=True, keys=tuple(map(ord, "secret\r")),
            password_required=True, himem=0x3000,
            screen_width=80, screen_height=32,
        )
        machine.run()
        self.assertEqual(machine.mode_changes, [4])
        self.assertEqual(machine.screen.width, 40)
        self.assertIn("OK", machine.screen.text())


if __name__ == "__main__":
    unittest.main()
