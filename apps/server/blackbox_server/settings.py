from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str
    data_root: Path
    artifact_root: Path
    artifact_storage: str = "local"
    s3_endpoint_url: str | None = None
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_prefix: str = "blackbox"
    auth_enabled: bool = False
    api_token: str | None = None
    max_metric_payload_bytes: int = 65536


def get_settings() -> Settings:
    data_root = Path(os.getenv("BLACKBOX_DATA_DIR", "~/.blackbox")).expanduser().resolve()
    database_url = os.getenv("BLACKBOX_DATABASE_URL", f"sqlite:///{data_root / 'blackbox.db'}")
    artifact_root = Path(os.getenv("BLACKBOX_ARTIFACT_ROOT", data_root / "artifacts")).expanduser().resolve()
    artifact_storage = os.getenv("BLACKBOX_ARTIFACT_STORAGE", "local").lower()
    auth_enabled = os.getenv("BLACKBOX_AUTH_ENABLED", "0").lower() in {"1", "true", "yes"}
    api_token = os.getenv("BLACKBOX_API_TOKEN") or os.getenv("BLACKBOX_TOKEN")
    return Settings(
        database_url=database_url,
        data_root=data_root,
        artifact_root=artifact_root,
        artifact_storage=artifact_storage,
        s3_endpoint_url=os.getenv("BLACKBOX_S3_ENDPOINT_URL"),
        s3_bucket=os.getenv("BLACKBOX_S3_BUCKET"),
        s3_region=os.getenv("BLACKBOX_S3_REGION"),
        s3_access_key_id=os.getenv("BLACKBOX_S3_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID"),
        s3_secret_access_key=os.getenv("BLACKBOX_S3_SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY"),
        s3_prefix=os.getenv("BLACKBOX_S3_PREFIX", "blackbox").strip("/"),
        auth_enabled=auth_enabled,
        api_token=api_token,
        max_metric_payload_bytes=parse_int_env("BLACKBOX_MAX_METRIC_PAYLOAD_BYTES", 65536),
    )


def parse_int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default
