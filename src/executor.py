"""Runs a shell command and captures its exit code + combined stdout/stderr."""

import os
import subprocess
from typing import Dict, Optional, Tuple


def run_command(
    cmd: str, timeout_seconds: int, base_dir: Optional[str] = None, extra_env: Optional[Dict[str, str]] = None
) -> Tuple[int, str]:
    """Runs `cmd` through the shell. When `base_dir` is given, the command runs from there with
    HOME pointed at it — the agent runs as root via cron, so without this a command containing
    `~` (the backend's RUN commands do `cd ~/<code>`) would resolve to /root instead of the real
    user's home where INSTALL put everything. `extra_env` is added on top (e.g. STY_COMMAND_ID)."""
    env = {**os.environ, **extra_env} if extra_env else None
    cwd = None
    if base_dir:
        env = {**(env or os.environ), "HOME": base_dir}
        # Only chdir if it actually exists: subprocess raises before running anything otherwise,
        # which would cost us the command's own error message.
        cwd = base_dir if os.path.isdir(base_dir) else None

    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout_seconds,
            cwd=cwd, env=env,
        )
        return result.returncode, (result.stdout or "") + (result.stderr or "")
    except subprocess.TimeoutExpired as e:
        partial = (e.stdout or "") + (e.stderr or "") if isinstance(e.stdout, str) else ""
        return 124, f"Command timed out after {timeout_seconds}s\n{partial}"
