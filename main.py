#!/usr/bin/env python3
"""Single-pass entry point, invoked by cron every minute (see install.sh). Not a long-running
daemon: it polls once for a pending command, runs it if there is one, reports the result, and
exits — the backend's atomic PENDING->RUNNING claim already makes overlapping cron ticks safe."""

import sys

from src.api_client import get_next_command, post_result
from src.config import load_config
from src.device_identity import get_board_id
from src.executor import run_command
from src.installer import run_install


def main() -> None:
    config = load_config()
    board_id = get_board_id()

    command = get_next_command(config.base_url, board_id)
    if command is None:
        return

    if command.get("type") == "INSTALL":
        exit_code, log = run_install(command["githubUrl"], command["code"], config.base_dir, config.timeout_seconds)
    else:
        exit_code, log = run_command(command["cmd"], config.timeout_seconds, config.base_dir)

    post_result(config.base_url, board_id, command["id"], exit_code, log[: config.max_log_chars])


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # A cron-run agent must never fail loudly (cron mails stderr on non-zero exit) — log locally
        # and try again next minute.
        print(f"[storeyes-agent] error: {e}", file=sys.stderr)
        sys.exit(0)
