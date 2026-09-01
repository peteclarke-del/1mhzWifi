"""Builds and runs the media service transport binding on the build host.

media_service_core.c is covered by test_media_catalogue.py. This covers
media_service.c, the binding that moves a command block and a bounded reply
between JIM and the core, using the stub Pi1MHz declarations in
pi-side/tests/stubs. It proves the transport's own logic, not the kernel build.
"""

import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "pi-side/pi1mhz-516a267/overlay/src"
STUBS = ROOT / "pi-side/tests/stubs"
HARNESS = ROOT / "pi-side/tests/test_media_service_binding.c"


class MediaServiceBindingTest(unittest.TestCase):
    def test_binding_builds_clean_and_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "binding"
            build = subprocess.run(
                [
                    "cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                    "-I", str(STUBS), "-I", str(OVERLAY),
                    str(HARNESS),
                    str(OVERLAY / "media_service.c"),
                    str(OVERLAY / "media_service_core.c"),
                    str(OVERLAY / "media_catalogue.c"),
                    "-o", str(binary),
                ],
                capture_output=True, text=True,
            )
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("media service binding: OK", run.stdout)

    def test_binding_registers_the_documented_command_range(self) -> None:
        # docs/media-service-abi.md reserves 120-127 for the media service and
        # allocates 120-124 to this session protocol. FTP owns 114-119, so an
        # overlap would silently steal another service's commands.
        header = (OVERLAY / "media_service.h").read_text()
        self.assertIn("#define MEDIA_SVC_CMD_FIRST 120u", header)
        self.assertIn("#define MEDIA_SVC_CMD_LAST  124u", header)
        ftp = (OVERLAY / "ftp_service.h").read_text()
        self.assertIn("#define FTP_CMD_LAST    FTP_CMD_CANCEL", ftp)
        self.assertIn("#define FTP_CMD_CANCEL  119u", ftp)

    def test_binding_opens_the_shared_upload_buffer(self) -> None:
        # The container arrives through the incremental window protocol that
        # *UEF LOAD already fills, so there is one upload path rather than two.
        source = (OVERLAY / "media_service.c").read_text()
        self.assertIn("elkwifi_uef_stream_image", source)
        self.assertIn("media_service_open", source)
        header = (OVERLAY / "elkwifi_service.h").read_text()
        self.assertIn("const uint8_t *elkwifi_uef_stream_image(size_t *length);",
                      header)


if __name__ == "__main__":
    unittest.main()
