"""Structural checks on the patch stacks, from defects that reached the tree.

Two real ones. media-service.patch carried a hand-written hunk header declaring
six context lines for a hunk with seven, so patch(1) rejected it and the change
never landed; the emulator compiles those sources directly, so nothing noticed.
And elkwifi_service.c, which is named in the kernel build, was made to call
media_catalogue.c, which was not, so the ARM kernel would not have linked.

The first is only reliably caught by applying the patch. A textual check on the
declared hunk counts looks attractive and is not sound here: patches in this
tree have had trailing whitespace stripped, so an empty context line and the
blank line after a hunk are indistinguishable, and the tolerance needed to
accept one would be exactly the error that has to be caught.
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PI_PATCHES = ROOT / "pi-side/pi1mhz-516a267/patches"
ROM_PATCHES = ROOT / "rom-side/elkwifi-0.23/patches"
OVERLAY = ROOT / "pi-side/pi1mhz-516a267/overlay/src"


def pinned_commit() -> str:
    for line in (ROOT / "pi-side/upstream.env").read_text().splitlines():
        if line.startswith("PI1MHZ_UPSTREAM_COMMIT="):
            return line.split("=", 1)[1].strip()
    raise AssertionError("upstream.env does not pin a commit")


class PatchApplicationTest(unittest.TestCase):
    """Every Pi patch must apply to the pinned upstream.

    Skipped without a checkout, because the alternative is a textual
    approximation that cannot distinguish a malformed header from a stripped
    blank line. Point PI1MHZ_SOURCE at a Pi1MHz clone to run it.
    """

    def test_every_pi_patch_applies_to_the_pinned_commit(self) -> None:
        source = os.environ.get("PI1MHZ_SOURCE")
        if not source or not Path(source, ".git").exists():
            self.skipTest("set PI1MHZ_SOURCE to a Pi1MHz checkout to run this")
        if not shutil.which("git"):
            self.skipTest("git is required")
        commit = pinned_commit()
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder) / "Pi1MHz"
            clone = subprocess.run(
                ["git", "clone", "--quiet", "--shared", source, str(work)],
                capture_output=True, text=True,
            )
            if clone.returncode:
                self.skipTest(f"could not clone the checkout: {clone.stderr}")
            checkout = subprocess.run(
                ["git", "-C", str(work), "checkout", "--quiet", commit],
                capture_output=True, text=True,
            )
            if checkout.returncode:
                self.skipTest(f"the checkout lacks {commit}")
            # Overlay sources first: several patches only touch files the
            # overlay supplies, and a patch cannot apply to an absent file.
            for source_file in OVERLAY.glob("*.[ch]"):
                shutil.copy2(source_file, work / "src" / source_file.name)
            installer = (ROOT / "pi-side/install_bundle.sh").read_text()
            order = [
                token for token in installer.split("for patch_name in ", 1)[1]
                .split(";", 1)[0].split()
            ]
            self.assertGreater(len(order), 5, "the patch order was not parsed")
            for name in order:
                patch = PI_PATCHES / name
                self.assertTrue(patch.is_file(), f"{name} is listed but missing")
                applied = subprocess.run(
                    ["patch", "-p1", "--forward", "--silent",
                     "--no-backup-if-mismatch", "-i", str(patch)],
                    cwd=work, capture_output=True, text=True,
                )
                self.assertIn(
                    applied.returncode, (0, 1),
                    f"{name} failed to apply: {applied.stdout}{applied.stderr}",
                )
                self.assertNotIn(
                    "FAILED", applied.stdout + applied.stderr,
                    f"{name} has a hunk which does not apply:\n"
                    f"{applied.stdout}{applied.stderr}",
                )


class KernelLinkageTest(unittest.TestCase):
    def test_a_linked_pi_source_never_calls_an_unlinked_one(self) -> None:
        # elkwifi_service.c is in the kernel build and calls media_catalogue.c.
        # When that was not also named, the kernel would not have linked, and
        # the emulator did not notice because it compiles the sources directly.
        linked: set[str] = set()
        for directory in (PI_PATCHES, ROM_PATCHES):
            for patch in directory.glob("*.patch"):
                text = patch.read_text(encoding="utf-8", errors="replace")
                if "CMakeLists.txt" not in text:
                    continue
                for line in text.splitlines():
                    stripped = line[1:].strip() if line[:1] in "+ " else ""
                    if stripped.endswith(".c"):
                        linked.add(stripped)
        self.assertIn("elkwifi_service.c", linked)
        self.assertIn("media_catalogue.c", linked)

        for name in sorted(linked):
            source = OVERLAY / name
            if not source.is_file():
                continue
            text = source.read_text(encoding="utf-8", errors="replace")
            includes = {
                f"{stem}.c"
                for stem in __import__("re").findall(
                    r'#include\s+"([A-Za-z0-9_]+)\.h"', text
                )
            }
            for companion in sorted(includes):
                if not (OVERLAY / companion).is_file():
                    continue
                self.assertIn(
                    companion, linked,
                    f"{name} is linked into the kernel and includes "
                    f"{companion[:-2]}.h, but {companion} is not named in any "
                    "CMakeLists patch, so the kernel would not link",
                )


if __name__ == "__main__":
    unittest.main()
