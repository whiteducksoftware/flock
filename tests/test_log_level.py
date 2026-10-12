"""Logging is apart from tracing: warnings by default, FLOCK_LOG_LEVEL for more (#601)."""

import os
import subprocess
import sys

import pytest

from flock.logging import logging as flock_logging


PROBE = (
    "import flock\n"
    "from flock.logging.logging import get_logger\n"
    "import logging\n"
    "print(logging.getLevelName(get_logger('flock.probe').min_level_severity))\n"
)


def level_after_import(**env: str) -> str:
    """The level of a new Flock logger in a fresh process with ``env``."""
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in ("FLOCK_LOG_LEVEL", "FLOCK_AUTO_TRACE")
    }
    environment.update(env, FLOCK_TRACE_FILE="false")
    result = subprocess.run(
        [sys.executable, "-c", PROBE],
        capture_output=True,
        text=True,
        env=environment,
        timeout=120,
        check=True,
    )
    return result.stdout.strip().splitlines()[-1]


def test_flock_shows_warnings_by_default_with_tracing_on_or_off():
    assert level_after_import(FLOCK_AUTO_TRACE="true") == "WARNING"
    assert level_after_import(FLOCK_AUTO_TRACE="false") == "WARNING"


def test_flock_log_level_asks_for_more():
    assert level_after_import(FLOCK_LOG_LEVEL="debug") == "DEBUG"


@pytest.mark.parametrize(
    ("value", "level"),
    [
        ("info", "INFO"),
        (" DEBUG ", "DEBUG"),
        ("error", "ERROR"),
        ("no_logs", "NO_LOGS"),
        ("", "WARNING"),
        ("loud", "WARNING"),
    ],
)
def test_the_level_comes_from_the_environment(monkeypatch, value, level):
    monkeypatch.setenv("FLOCK_LOG_LEVEL", value)

    assert flock_logging._log_level_from_env() == level
