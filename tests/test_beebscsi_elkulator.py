import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "emulator/pi1mhz-mailbox/integrations/elkulator"


class BeebScsiElkulatorTests(unittest.TestCase):
 def test_register_protocol_reads_and_writes_lun(self) -> None:
    temporary = tempfile.TemporaryDirectory()
    self.addCleanup(temporary.cleanup)
    tmp_path = Path(temporary.name)
    lun = tmp_path / "scsi0.dat"
    image = bytearray(4 * 256)
    image[256:512] = bytes(range(256))
    lun.write_bytes(image)
    geometry = bytearray(22)
    geometry[13:16] = bytes((0x0F, 0x83, 0x10))
    dsc = tmp_path / "scsi0.dsc"
    dsc.write_bytes(geometry)
    fallback_lun = tmp_path / "fallback.dat"
    fallback_image = bytearray(10000)
    fallback_image[256:512] = bytes(range(256))
    fallback_lun.write_bytes(fallback_image)
    harness = tmp_path / "beebscsi_harness.c"
    harness.write_text(
        r'''
#include "beebscsi_elkulator.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

static unsigned irq_updates;
static int elkulator_irq;

static void updateulaints_fixture(void)
{
    ++irq_updates;
    elkulator_irq = beebscsi_elkulator_host_irq();
}

static void command(const uint8_t *cdb)
{
    unsigned i;
    beebscsi_elkulator_write(0xfc40, 0);
    beebscsi_elkulator_write(0xfc42, 0);
    for (i = 0; i < 6; ++i)
        beebscsi_elkulator_write(0xfc40, cdb[i]);
}

int main(int argc, char **argv)
{
    const uint8_t read1[6] = {0x08, 0, 0, 1, 1, 0};
    const uint8_t write2[6] = {0x0a, 0, 0, 2, 1, 0};
    const uint8_t mode_sense[6] = {0x1a, 0, 0, 0, 33, 0};
    unsigned i;
    FILE *file;
    uint8_t sector[256];

    if (argc != 3 || setenv("PI1MHZ_BEEBSCSI_LUN", argv[1], 1))
        return 2;
    beebscsi_elkulator_set_irq_callback(updateulaints_fixture);
    if (!beebscsi_elkulator_handles(0xfc40) ||
        !beebscsi_elkulator_handles(0xfc44) ||
        beebscsi_elkulator_handles(0xfc45))
        return 3;
    command(read1);
    if ((beebscsi_elkulator_read(0xfc41) & 0x62) != 0x62)
        return 4;
    beebscsi_elkulator_write(0xfc43, 1);
    if (!beebscsi_elkulator_host_irq() || elkulator_irq != 1 ||
        irq_updates != 1 || !(beebscsi_elkulator_read(0xfc41) & 0x10))
        return 11;
    if (beebscsi_elkulator_read(0xfc40) != 0 ||
        !beebscsi_elkulator_host_irq() || elkulator_irq != 1 ||
        irq_updates != 1)
        return 15;
    beebscsi_elkulator_write(0xfc43, 0);
    if (beebscsi_elkulator_host_irq() || elkulator_irq != 0 ||
        irq_updates != 2)
        return 12;
    for (i = 1; i < 256; ++i) {
        if (!(beebscsi_elkulator_read(0xfc41) & 0x20))
            return 16;
        if (beebscsi_elkulator_read(0xfc40) != (uint8_t)i)
            return 5;
    }
    if (beebscsi_elkulator_host_irq() || irq_updates != 2)
        return 13;
    if (beebscsi_elkulator_read(0xfc40) != 0 ||
        beebscsi_elkulator_read(0xfc40) != 0)
        return 6;
    command(write2);
    for (i = 0; i < 256; ++i)
        beebscsi_elkulator_write(0xfc40, (uint8_t)(255 - i));
    if (beebscsi_elkulator_read(0xfc40) != 0 ||
        beebscsi_elkulator_read(0xfc40) != 0)
        return 7;
    file = fopen(argv[1], "rb");
    if (!file || fseek(file, 512, SEEK_SET) ||
        fread(sector, 1, sizeof(sector), file) != sizeof(sector))
        return 8;
    fclose(file);
    for (i = 0; i < 256; ++i)
        if (sector[i] != (uint8_t)(255 - i))
            return 9;
    beebscsi_elkulator_reset();
    if (beebscsi_elkulator_read(0xfc41) != 0x20)
        return 10;
    command(mode_sense);
    for (i = 0; i < 33; ++i) {
        uint8_t expected = i == 13 ? (argv[2][0] == 'f' ? 0 : 0x0f) :
                           i == 14 ? (argv[2][0] == 'f' ? 1 : 0x83) :
                           i == 15 ? (argv[2][0] == 'f' ? 255 : 0x10) : 0;
        if (beebscsi_elkulator_read(0xfc40) != expected)
            return 14;
    }
    return 0;
}
'''
    )
    executable = tmp_path / "beebscsi_harness"
    subprocess.run(
        [
            "cc",
            "-std=c11",
            "-D_POSIX_C_SOURCE=200809L",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I",
            str(INTEGRATION),
            str(harness),
            str(INTEGRATION / "beebscsi_elkulator.c"),
            "-o",
            str(executable),
        ],
        check=True,
    )
    subprocess.run([str(executable), str(lun), "sidecar"], check=True)
    subprocess.run([str(executable), str(fallback_lun), "fallback"], check=True)

 def test_patch_connects_irq_transitions_to_elkulator_ula(self) -> None:
    patch = (INTEGRATION / "elkulator-beebscsi.patch").read_text()
    self.assertIn(
        "beebscsi_elkulator_set_irq_callback(updateulaints);", patch
    )
    self.assertIn("beebscsi_elkulator_host_irq()", patch)
    self.assertIn("else if ((plus1 && serial_irq)", patch)


 def test_disabled_without_explicit_lun(self) -> None:
    temporary = tempfile.TemporaryDirectory()
    self.addCleanup(temporary.cleanup)
    tmp_path = Path(temporary.name)
    harness = tmp_path / "disabled.c"
    harness.write_text(
        r'''
#include "beebscsi_elkulator.h"
int main(void) { return beebscsi_elkulator_handles(0xfc40) ? 1 : 0; }
'''
    )
    executable = tmp_path / "disabled"
    subprocess.run(
        [
            "cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
            "-I", str(INTEGRATION), str(harness),
            str(INTEGRATION / "beebscsi_elkulator.c"), "-o", str(executable),
        ],
        check=True,
    )
    subprocess.run([str(executable)], check=True, env={})


if __name__ == "__main__":
    unittest.main()
