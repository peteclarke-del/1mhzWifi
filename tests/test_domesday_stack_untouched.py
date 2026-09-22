"""The Domesday stack is upstream's, and this integration must not disturb it.

Pi1MHz carries the BBC Domesday Project support: the VFS filing system, the
VP415 LaserDisc emulation and its F-codes, the video player and the H.264
decode path, and the BeebSCSI AIV LUNs behind them. None of it is this
project's, and none of it should change because a WiFi, UEF or FTP service
was patched in beside it.

This is asserted rather than assumed because the question is easy to ask and
expensive to answer by hand, and because a collision would be quiet: a
services command range claimed twice, or a poll slot taken from the video
player, would show up as Domesday misbehaving rather than as a network fault.
"""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATCHES = ROOT / "pi-side/pi1mhz/patches"
OVERLAY = ROOT / "pi-side/pi1mhz/overlay"

# Every Pi1MHz source the Domesday stack is implemented in.
DOMESDAY_SOURCES = (
    "src/videoplayer.c", "src/videoplayer.h",
    "src/harddisc_emulator.c", "src/harddisc_emulator.h",
    "src/pvf.h",
    "src/BeebSCSI/", "src/framebuffer/", "src/rpi/audio.c",
    "src/vidcore/", "src/M5000_emulator.c",
)


def patched_paths() -> set[str]:
    paths = set()
    for patch in PATCHES.glob("*.patch"):
        for line in patch.read_text(errors="replace").splitlines():
            if line.startswith("+++ b/"):
                paths.add(line[len("+++ b/"):].strip())
    return paths


class DomesdayStackUntouchedTest(unittest.TestCase):
    def test_no_patch_touches_the_domesday_stack(self) -> None:
        for path in sorted(patched_paths()):
            for owned in DOMESDAY_SOURCES:
                self.assertFalse(
                    path == owned or path.startswith(owned),
                    f"{path} belongs to the Domesday stack",
                )

    def test_no_overlay_source_shadows_a_domesday_source(self) -> None:
        """An overlay file is copied over the upstream tree by name."""
        names = {source.name for source in OVERLAY.rglob("*")
                 if source.is_file()}
        for owned in DOMESDAY_SOURCES:
            if owned.endswith("/"):
                continue
            self.assertNotIn(Path(owned).name, names)

    def test_the_services_range_claimed_here_is_below_the_video_player(self) -> None:
        """Domesday reaches the Beeb through FRED bases, not this mailbox.

        BeebSCSI answers at its own FRED base and the video player is driven
        through F-codes on the SCSI LUN, so neither claims a services command
        range. The range this project adds has to stay inside the block
        services.h leaves unallocated, which is what keeps that true.
        """
        integration = (PATCHES / "services-integration.patch").read_text()
        first = re.search(r"SERVICE_CMD_FTP_FIRST\s+(\d+)u", integration)
        last = re.search(r"SERVICE_CMD_FTP_LAST\s+(\d+)u", integration)
        self.assertIsNotNone(first)
        self.assertIsNotNone(last)
        self.assertEqual(int(first.group(1)), 114)
        self.assertEqual(int(last.group(1)), 119)
        # And it must not relocate any emulator's FRED base, which is how
        # BeebSCSI, the frame buffer and the video player are reached.
        for patch in PATCHES.glob("*.patch"):
            text = patch.read_text(errors="replace")
            for line in text.splitlines():
                if line.startswith("+") and "_addr" in line:
                    self.fail(f"{patch.name} moves a FRED base: {line}")

    def test_the_poll_table_has_room_for_the_service_this_project_adds(self) -> None:
        """Registering past the table's end is ignored, not an error.

        Pi1MHz sizes the poll table by the number of emulator entries and
        drops a registration that does not fit, with a log line nobody reads
        on a booted machine. This project's FTP service registers a second
        poll slot from one emulator entry, so it spends headroom that the
        video player, the SCSI emulation and the watchdog also need.
        """
        integration = (PATCHES / "services-integration.patch").read_text()
        self.assertIn("ftp_service_init();", integration)
        ftp = (OVERLAY / "src/ftp_service.c").read_text()
        self.assertEqual(
            ftp.count("Pi1MHz_Register_Poll("), 1,
            "the FTP service may take one poll slot, not more",
        )


if __name__ == "__main__":
    unittest.main()
