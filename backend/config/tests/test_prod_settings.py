import os
import secrets
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _run_prod(code, **env):
    # Subprocess, because prod settings run at import time and must not leak into this process.
    full_env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings.prod",
        "SENTRY_DSN": "",
    }
    full_env.pop("LOG_LEVEL", None)
    full_env.update(env)
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_DIR,
        env=full_env,
        capture_output=True,
        text=True,
    )


def test_short_secret_key_fails_fast():
    result = _run_prod("import django; django.setup()", SECRET_KEY="x" * 49)
    assert result.returncode != 0
    assert "SECRET_KEY must be at least 50 characters" in result.stderr


def test_long_secret_key_boots():
    result = _run_prod("import django; django.setup()", SECRET_KEY=secrets.token_urlsafe(50))
    assert result.returncode == 0, result.stderr


def test_log_level_comes_from_env():
    code = "import django, logging; django.setup(); print(logging.getLogger().getEffectiveLevel())"
    result = _run_prod(code, SECRET_KEY=secrets.token_urlsafe(50), LOG_LEVEL="ERROR")
    assert result.stdout.strip() == "40"


def test_log_level_defaults_to_info():
    code = "import django, logging; django.setup(); print(logging.getLogger().getEffectiveLevel())"
    result = _run_prod(code, SECRET_KEY=secrets.token_urlsafe(50))
    assert result.stdout.strip() == "20"


def test_log_level_is_case_insensitive():
    code = "import django, logging; django.setup(); print(logging.getLogger().getEffectiveLevel())"
    result = _run_prod(code, SECRET_KEY=secrets.token_urlsafe(50), LOG_LEVEL="error")
    assert result.stdout.strip() == "40", result.stderr
