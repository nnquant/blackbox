from __future__ import annotations

import importlib
import json
from typing import Any


class FakeRun:
    id = "run_1"

    def __init__(self) -> None:
        self.metrics: list[dict[str, Any]] = []
        self.artifacts: list[dict[str, Any]] = []

    def log(
        self,
        values: dict[str, Any],
        namespace: str = "strategy.summary",
        point: dict[str, Any] | None = None,
        client_event_id: str | None = None,
    ) -> list[dict[str, Any]]:
        payload = {"values": values, "namespace": namespace, "point": point or {"kind": "summary"}, "client_event_id": client_event_id}
        self.metrics.append(payload)
        return [payload]

    def log_bytes(
        self,
        name: str,
        content: bytes,
        kind: str | None = None,
        filename: str | None = None,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        del idempotency_key
        payload = {"name": name, "content": content, "kind": kind, "filename": filename, "metadata": metadata or {}}
        self.artifacts.append(payload)
        return payload


class FakeClient:
    def __init__(self) -> None:
        self.updates: list[dict[str, Any]] = []
        self.notes: list[dict[str, Any]] = []
        self.sweeps: list[dict[str, Any]] = []

    def update_run(self, run_id: str, **payload: Any) -> dict[str, Any]:
        update = {"run_id": run_id, **payload}
        self.updates.append(update)
        return update

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
        note = {
            "run_id": run_id,
            "kind": kind,
            "summary": summary,
            "content": content,
            "structured": structured or {},
            "author_type": author_type,
            "client_event_id": client_event_id,
        }
        self.notes.append(note)
        return note

    def create_sweep(
        self,
        branch_id: str,
        name: str,
        search_space: dict[str, Any] | None = None,
        objective: dict[str, Any] | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        sweep = {
            "branch_id": branch_id,
            "name": name,
            "search_space": search_space or {},
            "objective": objective or {},
            "status": status,
        }
        self.sweeps.append(sweep)
        return sweep


class FakeRunWithClient(FakeRun):
    def __init__(self) -> None:
        super().__init__()
        self.config = {"lookback": 10}
        self.tags = ["baseline"]
        self.client = FakeClient()

    def log_params(self, params: dict[str, Any]) -> dict[str, Any]:
        self.config = {**self.config, **params}
        return self.client.update_run(self.id, config=self.config)

    def set_tags(self, tags: list[str]) -> dict[str, Any]:
        self.tags = tags
        return self.client.update_run(self.id, tags=self.tags)

    def set_summary(self, values: dict[str, Any], namespace: str = "strategy.summary") -> list[dict[str, Any]]:
        return self.log(values, namespace=namespace, point={"kind": "summary"})


def test_quant_sdk_helpers_emit_expected_namespaces_and_artifact_kinds(monkeypatch) -> None:
    from blackbox import (
        log_backtest_summary,
        log_cost_breakdown,
        log_drawdown_series,
        log_factor_coverage,
        log_factor_ic_series,
        log_factor_summary,
        log_factor_turnover,
        log_positions,
        log_quantile_returns,
        log_returns_series,
        log_risk_exposure,
        log_sweep_coord,
        log_trades,
    )
    logging_module = importlib.import_module("blackbox.logging")

    fake_run = FakeRun()
    monkeypatch.setattr(logging_module, "current_run", lambda: fake_run)

    assert log_factor_summary({"ic_mean": 0.03})[0]["namespace"] == "factor.summary"
    assert log_backtest_summary({"sharpe": 1.2})[0]["namespace"] == "strategy.summary"
    assert log_factor_turnover({"turnover": 0.4})[0]["namespace"] == "factor.turnover"
    assert log_factor_coverage({"coverage": 0.95})[0]["namespace"] == "factor.coverage"
    assert log_cost_breakdown({"fee_bps": 10})[0]["namespace"] == "cost.breakdown"
    assert log_sweep_coord({"lookback": 20})[0]["point"] == {"kind": "coordinate", "coord": {"lookback": 20}}

    ic = log_factor_ic_series([{"date": "2026-01-01", "ic": 0.02}])
    quantile = log_quantile_returns([{"quantile": 1, "return": 0.01}])
    returns = log_returns_series([{"date": "2026-01-01", "return": 0.01}])
    drawdown = log_drawdown_series([{"date": "2026-01-01", "drawdown": -0.02}])
    positions = log_positions([{"date": "2026-01-01", "symbol": "000001", "weight": 0.1}])
    trades = log_trades([{"date": "2026-01-01", "symbol": "000001", "qty": 100}])
    risk = log_risk_exposure([{"factor": "size", "exposure": 0.2}])

    assert ic["kind"] == "table_csv"
    assert ic["metadata"]["series"] == {"name": "factor_ic_series", "x": "date", "y": "ic", "namespace": "factor.ic"}
    assert quantile["name"] == "factor_quantile_returns"
    assert quantile["kind"] == "table_parquet"
    assert quantile["filename"] == "factor_quantile_returns.parquet"
    assert returns["kind"] == "returns_series_parquet"
    assert returns["filename"] == "returns_series.parquet"
    assert drawdown["metadata"]["series"]["namespace"] == "strategy.drawdown"
    assert positions["kind"] == "position_log_parquet"
    assert positions["filename"] == "positions.parquet"
    assert trades["kind"] == "trade_log_parquet"
    assert risk["kind"] == "risk_report_json"
    assert risk["filename"] == "risk_exposure.json"
    assert positions["content"].startswith(b"PAR1")


def test_core_sdk_helpers_update_run_and_summary(monkeypatch) -> None:
    from blackbox import capture_env, capture_git, capture_requirements, create_sweep, log, log_note, log_params, set_summary, set_tags

    logging_module = importlib.import_module("blackbox.logging")
    fake_run = FakeRunWithClient()
    monkeypatch.setattr(logging_module, "current_run", lambda: fake_run)

    assert log({"sharpe": 1.4}, client_event_id="met_once")[0]["client_event_id"] == "met_once"
    assert log_params({"hold_days": 5})["config"] == {"lookback": 10, "hold_days": 5}
    assert set_tags(["candidate"])["tags"] == ["candidate"]
    assert set_summary({"sharpe": 1.2})[0]["point"] == {"kind": "summary"}
    assert log_note("decision", "Promote", structured={"promote": True}, author_type="human")["author_type"] == "human"
    assert create_sweep("br_1", "grid", {"lookback": [10, 20]}, {"metric": "strategy.summary.sharpe"})["branch_id"] == "br_1"
    assert fake_run.metrics[-1]["namespace"] == "strategy.summary"
    assert fake_run.client.notes[-1]["structured"] == {"promote": True}
    assert fake_run.client.sweeps[-1]["objective"] == {"metric": "strategy.summary.sharpe"}
    assert capture_env()["hostname"]
    assert isinstance(capture_git(), dict)
    assert isinstance(capture_requirements(), dict)


def test_client_logging_payloads_accept_caller_ids_and_author_type() -> None:
    from blackbox import BlackboxClient

    client = BlackboxClient(endpoint="http://example.invalid")
    requests: list[dict[str, Any]] = []

    def fake_request(method: str, path: str, **kwargs: Any) -> Any:
        requests.append({"method": method, "path": path, **kwargs})
        return kwargs["json"]

    client.request = fake_request  # type: ignore[method-assign]

    event = client.log_event("run_1", "stage_completed", stage="train", payload={"rows": 10}, client_event_id="evt_once")
    metric = client.log_metric("run_1", "strategy.summary", {"sharpe": 1.23}, client_event_id="met_once")
    note = client.log_note("run_1", "decision", "Promote candidate", structured={"promote": True}, author_type="human", client_event_id="note_once")

    assert event["client_event_id"] == "evt_once"
    assert metric["client_event_id"] == "met_once"
    assert note["author_type"] == "human"
    assert note["client_event_id"] == "note_once"
    assert requests[0]["path"] == "/api/v1/runs/run_1/events"
    assert requests[1]["json"]["client_event_id"] == "met_once"
    assert requests[2]["json"]["structured"] == {"promote": True}
    assert requests[2]["json"]["client_event_id"] == "note_once"


def test_client_buffered_logging_flushes_in_order(monkeypatch) -> None:
    from blackbox import BlackboxClient

    client_module = importlib.import_module("blackbox.client")
    registered: list[Any] = []
    monkeypatch.setattr(client_module.atexit, "register", lambda func: registered.append(func))

    client = BlackboxClient(endpoint="http://example.invalid", buffered=True)
    requests: list[dict[str, Any]] = []

    def fake_request(method: str, path: str, **kwargs: Any) -> Any:
        requests.append({"method": method, "path": path, **kwargs})
        return {"path": path, **kwargs}

    client.request = fake_request  # type: ignore[method-assign]

    event = client.log_event("run_1", "stage_completed", stage="train", client_event_id="evt_once")
    metric = client.log_metric("run_1", "strategy.summary", {"sharpe": 1.23}, client_event_id="met_once")
    note = client.log_note("run_1", "decision", "Promote candidate", client_event_id="note_once")
    series = client.log_series("run_1", "returns", [{"date": "2026-01-01", "return": 0.01}], x="date", y="return")

    assert registered == [client._flush_at_exit]
    assert requests == []
    assert event["buffered"] is True
    assert metric[0]["buffered"] is True
    assert note["buffered"] is True
    assert series["buffered"] is True

    flushed = client.flush()

    assert len(flushed) == 4
    assert requests == [
        {"method": "POST", "path": "/api/v1/runs/run_1/events", "json": {"event_type": "stage_completed", "stage": "train", "payload": {}, "client_event_id": "evt_once"}},
        {
            "method": "POST",
            "path": "/api/v1/runs/run_1/metrics",
            "json": {"namespace": "strategy.summary", "values": {"sharpe": 1.23}, "point": {"kind": "summary"}, "client_event_id": "met_once"},
        },
        {"method": "POST", "path": "/api/v1/runs/run_1/notes", "json": {"kind": "decision", "summary": "Promote candidate", "content": None, "structured": {}, "author_type": "agent", "client_event_id": "note_once"}},
        {
            "method": "POST",
            "path": "/api/v1/runs/run_1/series",
            "json": {
                "name": "returns",
                "data": [{"date": "2026-01-01", "return": 0.01}],
                "x": "date",
                "y": "return",
                "namespace": None,
                "kind": "table_csv",
                "filename": None,
                "metadata": {},
            },
        },
    ]
    assert client.flush() == []


def test_client_finish_flushes_buffer_before_terminal_request() -> None:
    from blackbox import BlackboxClient

    client = BlackboxClient(endpoint="http://example.invalid", buffered=True)
    requests: list[dict[str, Any]] = []

    def fake_request(method: str, path: str, **kwargs: Any) -> Any:
        requests.append({"method": method, "path": path, **kwargs})
        return {"id": "run_1", "path": path}

    client.request = fake_request  # type: ignore[method-assign]

    client.log_event("run_1", "stage_completed", client_event_id="evt_once")
    client.finish("run_1")

    assert requests == [
        {"method": "POST", "path": "/api/v1/runs/run_1/events", "json": {"event_type": "stage_completed", "stage": None, "payload": {}, "client_event_id": "evt_once"}},
        {"method": "POST", "path": "/api/v1/runs/run_1/finish"},
    ]


def test_client_buffered_flush_preserves_unflushed_tail_on_error() -> None:
    from blackbox import BlackboxClient

    client = BlackboxClient(endpoint="http://example.invalid", buffered=True)
    requests: list[dict[str, Any]] = []

    def flaky_request(method: str, path: str, **kwargs: Any) -> Any:
        requests.append({"method": method, "path": path, **kwargs})
        if path.endswith("/metrics"):
            raise RuntimeError("temporary failure")
        return {"path": path}

    client.request = flaky_request  # type: ignore[method-assign]
    client.log_event("run_1", "stage_completed", client_event_id="evt_once")
    client.log_metric("run_1", "strategy.summary", {"sharpe": 1.23}, client_event_id="met_once")
    client.log_note("run_1", "decision", "Promote candidate")

    try:
        client.flush()
    except RuntimeError as exc:
        assert "temporary failure" in str(exc)
    else:
        raise AssertionError("flush should raise request errors")

    assert [item["path"] for item in client._buffer] == ["/api/v1/runs/run_1/metrics", "/api/v1/runs/run_1/notes"]

    client.request = lambda method, path, **kwargs: {"method": method, "path": path, **kwargs}  # type: ignore[method-assign]
    flushed = client.flush()

    assert [item["path"] for item in flushed] == ["/api/v1/runs/run_1/metrics", "/api/v1/runs/run_1/notes"]


def test_client_buffered_flush_retries_transient_failures(monkeypatch) -> None:
    from blackbox import BlackboxClient

    monkeypatch.setenv("BLACKBOX_FLUSH_RETRIES", "1")
    client = BlackboxClient(endpoint="http://example.invalid", buffered=True)
    attempts: list[str] = []

    def flaky_request(method: str, path: str, **kwargs: Any) -> Any:
        attempts.append(path)
        if len(attempts) == 1:
            raise RuntimeError("temporary failure")
        return {"method": method, "path": path, **kwargs}

    client.request = flaky_request  # type: ignore[method-assign]
    client.log_event("run_1", "stage_completed", client_event_id="evt_once")

    assert client.flush()[0]["path"] == "/api/v1/runs/run_1/events"
    assert attempts == ["/api/v1/runs/run_1/events", "/api/v1/runs/run_1/events"]
    assert client._buffer == []


def test_top_level_flush_is_exported() -> None:
    import blackbox as bb

    assert callable(bb.flush)


def test_run_context_exception_records_failure_note_before_fail() -> None:
    from blackbox import RunContext

    calls: list[dict[str, Any]] = []

    class FakeLifecycleClient:
        def start_run(self, **kwargs: Any) -> dict[str, Any]:
            calls.append({"action": "start_run", **kwargs})
            return {"id": "run_1"}

        def finish(self, run_id: str) -> dict[str, Any]:
            calls.append({"action": "finish", "run_id": run_id})
            return {"id": run_id, "status": "completed"}

        def log_note(
            self,
            run_id: str,
            kind: str,
            summary: str,
            content: str | None = None,
            structured: dict[str, Any] | None = None,
            author_type: str = "agent",
        ) -> dict[str, Any]:
            note = {"action": "log_note", "run_id": run_id, "kind": kind, "summary": summary, "content": content, "structured": structured or {}, "author_type": author_type}
            calls.append(note)
            return note

        def fail(self, run_id: str, error: dict[str, Any] | None = None) -> dict[str, Any]:
            calls.append({"action": "fail", "run_id": run_id, "error": error or {}})
            return {"id": run_id, "status": "failed"}

    try:
        with RunContext(client=FakeLifecycleClient(), project="proj", research="res", branch="main", name="failing"):
            raise ValueError("boom")
    except ValueError:
        pass
    else:
        raise AssertionError("context manager should re-raise user exceptions")

    assert [call["action"] for call in calls] == ["start_run", "log_note", "fail"]
    assert calls[1]["kind"] == "anomaly"
    assert calls[1]["author_type"] == "system"
    assert calls[1]["structured"]["error_type"] == "ValueError"
    assert calls[2]["error"]["message"] == "boom"


def test_client_register_external_artifact_sends_full_metadata() -> None:
    from blackbox import BlackboxClient

    client = BlackboxClient(endpoint="http://example.invalid")
    requests: list[dict[str, Any]] = []

    def fake_request(method: str, path: str, **kwargs: Any) -> Any:
        requests.append({"method": method, "path": path, **kwargs})
        return kwargs["json"]

    client.request = fake_request  # type: ignore[method-assign]

    result = client.register_external_artifact(
        "run_1",
        "hosted_report",
        "https://example.com/report.html",
        kind="report_html",
        metadata={"source": "external"},
        filename="report.html",
        mime_type="text/html",
        size_bytes=123,
        sha256="abc",
        preview={"title": "Report"},
        idempotency_key="external-once",
    )

    assert result == {
        "name": "hosted_report",
        "uri": "https://example.com/report.html",
        "kind": "report_html",
        "metadata": {"source": "external"},
        "filename": "report.html",
        "mime_type": "text/html",
        "size_bytes": 123,
        "sha256": "abc",
        "preview": {"title": "Report"},
    }
    assert requests[0]["path"] == "/api/v1/runs/run_1/artifacts/register-external"
    assert requests[0]["headers"] == {"Idempotency-Key": "external-once"}


def test_client_read_paths_match_api_contract() -> None:
    from blackbox import BlackboxClient

    client = BlackboxClient(endpoint="http://example.invalid")
    requests: list[dict[str, Any]] = []

    def fake_request(method: str, path: str, **kwargs: Any) -> Any:
        requests.append({"method": method, "path": path, **kwargs})
        return {"method": method, "path": path, **kwargs}

    client.request = fake_request  # type: ignore[method-assign]

    client.dashboard()
    client.get_run("run_1")
    client.search_runs(project_key="alpha", status=None, metrics=[{"metric": "strategy.summary.sharpe", "op": ">=", "value": 1.2}])
    client.search_researches(project_key="alpha", text="neutralization")
    client.compare_runs(["run_1", "run_2"], metrics=["strategy.summary.sharpe"], series=["returns"], with_config_diff=False)
    client.research_lineage("rsr_1")
    client.branch_lineage("br_1")
    client.get_sweep("swp_1")
    client.get_sweep_summary("swp_1")

    assert requests == [
        {"method": "GET", "path": "/api/v1/dashboard"},
        {"method": "GET", "path": "/api/v1/runs/run_1"},
        {
            "method": "POST",
            "path": "/api/v1/search/runs",
            "json": {"project_key": "alpha", "metrics": [{"metric": "strategy.summary.sharpe", "op": ">=", "value": 1.2}]},
        },
        {"method": "POST", "path": "/api/v1/search/researches", "json": {"project_key": "alpha", "text": "neutralization"}},
        {
            "method": "POST",
            "path": "/api/v1/compare/runs",
            "json": {"run_ids": ["run_1", "run_2"], "metrics": ["strategy.summary.sharpe"], "series": ["returns"], "with_config_diff": False},
        },
        {"method": "GET", "path": "/api/v1/lineage/researches/rsr_1"},
        {"method": "GET", "path": "/api/v1/lineage/branches/br_1"},
        {"method": "GET", "path": "/api/v1/sweeps/swp_1"},
        {"method": "GET", "path": "/api/v1/sweeps/swp_1/summary"},
    ]


def test_client_saved_view_paths_match_api_contract() -> None:
    from blackbox import BlackboxClient

    client = BlackboxClient(endpoint="http://example.invalid")
    requests: list[dict[str, Any]] = []

    def fake_request(method: str, path: str, **kwargs: Any) -> Any:
        requests.append({"method": method, "path": path, **kwargs})
        if path == "/api/v1/compare-sets/cmp_1":
            return {"id": "cmp_1", "run_ids_json": ["run_1", "run_2"], "layout_json": {"metrics": ["strategy.summary.sharpe"], "series": ["returns"]}}
        return {"method": method, "path": path, **kwargs}

    client.request = fake_request  # type: ignore[method-assign]

    client.create_compare_set("prj_1", "winners", ["run_1"], layout={"metrics": ["strategy.summary.sharpe"]})
    client.list_compare_sets("prj_1")
    client.get_compare_set("cmp_1")
    client.update_compare_set("cmp_1", name="updated", run_ids=["run_1", "run_2"])
    client.run_compare_set("cmp_1", with_config_diff=False)
    client.create_search_view("prj_1", "strong runs", {"project_key": "alpha"}, description="baseline")
    client.list_search_views("prj_1")
    client.get_search_view("svw_1")
    client.update_search_view("svw_1", description="updated")
    client.run_search_view("svw_1", overrides={"limit": 2})

    assert requests == [
        {
            "method": "POST",
            "path": "/api/v1/compare-sets",
            "json": {"project_id": "prj_1", "name": "winners", "run_ids": ["run_1"], "layout": {"metrics": ["strategy.summary.sharpe"]}},
        },
        {"method": "GET", "path": "/api/v1/projects/prj_1/compare-sets"},
        {"method": "GET", "path": "/api/v1/compare-sets/cmp_1"},
        {"method": "PATCH", "path": "/api/v1/compare-sets/cmp_1", "json": {"name": "updated", "run_ids": ["run_1", "run_2"]}},
        {"method": "GET", "path": "/api/v1/compare-sets/cmp_1"},
        {
            "method": "POST",
            "path": "/api/v1/compare/runs",
            "json": {"run_ids": ["run_1", "run_2"], "metrics": ["strategy.summary.sharpe"], "series": ["returns"], "with_config_diff": False},
        },
        {"method": "POST", "path": "/api/v1/search-views", "json": {"project_id": "prj_1", "name": "strong runs", "description": "baseline", "filters": {"project_key": "alpha"}}},
        {"method": "GET", "path": "/api/v1/projects/prj_1/search-views"},
        {"method": "GET", "path": "/api/v1/search-views/svw_1"},
        {"method": "PATCH", "path": "/api/v1/search-views/svw_1", "json": {"description": "updated"}},
        {"method": "POST", "path": "/api/v1/search-views/svw_1/run", "json": {"limit": 2}},
    ]


def test_top_level_read_helpers_use_default_client(monkeypatch) -> None:
    from blackbox import compare_runs, get_sweep_summary, search_runs

    logging_module = importlib.import_module("blackbox.logging")
    created_clients: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []

    class FakeQueryClient:
        def __init__(self, **kwargs: Any) -> None:
            created_clients.append(kwargs)

        def search_runs(self, **filters: Any) -> list[dict[str, Any]]:
            calls.append({"action": "search_runs", "filters": filters})
            return [{"id": "run_1"}]

        def compare_runs(
            self,
            run_ids: list[str],
            metrics: list[str] | None = None,
            series: list[str] | None = None,
            with_config_diff: bool = True,
        ) -> dict[str, Any]:
            calls.append({"action": "compare_runs", "run_ids": run_ids, "metrics": metrics, "series": series, "with_config_diff": with_config_diff})
            return {"runs": run_ids}

        def get_sweep_summary(self, sweep_id: str) -> dict[str, Any]:
            calls.append({"action": "get_sweep_summary", "sweep_id": sweep_id})
            return {"sweep_id": sweep_id}

    monkeypatch.setattr(logging_module, "BlackboxClient", FakeQueryClient)

    assert search_runs(endpoint="http://blackbox.local", token="secret", project_key="alpha") == [{"id": "run_1"}]
    assert compare_runs(["run_1"], metrics=["strategy.summary.sharpe"], with_config_diff=False) == {"runs": ["run_1"]}
    assert get_sweep_summary("swp_1") == {"sweep_id": "swp_1"}
    assert created_clients[0] == {"endpoint": "http://blackbox.local", "token": "secret", "offline": None, "spool_dir": None}
    assert calls == [
        {"action": "search_runs", "filters": {"project_key": "alpha"}},
        {"action": "compare_runs", "run_ids": ["run_1"], "metrics": ["strategy.summary.sharpe"], "series": None, "with_config_diff": False},
        {"action": "get_sweep_summary", "sweep_id": "swp_1"},
    ]


def test_top_level_saved_view_helpers_use_default_client(monkeypatch) -> None:
    from blackbox import create_compare_set, create_search_view, run_compare_set, run_search_view

    logging_module = importlib.import_module("blackbox.logging")
    calls: list[dict[str, Any]] = []

    class FakeSavedViewClient:
        def __init__(self, **kwargs: Any) -> None:
            calls.append({"action": "client", "kwargs": kwargs})

        def create_compare_set(self, project_id: str, name: str, run_ids: list[str], layout: dict[str, Any] | None = None) -> dict[str, Any]:
            calls.append({"action": "create_compare_set", "project_id": project_id, "name": name, "run_ids": run_ids, "layout": layout})
            return {"id": "cmp_1"}

        def run_compare_set(self, compare_set_id: str, metrics: list[str] | None = None, series: list[str] | None = None, with_config_diff: bool = True) -> dict[str, Any]:
            calls.append({"action": "run_compare_set", "compare_set_id": compare_set_id, "metrics": metrics, "series": series, "with_config_diff": with_config_diff})
            return {"id": compare_set_id}

        def create_search_view(self, project_id: str, name: str, filters: dict[str, Any], description: str | None = None) -> dict[str, Any]:
            calls.append({"action": "create_search_view", "project_id": project_id, "name": name, "filters": filters, "description": description})
            return {"id": "svw_1"}

        def run_search_view(self, view_id: str, overrides: dict[str, Any] | None = None) -> list[dict[str, Any]]:
            calls.append({"action": "run_search_view", "view_id": view_id, "overrides": overrides})
            return [{"id": "run_1"}]

    monkeypatch.setattr(logging_module, "BlackboxClient", FakeSavedViewClient)

    assert create_compare_set("prj_1", "winners", ["run_1"], layout={"metrics": ["strategy.summary.sharpe"]}) == {"id": "cmp_1"}
    assert run_compare_set("cmp_1", with_config_diff=False) == {"id": "cmp_1"}
    assert create_search_view("prj_1", "strong runs", {"project_key": "alpha"}, description="baseline") == {"id": "svw_1"}
    assert run_search_view("svw_1", overrides={"limit": 2}) == [{"id": "run_1"}]
    assert calls == [
        {"action": "client", "kwargs": {"endpoint": None, "token": None, "offline": None, "spool_dir": None}},
        {"action": "create_compare_set", "project_id": "prj_1", "name": "winners", "run_ids": ["run_1"], "layout": {"metrics": ["strategy.summary.sharpe"]}},
        {"action": "client", "kwargs": {"endpoint": None, "token": None, "offline": None, "spool_dir": None}},
        {"action": "run_compare_set", "compare_set_id": "cmp_1", "metrics": None, "series": None, "with_config_diff": False},
        {"action": "client", "kwargs": {"endpoint": None, "token": None, "offline": None, "spool_dir": None}},
        {"action": "create_search_view", "project_id": "prj_1", "name": "strong runs", "filters": {"project_key": "alpha"}, "description": "baseline"},
        {"action": "client", "kwargs": {"endpoint": None, "token": None, "offline": None, "spool_dir": None}},
        {"action": "run_search_view", "view_id": "svw_1", "overrides": {"limit": 2}},
    ]


def test_create_sweep_helper_can_use_default_client_without_active_run(monkeypatch) -> None:
    from blackbox import create_sweep

    logging_module = importlib.import_module("blackbox.logging")
    created_clients: list[dict[str, Any]] = []

    class FakeSweepClient:
        def __init__(self, **kwargs: Any) -> None:
            created_clients.append(kwargs)

        def create_sweep(
            self,
            branch_id: str,
            name: str,
            search_space: dict[str, Any] | None = None,
            objective: dict[str, Any] | None = None,
            status: str = "active",
        ) -> dict[str, Any]:
            return {
                "branch_id": branch_id,
                "name": name,
                "search_space": search_space or {},
                "objective": objective or {},
                "status": status,
            }

    monkeypatch.setattr(logging_module, "current_run", lambda: (_ for _ in ()).throw(RuntimeError("no active blackbox run")))
    monkeypatch.setattr(logging_module, "BlackboxClient", FakeSweepClient)

    sweep = create_sweep("br_1", "grid", {"lookback": [10]}, endpoint="http://blackbox.local", token="secret")

    assert sweep["name"] == "grid"
    assert created_clients == [{"endpoint": "http://blackbox.local", "token": "secret", "offline": None, "spool_dir": None}]


def test_client_download_artifact_writes_content(monkeypatch, tmp_path) -> None:
    from blackbox import BlackboxClient

    calls: list[dict[str, Any]] = []

    class FakeResponse:
        status_code = 200
        content = b"date,pnl\n2026-01-01,1.5\n"
        headers = {"content-type": "text/csv"}
        text = "ok"
        url = "https://storage.example/trades.csv"

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            calls.append({"client_kwargs": kwargs})

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def get(self, url: str, headers: dict[str, str]) -> FakeResponse:
            calls.append({"url": url, "headers": headers})
            return FakeResponse()

    client = BlackboxClient(endpoint="http://blackbox.local/", token="secret")
    monkeypatch.setattr(importlib.import_module("blackbox.client").httpx, "Client", FakeClient)
    output_path = tmp_path / "downloads" / "trades.csv"

    result = client.download_artifact("art_1", output_path)

    assert output_path.read_bytes() == FakeResponse.content
    assert result == {
        "artifact_id": "art_1",
        "path": str(output_path.resolve()),
        "size_bytes": len(FakeResponse.content),
        "content_type": "text/csv",
        "source_url": "https://storage.example/trades.csv",
    }
    assert calls == [
        {"client_kwargs": {"timeout": 30.0, "follow_redirects": True}},
        {"url": "http://blackbox.local/api/v1/artifacts/art_1/content", "headers": {"User-Agent": "blackbox-sdk/0.1.0", "Authorization": "Bearer secret"}},
    ]


def test_download_artifact_helper_can_use_default_client_without_active_run(monkeypatch, tmp_path) -> None:
    from blackbox import download_artifact

    logging_module = importlib.import_module("blackbox.logging")
    created_clients: list[dict[str, Any]] = []

    class FakeArtifactClient:
        def __init__(self, **kwargs: Any) -> None:
            created_clients.append(kwargs)

        def download_artifact(self, artifact_id: str, path: str) -> dict[str, Any]:
            return {"artifact_id": artifact_id, "path": path}

    monkeypatch.setattr(logging_module, "current_run", lambda: (_ for _ in ()).throw(RuntimeError("no active blackbox run")))
    monkeypatch.setattr(logging_module, "BlackboxClient", FakeArtifactClient)

    output_path = tmp_path / "report.html"
    result = download_artifact("art_1", str(output_path), endpoint="http://blackbox.local", token="secret")

    assert result == {"artifact_id": "art_1", "path": str(output_path)}
    assert created_clients == [{"endpoint": "http://blackbox.local", "token": "secret", "offline": None, "spool_dir": None}]


def test_client_reads_api_token_env_and_finish_status_contract(monkeypatch) -> None:
    from blackbox import BlackboxClient

    monkeypatch.delenv("BLACKBOX_TOKEN", raising=False)
    monkeypatch.setenv("BLACKBOX_API_TOKEN", "api-secret")
    client = BlackboxClient(endpoint="http://example.invalid")
    requests: list[dict[str, Any]] = []

    def fake_request(method: str, path: str, **kwargs: Any) -> Any:
        requests.append({"method": method, "path": path, **kwargs})
        return {"id": "run_1", "status": "completed"}

    client.request = fake_request  # type: ignore[method-assign]

    assert client.headers["Authorization"] == "Bearer api-secret"
    assert client.finish("run_1", status="completed")["status"] == "completed"
    assert requests == [{"method": "POST", "path": "/api/v1/runs/run_1/finish"}]

    try:
        client.finish("run_1", status="failed")
    except ValueError as exc:
        assert "use fail() or cancel()" in str(exc)
    else:
        raise AssertionError("finish should reject non-completed statuses")


def test_offline_spool_preserves_logging_ids_and_author_type(tmp_path) -> None:
    from blackbox import BlackboxClient

    client = BlackboxClient(offline=True, spool_dir=tmp_path)
    run = client.start_run(project="proj", research="res", branch="main", name="offline", created_by_type="agent", created_by_id="agent-alpha")

    client.log_event(run["id"], "stage_completed", client_event_id="evt_offline")
    client.log_metric(run["id"], "strategy.summary", {"sharpe": 1.0}, client_event_id="met_offline")
    client.log_note(run["id"], "observation", "Looks stable", author_type="human")

    manifest_path = tmp_path / "queue" / f"{run['id']}.json"
    mirror_path = tmp_path / "manifests" / f"{run['id']}.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert mirror_path.exists()
    assert run["created_by_type"] == "agent"
    assert run["created_by_id"] == "agent-alpha"
    assert manifest["run_create"]["created_by_id"] == "agent-alpha"
    assert manifest["events"][-1]["payload"]["client_event_id"] == "evt_offline"
    assert manifest["metrics"][-1]["payload"]["client_event_id"] == "met_offline"
    assert manifest["notes"][-1]["payload"]["author_type"] == "human"


def test_offline_spool_can_list_manifest_mirror_when_queue_is_missing(tmp_path) -> None:
    from blackbox import BlackboxClient
    from blackbox.offline import OfflineSpool

    client = BlackboxClient(offline=True, spool_dir=tmp_path)
    run = client.start_run(project="proj", research="res", branch="main", name="offline")
    (tmp_path / "queue" / f"{run['id']}.json").unlink()

    manifests = OfflineSpool(tmp_path).list_manifests()

    assert [item["local_run_id"] for item in manifests] == [run["id"]]
