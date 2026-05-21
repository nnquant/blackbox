from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace

from fastapi.testclient import TestClient


def test_local_storage_put_bytes(tmp_path: Path) -> None:
    from blackbox_server.storage import LocalFileStorage

    stored = LocalFileStorage(tmp_path).put_bytes(
        run_id="run_1",
        artifact_id="artifact_1",
        filename="../report.html",
        content=b"<html><title>ok</title></html>",
    )

    assert stored.filename == "report.html"
    assert stored.path is not None
    assert stored.path.exists()
    assert stored.storage_uri.startswith("file:///")
    assert stored.size_bytes == len(b"<html><title>ok</title></html>")
    content = LocalFileStorage(tmp_path).content_target(stored.storage_uri)
    assert content.path == stored.path.resolve()
    assert content.redirect_url is None


def test_local_init_upload_urlencodes_query_params(tmp_path: Path) -> None:
    from urllib.parse import parse_qs, urlparse

    from blackbox_server.storage import LocalFileStorage

    target = LocalFileStorage(tmp_path).init_upload(
        run_id="run_1",
        artifact_id="artifact_1",
        name="post cost & report",
        kind="report_html",
        filename="报告 v1.html",
        metadata={},
    )

    parsed = urlparse(target.upload_path or "")
    query = parse_qs(parsed.query)
    assert parsed.path == "/api/v1/runs/run_1/artifacts/upload"
    assert query == {
        "artifact_id": ["artifact_1"],
        "name": ["post cost & report"],
        "kind": ["report_html"],
        "filename": ["报告 v1.html"],
    }


def test_s3_storage_put_bytes_and_presigned_url(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []

    class FakeS3Client:
        def put_object(self, **kwargs):
            calls.append(("put_object", kwargs))

        def generate_presigned_url(self, operation, Params, ExpiresIn, HttpMethod):
            calls.append(
                (
                    "generate_presigned_url",
                    {"operation": operation, "Params": Params, "ExpiresIn": ExpiresIn, "HttpMethod": HttpMethod},
                )
            )
            return f"http://minio/{operation}-url"

    def fake_client(service, **kwargs):
        calls.append(("client", {"service": service, **kwargs}))
        return FakeS3Client()

    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=fake_client))

    from blackbox_server.settings import Settings
    from blackbox_server.storage import S3ObjectStorage

    settings = Settings(
        database_url="sqlite:///:memory:",
        data_root=Path("."),
        artifact_root=Path("."),
        artifact_storage="s3",
        s3_endpoint_url="http://127.0.0.1:9000",
        s3_bucket="blackbox",
        s3_access_key_id="access",
        s3_secret_access_key="secret",
        s3_prefix="experiments",
    )
    storage = S3ObjectStorage(settings)

    stored = storage.put_bytes(run_id="run_1", artifact_id="artifact_1", filename="report.html", content=b"ok")
    assert stored.storage_uri == "s3://blackbox/experiments/run/run_1/artifacts/artifact_1/report.html"
    assert stored.path is None
    assert calls[1][0] == "put_object"
    assert calls[1][1]["Bucket"] == "blackbox"
    assert calls[1][1]["ContentType"] == "text/html"

    target = storage.init_upload(
        run_id="run_1",
        artifact_id="artifact_2",
        name="report",
        kind="report_html",
        filename="report.html",
        metadata={"source": "test"},
    )
    assert target.method == "PUT"
    assert target.upload_url == "http://minio/put_object-url"
    assert target.upload_path is None
    assert target.storage_uri == "s3://blackbox/experiments/run/run_1/artifacts/artifact_2/report.html"
    content = storage.content_target(
        "s3://blackbox/experiments/run/run_1/artifacts/artifact_2/report.html",
        mime_type="text/html",
    )
    assert content.path is None
    assert content.redirect_url == "http://minio/get_object-url"
    assert calls[-1][1]["operation"] == "get_object"
    assert calls[-1][1]["Params"]["ResponseContentType"] == "text/html"


