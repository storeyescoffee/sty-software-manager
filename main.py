#!/usr/bin/env python3
"""Single-pass entry point, invoked by cron every minute (see install.sh). Not a long-running
daemon: it polls once for a pending command, runs it if there is one, reports the result, and
exits — the backend's atomic PENDING->RUNNING claim already makes overlapping cron ticks safe.

The minute tick that lands on 00:00 also reloads the day's schedules into
/etc/cron.d/sty-schedule first. Flags:
  --update-schedules      reload today's schedules into /etc/cron.d/sty-schedule now, then exit.
  --start-schedule ID     create the Command for a schedule firing and print its id (used by the
                          /etc/cron.d/sty-schedule lines, which then run the command themselves).
  --report --command-id N --exit-code C
                          report a run's result, log read from stdin. Called by the software
                          itself, which gets N from STY_COMMAND_ID and this checkout from
                          STY_MANAGER in its environment (see README)."""

import argparse
import datetime
import os
import sys

from src.api_client import get_next_command, get_schedules, post_result, trigger_schedule
from src.config import load_config
from src.device_identity import get_board_id
from src.executor import run_command
from src.installer import run_install
from src.scheduler import render, write_cron_file


def update_schedules(config, board_id: str) -> str:
    today = datetime.date.today().isoformat()
    schedules = get_schedules(config.base_url, board_id, today)
    write_cron_file(render(schedules, config.base_dir))
    return f"Wrote {len(schedules)} schedule(s) for {today} to /etc/cron.d/sty-schedule"


def start_schedule(config, board_id: str, schedule_id: int) -> None:
    """Prints the new command id on stdout for the cron line to capture. Exits 1 only when the
    schedule was deleted (so the cron line skips the run); if the backend can't be reached it
    prints nothing and the command still runs, just unreported."""
    try:
        triggered = trigger_schedule(config.base_url, board_id, schedule_id)
    except Exception as e:
        print(f"[storeyes-agent] could not start schedule {schedule_id}, running unreported: {e}", file=sys.stderr)
        return
    if triggered is None:
        print(f"[storeyes-agent] schedule {schedule_id} no longer exists, skipping", file=sys.stderr)
        sys.exit(1)
    print(triggered["commandId"])


def report(config, board_id: str, command_id: int, exit_code: int) -> None:
    log = sys.stdin.read() if not sys.stdin.isatty() else ""
    post_result(config.base_url, board_id, command_id, exit_code, log[-config.max_log_chars:], reporter="SOFTWARE")


def poll(config, board_id: str) -> None:
    command = get_next_command(config.base_url, board_id)
    if command is None:
        return

    if command.get("type") == "INSTALL":
        exit_code, log = run_install(command["githubUrl"], command["code"], config.base_dir, config.timeout_seconds)
    elif command.get("type") == "SYNC_SCHEDULES":
        try:
            exit_code, log = 0, update_schedules(config, board_id)
        except Exception as e:
            exit_code, log = 1, f"Failed to update schedules: {e}"
    else:
        # Lets a self-reporting software send its own log/exit code (main.py --report); if it
        # doesn't, the report below stands — the backend ignores it if the software already did.
        sty_env = {"STY_COMMAND_ID": str(command["id"]), "STY_MANAGER": os.path.dirname(os.path.abspath(__file__))}
        exit_code, log = run_command(command["cmd"], config.timeout_seconds, config.base_dir, sty_env)

    post_result(config.base_url, board_id, command["id"], exit_code, log[: config.max_log_chars])


def main() -> None:
    parser = argparse.ArgumentParser(description="Storeyes device agent")
    parser.add_argument("--update-schedules", action="store_true",
                        help="reload today's schedules into /etc/cron.d/sty-schedule now")
    parser.add_argument("--start-schedule", type=int, metavar="ID",
                        help="create the Command for a schedule firing and print its id")
    parser.add_argument("--report", action="store_true",
                        help="report a run's result (log on stdin); needs --command-id and --exit-code")
    parser.add_argument("--command-id", type=int)
    parser.add_argument("--exit-code", type=int)
    args = parser.parse_args()
    if args.report and (args.command_id is None or args.exit_code is None):
        parser.error("--report needs --command-id and --exit-code")

    config = load_config()
    board_id = get_board_id()

    if args.update_schedules:
        print(f"[storeyes-agent] {update_schedules(config, board_id)}")
        return
    if args.start_schedule is not None:
        start_schedule(config, board_id, args.start_schedule)
        return
    if args.report:
        report(config, board_id, args.command_id, args.exit_code)
        return

    now = datetime.datetime.now()
    if now.hour == 0 and now.minute == 0:
        try:
            print(f"[storeyes-agent] {update_schedules(config, board_id)}")
        except Exception as e:
            # Don't let a failed reload skip this minute's poll.
            print(f"[storeyes-agent] midnight schedule update failed: {e}", file=sys.stderr)

    poll(config, board_id)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # A cron-run agent must never fail loudly (cron mails stderr on non-zero exit) — log locally
        # and try again next minute.
        print(f"[storeyes-agent] error: {e}", file=sys.stderr)
        sys.exit(0)
