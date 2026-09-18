"""Derives this device's boardId from the Raspberry Pi's own hardware serial number, so no manual
per-device configuration is needed — the admin just enters the same serial as the Device's boardId
in the admin panel."""

CPUINFO_PATH = "/proc/cpuinfo"


def get_board_id() -> str:
    with open(CPUINFO_PATH, "r") as f:
        for line in f:
            if line.startswith("Serial"):
                return line.split(":")[1].strip()
    raise RuntimeError(f"Could not find a 'Serial' line in {CPUINFO_PATH}")
