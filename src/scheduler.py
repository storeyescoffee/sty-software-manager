"""Renders the day's schedules into /etc/cron.d/sty-schedule. Cron itself runs each schedule's
command: the line first asks the manager for a command id (`main.py --start-schedule <id>`, which
creates the CRON/SCHEDULED Command on the backend), then runs the command with STY_COMMAND_ID /
STY_MANAGER in its environment so the software can report its own log and exit code
(`main.py --report`). The file is rewritten wholesale on every update, so it always reflects
exactly one day."""

import datetime
import os
import tempfile
from typing import List

CRON_FILE = "/etc/cron.d/sty-schedule"
LOG_FILE = "/var/log/storeyes-agent.log"
INSTALL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(INSTALL_DIR, "main.py")


def posix_single_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def render_line(schedule: dict) -> str:
    if schedule.get("type") == "ONE_TIME":
        # runAt is "YYYY-MM-DDTHH:MM[:SS]". Pin day + month so a file that somehow isn't
        # rewritten can't re-fire it on a later day.
        run_at = datetime.datetime.fromisoformat(schedule["runAt"])
        when = f"{run_at.minute} {run_at.hour} {run_at.day} {run_at.month} *"
    else:
        # CRON: the backend already validated it as 5 plain cron fields.
        when = schedule["cronExpression"]

    # --start-schedule exits non-zero only when the schedule was deleted, so `&&` skips the run;
    # if the backend is unreachable it prints nothing and the command still runs, unreported.
    command = (
        f"ID=$(/usr/bin/python3 {MAIN_PY} --start-schedule {schedule['id']} 2>>{LOG_FILE})"
        f" && STY_COMMAND_ID=\"$ID\" STY_MANAGER={INSTALL_DIR}"
        f" /bin/sh -c {posix_single_quote(schedule['cmd'])} >> {LOG_FILE} 2>&1"
    )
    # cron turns an unescaped % into a newline.
    return f"{when} root {command.replace('%', chr(92) + '%')}"


def render(schedules: List[dict], base_dir: str) -> str:
    lines = [
        "# Managed by sty-software-manager (--update-schedules) - rewritten at midnight, do not edit.",
        f"HOME={base_dir}",
    ]
    lines.extend(render_line(schedule) for schedule in schedules if schedule.get("cmd"))
    return "\n".join(lines) + "\n"


def write_cron_file(content: str, path: str = CRON_FILE) -> None:
    """Atomic replace (cron may read the file at any moment). cron.d files must be 0644."""
    directory = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".sty-schedule.")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