def test_api_init_upload_returns_s3_presigned_url(tmp_path: Path, monkeypatch) -> None:
    install_fake_boto3(monkeypatch)
    app_module = load_server_app_with_s3(tmp_path, monkeypatch)

    with TestClient(app_module.create_app()) as client:
        project = unwrap(client.post("/api/v1/projects", json={"key": "alpha-lab", "title": "Alpha Lab"}))
        research = unwrap(
            client.post(
                "/api/v1/researches",
                json={"project_key": project["key"], "key": "reversal", "title": "Reversal"},
            )
        )
        branch = unwrap(client.post("/api/v1/branches", json={"research_id": research["id"], "key": "baseline", "title": "Baseline"}))
        run = unwrap(client.post("/api/v1/runs", json={"branch_id": branch["id"], "name": "run-1"}))

        target = unwrap(
            client.post(
                f"/api/v1/runs/{run['id']}/artifacts/init-upload",
                json={"name": "report", "kind": "report_html", "filename": "report.html"},
            )
        )
        artifact = unwrap(
            client.post(
                f"/api/v1/runs/{run['id']}/artifacts/complete-upload",
                json={
                    "artifact_id": target["artifact_id"],
                    "name": "report",
                    "kind": "report_html",
                    "uri": target["storage_uri"],
                    "filename": "report.html",
                    "mime_type": "text/html",
                    "size_bytes": 2,
                    "sha256": "ok",
                },
            )
        )
        content = client.get(f"/api/v1/artifacts/{artifact['id']}/content", follow_redirects=False)

    assert target["method"] == "PUT"
    assert target["upload_url"] == "http://minio/put_object-url"
    assert target["upload_path"] is None
    assert target["storage_uri"].startswith("s3://blackbox/test-prefix/run/")
    assert content.status_code in {302, 307}
    assert content.headers["location"] == "http://minio/get_object-url"


def install_fake_boto3(monkeypatch) -> list[tuple[str, dict]]:
    calls: list[tuple[str, dict]] = []

    class FakeS3Client:
        def put_object(self, **kwargs):
            calls.append(("put_object", kwargs))

        def generate_presigned_url(self, operation, Params, ExpiresIn, HttpMethod):
            calls.append(
                (
                    "generate_presigned_url",
                    {"operation": operation, "Params": Params, "ExpiresIn": ExpiresIn, "HttpMethod": HttpMethod},
                )
            )
            return f"http://minio/{operation}-url"

    def fake_client(service, **kwargs):
        calls.append(("client", {"service": service, **kwargs}))
        return FakeS3Client()

    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=fake_client))
    return calls


def load_server_app_with_s3(tmp_path: Path, monkeypatch) -> ModuleType:
    import importlib

    monkeypatch.setenv("BLACKBOX_DATABASE_URL", f"sqlite:///{tmp_path / 'blackbox.db'}")
    monkeypatch.setenv("BLACKBOX_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("BLACKBOX_ARTIFACT_STORAGE", "s3")
    monkeypatch.setenv("BLACKBOX_S3_BUCKET", "blackbox")
    monkeypatch.setenv("BLACKBOX_S3_ENDPOINT_URL", "http://127.0.0.1:9000")
    monkeypatch.setenv("BLACKBOX_S3_PREFIX", "test-prefix")
    monkeypatch.delenv("BLACKBOX_AUTH_ENABLED", raising=False)
    monkeypatch.delenv("BLACKBOX_API_TOKEN", raising=False)
    monkeypatch.delenv("BLACKBOX_TOKEN", raising=False)

    settings_module = importlib.import_module("blackbox_server.settings")
    db_module = importlib.import_module("blackbox_server.db")
    models_module = importlib.import_module("blackbox_server.models")
    realtime_module = importlib.import_module("blackbox_server.realtime")
    storage_module = importlib.import_module("blackbox_server.storage")
    main_module = importlib.import_module("blackbox_server.main")

    importlib.reload(settings_module)
    importlib.reload(db_module)
    importlib.reload(models_module)
    importlib.reload(realtime_module)
    importlib.reload(storage_module)
    return importlib.reload(main_module)


def unwrap(response) -> dict:
    assert response.status_code < 400, response.text
    body = response.json()
    assert body["ok"], body
    return body["data"]
