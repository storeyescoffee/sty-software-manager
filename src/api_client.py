"""Talks to the backend's /device-gw/commands endpoints using only the stdlib (no pip install
needed on a fresh Pi). Auth reuses the existing device-gw header convention: X-DEVICE-ID alone
(no API key for now) — matches a Device row with apiKey = null."""

import json
import urllib.error
import urllib.request
from typing import List, Optional


def get_next_command(base_url: str, board_id: str) -> Optional[dict]:
    """Returns the claimed command's payload ({id, type, cmd, githubUrl, code}) if one was
    claimed, or None if there's nothing pending. For type=="INSTALL", githubUrl/code are set and
    the agent builds the install sequence itself; for type=="RUN", cmd is the command to run as-is."""
    req = urllib.request.Request(
        f"{base_url}/device-gw/commands/next",
        headers={"X-DEVICE-ID": board_id, "Accept": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        if resp.status == 204:
            return None
        return json.loads(resp.read().decode("utf-8"))


def get_schedules(base_url: str, board_id: str, date: str) -> List[dict]:
    """Schedules due on `date` (the device's local YYYY-MM-DD): [{id, time, frequency, date, cmd}]."""
    req = urllib.request.Request(
        f"{base_url}/device-gw/schedules?date={date}",
        headers={"X-DEVICE-ID": board_id, "Accept": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def trigger_schedule(base_url: str, board_id: str, schedule_id: int) -> Optional[dict]:
    """Creates the Command for a schedule firing and returns {commandId, cmd}, or None if the
    schedule no longer exists (deleted since the cron file was written)."""
    req = urllib.request.Request(
        f"{base_url}/device-gw/schedules/{schedule_id}/trigger",
        data=b"",
        headers={"X-DEVICE-ID": board_id, "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def post_result(
    base_url: str, board_id: str, command_id: int, exit_code: int, log: str, reporter: str = "AGENT"
) -> None:
    """reporter="SOFTWARE" (a self-report via `main.py --report`) always overwrites; the agent's
    own "AGENT" report is ignored by the backend once the command already has a result."""
    body = json.dumps({"exitCode": exit_code, "log": log, "reporter": reporter}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/device-gw/commands/{command_id}/result",
        data=body,
        headers={"X-DEVICE-ID": board_id, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        resp.read()
