"""Talks to the backend's /device-gw/commands endpoints using only the stdlib (no pip install
needed on a fresh Pi). Auth reuses the existing device-gw header convention: X-DEVICE-ID alone
(no API key for now) — matches a Device row with apiKey = null."""

import json
import urllib.request
from typing import Optional


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


def post_result(base_url: str, board_id: str, command_id: int, exit_code: int, log: str) -> None:
    body = json.dumps({"exitCode": exit_code, "log": log}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/device-gw/commands/{command_id}/result",
        data=body,
        headers={"X-DEVICE-ID": board_id, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        resp.read()
