import os
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = (ROOT / "frontend/nginx/security-headers.conf.template").read_text()
SCRIPT = ROOT / "frontend/nginx/15-validate-media-cdn-origin.sh"
DOCKERFILE = (ROOT / "frontend/Dockerfile").read_text()


def validate(origin):
    env = {"PATH": os.environ["PATH"], "MEDIA_CDN_ORIGIN": origin}
    return subprocess.run(["sh", str(SCRIPT)], env=env, capture_output=True, text=True)


def render(origin):
    """What the image's envsubst step produces."""
    return TEMPLATE.replace("${MEDIA_CDN_ORIGIN}", origin)


class MediaCdnTests(unittest.TestCase):
    def test_origin_only_appears_in_img_src(self):
        placeholders = re.findall(r"\$\{[A-Z_]+\}", TEMPLATE)
        self.assertEqual(placeholders, ["${MEDIA_CDN_ORIGIN}"])
        directive = next(
            part for part in TEMPLATE.split(";") if "img-src" in part
        )
        self.assertIn("${MEDIA_CDN_ORIGIN}", directive)

    def test_service_worker_and_manifest_are_allowed_and_nothing_wider(self):
        csp = next(line for line in render("").splitlines() if "Content-Security-Policy" in line)
        self.assertIn("worker-src 'self'", csp)
        self.assertIn("manifest-src 'self'", csp)
        self.assertNotIn("script-src 'self' 'unsafe", csp)

    def test_empty_origin_keeps_the_policy_tight(self):
        csp = next(line for line in render("").splitlines() if "Content-Security-Policy" in line)
        self.assertIn("img-src 'self' data: blob:", csp)
        self.assertNotIn("*", csp)
        self.assertEqual(validate("").returncode, 0)

    def test_a_single_https_origin_is_accepted_and_lands_in_img_src(self):
        for origin in ("https://cdn.example.com", "https://media.example.org:8443"):
            with self.subTest(origin=origin):
                self.assertEqual(validate(origin).returncode, 0, validate(origin).stderr)
                self.assertIn(f"img-src 'self' data: blob: {origin};", render(origin))

    def test_anything_that_could_widen_the_policy_is_refused(self):
        bad = [
            "*",
            "https://*.example.com",
            "http://cdn.example.com",
            "https://cdn.example.com/media",
            "https://cdn.example.com;script-src *",
            "https://cdn.example.com 'unsafe-inline'",
            "https://cdn.example.com\nscript-src *",
            "https://cdn.example.com'",
            "cdn.example.com",
            "data:",
            "https://",
            "https://-bad.example.com",
        ]
        for origin in bad:
            with self.subTest(origin=origin):
                result = validate(origin)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("MEDIA_CDN_ORIGIN rejected", result.stderr)

    def test_image_renders_the_template_only_for_media_variables(self):
        self.assertIn("NGINX_ENVSUBST_FILTER=MEDIA_CDN_", DOCKERFILE)
        self.assertIn("NGINX_ENVSUBST_OUTPUT_DIR=/etc/nginx/snippets", DOCKERFILE)
        self.assertIn("/docker-entrypoint.d/15-validate-media-cdn-origin.sh", DOCKERFILE)
        # The entrypoint runs /docker-entrypoint.d scripts in lexical order; the base image renders
        # templates in 20-envsubst-on-templates.sh, so the validator's real name must sort before it.
        copy = re.search(r"COPY\s+\S+\s+/docker-entrypoint\.d/(\S+)", DOCKERFILE)
        self.assertIsNotNone(copy)
        validator = copy.group(1)
        self.assertTrue(SCRIPT.name == validator, validator)
        self.assertLess(validator, "20-envsubst-on-templates.sh")

    def test_compose_passes_the_origin_through(self):
        prod = (ROOT / "docker-compose.prod.yml").read_text()
        self.assertIn("MEDIA_CDN_ORIGIN: ${MEDIA_CDN_ORIGIN:-}", prod)


if __name__ == "__main__":
    unittest.main()
