"""The installation process: given a software's githubUrl and code, clones it and runs its
install.sh. This is deliberately built here (agent-side) rather than as a single string handed
down by the backend — the backend only supplies the raw ingredients (githubUrl, code)."""

import os
from typing import Tuple

from .executor import run_command


def run_install(github_url: str, code: str, base_dir: str, timeout_seconds: int) -> Tuple[int, str]:
    target_dir = os.path.join(base_dir, code)
    if os.path.isdir(target_dir):
        return 0, f"{target_dir} already exists — treating as already installed, skipping."

    steps = [
        f"git clone {github_url} {target_dir}",
        f"cd {target_dir}",
        "chmod +x install.sh",
        "sudo ./install.sh",
    ]
    # Chained in one shell invocation so `cd` carries over to the following steps, and so the
    # whole sequence stops (and reports a non-zero exit code) at the first failing step.
    return run_command(" && ".join(steps), timeout_seconds, base_dir)
