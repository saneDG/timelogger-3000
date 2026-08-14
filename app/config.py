from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import os
import sys


def _list_setting(name: str) -> tuple:
    return tuple(value.strip() for value in os.getenv(name, "").split(";") if value.strip())


def _default_database_path() -> Path:
    if os.getenv("TIMELOGGER_DESKTOP") == "1" or getattr(sys, "frozen", False):
        return Path.home() / "Library" / "Application Support" / "TimeLogger 3000" / "timelogger.db"
    return Path("data/timelogger.db")


@dataclass(frozen=True)
class Settings:
    activitywatch_host: str = os.getenv("AW_HOST", "127.0.0.1")
    activitywatch_port: int = int(os.getenv("AW_PORT", "5600"))
    activitywatch_hostname: Optional[str] = os.getenv("AW_HOSTNAME")
    lm_studio_url: str = os.getenv("LM_STUDIO_URL", "http://127.0.0.1:1234/v1")
    lm_studio_model: Optional[str] = os.getenv("LM_STUDIO_MODEL")
    git_directory: Optional[str] = os.getenv("TIMELOGGER_GIT_DIRECTORY")
    title_redaction_patterns: tuple = _list_setting("TIMELOGGER_TITLE_REDACT_PATTERNS")
    redacted_domains: tuple = _list_setting("TIMELOGGER_REDACT_DOMAINS")
    database_path: Path = Path(os.getenv("TIMELOGGER_DB", str(_default_database_path())))


settings = Settings()
