from __future__ import annotations

import atexit
import contextvars
import importlib.metadata
import json
import os
import platform
import socket
import subprocess
import sys
import traceback
import uuid
from pathlib import Path
from types import TracebackType
from typing import Any

import httpx

from .offline import OfflineSpool


_current_run: contextvars.ContextVar["RunContext | None"] = contextvars.ContextVar("blackbox_current_run", default=None)


class BlackboxClient:
    def __init__(
        self,
        endpoint: str | None = None,
        token: str | None = None,
        timeout: float = 30.0,
        offline: bool | None = None,
        spool_dir: str | Path | None = None,
        buffered: bool | None = None,
    ):
        self.endpoint = (endpoint or os.getenv("BLACKBOX_ENDPOINT") or "http://127.0.0.1:8000").rstrip("/")
        self.token = token or os.getenv("BLACKBOX_TOKEN") or os.getenv("BLACKBOX_API_TOKEN")
        self.timeout = timeout
        self.offline = offline if offline is not None else os.getenv("BLACKBOX_OFFLINE", "0").lower() in {"1", "true", "yes"}
        self.spool = OfflineSpool(spool_dir or os.getenv("BLACKBOX_SPOOL_DIR") or os.getenv("BLACKBOX_DATA_DIR") or "~/.blackbox") if self.offline else None
        self.buffered = buffered if buffered is not None else os.getenv("BLACKBOX_BUFFERED", "0").lower() in {"1", "true", "yes"}
        self.flush_retries = parse_int_env("BLACKBOX_FLUSH_RETRIES", 2)
        self._buffer: list[dict[str, Any]] = []
        self._flushing = False
        if self.buffered and self.spool is None:
            atexit.register(self._flush_at_exit)

    @property
    def headers(self) -> dict[str, str]:
        headers = {"User-Agent": "blackbox-sdk/0.1.0"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = {**self.headers, **kwargs.pop("headers", {})}
        with httpx.Client(timeout=self.timeout) as client:
            response = client.request(method, f"{self.endpoint}{path}", headers=headers, **kwargs)
        payload = response.json()
        if not payload.get("ok"):
            error = payload.get("error") or {}
            raise RuntimeError(f"{error.get('code', response.status_code)}: {error.get('message', response.text)}")
        return payload["data"]

    def buffer_request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        item = {"method": method, "path": path, "kwargs": kwargs}
        self._buffer.append(item)
        return {"buffered": True, "method": method, "path": path, **kwargs}

    def flush(self) -> list[Any]:
        if not self._buffer:
            return []
        pending = self._buffer
        self._buffer = []
        self._flushing = True
        results: list[Any] = []
        try:
            for item in pending:
                results.append(self._send_buffered_item(item))
        except Exception:
            self._buffer = pending[len(results):] + self._buffer
            raise
        finally:
            self._flushing = False
        return results

    def _send_buffered_item(self, item: dict[str, Any]) -> Any:
        last_error: Exception | None = None
        for _ in range(self.flush_retries + 1):
            try:
                return self.request(item["method"], item["path"], **item["kwargs"])
            except Exception as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise RuntimeError("buffered request failed")

    def _flush_at_exit(self) -> None:
        try:
            self.flush()
        except Exception:
            pass

    def should_buffer_logs(self) -> bool:
        return self.buffered and self.spool is None and not self._flushing

    def dashboard(self) -> dict[str, Any]:
        return self.request("GET", "/api/v1/dashboard")

    def get_run(self, run_id: str) -> dict[str, Any]:
        return self.request("GET", f"/api/v1/runs/{run_id}")

    def search_runs(self, **filters: Any) -> list[dict[str, Any]]:
        return self.request("POST", "/api/v1/search/runs", json=compact_payload(filters))

    def search_researches(self, **filters: Any) -> list[dict[str, Any]]:
        return self.request("POST", "/api/v1/search/researches", json=compact_payload(filters))

    def compare_runs(
        self,
        run_ids: list[str],
        metrics: list[str] | None = None,
        series: list[str] | None = None,
        with_config_diff: bool = True,
    ) -> dict[str, Any]:
        return self.request(
            "POST",
            "/api/v1/compare/runs",
            json={
                "run_ids": run_ids,
                "metrics": metrics or [],
                "series": series or [],
                "with_config_diff": with_config_diff,
            },
        )

    def create_compare_set(self, project_id: str, name: str, run_ids: list[str], layout: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.request(
            "POST",
            "/api/v1/compare-sets",
            json={"project_id": project_id, "name": name, "run_ids": run_ids, "layout": layout or {}},
        )

    def list_compare_sets(self, project_id: str) -> list[dict[str, Any]]:
        return self.request("GET", f"/api/v1/projects/{project_id}/compare-sets")

    def get_compare_set(self, compare_set_id: str) -> dict[str, Any]:
        return self.request("GET", f"/api/v1/compare-sets/{compare_set_id}")

    def update_compare_set(
        self,
        compare_set_id: str,
        *,
        name: str | None = None,
        run_ids: list[str] | None = None,
        layout: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.request("PATCH", f"/api/v1/compare-sets/{compare_set_id}", json=compact_payload({"name": name, "run_ids": run_ids, "layout": layout}))

    def run_compare_set(
        self,
        compare_set_id: str,
        metrics: list[str] | None = None,
        series: list[str] | None = None,
        with_config_diff: bool = True,
    ) -> dict[str, Any]:
        compare_set = self.get_compare_set(compare_set_id)
        layout = compare_set.get("layout_json") or {}
        return self.compare_runs(
            compare_set.get("run_ids_json") or [],
            metrics=metrics if metrics is not None else list_or_empty(layout.get("metrics")),
            series=series if series is not None else list_or_empty(layout.get("series")),
            with_config_diff=with_config_diff,
        )

    def create_search_view(self, project_id: str, name: str, filters: dict[str, Any], description: str | None = None) -> dict[str, Any]:
        return self.request("POST", "/api/v1/search-views", json={"project_id": project_id, "name": name, "description": description, "filters": filters})

    def list_search_views(self, project_id: str) -> list[dict[str, Any]]:
        return self.request("GET", f"/api/v1/projects/{project_id}/search-views")

    def get_search_view(self, view_id: str) -> dict[str, Any]:
        return self.request("GET", f"/api/v1/search-views/{view_id}")

    def update_search_view(
        self,
        view_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.request("PATCH", f"/api/v1/search-views/{view_id}", json=compact_payload({"name": name, "description": description, "filters": filters}))

    def run_search_view(self, view_id: str, overrides: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return self.request("POST", f"/api/v1/search-views/{view_id}/run", json=overrides or {})

    def research_lineage(self, research_id: str) -> dict[str, Any]:
        return self.request("GET", f"/api/v1/lineage/researches/{research_id}")

    def branch_lineage(self, branch_id: str) -> dict[str, Any]:
        return self.request("GET", f"/api/v1/lineage/branches/{branch_id}")

    def get_sweep(self, sweep_id: str) -> dict[str, Any]:
        return self.request("GET", f"/api/v1/sweeps/{sweep_id}")

    def get_sweep_summary(self, sweep_id: str) -> dict[str, Any]:
        return self.request("GET", f"/api/v1/sweeps/{sweep_id}/summary")

    def ensure_project(
        self,
        key: str,
        title: str | None = None,
        *,
        workspace_id: str = "local",
        description: str | None = None,
        tags: list[str] | None = None,
        retention_policy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self.spool:
            return {
                "id": key,
                "workspace_id": workspace_id,
                "key": key,
                "title": title or key,
                "description": description,
                "tags": tags or [],
                "retention_policy_json": retention_policy or {},
            }
        return self.request(
            "POST",
            "/api/v1/projects",
            json={
                "key": key,
                "title": title or key,
                "workspace_id": workspace_id,
                "description": description,
                "tags": tags or [],
                "retention_policy": retention_policy or {},
            },
        )

    def ensure_research(self, project_key: str, key: str, title: str | None = None) -> dict[str, Any]:
        if self.spool:
            return {"id": key, "project_id": project_key, "key": key, "title": title or key}
        return self.request(
            "POST",
            "/api/v1/researches",
            json={"project_key": project_key, "key": key, "title": title or key},
        )

    def ensure_branch(self, research_id: str, key: str, title: str | None = None) -> dict[str, Any]:
        if self.spool:
            return {"id": key, "research_id": research_id, "key": key, "title": title or key}
        return self.request(
            "POST",
            "/api/v1/branches",
            json={"research_id": research_id, "key": key, "title": title or key},
        )

    def start_run(
        self,
        *,
        project: str,
        research: str,
        branch: str,
        name: str,
        title: str | None = None,
        config: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        created_by_type: str = "human",
        created_by_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        project_obj = self.ensure_project(project)
        research_obj = self.ensure_research(project_obj["key"], research)
        self.ensure_branch(research_obj["id"], branch)
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else {}
        runtime_context = capture_runtime_context()
        if self.spool:
            run = self.spool.start_run(
                project=project,
                research=research,
                branch=branch,
                name=name,
                title=title,
                config=config or {},
                context={**runtime_context, **(context or {})},
                tags=tags or [],
                created_by_type=created_by_type,
                created_by_id=created_by_id,
                idempotency_key=idempotency_key,
            )
            self.capture_code_snapshot(run["id"], runtime_context.get("git", {}))
            self.capture_env_snapshot(run["id"], runtime_context)
            return run
        run = self.request(
            "POST",
            "/api/v1/runs",
            headers=headers,
            json={
                "project_key": project,
                "research_key": research,
                "branch_key": branch,
                "name": name,
                "title": title,
                "config": config or {},
                "context": {**runtime_context, **(context or {})},
                "tags": tags or [],
                "created_by_type": created_by_type,
                "created_by_id": created_by_id,
            },
        )
        self.capture_code_snapshot(run["id"], runtime_context.get("git", {}))
        self.capture_env_snapshot(run["id"], runtime_context)
        return run

    def capture_code_snapshot(self, run_id: str, git: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "repo_url": git.get("repo_url"),
            "git_commit": git.get("commit"),
            "git_dirty": bool(git.get("dirty", False)),
            "metadata": {
                "cwd": str(Path.cwd()),
                "git_error": git.get("error"),
            },
        }
        if self.spool:
            return self.spool.add_snapshot(run_id, "code", payload)
        return self.request(
            "POST",
            f"/api/v1/runs/{run_id}/snapshots/code",
            json=payload,
        )

    def capture_env_snapshot(self, run_id: str, runtime_context: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "python_version": runtime_context.get("python_version"),
            "platform": runtime_context.get("platform"),
            "hostname": runtime_context.get("hostname"),
            "packages": capture_packages(),
            "metadata": {
                "pid": runtime_context.get("pid"),
                "cwd": runtime_context.get("cwd"),
                "entry_file": runtime_context.get("entry_file"),
            },
        }
        if self.spool:
            return self.spool.add_snapshot(run_id, "env", payload)
        return self.request(
            "POST",
            f"/api/v1/runs/{run_id}/snapshots/env",
            json=payload,
        )

    def log_event(
        self,
        run_id: str,
        event_type: str,
        stage: str | None = None,
        payload: dict[str, Any] | None = None,
        client_event_id: str | None = None,
    ) -> dict[str, Any]:
        event_payload = {
            "event_type": event_type,
            "stage": stage,
            "payload": payload or {},
            "client_event_id": client_event_id or make_client_event_id("evt"),
        }
        if self.spool:
            return self.spool.add_event(run_id, event_payload)
        if self.should_buffer_logs():
            return self.buffer_request("POST", f"/api/v1/runs/{run_id}/events", json=event_payload)
        return self.request(
            "POST",
            f"/api/v1/runs/{run_id}/events",
            json=event_payload,
        )

    def log_metric(
        self,
        run_id: str,
        namespace: str,
        values: dict[str, Any],
        point: dict[str, Any] | None = None,
        client_event_id: str | None = None,
    ) -> list[dict[str, Any]]:
        metric_payload = {
            "namespace": namespace,
            "values": values,
            "point": point or {"kind": "summary"},
            "client_event_id": client_event_id or make_client_event_id("met"),
        }
        if self.spool:
            return self.spool.add_metric(run_id, metric_payload)
        if self.should_buffer_logs():
            return [self.buffer_request("POST", f"/api/v1/runs/{run_id}/metrics", json=metric_payload)]
        return self.request(
            "POST",
            f"/api/v1/runs/{run_id}/metrics",
            json=metric_payload,
        )

    def log_note(
        self,
        run_id: str,
        kind: str,
        summary: str,
        content: str | None = None,
        structured: dict[str, Any] | None = None,
        author_type: str = "agent",
        client_event_id: str | None = None,
    ) -> dict[str, Any]:
        note_payload = {
            "kind": kind,
            "summary": summary,
            "content": content,
            "structured": structured or {},
            "author_type": author_type,
            "client_event_id": client_event_id or make_client_event_id("note"),
        }
        if self.spool:
            return self.spool.add_note(run_id, note_payload)
        if self.should_buffer_logs():
            return self.buffer_request("POST", f"/api/v1/runs/{run_id}/notes", json=note_payload)
        return self.request(
            "POST",
            f"/api/v1/runs/{run_id}/notes",
            json=note_payload,
        )

    def log_series(
        self,
        run_id: str,
        name: str,
        data: list[dict[str, Any]],
        x: str | None = None,
        y: str | list[str] | None = None,
        mode: str | None = None,
        namespace: str | None = None,
        metric: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        kind: str = "table_csv",
        filename: str | None = None,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        series_payload = {
            "name": name,
            "data": data,
            "x": x,
            "y": y,
            "mode": mode,
            "namespace": namespace,
            "kind": kind,
            "filename": filename,
            "metadata": metadata or {},
        }
        if metric is not None:
            series_payload["metric"] = metric
        if result is not None:
            series_payload["result"] = result
        request_kwargs = {"json": series_payload}
        if idempotency_key:
            request_kwargs["headers"] = {"Idempotency-Key": idempotency_key}
        if self.spool:
            return self.spool.add_series(run_id, series_payload)
        if self.should_buffer_logs():
            return self.buffer_request("POST", f"/api/v1/runs/{run_id}/series", **request_kwargs)
        return self.request("POST", f"/api/v1/runs/{run_id}/series", **request_kwargs)

    def upload_artifact(
        self,
        run_id: str,
        name: str,
        path: str | Path,
        kind: str | None = None,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        file_path = Path(path)
        if self.spool:
            return self.spool.add_artifact(run_id, name, file_path, kind or "other", metadata or {})
        content = file_path.read_bytes()
        request_kwargs = {
            "params": {"name": name, "kind": kind or "other", "filename": file_path.name, "metadata": json_dumps(metadata or {})},
            "content": content,
        }
        if idempotency_key:
            request_kwargs["headers"] = {"Idempotency-Key": idempotency_key}
        return self.request(
            "POST",
            f"/api/v1/runs/{run_id}/artifacts/upload",
            **request_kwargs,
        )

    def upload_bytes(
        self,
        run_id: str,
        name: str,
        content: bytes,
        kind: str | None = None,
        filename: str | None = None,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        artifact_kind = kind or "other"
        artifact_filename = filename or f"{name}.bin"
        if self.spool:
            return self.spool.add_bytes(run_id, name, content, artifact_kind, artifact_filename, metadata or {})
        request_kwargs = {
            "params": {"name": name, "kind": artifact_kind, "filename": artifact_filename, "metadata": json_dumps(metadata or {})},
            "content": content,
        }
        if idempotency_key:
            request_kwargs["headers"] = {"Idempotency-Key": idempotency_key}
        return self.request(
            "POST",
            f"/api/v1/runs/{run_id}/artifacts/upload",
            **request_kwargs,
        )

    def register_external_artifact(
        self,
        run_id: str,
        name: str,
        uri: str,
        kind: str | None = None,
        metadata: dict[str, Any] | None = None,
        filename: str | None = None,
        mime_type: str | None = None,
        size_bytes: int | None = None,
        sha256: str | None = None,
        preview: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if self.spool:
            return self.spool.add_external_artifact(run_id, name, uri, kind or "other", metadata or {})
        request_kwargs: dict[str, Any] = {}
        if idempotency_key:
            request_kwargs["headers"] = {"Idempotency-Key": idempotency_key}
        return self.request(
            "POST",
            f"/api/v1/runs/{run_id}/artifacts/register-external",
            **request_kwargs,
            json={
                key: value
                for key, value in {
                    "name": name,
                    "uri": uri,
                    "kind": kind or "other",
                    "metadata": metadata or {},
                    "filename": filename,
                    "mime_type": mime_type,
                    "size_bytes": size_bytes,
                    "sha256": sha256,
                    "preview": preview,
                }.items()
                if value is not None
            },
        )

    def download_artifact(self, artifact_id: str, path: str | Path) -> dict[str, Any]:
        if self.spool:
            raise RuntimeError("offline artifact download is not supported")
        output_path = Path(path).expanduser().resolve()
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            response = client.get(f"{self.endpoint}/api/v1/artifacts/{artifact_id}/content", headers=self.headers)
        if response.status_code >= 400:
            try:
                payload = response.json()
                error = payload.get("error") or {}
                message = error.get("message", response.text)
                code = error.get("code", response.status_code)
            except Exception:
                message = response.text
                code = response.status_code
            raise RuntimeError(f"{code}: {message}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)
        return {
            "artifact_id": artifact_id,
            "path": str(output_path),
            "size_bytes": len(response.content),
            "content_type": response.headers.get("content-type"),
            "source_url": str(response.url),
        }

    def register_dataset(self, run_id: str, **kwargs: Any) -> dict[str, Any]:
        payload = {
            "dataset_name": kwargs.get("dataset_name") or kwargs.get("name"),
            "dataset_version": kwargs.get("dataset_version") or kwargs.get("version"),
            "fingerprint": kwargs.get("fingerprint"),
            "universe": kwargs.get("universe"),
            "benchmark": kwargs.get("benchmark"),
            "calendar": kwargs.get("calendar"),
            "fee_model": kwargs.get("fee_model"),
            "slippage_model": kwargs.get("slippage_model"),
            "time_range": kwargs.get("time_range") or {},
            "metadata": kwargs.get("metadata") or {},
        }
        if self.spool:
            return self.spool.add_snapshot(run_id, "data", payload)
        return self.request("POST", f"/api/v1/runs/{run_id}/snapshots/data", json=payload)

    def update_run(
        self,
        run_id: str,
        *,
        name: str | None = None,
        title: str | None = None,
        source_run_id: str | None = None,
        config: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        if self.spool:
            return self.spool.update_run(run_id, config=config, context=context, tags=tags)
        payload = {
            key: value
            for key, value in {
                "name": name,
                "title": title,
                "source_run_id": source_run_id,
                "config": config,
                "context": context,
                "tags": tags,
            }.items()
            if value is not None
        }
        return self.request("PATCH", f"/api/v1/runs/{run_id}", json=payload)

    def create_sweep(
        self,
        branch_id: str,
        name: str,
        search_space: dict[str, Any] | None = None,
        objective: dict[str, Any] | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        if self.spool:
            return self.spool.create_sweep(branch_id, name, search_space=search_space, objective=objective, status=status)
        return self.request(
            "POST",
            "/api/v1/sweeps",
            json={
                "branch_id": branch_id,
                "name": name,
                "search_space": search_space or {},
                "objective": objective or {},
                "status": status,
            },
        )

    def attach_sweep(self, run_id: str, sweep_id: str, coord: dict[str, Any] | None = None, rank: int | None = None) -> dict[str, Any]:
        if self.spool:
            return self.spool.attach_sweep(run_id, sweep_id, coord, rank)
        return self.request(
            "POST",
            f"/api/v1/sweeps/{sweep_id}/runs",
            json={"run_id": run_id, "coord": coord or {}, "rank": rank},
        )

    def finish(self, run_id: str, status: str = "completed") -> dict[str, Any]:
        if status != "completed":
            raise ValueError("finish only supports status='completed'; use fail() or cancel() for terminal errors")
        if self.spool:
            return self.spool.finish(run_id)
        self.flush()
        return self.request("POST", f"/api/v1/runs/{run_id}/finish")

    def fail(self, run_id: str, error: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.spool:
            return self.spool.fail(run_id, error or {})
        self.flush()
        return self.request("POST", f"/api/v1/runs/{run_id}/fail", json=error or {})

    def cancel(self, run_id: str, reason: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.spool:
            return self.spool.cancel(run_id, reason or {})
        self.flush()
        return self.request("POST", f"/api/v1/runs/{run_id}/cancel", json=reason or {})


class RunContext:
    def __init__(
        self,
        *,
        client: BlackboxClient,
        project: str,
        research: str,
        branch: str,
        name: str,
        title: str | None = None,
        config: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        created_by_type: str = "human",
        created_by_id: str | None = None,
    ):
        self.client = client
        self.project = project
        self.research = research
        self.branch = branch
        self.name = name
        self.title = title
        self.config = config or {}
        self.context = context or {}
        self.tags = tags or []
        self.created_by_type = created_by_type
        self.created_by_id = created_by_id
        self.run: dict[str, Any] | None = None
        self._token: contextvars.Token[RunContext | None] | None = None

    @property
    def id(self) -> str:
        if not self.run:
            raise RuntimeError("run has not been started")
        return self.run["id"]

    def __enter__(self) -> "RunContext":
        self.run = self.client.start_run(
            project=self.project,
            research=self.research,
            branch=self.branch,
            name=self.name,
            title=self.title,
            config=self.config,
            context=self.context,
            tags=self.tags,
            created_by_type=self.created_by_type,
            created_by_id=self.created_by_id,
            idempotency_key=make_client_event_id("run"),
        )
        self._token = _current_run.set(self)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        try:
            if exc_type is None:
                self.client.finish(self.id)
            else:
                failure_payload = {
                    "error_type": exc_type.__name__ if exc_type else None,
                    "message": str(exc_value) if exc_value else None,
                    "traceback": "".join(traceback.format_exception(exc_type, exc_value, exc_tb))[-4000:],
                }
                self.client.log_note(
                    self.id,
                    "anomaly",
                    f"Run failed: {failure_payload['error_type'] or 'error'}",
                    content=failure_payload["traceback"],
                    structured=failure_payload,
                    author_type="system",
                )
                self.client.fail(
                    self.id,
                    failure_payload,
                )
        finally:
            if self._token is not None:
                _current_run.reset(self._token)
        return False

    def log(
        self,
        values: dict[str, Any],
        namespace: str = "strategy.summary",
        point: dict[str, Any] | None = None,
        client_event_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return self.client.log_metric(self.id, namespace, values, point, client_event_id=client_event_id)

    def log_event(
        self,
        event_type: str,
        stage: str | None = None,
        payload: dict[str, Any] | None = None,
        client_event_id: str | None = None,
    ) -> dict[str, Any]:
        return self.client.log_event(self.id, event_type, stage, payload, client_event_id=client_event_id)

    def log_note(
        self,
        kind: str,
        summary: str,
        content: str | None = None,
        structured: dict[str, Any] | None = None,
        author_type: str = "agent",
        client_event_id: str | None = None,
    ) -> dict[str, Any]:
        return self.client.log_note(self.id, kind, summary, content, structured, author_type=author_type, client_event_id=client_event_id)

    def log_artifact(
        self,
        name: str,
        path: str | Path,
        kind: str | None = None,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self.client.upload_artifact(self.id, name, path, kind, metadata, idempotency_key=idempotency_key)

    def log_bytes(
        self,
        name: str,
        content: bytes,
        kind: str | None = None,
        filename: str | None = None,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self.client.upload_bytes(self.id, name, content, kind, filename, metadata, idempotency_key=idempotency_key)

    def log_params(self, params: dict[str, Any]) -> dict[str, Any]:
        self.config = {**self.config, **params}
        return self.client.update_run(self.id, config=self.config)

    def set_tags(self, tags: list[str]) -> dict[str, Any]:
        self.tags = list(tags)
        return self.client.update_run(self.id, tags=self.tags)

    def set_summary(self, values: dict[str, Any], namespace: str = "strategy.summary") -> list[dict[str, Any]]:
        return self.log(values, namespace=namespace, point={"kind": "summary"})


def init(
    *,
    project: str,
    research: str,
    branch: str,
    name: str,
    title: str | None = None,
    config: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    endpoint: str | None = None,
    token: str | None = None,
    offline: bool | None = None,
    spool_dir: str | Path | None = None,
    buffered: bool | None = None,
    created_by_type: str = "human",
    created_by_id: str | None = None,
) -> RunContext:
    return RunContext(
        client=BlackboxClient(endpoint=endpoint, token=token, offline=offline, spool_dir=spool_dir, buffered=buffered),
        project=project,
        research=research,
        branch=branch,
        name=name,
        title=title,
        config=config,
        context=context,
        tags=tags,
        created_by_type=created_by_type,
        created_by_id=created_by_id,
    )


def current_run() -> RunContext:
    run = _current_run.get()
    if run is None:
        raise RuntimeError("no active blackbox run")
    return run


def finish(status: str = "completed") -> dict[str, Any]:
    run = current_run()
    return run.client.finish(run.id, status=status)


def fail(error: dict[str, Any] | None = None) -> dict[str, Any]:
    run = current_run()
    return run.client.fail(run.id, error)


def cancel(reason: dict[str, Any] | None = None) -> dict[str, Any]:
    run = current_run()
    return run.client.cancel(run.id, reason)


def flush() -> list[Any]:
    return current_run().client.flush()


def make_client_event_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def client_event_id(prefix: str) -> str:
    return make_client_event_id(prefix)


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def parse_int_env(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def compact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def list_or_empty(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return list(value)


def capture_runtime_context() -> dict[str, Any]:
    return {
        "hostname": socket.gethostname(),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "pid": os.getpid(),
        "cwd": str(Path.cwd()),
        "entry_file": sys.argv[0] if sys.argv else None,
        "git": capture_git(),
    }


def capture_git() -> dict[str, Any]:
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True, stderr=subprocess.DEVNULL).strip())
        repo_url = subprocess.check_output(
            ["git", "config", "--get", "remote.origin.url"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return {"commit": commit, "dirty": dirty, "repo_url": repo_url or None}
    except Exception as exc:
        return {"error": str(exc)}


def capture_packages(limit: int = 300) -> dict[str, str]:
    packages: dict[str, str] = {}
    try:
        for dist in sorted(importlib.metadata.distributions(), key=lambda item: (item.metadata.get("Name") or "").lower()):
            name = dist.metadata.get("Name")
            if name:
                packages[name] = dist.version
            if len(packages) >= limit:
                break
    except Exception:
        return {}
    return packages
