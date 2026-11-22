import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONF = (ROOT / "frontend/nginx.conf").read_text()


def location_block(prefix: str) -> str:
    start = CONF.index(f"location {prefix} {{")
    depth = 0
    for index in range(start, len(CONF)):
        if CONF[index] == "{":
            depth += 1
        elif CONF[index] == "}":
            depth -= 1
            if depth == 0:
                return CONF[start : index + 1]
    raise AssertionError(f"unterminated location {prefix}")


class NginxConfTests(unittest.TestCase):
    def test_upstreams_are_resolved_per_request(self):
        # A literal host is resolved once at startup; a recreated container then gets 502s.
        self.assertRegex(CONF, r"(?m)^    resolver 127\.0\.0\.11 valid=10s ipv6=off;$")
        targets = re.findall(r"(?m)^\s*proxy_pass\s+([^;]+);", CONF)
        self.assertGreaterEqual(len(targets), 3)
        for target in targets:
            with self.subTest(proxy_pass=target):
                self.assertTrue(target.startswith("$"), target)

    def test_websockets_are_capped_per_address_and_in_total(self):
        self.assertRegex(CONF, r"limit_conn_zone \$binary_remote_addr zone=ws_per_ip:\S+;")
        self.assertRegex(CONF, r"limit_conn_zone \$server_name zone=ws_total:\S+;")
        ws = location_block("/ws/")
        self.assertIn("limit_conn ws_per_ip 30;", ws)
        self.assertIn("limit_conn ws_total 1000;", ws)
        self.assertIn("limit_conn_status 429;", ws)


class ServiceWorkerTests(unittest.TestCase):
    def test_service_worker_and_manifest_are_never_cached(self):
        for path in ("= /sw.js", "= /manifest.webmanifest"):
            with self.subTest(path=path):
                block = location_block(path)
                self.assertIn('Cache-Control "no-cache"', block)
                self.assertIn("security-headers.conf", block)


if __name__ == "__main__":
    unittest.main()
