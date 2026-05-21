from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

from fastapi.testclient import TestClient


def test_api_token_authentication(tmp_path: Path, monkeypatch) -> None:
    app_module = load_server_app(
        tmp_path,
        monkeypatch,
        auth_enabled=True,
        api_token="secret-token",
    )

    with TestClient(app_module.create_app()) as client:
        health = client.get("/healthz")
        assert health.status_code == 200
        assert health.json()["ok"]

        status = client.get("/api/v1/auth/status")
        assert status.status_code == 200
        assert status.json()["data"] == {"auth_enabled": True, "token_configured": True}

        db_status_missing_token = client.get("/api/v1/system/db-status")
        assert db_status_missing_token.status_code == 401
        assert db_status_missing_token.json()["error"]["code"] == "AUTH_ERROR"

        runtime_missing_token = client.get("/api/v1/system/runtime-status")
        assert runtime_missing_token.status_code == 401
        assert runtime_missing_token.json()["error"]["code"] == "AUTH_ERROR"

        missing = client.get("/api/v1/projects")
        assert missing.status_code == 401
        assert missing.json()["error"]["code"] == "AUTH_ERROR"

        wrong = client.get("/api/v1/projects", headers={"Authorization": "Bearer wrong"})
        assert wrong.status_code == 401
        assert wrong.json()["error"]["code"] == "AUTH_ERROR"

        bearer = client.get("/api/v1/projects", headers={"Authorization": "Bearer secret-token"})
        assert bearer.status_code == 200
        assert bearer.json()["data"] == []

        db_status = client.get("/api/v1/system/db-status", headers={"Authorization": "Bearer secret-token"})
        assert db_status.status_code == 200
        assert db_status.json()["data"]["needs_migration"] is False

        runtime_status = client.get("/api/v1/system/runtime-status", headers={"Authorization": "Bearer secret-token"})
        assert runtime_status.status_code == 200
        assert runtime_status.json()["data"]["worker_backend"] == "InlineWorker"
        assert runtime_status.json()["data"]["artifact_storage"] == "local"

        custom_header = client.get("/api/v1/projects", headers={"X-Blackbox-Token": "secret-token"})
        assert custom_header.status_code == 200
        assert custom_header.json()["data"] == []

        api_key = client.get("/api/v1/projects", headers={"X-API-Key": "secret-token"})
        assert api_key.status_code == 200
        assert api_key.json()["data"] == []

        query_token = client.get("/api/v1/projects?token=secret-token")
        assert query_token.status_code == 200
        assert query_token.json()["data"] == []


def test_auth_enabled_requires_configured_token(tmp_path: Path, monkeypatch) -> None:
    app_module = load_server_app(
        tmp_path,
        monkeypatch,
        auth_enabled=True,
        api_token=None,
    )

    with TestClient(app_module.create_app()) as client:
        status = client.get("/api/v1/auth/status")
        assert status.status_code == 200
        assert status.json()["data"] == {"auth_enabled": True, "token_configured": False}

        response = client.get("/api/v1/projects")
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "AUTH_ERROR"


def load_server_app(
    tmp_path: Path,
    monkeypatch,
    *,
    auth_enabled: bool,
    api_token: str | None,
) -> ModuleType:
    monkeypatch.setenv("BLACKBOX_DATABASE_URL", f"sqlite:///{tmp_path / 'blackbox.db'}")
    monkeypatch.setenv("BLACKBOX_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("BLACKBOX_AUTH_ENABLED", "1" if auth_enabled else "0")
    if api_token is None:
        monkeypatch.delenv("BLACKBOX_API_TOKEN", raising=False)
        monkeypatch.delenv("BLACKBOX_TOKEN", raising=False)
    else:
        monkeypatch.setenv("BLACKBOX_API_TOKEN", api_token)

    settings_module = importlib.import_module("blackbox_server.settings")
    db_module = importlib.import_module("blackbox_server.db")
    models_module = importlib.import_module("blackbox_server.models")
    main_module = importlib.import_module("blackbox_server.main")

    importlib.reload(settings_module)
    importlib.reload(db_module)
    importlib.reload(models_module)
    return importlib.reload(main_module)
