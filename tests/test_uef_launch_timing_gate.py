"""Executable timing gate for the generic normalised-UEF install boundary."""

from pathlib import Path
import os
import re
import unittest

from tests.test_wicfs_runtime_contract import DelayedOneSlotMailbox, MPU, ROOT


class RecordingMailbox(DelayedOneSlotMailbox):
    def __init__(self, rom: bytes, delay_accesses: int):
        super().__init__(rom, delay_accesses)
        self.replacements = []

    def _schedule(self, operation: str, address: int, value: int) -> None:
        if self.pending is not None:
            self.replacements.append((self.pending, (operation, address, value)))
        super()._schedule(operation, address, value)


def mos_return(mpu: MPU, memory: RecordingMailbox) -> None:
    low = memory.ram[0x0100 + ((mpu.sp + 1) & 0xFF)]
    high = memory.ram[0x0100 + ((mpu.sp + 2) & 0xFF)]
    mpu.sp = (mpu.sp + 2) & 0xFF
    mpu.pc = (((high << 8) | low) + 1) & 0xFFFF


class UefLaunchTimingGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        path = Path(os.environ.get(
            "ELKWIFI_TEST_ROM", ROOT / "build/pi1mhz-all/Pi1MHz/1mhz-wifi.rom",
        ))
        cls.rom = path.read_bytes()
        entry = re.search(
            rb"\x20(..)\xB0.\x20(..)\xAD..\xC9\xA5\xD0."
            rb"\xAD..\xC9\x5A\xD0.",
            cls.rom, re.S,
        )
        if entry is None:
            raise AssertionError("assembled UEF run/install entry not found")
        cls.install = entry.group(1)[0] | entry.group(1)[1] << 8

    def run_install(self, delay: int) -> RecordingMailbox:
        memory = RecordingMailbox(self.rom, delay)
        mpu = MPU(memory=memory, pc=self.install)
        mpu.sp = 0xFD
        memory.ram[0x01FE:0x0200] = bytes((0xFF, 0x05))
        for address, value in (
            (0x0212, 0x1B), (0x0213, 0xFF),
            (0x0216, 0x21), (0x0217, 0xFF),
            (0x021C, 0x2A), (0x021D, 0xFF),
            (0x021E, 0x2D), (0x021F, 0xFF),
            (0x020A, 0x34), (0x020B, 0x12), (0x00F4, 3),
        ):
            memory.ram[address] = value
        for index, values in enumerate(
            ((0x11, 0x22, 1), (0x33, 0x44, 2),
             (0x55, 0x66, 3), (0x77, 0x88, 4))
        ):
            start = 0x0400 + index * 3
            memory.ram[start:start + 3] = bytes(values)
        # Generic completed normalisation fixture: public JIM length &3077.
        memory.page_data[0xFF, 0xFE] = 0x77
        memory.page_data[0xFF, 0xFF] = 0x30

        for _ in range(500000):
            if mpu.pc == 0x0600:
                break
            if mpu.pc == 0xFFF4:
                if mpu.a == 0xA8:
                    mpu.x, mpu.y = 0x00, 0x04
                mos_return(mpu, memory)
            elif mpu.pc == 0xFFE3:
                mos_return(mpu, memory)
            else:
                mpu.step()
        else:
            self.fail(f"WiCFS install hung with callback delay {delay}")
        self.assertEqual(mpu.sp, 0xFF)
        return memory

    def test_normalise_to_install_survives_supported_delay_sweep(self) -> None:
        for delay in (1, 4, 12, 14, 32, 64, 128, 255):
            with self.subTest(delay=delay):
                memory = self.run_install(delay)
                overwritten_writes = [
                    pair for pair in memory.replacements
                    if pair[0][0] == "write"
                ]
                self.assertEqual(overwritten_writes, [])
