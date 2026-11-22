import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CI = (ROOT / ".github/workflows/ci.yml").read_text()


def job(name: str) -> str:
    """The text of a top-level job in ci.yml (two-space indented key under `jobs:`)."""
    match = re.search(rf"(?ms)^  {re.escape(name)}:\n(.*?)(?=^  \S|\Z)", CI)
    if match is None:
        raise AssertionError(f"ci.yml has no job {name!r}")
    return match.group(1)


class CiWorkflowTests(unittest.TestCase):
    def test_these_tests_run_in_ci(self):
        config = job("config-tests")
        self.assertIn("run: python3 -m unittest discover -s .github/tests", config)
        self.assertRegex(config, r"timeout-minutes: \d+")
        self.assertIn("persist-credentials: false", config)
        # Every action is pinned to a full commit SHA.
        for use in re.findall(r"uses: (\S+)", config):
            with self.subTest(uses=use):
                self.assertRegex(use, r"@[0-9a-f]{40}$")

    def test_existing_check_names_are_kept(self):
        # Branch protection refers to these.
        job("backend")
        job("frontend")

    def test_workflow_token_is_read_only(self):
        self.assertRegex(CI, r"(?m)^permissions:\n  contents: read\n")
        self.assertNotRegex(CI, r"(?m)^ +permissions:")


if __name__ == "__main__":
    unittest.main()
