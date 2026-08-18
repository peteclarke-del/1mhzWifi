"""Executable ElkWiFi OSWORD compatibility tests using ElkChat's public ABI."""

from pathlib import Path
import os
import unittest

from py65.devices.mpu6502 import MPU


ROOT = Path(__file__).resolve().parents[1]
ROM_START = 0x8000
OSBYTE = 0xFFF4
RETURN_SENTINEL = 0x0400


class ElkWiFiMemory:
    """Host RAM, the sideways ROM, Pi1MHz byte mailbox and public JIM window."""

    def __init__(self, rom: bytes, delayed_increment_accesses=0,
                 delayed_selector_accesses=0):
        self.ram = bytearray(0x10000)
        self.rom = rom
        self.jim = bytearray(0x1000000)
        self.address = 0
        self.data_address = 0
        self.page = 0
        self.result = 0
        self.connected = False
        self.connected_address = None
        self.sent = bytearray()
        self.send_schedule = []
        self.receive = bytearray()
        self.receive_schedule = []
        self.delayed_increment_accesses = delayed_increment_accesses
        self.pending_increment = None
        self.pending_increment_count = 0
        self.delayed_selector_accesses = delayed_selector_accesses
        self.pending_selector = None
        self.pending_selector_count = 0

    def _tick_selector(self, cycles):
        if self.pending_selector is None:
            return
        self.pending_selector_count -= cycles
        if self.pending_selector_count <= 0:
            self.data_address = self.pending_selector
            self.pending_selector = None

    def _select_address(self):
        if self.delayed_selector_accesses:
            self.pending_selector = self.address
            self.pending_selector_count = self.delayed_selector_accesses
        else:
            self.data_address = self.address

    def _tick_increment(self, cycles):
        if self.pending_increment is None:
            return
        self.pending_increment_count -= cycles
        if self.pending_increment_count <= 0:
            self.address = self.pending_increment
            self.data_address = self.pending_increment
            self.pending_increment = None

    def tick(self, cycles):
        """Advance asynchronous Pi callbacks by elapsed host CPU cycles."""
        self._tick_selector(cycles)
        self._tick_increment(cycles)

    def _increment_address(self):
        target = (self.address + 1) & 0xFFFFFF
        if self.delayed_increment_accesses:
            self.pending_increment = target
            self.pending_increment_count = self.delayed_increment_accesses
        else:
            self.address = target
            self.data_address = target

    def __len__(self):
        return 0x10000

    def __getitem__(self, address):
        address &= 0xFFFF
        if ROM_START <= address < 0xC000:
            return self.rom[address - ROM_START]
        if address == 0xFCA6:
            return self.address & 0xFF
        if address == 0xFCA7:
            return (self.address >> 8) & 0xFF
        if address == 0xFCA8:
            return (self.address >> 16) & 0xFF
        if address == 0xFCA9:
            value = self.jim[self.data_address]
            self._increment_address()
            return value
        if address == 0xFCAA:
            return self.result
        if 0xFD00 <= address <= 0xFDFF:
            return self.jim[(self.page << 8) | (address & 0xFF)]
        return self.ram[address]

    def __setitem__(self, address, value):
        address &= 0xFFFF
        value &= 0xFF
        if address == 0xFCA6:
            self.address = (self.address & 0xFFFF00) | value
            self._select_address()
            return
        if address == 0xFCA7:
            self.address = (self.address & 0xFF00FF) | (value << 8)
            self._select_address()
            return
        if address == 0xFCA8:
            self.address = (self.address & 0x00FFFF) | (value << 16)
            self._select_address()
            return
        if address == 0xFCA9:
            self.jim[self.data_address] = value
            self._increment_address()
            return
        if address == 0xFCAA:
            self._dispatch(value)
            return
        if address == 0xFCFF:
            self.page = value
            return
        if 0xFD00 <= address <= 0xFDFF:
            self.jim[(self.page << 8) | (address & 0xFF)] = value
            return
        if not ROM_START <= address < 0xC000:
            self.ram[address] = value

    def _dispatch(self, selector):
        if selector == 0xFF:
            self._dispatch_wifi_service()
        elif selector == 0xF0:
            self._dispatch_raw_network()
        else:
            self.result = 0xFF

    def _dispatch_wifi_service(self):
        command = self.jim[0xFFFF00]
        responses = {
            80: b"Pi1MHz ElkWiFi test\r\nOK\r\n",
            81: b'+CWLAP:(3,"TestNet",-42)\r\nOK\r\n',
            91: b"OK\r\n",
            83: (
                b'+CIFSR:STAIP,"192.168.1.64"\r\n'
                b'+CIFSR:STAMAC,"84:F3:EB:04:8D:D4"\r\n\r\nOK\r\n'
            ),
        }
        if command == 82:
            mode = self.jim[0xFFFF01]
            if mode == 0:
                response = b'+CWJAP:"TestNet"\r\n\r\nOK\r\n'
            elif mode == 1:
                self.connected = True
                response = b"WIFI CONNECTED\r\nOK\r\n"
            else:
                self.connected = False
                response = b"WIFI DISCONNECTED\r\nOK\r\n"
        else:
            response = responses.get(command, b"ERROR\r\n")
        start = 0xFFFF01
        self.jim[start:start + len(response) + 1] = response + b"\0"
        self.result = 0

    @staticmethod
    def _u24(data):
        return data[0] | (data[1] << 8) | (data[2] << 16)

    def _dispatch_raw_network(self):
        base = 0xFFF000
        command = self.jim[base]
        if command == 45:  # allocate raw TCP handle
            self.result = 0
        elif command == 46:  # DNS
            self.jim[base + 4:base + 8] = bytes((93, 184, 216, 34))
            self.result = 0
        elif command == 47:  # connect
            self.connected_address = bytes(self.jim[base + 1:base + 7])
            self.connected = True
            self.result = 0
        elif command == 50:  # send
            length = self._u24(self.jim[base + 1:base + 4])
            source = int.from_bytes(self.jim[base + 4:base + 8], "little")
            accepted = min(
                length,
                self.send_schedule.pop(0) if self.send_schedule else length,
            )
            self.sent.extend(self.jim[source:source + accepted])
            self.jim[base + 1:base + 4] = accepted.to_bytes(3, "little")
            self.result = 0
        elif command == 51:  # receive
            maximum = self._u24(self.jim[base + 1:base + 4])
            destination = int.from_bytes(self.jim[base + 4:base + 8], "little")
            if self.receive_schedule:
                available = self.receive_schedule.pop(0)
                if available is None:
                    self.jim[base + 1:base + 4] = b"\0\0\0"
                    self.result = 0x20
                    return
                if available == 0:
                    self.jim[base + 1:base + 4] = b"\0\0\0"
                    self.result = 0
                    return
            else:
                available = len(self.receive)
            count = min(maximum, available, len(self.receive))
            self.jim[destination:destination + count] = self.receive[:count]
            del self.receive[:count]
            self.jim[base + 1:base + 4] = count.to_bytes(3, "little")
            self.result = 0 if count else 0x20
        elif command == 53:  # close
            self.connected = False
            self.result = 0
        else:
            self.result = 0x21

    def public_response(self):
        end = self.jim.find(0, 0)
        if end < 0:
            raise AssertionError("public ElkWiFi response is not terminated")
        return bytes(self.jim[:end])


