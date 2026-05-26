"""Ensure uv is installed."""

import shutil
import subprocess
import sys


def has_uv():
    """Check if uv is installed."""
    return shutil.which("uv") is not None


def install_uv():
    """Install uv via pip."""
    print("Installing uv via pip...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "uv"])


if not has_uv():
    install_uv()
