from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

from fastapi.testclient import TestClient


def test_websocket_broadcasts_project_mutation(tmp_path: Path, monkeypatch) -> None:
    app_module = load_server_app(tmp_path, monkeypatch)

    with TestClient(app_module.create_app()) as client:
        with client.websocket_connect("/api/v1/ws") as websocket:
            connected = websocket.receive_json()
            assert connected["type"] == "connected"
            assert connected["version"] == 0

            response = client.post("/api/v1/projects", json={"key": "alpha-lab", "title": "Alpha Lab"})
            assert response.status_code == 200, response.text

            event = websocket.receive_json()
            assert event["type"] == "project.created"
            assert event["version"] == 1
            assert event["payload"]["project_key"] == "alpha-lab"


def load_server_app(tmp_path: Path, monkeypatch) -> ModuleType:
    monkeypatch.setenv("BLACKBOX_DATABASE_URL", f"sqlite:///{tmp_path / 'blackbox.db'}")
    monkeypatch.setenv("BLACKBOX_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.delenv("BLACKBOX_AUTH_ENABLED", raising=False)
    monkeypatch.delenv("BLACKBOX_API_TOKEN", raising=False)
    monkeypatch.delenv("BLACKBOX_TOKEN", raising=False)

    settings_module = importlib.import_module("blackbox_server.settings")
    db_module = importlib.import_module("blackbox_server.db")
    models_module = importlib.import_module("blackbox_server.models")
    realtime_module = importlib.import_module("blackbox_server.realtime")
    main_module = importlib.import_module("blackbox_server.main")

    importlib.reload(settings_module)
    importlib.reload(db_module)
    importlib.reload(models_module)
    importlib.reload(realtime_module)
    return importlib.reload(main_module)
