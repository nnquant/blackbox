from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from blackbox.offline import OfflineSpool


class SyncError(Exception):
    pass


class SyncClient:
    def __init__(self, endpoint: str, token: str | None = None, timeout: float = 30.0):
        self.endpoint = endpoint.rstrip("/")
        self.token = token
        self.timeout = timeout

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = kwargs.pop("headers", {})
        if self.token:
            headers = {**headers, "Authorization": f"Bearer {self.token}"}
        with httpx.Client(timeout=self.timeout) as client:
            response = client.request(method, f"{self.endpoint}{path}", headers=headers, **kwargs)
        try:
            payload = response.json()
        except Exception as exc:
            raise SyncError(f"server returned non-JSON response: {response.text}") from exc
        if not payload.get("ok"):
            error = payload.get("error") or {}
            raise SyncError(f"{error.get('code', response.status_code)}: {error.get('message', response.text)}")
        return payload["data"]


def sync_spool(endpoint: str, spool_dir: str | Path, include_synced: bool = False, token: str | None = None) -> dict[str, Any]:
    spool = OfflineSpool(spool_dir)
    client = SyncClient(endpoint, token=token)
    manifests = spool.list_manifests()
    synced: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    for manifest in manifests:
        local_run_id = manifest["local_run_id"]
        if manifest.get("synced_at") and not include_synced:
            skipped.append({"local_run_id": local_run_id, "reason": "already_synced"})
            continue
        try:
            remote_run = sync_manifest(client, manifest)
            spool.mark_synced(local_run_id, remote_run["id"])
            synced.append({"local_run_id": local_run_id, "remote_run_id": remote_run["id"]})
        except Exception as exc:
            failed.append({"local_run_id": local_run_id, "error": str(exc)})

    return {
        "spool_dir": str(Path(spool_dir).expanduser().resolve()),
        "synced": synced,
        "skipped": skipped,
        "failed": failed,
    }


def sync_manifest(client: SyncClient, manifest: dict[str, Any]) -> dict[str, Any]:
    run_create = manifest["run_create"]
    project_key = run_create["project_key"]
    research_key = run_create["research_key"]
    branch_key = run_create["branch_key"]

    project = client.request("POST", "/api/v1/projects", json={"key": project_key, "title": project_key})
    research = client.request(
        "POST",
        "/api/v1/researches",
        json={"project_key": project["key"], "key": research_key, "title": research_key},
    )
    branch = client.request(
        "POST",
        "/api/v1/branches",
        json={"research_id": research["id"], "key": branch_key, "title": branch_key},
    )
    headers = {}
    if run_create.get("idempotency_key"):
        headers["Idempotency-Key"] = run_create["idempotency_key"]
    run = client.request(
        "POST",
        "/api/v1/runs",
        headers=headers,
        json={
            "project_key": project_key,
            "research_key": research_key,
            "branch_key": branch_key,
            "name": run_create["name"],
            "title": run_create.get("title"),
            "config": run_create.get("config", {}),
            "context": run_create.get("context", {}),
            "tags": run_create.get("tags", []),
            "created_by_type": run_create.get("created_by_type", "human"),
            "created_by_id": run_create.get("created_by_id"),
        },
    )
    run_id = run["id"]

    sync_snapshots(client, run_id, manifest.get("snapshots", {}))
    for item in manifest.get("events", []):
        client.request("POST", f"/api/v1/runs/{run_id}/events", json=item["payload"])
    for item in manifest.get("metrics", []):
        client.request("POST", f"/api/v1/runs/{run_id}/metrics", json=item["payload"])
    for item in manifest.get("series", []):
        client.request("POST", f"/api/v1/runs/{run_id}/series", json=item["payload"])
    for item in manifest.get("notes", []):
        client.request("POST", f"/api/v1/runs/{run_id}/notes", json=item["payload"])
    for item in manifest.get("artifacts", []):
        sync_artifact(client, run_id, item)
    for item in manifest.get("sweeps", []):
        sweep_id = sync_sweep(client, item, branch)
        client.request(
            "POST",
            f"/api/v1/sweeps/{sweep_id}/runs",
            json={"run_id": run_id, "coord": item.get("coord") or {}, "rank": item.get("rank")},
        )

    terminal = manifest.get("terminal")
    if terminal:
        if terminal["status"] == "completed":
            client.request("POST", f"/api/v1/runs/{run_id}/finish")
        elif terminal["status"] == "failed":
            client.request("POST", f"/api/v1/runs/{run_id}/fail", json=terminal.get("error") or {})
        elif terminal["status"] == "cancelled":
            client.request("POST", f"/api/v1/runs/{run_id}/cancel", json=terminal.get("reason") or {})

    return run


def sync_sweep(client: SyncClient, item: dict[str, Any], branch: dict[str, Any]) -> str:
    sweep = item.get("sweep")
    if not sweep:
        return item["sweep_id"]
    branch_id = sweep.get("branch_id") or branch["id"]
    if branch_id in {branch.get("id"), branch.get("key")}:
        branch_id = branch["id"]
    remote = client.request(
        "POST",
        "/api/v1/sweeps",
        json={
            "branch_id": branch_id,
            "name": sweep["name"],
            "search_space": sweep.get("search_space") or sweep.get("search_space_json") or {},
            "objective": sweep.get("objective") or sweep.get("objective_json") or {},
            "status": sweep.get("status", "active"),
        },
    )
    return remote["id"]


def sync_snapshots(client: SyncClient, run_id: str, snapshots: dict[str, list[dict[str, Any]]]) -> None:
    for kind in ("code", "data", "env"):
        for item in snapshots.get(kind, []):
            client.request("POST", f"/api/v1/runs/{run_id}/snapshots/{kind}", json=item["payload"])


def sync_artifact(client: SyncClient, run_id: str, item: dict[str, Any]) -> None:
    if uri := item.get("uri"):
        client.request(
            "POST",
            f"/api/v1/runs/{run_id}/artifacts/register-external",
            json={
                "name": item["name"],
                "kind": item.get("kind", "other"),
                "uri": uri,
                "metadata": item.get("metadata", {}),
            },
        )
        return

    path = Path(item["path"])
    if not path.exists():
        raise SyncError(f"artifact file not found: {path}")
    client.request(
        "POST",
        f"/api/v1/runs/{run_id}/artifacts/upload",
        params={
            "name": item["name"],
            "kind": item.get("kind", "other"),
            "filename": item.get("filename") or path.name,
            "metadata": json.dumps(item.get("metadata", {}), ensure_ascii=False),
        },
        content=path.read_bytes(),
    )
