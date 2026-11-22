import os
import secrets
import subprocess
import sys
from pathlib import Path

import pytest

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


@pytest.mark.parametrize(
    "env, expected",
    [
        pytest.param({"LOG_LEVEL": "ERROR"}, "40", id="uppercase-error"),
        pytest.param({}, "20", id="default-info"),
        pytest.param({"LOG_LEVEL": "error"}, "40", id="lowercase-error"),
    ],
)
def test_log_level_from_env(env, expected):
    code = "import django, logging; django.setup(); print(logging.getLogger().getEffectiveLevel())"
    result = _run_prod(code, SECRET_KEY=secrets.token_urlsafe(50), **env)
    assert result.stdout.strip() == expected, result.stderr


_CONN_CODE = (
    "import django; django.setup(); from django.conf import settings as s; "
    "d=s.DATABASES['default']; print(d['CONN_MAX_AGE'], d['CONN_HEALTH_CHECKS'])"
)


@pytest.mark.parametrize(
    "env, expected",
    [
        pytest.param({}, ["60", "True"], id="default"),
        pytest.param({"DB_CONN_MAX_AGE": "0"}, ["0", "True"], id="disabled"),
    ],
)
def test_conn_max_age(env, expected):
    result = _run_prod(_CONN_CODE, SECRET_KEY=secrets.token_urlsafe(50), **env)
    assert result.stdout.split() == expected


@pytest.mark.parametrize(
    "env, expected",
    [
        # Bounded by default so a stuck SMTP server cannot outlive the worker's grace period.
        pytest.param({}, "30.0", id="default"),
        pytest.param({"EMAIL_TIMEOUT": "10"}, "10.0", id="from-env"),
    ],
)
def test_email_timeout(env, expected):
    code = "import django; django.setup(); from django.conf import settings; print(settings.EMAIL_TIMEOUT)"
    result = _run_prod(code, SECRET_KEY=secrets.token_urlsafe(50), **env)
    assert result.stdout.strip() == expected
