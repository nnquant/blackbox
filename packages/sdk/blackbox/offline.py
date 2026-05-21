from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from blackbox_common.ids import new_id


class OfflineSpool:
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or "~/.blackbox").expanduser().resolve()
        self.queue_dir = self.root / "queue"
        self.artifact_dir = self.root / "artifacts"
        self.manifests_dir = self.root / "manifests"
        self.sweeps_dir = self.root / "sweeps"
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        self.sweeps_dir.mkdir(parents=True, exist_ok=True)

    def start_run(
        self,
        *,
        project: str,
        research: str,
        branch: str,
        name: str,
        title: str | None,
        config: dict[str, Any],
        context: dict[str, Any],
        tags: list[str],
        created_by_type: str,
        created_by_id: str | None,
        idempotency_key: str | None,
    ) -> dict[str, Any]:
        run_id = new_id("run")
        manifest = {
            "version": 1,
            "local_run_id": run_id,
            "remote_run_id": None,
            "created_at": utc_iso(),
            "synced_at": None,
            "run_create": {
                "project_key": project,
                "research_key": research,
                "branch_key": branch,
                "name": name,
                "title": title,
                "config": config,
                "context": context,
                "tags": tags,
                "created_by_type": created_by_type,
                "created_by_id": created_by_id,
                "idempotency_key": idempotency_key,
            },
            "snapshots": {"code": [], "data": [], "env": []},
            "events": [],
            "metrics": [],
            "series": [],
            "notes": [],
            "artifacts": [],
            "sweeps": [],
            "terminal": None,
        }
        self._write_manifest(run_id, manifest)
        return {
            "id": run_id,
            "branch_id": branch,
            "name": name,
            "title": title,
            "status": "running",
            "source_run_id": None,
            "sequence_no": 1,
            "config_json": config,
            "context_json": context,
            "summary_json": {"offline": True},
            "tags": tags,
            "started_at": manifest["created_at"],
            "ended_at": None,
            "created_by_type": created_by_type,
            "created_by_id": created_by_id,
            "created_at": manifest["created_at"],
            "updated_at": manifest["created_at"],
        }

    def add_snapshot(self, run_id: str, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        manifest = self._read_manifest(run_id)
        snapshot = {"id": new_id("snapshot"), "payload": payload, "created_at": utc_iso()}
        manifest["snapshots"][kind].append(snapshot)
        self._write_manifest(run_id, manifest)
        return snapshot

    def update_run(
        self,
        run_id: str,
        *,
        config: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        manifest = self._read_manifest(run_id)
        run_create = manifest["run_create"]
        if config is not None:
            run_create["config"] = config
        if context is not None:
            run_create["context"] = context
        if tags is not None:
            run_create["tags"] = tags
        manifest["updated_at"] = utc_iso()
        self._write_manifest(run_id, manifest)
        return {
            "id": run_id,
            "config_json": run_create.get("config", {}),
            "context_json": run_create.get("context", {}),
            "tags": run_create.get("tags", []),
        }

    def add_event(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        manifest = self._read_manifest(run_id)
        event = {"id": new_id("event"), "payload": payload, "created_at": utc_iso()}
        manifest["events"].append(event)
        self._write_manifest(run_id, manifest)
        return event

    def add_metric(self, run_id: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        manifest = self._read_manifest(run_id)
        metric = {"id": new_id("metric"), "payload": payload, "created_at": utc_iso()}
        manifest["metrics"].append(metric)
        self._write_manifest(run_id, manifest)
        return [metric]

    def add_series(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        manifest = self._read_manifest(run_id)
        series = {"id": new_id("artifact"), "payload": payload, "created_at": utc_iso()}
        manifest.setdefault("series", []).append(series)
        self._write_manifest(run_id, manifest)
        return series

    def add_note(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        manifest = self._read_manifest(run_id)
        note = {"id": new_id("note"), "payload": payload, "created_at": utc_iso()}
        manifest["notes"].append(note)
        self._write_manifest(run_id, manifest)
        return note

    def add_artifact(self, run_id: str, name: str, source_path: str | Path, kind: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        manifest = self._read_manifest(run_id)
        source = Path(source_path)
        target_dir = self.artifact_dir / run_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target = unique_path(target_dir / source.name)
        shutil.copy2(source, target)
        artifact = {
            "id": new_id("artifact"),
            "name": name,
            "kind": kind,
            "filename": target.name,
            "path": str(target),
            "metadata": metadata or {},
            "created_at": utc_iso(),
        }
        manifest["artifacts"].append(artifact)
        self._write_manifest(run_id, manifest)
        return artifact

    def add_bytes(self, run_id: str, name: str, content: bytes, kind: str, filename: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        manifest = self._read_manifest(run_id)
        target_dir = self.artifact_dir / run_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target = unique_path(target_dir / Path(filename).name)
        target.write_bytes(content)
        artifact = {
            "id": new_id("artifact"),
            "name": name,
            "kind": kind,
            "filename": target.name,
            "path": str(target),
            "metadata": metadata or {},
            "created_at": utc_iso(),
        }
        manifest["artifacts"].append(artifact)
        self._write_manifest(run_id, manifest)
        return artifact

    def add_external_artifact(
        self,
        run_id: str,
        name: str,
        uri: str,
        kind: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        manifest = self._read_manifest(run_id)
        artifact = {
            "id": new_id("artifact"),
            "name": name,
            "kind": kind,
            "uri": uri,
            "metadata": metadata,
            "created_at": utc_iso(),
        }
        manifest["artifacts"].append(artifact)
        self._write_manifest(run_id, manifest)
        return artifact

    def create_sweep(
        self,
        branch_id: str,
        name: str,
        search_space: dict[str, Any] | None = None,
        objective: dict[str, Any] | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        sweep_id = new_id("sweep")
        created_at = utc_iso()
        sweep = {
            "id": sweep_id,
            "branch_id": branch_id,
            "name": name,
            "search_space": search_space or {},
            "objective": objective or {},
            "status": status,
            "created_at": created_at,
            "updated_at": created_at,
        }
        self._write_json_atomic(self._sweep_path(sweep_id), sweep)
        return {
            "id": sweep_id,
            "branch_id": branch_id,
            "name": name,
            "search_space_json": sweep["search_space"],
            "objective_json": sweep["objective"],
            "status": status,
            "created_at": created_at,
            "updated_at": created_at,
        }

    def attach_sweep(self, run_id: str, sweep_id: str, coord: dict[str, Any] | None = None, rank: int | None = None) -> dict[str, Any]:
        manifest = self._read_manifest(run_id)
        attachment = {
            "id": new_id("sweep_run"),
            "sweep_id": sweep_id,
            "coord": coord or {},
            "rank": rank,
            "created_at": utc_iso(),
        }
        if sweep := self._read_sweep(sweep_id):
            attachment["sweep"] = sweep
        manifest.setdefault("sweeps", []).append(attachment)
        self._write_manifest(run_id, manifest)
        return attachment

    def finish(self, run_id: str) -> dict[str, Any]:
        return self._set_terminal(run_id, {"status": "completed", "created_at": utc_iso()})

    def fail(self, run_id: str, error: dict[str, Any]) -> dict[str, Any]:
        return self._set_terminal(run_id, {"status": "failed", "error": error, "created_at": utc_iso()})

    def cancel(self, run_id: str, reason: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._set_terminal(run_id, {"status": "cancelled", "reason": reason or {}, "created_at": utc_iso()})

    def list_manifests(self) -> list[dict[str, Any]]:
        paths = {path.stem: path for path in self.manifests_dir.glob("*.json")}
        paths.update({path.stem: path for path in self.queue_dir.glob("*.json")})
        manifests = []
        for path in sorted(paths.values()):
            manifests.append(json.loads(path.read_text(encoding="utf-8")))
        return manifests

    def mark_synced(self, local_run_id: str, remote_run_id: str) -> dict[str, Any]:
        manifest = self._read_manifest(local_run_id)
        manifest["remote_run_id"] = remote_run_id
        manifest["synced_at"] = utc_iso()
        self._write_manifest(local_run_id, manifest)
        return manifest

    def _set_terminal(self, run_id: str, terminal: dict[str, Any]) -> dict[str, Any]:
        manifest = self._read_manifest(run_id)
        manifest["terminal"] = terminal
        self._write_manifest(run_id, manifest)
        return {"id": run_id, "status": terminal["status"]}

    def _manifest_path(self, run_id: str) -> Path:
        return self.queue_dir / f"{run_id}.json"

    def _manifest_mirror_path(self, run_id: str) -> Path:
        return self.manifests_dir / f"{run_id}.json"

    def _sweep_path(self, sweep_id: str) -> Path:
        return self.sweeps_dir / f"{sweep_id}.json"

    def _read_sweep(self, sweep_id: str) -> dict[str, Any] | None:
        path = self._sweep_path(sweep_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _read_manifest(self, run_id: str) -> dict[str, Any]:
        path = self._manifest_path(run_id)
        if not path.exists():
            path = self._manifest_mirror_path(run_id)
        if not path.exists():
            raise FileNotFoundError(f"offline run manifest not found: {run_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_manifest(self, run_id: str, manifest: dict[str, Any]) -> None:
        path = self._manifest_path(run_id)
        mirror_path = self._manifest_mirror_path(run_id)
        self._write_json_atomic(mirror_path, manifest)
        self._write_json_atomic(path, manifest)

    def _write_json_atomic(self, path: Path, manifest: dict[str, Any]) -> None:
        tmp_path = path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(path)


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    index = 1
    while True:
        candidate = parent / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1
