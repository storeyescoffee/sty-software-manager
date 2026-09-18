"""Loads config.conf (INI format) next to this package."""

import configparser
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.conf")


class AgentConfig:
    def __init__(self, base_url: str, timeout_seconds: int, max_log_chars: int):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_log_chars = max_log_chars


def load_config(path: str = CONFIG_PATH) -> AgentConfig:
    parser = configparser.ConfigParser()
    if not parser.read(path):
        raise FileNotFoundError(f"Missing config file: {path}")

    section = parser["agent"]
    return AgentConfig(
        base_url=section.get("base_url", "https://panel.storeyes.io/api"),
        timeout_seconds=section.getint("timeout_seconds", fallback=600),
        max_log_chars=section.getint("max_log_chars", fallback=20000),
    )