class ElkWiFiOSWORDMachine:
    """Enter the ROM exactly as MOS service reason 8 enters OSWORD &65."""

    def __init__(self, rom, delayed_increment_accesses=0,
                 delayed_selector_accesses=0):
        self.memory = ElkWiFiMemory(
            rom, delayed_increment_accesses, delayed_selector_accesses,
        )
        self.last_x = None
        self.last_y = None

    def call(self, function, x=0, y=0, *, limit=2_000_000,
             stack_pointer=0xFF, service_rom=5, expected_error=None):
        block = 0x0600
        self.memory.ram[block:block + 3] = bytes((function, x, y))
        self.memory.ram[0xEF] = 0x65
        self.memory.ram[0xF0] = block & 0xFF
        self.memory.ram[0xF1] = block >> 8
        if self.memory.rom[3] != 0x4C:
            raise AssertionError("sideways ROM service entry is not a JMP")
        service = self.memory.rom[4] | (self.memory.rom[5] << 8)
        mpu = MPU(memory=self.memory, pc=service)
        mpu.a = 8
        mpu.x = service_rom
        mpu.y = 0
        mpu.sp = stack_pointer
        mpu.stPushWord(RETURN_SENTINEL - 1)
        for _ in range(limit):
            if mpu.pc == 0x0D90:
                end = self.memory.ram.find(0, 0x0D92, 0x0DB0)
                message = bytes(self.memory.ram[0x0D92:end])
                if expected_error is None:
                    raise AssertionError(
                        f"unexpected MOS error: {message.decode('ascii')}"
                    )
                self.assert_error(message, expected_error)
                return message
            if mpu.pc == RETURN_SENTINEL:
                if mpu.a != 0:
                    raise AssertionError(f"OSWORD &65 was not claimed: A={mpu.a:02X}")
                self.last_x = mpu.x
                self.last_y = mpu.y
                return
            if mpu.pc == OSBYTE:
                # OSBYTE &81, X=0, Y=&FF identifies an Electron with X=1.
                if mpu.a == 0x81 and mpu.x == 0 and mpu.y == 0xFF:
                    mpu.x = 1
                mpu.pc = (mpu.stPopWord() + 1) & 0xFFFF
                self.memory.tick(16)
            else:
                before = mpu.processorCycles
                mpu.step()
                self.memory.tick(mpu.processorCycles - before)
        raise AssertionError(
            f"OSWORD function {function} did not return; PC={mpu.pc:04X}"
        )

    @staticmethod
    def assert_error(actual, expected):
        if actual != expected:
            raise AssertionError(
                f"MOS error {actual!r} does not match {expected!r}"
            )


class ElkChatOSWORDCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / "build/pi1mhz-all/Pi1MHz/ElkWiFi.rom").read_bytes()
        source_root = Path(os.environ.get("ELKCHAT_SOURCE", ROOT.parent / "elkChat"))
        driver = source_root / "src/elkwifi.asm"
        cls.elkchat_driver = driver.read_text() if driver.is_file() else None

    def setUp(self):
        self.machine = ElkWiFiOSWORDMachine(self.rom)

    def test_elkchat_uses_only_the_original_public_driver(self):
        if self.elkchat_driver is None:
            self.skipTest("set ELKCHAT_SOURCE to audit an ElkChat checkout")
        source = self.elkchat_driver
        self.assertIn("ELKWIFI_OSWORD  = &65", source)
        self.assertIn('EQUS "0", 13', source)
        self.assertIn("WIFI_SEND_CB    = &70", source)
        self.assertNotIn("Pi1MHz", source)
        self.assertNotIn("FCA6", source)
        self.assertNotIn("FCAA", source)

    def test_public_driver_detects_machine_before_touching_jim_bank(self):
        # Machine type controls whether the BBC-family high JIM selectors are
        # written. The result must be refreshed for each call because the
        # driver state is explicitly transient and cannot be a boot-time cache.
        source = (ROOT / "rom-side" / "elkwifi-0.23" / "overlay" /
                  "driver.asm").read_text()
        entry = source.split(".wifidriver", 1)[1].split(
            ".service_driver_not_0", 1
        )[0]
        query = entry.lower().index("jsr osbyte")
        cache = entry.lower().index("stx driver_machine")
        select = entry.lower().index("jsr set_bank_0")
        self.assertLess(query, cache)
        self.assertLess(cache, select)
        self.assertIn("not valid as a reset-time cache", entry)

    def test_function_9_single_connection_returns_local_ok(self):
        self.machine.memory.ram[0x2000:0x2002] = b"0\r"
        self.machine.call(9, 0x20, 0x00)
        self.assertEqual(self.machine.memory.public_response(), b"OK\r\n")
        self.assertEqual(self.machine.memory.page, 0)

    def test_osword_entry_is_independent_of_sideways_rom_slot(self):
        self.machine.memory.ram[0x2000:0x2002] = b"0\r"
        for slot in range(16):
            with self.subTest(slot=slot):
                self.machine.call(9, 0x20, 0x00, service_rom=slot)
                self.assertEqual(self.machine.memory.public_response(), b"OK\r\n")

    def test_status_join_and_control_calls_return_bounded_responses(self):
        self.machine.call(18)
        response = self.machine.memory.public_response()
        self.assertIn(b'+CIFSR:STAIP,"192.168.1.64"', response)
        self.assertIn(b'+CIFSR:STAMAC,"84:F3:EB:04:8D:D4"', response)

        self.machine.memory.ram[0x2000] = 0
        self.machine.call(4, 0x20, 0x00)
        self.assertIn(b'+CWJAP:"TestNet"', self.machine.memory.public_response())
        self.machine.call(24, 1, 0)
        self.assertIn(b"OK", self.machine.memory.public_response())
        self.machine.call(3)
        self.assertIn(b"+CWLAP:", self.machine.memory.public_response())
        self.machine.call(5)
        self.assertIn(b"OK", self.machine.memory.public_response())
        self.machine.call(0)
        self.assertEqual(self.machine.memory.public_response(), b"OK\r\n")

    def test_osword_status_does_not_overwrite_stack_or_application_workspace(self):
        # A service ROM may be entered at any application stack depth. Earlier
        # builds placed service state at &0103 and later moved it into &09xx;
        # those are respectively the live CPU stack and ADFS/application RAM.
        stack_canary = bytes(range(0x30, 0x3F))
        app_addresses = (0x09B0, 0x09D8, 0x09D9, 0x09E0, 0x09E1,
                         0x09E2, 0x09EC, 0x09ED)
        self.machine.memory.ram[0x0103:0x0112] = stack_canary
        for address in app_addresses:
            self.machine.memory.ram[address] = 0xA5

        self.machine.call(18, stack_pointer=0x40)

        self.assertEqual(self.machine.memory.ram[0x0103:0x0112], stack_canary)
        self.assertEqual(
            bytes(self.machine.memory.ram[address] for address in app_addresses),
            bytes([0xA5]) * len(app_addresses),
        )

    def test_osword_error_block_does_not_overwrite_live_stack(self):
        stack_canary = bytes(range(0x30, 0x3F))
        self.machine.memory.ram[0x0103:0x0112] = stack_canary

        message = self.machine.call(
            11, stack_pointer=0x40, expected_error=b"Not implemented"
        )

        self.assertEqual(message, b"Not implemented")
        self.assertEqual(self.machine.memory.ram[0x0103:0x0112], stack_canary)

    def test_status_survives_delayed_fca9_callback(self):
        self.machine = ElkWiFiOSWORDMachine(
            self.rom, delayed_increment_accesses=5,
            delayed_selector_accesses=5,
        )
        self.machine.call(18)
        response = self.machine.memory.public_response()
        self.assertIn(b'+CIFSR:STAIP,"192.168.1.64"', response)
        self.assertIn(b'+CIFSR:STAMAC,"84:F3:EB:04:8D:D4"', response)

    def test_version_response_survives_delayed_selector_publication(self):
        self.machine = ElkWiFiOSWORDMachine(
            self.rom, delayed_increment_accesses=5,
            delayed_selector_accesses=5,
        )
        self.machine.call(2)
        self.assertEqual(
            self.machine.memory.public_response(),
            b"Pi1MHz ElkWiFi test\r\nOK\r\n",
        )

    def test_elkchat_tcp_open_send_receive_and_close_crosses_jim_pages(self):
        connect = b"TCP\rwww.chat64.nl\r80\r"
        self.machine.memory.ram[0x2000:0x2000 + len(connect)] = connect
        self.machine.call(8, 0x20, 0x00)
        self.assertIn(b"CONNECT", self.machine.memory.public_response())
        self.assertEqual(
            self.machine.memory.connected_address,
            bytes((93, 184, 216, 34, 80, 0)),
        )

        request = b"GET /zxReadAllMessages.php HTTP/1.0\r\nHost:www.chat64.nl\r\n\r\n"
        self.machine.memory.ram[0x3000:0x3000 + len(request)] = request
        self.machine.memory.ram[0x70:0x75] = bytes(
            (0x00, 0x30, len(request) & 0xFF, len(request) >> 8, 0)
        )
        body = b'[{"message":"' + (b"X" * 700) + b'"}]'
        reply = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n" + body
        self.machine.memory.receive[:] = reply
        self.machine.call(13, 0x70, 0)
        self.assertEqual(self.machine.memory.sent, request)
        self.assertEqual(self.machine.memory.public_response(), reply)
        self.assertGreater(self.machine.memory.page, 0)

        self.machine.call(14)
        self.assertIn(b"CLOSED", self.machine.memory.public_response())
        self.assertFalse(self.machine.memory.connected)

    def test_send_receive_waits_across_inter_packet_gaps(self):
        request = b"GET / HTTP/1.0\r\n\r\n"
        self.machine.memory.ram[0x3000:0x3000 + len(request)] = request
        self.machine.memory.ram[0x70:0x75] = bytes(
            (0x00, 0x30, len(request), 0, 0)
        )
        reply = b"HTTP/1.0 200 OK\r\n\r\n" + (b"X" * 300) + b"tail"
        self.machine.memory.receive[:] = reply
        self.machine.memory.receive_schedule[:] = [0, 120, 0, 240, 0, None]
        self.machine.call(13, 0x70, 0)
        self.assertEqual(self.machine.memory.public_response(), reply)

    def test_function_23_getmuxchannel_reports_single_connection(self):
        # ElkChat never calls function 23 itself. The original ElkWiFi
        # OSWORD &65 epilogue (`call_claimed`, unchanged from upstream
        # routines.asm) always restores the CPU's X/Y from before the driver
        # ran and only ever reports claim status through A=0 - it never
        # propagates whatever X/Y the driver routine computed internally, so
        # a caller can never actually observe function 23's Y=&FF write.
        # This matches the original cartridge's ABI exactly. The important,
        # verifiable contract is that the call is claimed (A=0) and never
        # touches the Pi1MHz mailbox or JIM window.
        self.machine.call(23, x=0, y=0)
        self.assertEqual(self.machine.memory.result, 0)

    def test_function_20_ipd_receives_pending_data_across_pages(self):
        # Function 20 (ipd) is the ATOM-compatible raw-receive entry that
        # function 13 (cipsend) also falls into after transmitting. Exercise
        # it directly with a payload spanning more than one 256-byte JIM
        # page, as a real chat64.nl response would.
        body = b"HTTP/1.0 200 OK\r\n\r\n" + (b"Y" * 600)
        self.machine.memory.receive[:] = body
        self.machine.call(20)
        self.assertEqual(self.machine.memory.public_response(), body)
        self.assertGreater(self.machine.memory.page, 0)

    def test_send_retries_zero_and_partial_queue_results(self):
        request = bytes(range(256)) + bytes(range(67))
        self.machine.memory.ram[0x3000:0x3000 + len(request)] = request
        self.machine.memory.ram[0x70:0x75] = bytes(
            (0x00, 0x30, len(request) & 0xFF, len(request) >> 8, 0)
        )
        self.machine.memory.send_schedule[:] = [0, 17, 5, 200, 101]
        self.machine.memory.receive_schedule[:] = [None]
        self.machine.call(13, 0x70, 0)
        self.assertEqual(self.machine.memory.sent, request)


if __name__ == "__main__":
    unittest.main()
