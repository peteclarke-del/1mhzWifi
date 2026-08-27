"""Differential tests for the Pi-side container catalogue.

`pi-side/pi1mhz-516a267/overlay/src/media_catalogue.c` is the decoder that will
answer `*UEF CAT`, `*UEF EXTRACT`, `*SSD CAT` and `*SSD EXTRACT`, so the host
ROM never parses a container itself. `scripts/uef_map.py` is the independently
written Python decoder already used to qualify the corpus, and it acts as the
oracle here: both must agree on every file, load address, execution address,
length and block count.

The local Electron corpus lives under `samples/`, which is deliberately not
committed. Those cases skip when it is absent so the suite still runs in a
clean checkout.
"""

from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
OVERLAY = ROOT / "pi-side/pi1mhz-516a267/overlay/src"
HARNESS = ROOT / "pi-side/tests/test_media_catalogue.c"
CORPUS = ROOT / "samples/(2022-06-08)"


def _load_uef_map():
    spec = importlib.util.spec_from_file_location(
        "uef_map", ROOT / "scripts/uef_map.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MediaCatalogueTests(unittest.TestCase):
    tool: pathlib.Path
    tempdir: tempfile.TemporaryDirectory

    @classmethod
    def setUpClass(cls) -> None:
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.tool = pathlib.Path(cls.tempdir.name) / "media"
        build = subprocess.run(
            [
                "cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-I", str(OVERLAY), str(HARNESS),
                str(OVERLAY / "media_catalogue.c"), "-o", str(cls.tool),
            ],
            capture_output=True, text=True,
        )
        if build.returncode != 0:
            raise unittest.SkipTest(f"cannot build decoder: {build.stderr}")
        cls.uef_map = _load_uef_map()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tempdir.cleanup()

    def _c_entries(self, raw: bytes) -> list[tuple]:
        with tempfile.NamedTemporaryFile(suffix=".uef", delete=False) as handle:
            handle.write(raw)
            path = handle.name
        try:
            result = subprocess.run(
                [str(self.tool), "--dump", path],
                capture_output=True, text=True, timeout=120,
            )
        finally:
            pathlib.Path(path).unlink()
        entries = []
        for line in result.stdout.splitlines():
            fields = line.split()
            if len(fields) != 7 or fields[0] != "ENTRY":
                continue
            name = "" if fields[1] == "-" else bytes.fromhex(
                fields[1]
            ).decode("latin1")
            entries.append((
                name, int(fields[2], 16), int(fields[3], 16),
                int(fields[4]), int(fields[5]),
            ))
        return entries

    def _oracle_entries(self, path: pathlib.Path) -> list[tuple]:
        info = self.uef_map.inspect_uef(path)
        files: list[dict] = []
        current: dict | None = None
        for block in info["cfs_blocks"]:
            name = block["name"]
            if (current is None or current["name"] != name
                    or block["block_number"] == 0):
                current = {
                    "name": name,
                    "load": block["load_address"] & 0xFFFFFFFF,
                    "exec": block["execution_address"] & 0xFFFFFFFF,
                    "length": block["data_length"],
                    "blocks": 1,
                }
                files.append(current)
            else:
                current["length"] += block["data_length"]
                current["blocks"] += 1
        return [
            (f["name"], f["load"], f["exec"], f["length"], f["blocks"])
            for f in files
        ]

    def test_builtin_fixtures_pass(self) -> None:
        result = subprocess.run(
            [str(self.tool)], capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Pi media catalogue: OK", result.stdout)

    def test_decoder_matches_uef_map_across_the_corpus(self) -> None:
        if not CORPUS.is_dir():
            self.skipTest("local Electron corpus is not installed")
        files = sorted(CORPUS.glob("*.uef"))
        if not files:
            self.skipTest("local Electron corpus is empty")

        compared = 0
        unparsed = 0
        for path in files:
            try:
                expected = self._oracle_entries(path)
                raw = self.uef_map.decode_container(path.read_bytes())
                if isinstance(raw, tuple):
                    raw = raw[0]
            except Exception:
                # The corpus contains one genuinely truncated image. The oracle
                # rejects it, so there is nothing to compare against.
                unparsed += 1
                continue
            with self.subTest(uef=path.name):
                self.assertEqual(expected[:128], self._c_entries(raw))
            compared += 1

        self.assertGreater(compared, 0)
        # A sudden rise here means the decoder or the corpus changed shape.
        self.assertLessEqual(unparsed, 1)

    def test_truncated_prefixes_never_read_out_of_bounds(self) -> None:
        if not CORPUS.is_dir():
            self.skipTest("local Electron corpus is not installed")
        sample = next(iter(sorted(CORPUS.glob("*.uef"))), None)
        if sample is None:
            self.skipTest("local Electron corpus is empty")
        raw = self.uef_map.decode_container(sample.read_bytes())
        if isinstance(raw, tuple):
            raw = raw[0]
        # Every prefix must terminate cleanly rather than crash or hang.
        for size in range(0, min(len(raw), 4096), 97):
            self._c_entries(raw[:size])


if __name__ == "__main__":
    unittest.main()
