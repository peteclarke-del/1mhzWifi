import pathlib
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class RepositoryGovernanceTest(unittest.TestCase):
    def test_community_health_files_are_present(self) -> None:
        required = (
            "CODE_OF_CONDUCT.md",
            "CONTRIBUTING.md",
            "GOVERNANCE.md",
            "LICENSING.md",
            "NOTICE",
            "SECURITY.md",
            "SUPPORT.md",
            "THIRD_PARTY_NOTICES.md",
            "docs/github-repository-settings.md",
            ".github/CODEOWNERS",
            ".github/pull_request_template.md",
            ".github/dependabot.yml",
            ".github/ISSUE_TEMPLATE/bug_report.yml",
            ".github/ISSUE_TEMPLATE/config.yml",
            ".github/ISSUE_TEMPLATE/feature_request.yml",
            ".github/ISSUE_TEMPLATE/hardware_validation.yml",
        )
        for relative in required:
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_issue_forms_have_required_metadata(self) -> None:
        forms = ROOT / ".github/ISSUE_TEMPLATE"
        for path in forms.glob("*.yml"):
            source = path.read_text()
            if path.name == "config.yml":
                self.assertIn("blank_issues_enabled: false", source)
                self.assertIn("security/advisories/new", source)
                continue
            self.assertIn("name:", source, path.name)
            self.assertIn("description:", source, path.name)
            self.assertIn("body:", source, path.name)
            self.assertIn("validations:", source, path.name)

    def test_ownership_and_private_reporting_are_explicit(self) -> None:
        owners = (ROOT / ".github/CODEOWNERS").read_text()
        security = (ROOT / "SECURITY.md").read_text()
        self.assertIn("* @peteclarke-del", owners)
        self.assertIn("security/advisories/new", security)
        self.assertIn("Earlier test builds | Not supported", security)

    def test_licensing_statements_are_consistent(self) -> None:
        status = (ROOT / "LICENSING.md").read_text()
        notice = (ROOT / "NOTICE").read_text()
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text()
        self.assertIn("No project-wide open-source licence", status)
        self.assertIn("No project-wide open-source licence", notice)
        self.assertIn("No project-wide licence has been inferred", notices)
        self.assertIn("ElkWiFi", status)

    def test_local_test_roms_cannot_be_tracked(self) -> None:
        ignore = (ROOT / ".gitignore").read_text()
        self.assertIn("/local-roms/", ignore)
        tracked = subprocess.run(
            ["git", "ls-files", "local-roms"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.assertEqual(tracked, "")


if __name__ == "__main__":
    unittest.main()
