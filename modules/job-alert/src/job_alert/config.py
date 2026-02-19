from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Mapping, Sequence

from pydantic import BaseModel, Field, ValidationError, field_validator

MODULE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SENT_DB_PATH = MODULE_ROOT / "data" / "sent_posts.sqlite"
DEFAULT_HOJUBADA_STATE_PATH = MODULE_ROOT / "data" / "hojubada_storage_state.json"

RUN_REQUIRED_ENVS = (
    "SLACK_WEBHOOK_URL",
    "WOORIMEL_ID",
    "WOORIMEL_PW",
    "MELBSKY_ID",
    "MELBSKY_PW",
    "HOJUBADA_ID",
    "HOJUBADA_PW",
)


class Settings(BaseModel):
    slack_webhook_url: str = ""
    woorimel_id: str = ""
    woorimel_pw: str = ""
    melbsky_id: str = ""
    melbsky_pw: str = ""
    hojubada_id: str = ""
    hojubada_pw: str = ""
    hojubada_storage_state_b64: str = ""
    keywords_csv: str | None = None
    tz: str = "Australia/Melbourne"
    request_timeout_seconds: float = 20.0
    user_agent: str = "job-alert-bot/0.1"
    site_retry_attempts: int = Field(default=2, ge=1)
    site_retry_delay_seconds: float = Field(default=1.0, ge=0.0)
    error_alert_threshold: int = Field(default=2, ge=1)
    sent_db_path: Path = Field(default=DEFAULT_SENT_DB_PATH)
    hojubada_storage_path: Path = Field(default=DEFAULT_HOJUBADA_STATE_PATH)

    @field_validator("slack_webhook_url")
    @classmethod
    def _validate_webhook_url(cls, value: str) -> str:
        if value and not value.startswith("https://"):
            raise ValueError("SLACK_WEBHOOK_URL must use https://")
        return value


def _env_value(environ: Mapping[str, str], key: str) -> str:
    return environ.get(key, "").strip()


def missing_envs(required: Sequence[str], environ: Mapping[str, str] | None = None) -> list[str]:
    source = os.environ if environ is None else environ
    return [key for key in required if not _env_value(source, key)]


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    source = os.environ if environ is None else environ
    payload = {
        "slack_webhook_url": _env_value(source, "SLACK_WEBHOOK_URL"),
        "woorimel_id": _env_value(source, "WOORIMEL_ID"),
        "woorimel_pw": _env_value(source, "WOORIMEL_PW"),
        "melbsky_id": _env_value(source, "MELBSKY_ID"),
        "melbsky_pw": _env_value(source, "MELBSKY_PW"),
        "hojubada_id": _env_value(source, "HOJUBADA_ID"),
        "hojubada_pw": _env_value(source, "HOJUBADA_PW"),
        "hojubada_storage_state_b64": _env_value(source, "HOJUBADA_STORAGE_STATE_B64"),
        "keywords_csv": _env_value(source, "KEYWORDS_CSV") or None,
        "tz": _env_value(source, "TZ") or "Australia/Melbourne",
        "request_timeout_seconds": float(_env_value(source, "REQUEST_TIMEOUT_SECONDS") or "20"),
        "user_agent": _env_value(source, "USER_AGENT") or "job-alert-bot/0.1",
        "site_retry_attempts": int(_env_value(source, "SITE_RETRY_ATTEMPTS") or "2"),
        "site_retry_delay_seconds": float(_env_value(source, "SITE_RETRY_DELAY_SECONDS") or "1"),
        "error_alert_threshold": int(_env_value(source, "ERROR_ALERT_THRESHOLD") or "2"),
        "sent_db_path": Path(_env_value(source, "SENT_DB_PATH") or DEFAULT_SENT_DB_PATH),
        "hojubada_storage_path": Path(
            _env_value(source, "HOJUBADA_STORAGE_PATH") or DEFAULT_HOJUBADA_STATE_PATH
        ),
    }
    try:
        return Settings(**payload)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc


def assert_required_envs(required: Sequence[str], environ: Mapping[str, str] | None = None) -> None:
    missing = missing_envs(required, environ)
    if missing:
        keys = ", ".join(missing)
        raise ValueError(f"Missing required environment variables: {keys}")


def ensure_hojubada_storage_state(settings: Settings) -> Path | None:
    encoded = settings.hojubada_storage_state_b64.strip()
    if encoded:
        decoded = base64.b64decode(encoded, validate=True)
        settings.hojubada_storage_path.parent.mkdir(parents=True, exist_ok=True)
        settings.hojubada_storage_path.write_bytes(decoded)
        return settings.hojubada_storage_path
    if settings.hojubada_storage_path.exists():
        return settings.hojubada_storage_path
    return None


def mask_secret(value: str, visible_prefix: int = 3, visible_suffix: int = 2) -> str:
    if not value:
        return ""
    if len(value) <= visible_prefix + visible_suffix:
        return "*" * len(value)
    hidden = "*" * (len(value) - visible_prefix - visible_suffix)
    return f"{value[:visible_prefix]}{hidden}{value[-visible_suffix:]}"
