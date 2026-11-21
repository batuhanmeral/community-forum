"""Exercise release shell failure paths without Docker, credentials or network.

Run with: python3 -m unittest discover -s .github/tests -v
"""

import os
import re
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / "workflows" / "release.yml"
DIGEST = "sha256:" + "a" * 64


def script(name):
    # Read literal run blocks only; no third-party YAML parser is needed.
    source = WORKFLOW.read_text()
    step = source.split(f"      - name: {name}\n", 1)[1].split("\n      - ", 1)[0]
    block = step.split("        run: |\n", 1)[1]
    return textwrap.dedent(block)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = {
            **os.environ,
            "PATH": f"{self.root}:{os.environ['PATH']}",
            "GITHUB_OUTPUT": str(self.root / "output"),
            "GITHUB_ENV": str(self.root / "env"),
            "GITHUB_STEP_SUMMARY": str(self.root / "summary"),
            "GITHUB_REPOSITORY_OWNER": "ExampleOwner",
            "GITHUB_REPOSITORY": "ExampleOwner/community-forum",
            "GITHUB_REF_TYPE": "tag",
            "GITHUB_REF_NAME": "v1.2.3",
            "GITHUB_REF": "refs/tags/v1.2.3",
            "GITHUB_RUN_ID": "123",
            "GITHUB_RUN_ATTEMPT": "2",
            "IMAGE_COMPONENT": "backend",
            "IMAGE": "ghcr.io/exampleowner/nexus-backend",
            "TAG": "v1.2.3",
            "TRIVY_IMAGE": "scanner:test",
            "RUNNER_TEMP": str(self.root),
            "DIGEST": DIGEST,
            "REGISTRY_DIGEST": DIGEST,
            "CALL_LOG": str(self.root / "calls"),
            "GITHUB_SHA": "b" * 40,
        }
        self.stub(
            "docker",
            """
            printf '%s\\n' "$*" >> "$CALL_LOG"
            if [ "$1" = run ] && [ "${SCAN_FAIL:-0}" = 1 ]; then exit 42; fi
            if [ "$1" = buildx ]; then
              printf '{"digest":"%s"}\\n' "$REGISTRY_DIGEST"
            fi
        """,
        )
        self.stub(
            "git",
            """
            printf 'git %s\\n' "$*" >> "$CALL_LOG"
            if [ "${NOT_ON_MAIN:-0}" = 1 ]; then exit 1; fi
        """,
        )
        self.stub("cosign", 'printf "%s\\n" "$*" >> "$CALL_LOG"')

    def stub(self, name, body):
        path = self.root / name
        path.write_text("#!/bin/bash\nset -eu\n" + textwrap.dedent(body))
        path.chmod(0o755)

    def run_steps(self, *names):
        return subprocess.run(
            [
                "bash",
                "--noprofile",
                "--norc",
                "-euo",
                "pipefail",
                "-c",
                "\n".join(script(name) for name in names),
            ],
            check=False,
            env=self.env,
            cwd=self.root,
            capture_output=True,
            text=True,
        )

    def test_tag_and_owner(self):
        result = self.run_steps("Image reference")
        self.assertEqual(result.returncode, 0, result.stderr)
        output = (self.root / "output").read_text()
        self.assertIn("image=ghcr.io/exampleowner/nexus-backend\n", output)
        self.assertIn("tag=v1.2.3\n", output)

    def test_manual_branch_uses_unique_tag(self):
        self.env.update(GITHUB_REF_TYPE="branch", GITHUB_REF_NAME="feature/release")
        result = self.run_steps("Image reference")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("tag=run-123-2\n", (self.root / "output").read_text())

    def test_invalid_tag_is_rejected(self):
        for tag in ("vbad/tag", "vbad tag", "v" + "a" * 128, "not-a-release"):
            with self.subTest(tag=tag):
                self.env["GITHUB_REF_NAME"] = tag
                self.assertNotEqual(self.run_steps("Image reference").returncode, 0)

    def test_release_requires_commit_on_main(self):
        result = self.run_steps("Require commit on main")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            f"git merge-base --is-ancestor {'b' * 40} origin/main",
            (self.root / "calls").read_text(),
        )

    def test_commit_not_on_main_prevents_push(self):
        self.env["NOT_ON_MAIN"] = "1"
        result = self.run_steps("Require commit on main", "Publish image")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("push ", (self.root / "calls").read_text())

    def test_job_runs_only_for_main_or_release_tags(self):
        source = WORKFLOW.read_text()
        self.assertIn(
            "    if: ${{ github.ref == 'refs/heads/main' || "
            "startsWith(github.ref, 'refs/tags/v') }}\n",
            source,
        )
        self.assertIn("fetch-depth: 0", source)

    def test_build_labels_source_and_revision(self):
        result = self.run_steps("Build image without cache")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = (self.root / "calls").read_text()
        self.assertIn(
            "--label org.opencontainers.image.source="
            "https://github.com/ExampleOwner/community-forum",
            calls,
        )
        self.assertIn(f"--label org.opencontainers.image.revision={'b' * 40}", calls)

    def test_scan_failure_prevents_push(self):
        self.env["SCAN_FAIL"] = "1"
        result = self.run_steps("Scan image", "Publish image")
        self.assertEqual(result.returncode, 42, result.stderr)
        self.assertNotIn("push ", (self.root / "calls").read_text())

    def test_publish_gets_registry_digest(self):
        result = self.run_steps("Publish image")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"digest={DIGEST}\n", (self.root / "output").read_text())
        self.assertIn(
            "push ghcr.io/exampleowner/nexus-backend:v1.2.3",
            (self.root / "calls").read_text(),
        )

    def test_invalid_digest_prevents_signing(self):
        self.env["REGISTRY_DIGEST"] = "not-a-digest"
        result = self.run_steps("Publish image", "Attest SBOM and sign image")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("sign --yes", (self.root / "calls").read_text())

    def test_signs_digest_and_attests_cyclonedx(self):
        result = self.run_steps("Attest SBOM and sign image")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = (self.root / "calls").read_text()
        reference = f"{self.env['IMAGE']}@{DIGEST}"
        self.assertIn(
            f"attest --yes --type cyclonedx --predicate sbom.cdx.json {reference}",
            calls,
        )
        self.assertIn(f"sign --yes {reference}", calls)

    def test_summary_verifies_exact_identity_and_digest(self):
        result = self.run_steps("Verification summary")
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = (self.root / "summary").read_text()
        self.assertIn(f"oci://{self.env['IMAGE']}@{DIGEST}", summary)
        self.assertIn("cosign verify --certificate-identity", summary)
        self.assertIn("release.yml@refs/tags/v1.2.3", summary)
        self.assertNotRegex(summary, re.escape("${{"))


if __name__ == "__main__":
    unittest.main()
