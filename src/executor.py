"""Runs a shell command and captures its exit code + combined stdout/stderr."""

import subprocess
from typing import Tuple


def run_command(cmd: str, timeout_seconds: int) -> Tuple[int, str]:
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout_seconds
        )
        return result.returncode, (result.stdout or "") + (result.stderr or "")
    except subprocess.TimeoutExpired as e:
        partial = (e.stdout or "") + (e.stderr or "") if isinstance(e.stdout, str) else ""
        return 124, f"Command timed out after {timeout_seconds}s\n{partial}"
