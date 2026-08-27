"""Enforce permanent ownership of every recorded hardware regression."""

import ast
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests/regression_manifest.json"
REQUIRED_REGRESSIONS = {
    "BOOT-001", "MAILBOX-001", "WIFI-001", "WIFI-002",
    "MENU-001", "MENU-002", "MENU-003",
    "WICFS-001", "WICFS-002", "WICFS-003", "WICFS-004",
    "WICFS-005", "WICFS-006", "WICFS-007", "WICFS-008",
    "WICFS-009", "WICFS-010", "WICFS-011", "WICFS-012",
    "WICFS-013",
    "OSWORD-001", "OSWORD-002",
    "NETTOOLS-001", "NETTOOLS-002", "NETTOOLS-003",
    "ELKCHAT-001", "TUBE-001", "TUBE-002", "PLATFORM-001",
}


class RegressionManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = json.loads(MANIFEST.read_text())
        cls.failures = cls.document["failures"]

    def test_manifest_is_well_formed_and_has_unique_stable_ids(self) -> None:
        self.assertEqual(self.document["schema"], 1)
        identifiers = [failure["id"] for failure in self.failures]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertTrue(
            REQUIRED_REGRESSIONS.issubset(identifiers),
            "a historical regression cannot be removed from the ownership ledger",
        )
        for failure in self.failures:
            with self.subTest(failure=failure["id"]):
                self.assertRegex(failure["id"], r"^[A-Z]+-[0-9]{3}$")
                self.assertGreaterEqual(len(failure["symptom"]), 24)
                self.assertIn(failure["status"], ("fixed", "open-hardware"))
                self.assertTrue(failure["tests"])
                if failure["status"] == "open-hardware":
                    self.assertIn("acceptance_runner", failure)
                    self.assertIn("required_profile", failure)

    def test_every_claimed_regression_test_exists_and_is_discovered(self) -> None:
        parsed = {}
        for failure in self.failures:
            for reference in failure["tests"]:
                with self.subTest(failure=failure["id"], reference=reference):
                    parts = reference.split("::")
                    self.assertEqual(len(parts), 3)
                    relative, class_name, method_name = parts
                    self.assertTrue(method_name.startswith("test_"))
                    source = ROOT / relative
                    self.assertTrue(source.is_file(), source)
                    self.assertIn(
                        source.parent,
                        (ROOT / "tests", ROOT / "host-tools/tests"),
                        "regression tests must live in an automatically discovered suite",
                    )
                    tree = parsed.setdefault(source, ast.parse(source.read_text()))
                    classes = {
                        node.name: node
                        for node in tree.body
                        if isinstance(node, ast.ClassDef)
                    }
                    self.assertIn(class_name, classes)
                    methods = {
                        node.name
                        for node in classes[class_name].body
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    }
                    self.assertIn(method_name, methods)

    def test_acceptance_qualified_failures_name_real_runners_and_profiles(self) -> None:
        for failure in self.failures:
            if "acceptance_runner" not in failure:
                continue
            with self.subTest(failure=failure["id"]):
                runner = ROOT / failure["acceptance_runner"]
                self.assertTrue(runner.is_file(), runner)
                self.assertTrue(runner.name.startswith("run_"))
                self.assertGreaterEqual(len(failure["required_profile"]), 32)

    def test_lifecycle_regressions_require_same_process_outcome_coverage(self) -> None:
        by_id = {failure["id"]: failure for failure in self.failures}
        uef_outcome = (
            "tests/test_runner_acceptance_contract.py::"
            "RunnerAcceptanceContractTests::"
            "test_uef_recovery_replays_in_one_process_after_real_adfs_reads"
        )
        menu_outcome = (
            "tests/test_runner_acceptance_contract.py::"
            "RunnerAcceptanceContractTests::"
            "test_catalogue_repeats_menu_and_gameplay_in_one_process"
        )
        adfs = by_id["WICFS-009"]
        self.assertIn(uef_outcome, adfs["tests"])
        self.assertEqual(adfs["acceptance_runner"],
                         "tests/elkulator/run_uef_gameplay.py")
        self.assertIn("--recovery-check", adfs["required_profile"])
        menu = by_id["WICFS-010"]
        self.assertIn(uef_outcome, menu["tests"])
        self.assertIn(menu_outcome, menu["tests"])
        self.assertEqual(menu["acceptance_runner"],
                         "tests/elkulator/run_catalogue_differential.py")
        self.assertIn("--repeat-after-break", menu["required_profile"])

    def test_fixed_failure_categories_are_not_left_without_coverage(self) -> None:
        fixed_categories = {
            failure["id"].split("-", 1)[0]
            for failure in self.failures
            if failure["status"] == "fixed"
        }
        self.assertTrue({
            "BOOT", "MAILBOX", "WIFI", "MENU", "WICFS",
            "OSWORD", "NETTOOLS", "ELKCHAT", "TUBE",
        }.issubset(fixed_categories))


if __name__ == "__main__":
    unittest.main()
