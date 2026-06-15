from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path
from typing import Any


def test_bbox_source_entrypoint_help_runs() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "packages" / "cli" / "bbox.py"), "--help"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "usage: bbox" in result.stdout
    assert "sync" in result.stdout


def test_run_start_passes_idempotency_and_source_run(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"id": "run_1"}

    monkeypatch.setattr(cli_main, "request", fake_request)
    args = cli_main.build_parser().parse_args(
        [
            "run",
            "start",
            "--project",
            "alpha-lab",
            "--research",
            "reversal",
            "--branch",
            "baseline",
            "--name",
            "run-1",
            "--source-run-id",
            "run_source",
            "--config",
            '{"lookback":20}',
            "--context",
            '{"asset_class":"CN_EQ"}',
            "--idempotency-key",
            "task-1",
        ]
    )

    assert cli_main.dispatch(args) == {"id": "run_1"}
    assert calls == [
        {
            "method": "POST",
            "path": "/api/v1/runs",
            "headers": {"Idempotency-Key": "task-1"},
            "json": {
                "project_key": "alpha-lab",
                "research_key": "reversal",
                "branch_key": "baseline",
                "name": "run-1",
                "title": None,
                "source_run_id": "run_source",
                "config": {"lookback": 20},
                "context": {"asset_class": "CN_EQ"},
                "tags": [],
            },
        }
    ]


def test_run_start_and_branch_create_accept_created_by_id(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"id": path.rsplit("/", 1)[-1]}

    monkeypatch.setattr(cli_main, "request", fake_request)

    branch_args = cli_main.build_parser().parse_args(
        [
            "branch",
            "create",
            "--research",
            "reversal",
            "--key",
            "agent-v2",
            "--title",
            "Agent V2",
            "--created-by-type",
            "agent",
            "--created-by-id",
            "agent-alpha",
        ]
    )
    run_args = cli_main.build_parser().parse_args(
        [
            "run",
            "start",
            "--project",
            "alpha-lab",
            "--research",
            "reversal",
            "--branch",
            "agent-v2",
            "--name",
            "run-agent",
            "--created-by-type",
            "agent",
            "--created-by-id",
            "agent-alpha",
        ]
    )

    cli_main.dispatch(branch_args)
    cli_main.dispatch(run_args)

    assert calls[0]["json"]["created_by_type"] == "agent"
    assert calls[0]["json"]["created_by_id"] == "agent-alpha"
    assert calls[1]["json"]["created_by_type"] == "agent"
    assert calls[1]["json"]["created_by_id"] == "agent-alpha"


def test_run_start_accepts_yaml_config_file(monkeypatch, tmp_path) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"id": "run_yaml"}

    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "lookback: 20\n"
        "risk:\n"
        "  max_drawdown: 0.12\n"
        "features:\n"
        "  - momentum\n"
        "  - value\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cli_main, "request", fake_request)
    args = cli_main.build_parser().parse_args(
        [
            "run",
            "start",
            "--project",
            "alpha-lab",
            "--research",
            "reversal",
            "--branch",
            "baseline",
            "--name",
            "run-yaml",
            "--config-file",
            str(config_file),
        ]
    )

    assert cli_main.dispatch(args) == {"id": "run_yaml"}
    assert calls == [
        {
            "method": "POST",
            "path": "/api/v1/runs",
            "headers": {},
            "json": {
                "project_key": "alpha-lab",
                "research_key": "reversal",
                "branch_key": "baseline",
                "name": "run-yaml",
                "title": None,
                "source_run_id": None,
                "config": {"lookback": 20, "risk": {"max_drawdown": 0.12}, "features": ["momentum", "value"]},
                "context": {},
                "tags": [],
            },
        }
    ]


def test_run_update_and_clone_accept_yaml_config_files(monkeypatch, tmp_path) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"ok": True}

    update_file = tmp_path / "update.yml"
    update_file.write_text("lookback: 30\ncost_bp: 2\n", encoding="utf-8")
    overrides_file = tmp_path / "overrides.yaml"
    overrides_file.write_text("lookback: 40\nfilters:\n  universe: hs300\n", encoding="utf-8")
    monkeypatch.setattr(cli_main, "request", fake_request)

    update_args = cli_main.build_parser().parse_args(
        ["run", "update", "--run-id", "run_1", "--config-file", str(update_file)]
    )
    clone_args = cli_main.build_parser().parse_args(
        ["run", "clone", "--run-id", "run_1", "--config-overrides-file", str(overrides_file)]
    )

    assert cli_main.dispatch(update_args) == {"ok": True}
    assert cli_main.dispatch(clone_args) == {"ok": True}
    assert calls == [
        {"method": "PATCH", "path": "/api/v1/runs/run_1", "json": {"config": {"lookback": 30, "cost_bp": 2}}},
        {
            "method": "POST",
            "path": "/api/v1/runs/run_1/clone",
            "headers": {},
            "json": {
                "branch_id": None,
                "name": None,
                "title": None,
                "config_overrides": {"lookback": 40, "filters": {"universe": "hs300"}},
                "context_overrides": {},
                "tags": None,
            },
        },
    ]


def test_structured_file_parse_errors_are_validation_errors(tmp_path) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    invalid_yaml = tmp_path / "config.yaml"
    invalid_yaml.write_text("lookback: [20\n", encoding="utf-8")
    invalid_json = tmp_path / "config.json"
    invalid_json.write_text('{"lookback":', encoding="utf-8")

    for path in [invalid_yaml, invalid_json]:
        args = cli_main.build_parser().parse_args(
            [
                "run",
                "start",
                "--project",
                "alpha-lab",
                "--research",
                "reversal",
                "--branch",
                "baseline",
                "--name",
                "bad-config",
                "--config-file",
                str(path),
            ]
        )
        try:
            cli_main.dispatch(args)
        except cli_main.CliError as exc:
            assert exc.payload["code"] == "VALIDATION_ERROR"
        else:
            raise AssertionError(f"{path.name} should fail before request dispatch")


def test_branch_create_from_run_can_omit_research_and_use_reason_type_alias(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"id": "br_1"}

    monkeypatch.setattr(cli_main, "request", fake_request)
    args = cli_main.build_parser().parse_args(
        [
            "branch",
            "create",
            "--from-run",
            "run_source",
            "--key",
            "barra-neutralization",
            "--title",
            "Barra Neutralization",
            "--reason-type",
            "hypothesis_change",
        ]
    )

    assert cli_main.dispatch(args) == {"id": "br_1"}
    assert calls == [
        {
            "method": "POST",
            "path": "/api/v1/branches",
            "json": {
                "research_id": None,
                "research_key": None,
                "key": "barra-neutralization",
                "title": "Barra Neutralization",
                "source_run_id": "run_source",
                "parent_branch_id": None,
                "reason_code": "hypothesis_change",
                "reason_summary": None,
            },
        }
    ]


def test_run_clone_dispatches_clone_request(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"id": "run_clone"}

    monkeypatch.setattr(cli_main, "request", fake_request)
    args = cli_main.build_parser().parse_args(
        [
            "run",
            "clone",
            "--run-id",
            "run_source",
            "--name",
            "run-clone",
            "--branch-id",
            "branch_target",
            "--config-overrides",
            '{"lookback":40}',
            "--tags",
            '["clone"]',
            "--idempotency-key",
            "clone-once",
        ]
    )

    assert cli_main.dispatch(args) == {"id": "run_clone"}
    assert calls == [
        {
            "method": "POST",
            "path": "/api/v1/runs/run_source/clone",
            "headers": {"Idempotency-Key": "clone-once"},
            "json": {
                "branch_id": "branch_target",
                "name": "run-clone",
                "title": None,
                "config_overrides": {"lookback": 40},
                "context_overrides": {},
                "tags": ["clone"],
            },
        }
    ]


def test_run_cancel_dispatches_cancel_request(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"status": "cancelled"}

    monkeypatch.setattr(cli_main, "request", fake_request)
    args = cli_main.build_parser().parse_args(
        [
            "run",
            "cancel",
            "--run-id",
            "run_1",
            "--reason",
            '{"reason":"superseded"}',
        ]
    )

    assert cli_main.dispatch(args) == {"status": "cancelled"}
    assert calls == [
        {
            "method": "POST",
            "path": "/api/v1/runs/run_1/cancel",
            "json": {"reason": "superseded"},
        }
    ]


def test_run_log_event_and_metric_dispatch_client_event_id(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"ok": True}

    monkeypatch.setattr(cli_main, "request", fake_request)
    commands = [
        [
            "run",
            "log-event",
            "--run-id",
            "run_1",
            "--event-type",
            "stage_completed",
            "--stage",
            "backtest_done",
            "--payload",
            '{"coverage":0.93}',
            "--client-event-id",
            "evt_once",
        ],
        [
            "run",
            "log-metric",
            "--run-id",
            "run_1",
            "--namespace",
            "strategy.summary",
            "--values",
            '{"sharpe":1.2}',
            "--point",
            '{"kind":"summary"}',
            "--client-event-id",
            "met_once",
        ],
    ]
    for command in commands:
        assert cli_main.dispatch(cli_main.build_parser().parse_args(command)) == {"ok": True}

    assert calls == [
        {
            "method": "POST",
            "path": "/api/v1/runs/run_1/events",
            "json": {
                "event_type": "stage_completed",
                "stage": "backtest_done",
                "payload": {"coverage": 0.93},
                "client_event_id": "evt_once",
            },
        },
        {
            "method": "POST",
            "path": "/api/v1/runs/run_1/metrics",
            "json": {
                "namespace": "strategy.summary",
                "values": {"sharpe": 1.2},
                "point": {"kind": "summary"},
                "client_event_id": "met_once",
            },
        },
    ]


def test_run_log_series_dispatches_series_request(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"id": "art_1"}

    monkeypatch.setattr(cli_main, "request", fake_request)
    args = cli_main.build_parser().parse_args(
        [
            "run",
            "log-series",
            "--run-id",
            "run_1",
            "--name",
            "equity_curve",
            "--data",
            '[{"date":"2026-01-01","nav":1.01,"benchmark":1.0}]',
            "--x",
            "date",
            "--y",
            "nav,benchmark",
            "--mode",
            "nav",
            "--namespace",
            "strategy.equity",
            "--idempotency-key",
            "series-once",
        ]
    )

    assert cli_main.dispatch(args) == {"id": "art_1"}
    assert calls == [
        {
            "method": "POST",
            "path": "/api/v1/runs/run_1/series",
            "headers": {"Idempotency-Key": "series-once"},
            "json": {
                "name": "equity_curve",
                "data": [{"date": "2026-01-01", "nav": 1.01, "benchmark": 1.0}],
                "x": "date",
                "y": ["nav", "benchmark"],
                "mode": "nav",
                "namespace": "strategy.equity",
                "kind": "table_csv",
                "filename": None,
                "metadata": {},
            },
        }
    ]


def test_run_log_series_accepts_result_metadata(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"id": "art_1"}

    monkeypatch.setattr(cli_main, "request", fake_request)
    args = cli_main.build_parser().parse_args(
        [
            "run",
            "log-series",
            "--run-id",
            "run_1",
            "--name",
            "factor_ic_series",
            "--data",
            '[{"date":"2026-01-01","cumulative_ic":0.03}]',
            "--x",
            "date",
            "--y",
            "cumulative_ic",
            "--namespace",
            "factor.ic",
            "--result-domain",
            "factor",
            "--result-name",
            "primary_ic",
            "--result-role",
            "ic_curve",
            "--result-title",
            "Cumulative IC",
            "--result-group",
            "factor.primary",
            "--result-order",
            "10",
            "--result-view",
            '{"default":"plot","x":"date","y":"cumulative_ic"}',
        ]
    )

    assert cli_main.dispatch(args) == {"id": "art_1"}
    assert calls[0]["json"]["result"] == {
        "domain": "factor",
        "name": "primary_ic",
        "role": "ic_curve",
        "title": "Cumulative IC",
        "group": "factor.primary",
        "order": 10,
        "view": {"default": "plot", "x": "date", "y": "cumulative_ic"},
    }


def test_run_log_series_strict_contract_blocks_legacy_performance_upload(monkeypatch, capsys) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("request should not be sent after failed preflight")

    monkeypatch.setattr(cli_main, "request", fake_request)

    exit_code = cli_main.main(
        [
            "run",
            "log-series",
            "--run-id",
            "run_1",
            "--name",
            "equity_curve",
            "--data",
            '[{"date":"2026-01-01","nav":1.01}]',
            "--x",
            "date",
            "--y",
            "nav",
            "--mode",
            "nav",
            "--namespace",
            "strategy.equity",
            "--strict-contract",
        ]
    )

    assert exit_code == 4
    err = capsys.readouterr().err
    assert '"code": "VALIDATION_ERROR"' in err
    assert "PERFORMANCE_VALUE_COLUMN_NOT_SERIES_VALUES" in err
    assert "Performance curve does not use series_values" in err
    assert "Fix:" in err
    assert '"fix": "Use series_values as the preferred value column for performance curves."' in err


def test_run_log_series_skip_upload_validation_allows_manual_override(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"id": "art_1"}

    monkeypatch.setattr(cli_main, "request", fake_request)
    args = cli_main.build_parser().parse_args(
        [
            "run",
            "log-series",
            "--run-id",
            "run_1",
            "--name",
            "returns_series",
            "--data",
            '[{"date":"2026-01-01","ret":0.01}]',
            "--x",
            "date",
            "--y",
            "series_values",
            "--mode",
            "return",
            "--strict-contract",
            "--skip-upload-validation",
        ]
    )

    assert cli_main.dispatch(args) == {"id": "art_1"}
    assert calls[0]["json"]["y"] == "series_values"


def test_run_log_series_dry_run_validates_without_request(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("dry-run should not send request")

    monkeypatch.setattr(cli_main, "request", fake_request)
    args = cli_main.build_parser().parse_args(
        [
            "run",
            "log-series",
            "--run-id",
            "run_1",
            "--name",
            "equity_curve",
            "--data",
            '[{"date":"2026-01-01","series_values":1.0},{"date":"2026-01-02","series_values":1.01}]',
            "--x",
            "date",
            "--y",
            "series_values",
            "--mode",
            "nav",
            "--result-domain",
            "performance",
            "--result-name",
            "primary_performance",
            "--result-role",
            "primary_curve",
            "--strict-contract",
            "--dry-run",
        ]
    )

    result = cli_main.dispatch(args)

    assert result["dry_run"] is True
    assert result["kind"] == "series"
    assert result["validation"]["severity"] == "ok"


def test_run_log_metric_strict_contract_blocks_decimal_percent_units(monkeypatch, capsys) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    monkeypatch.setattr(cli_main, "request", lambda *args, **kwargs: {"ok": True})

    exit_code = cli_main.main(
        [
            "run",
            "log-metric",
            "--run-id",
            "run_1",
            "--namespace",
            "strategy.summary",
            "--values",
            '{"annual_return":0.18}',
            "--strict-contract",
        ]
    )

    assert exit_code == 4
    err = capsys.readouterr().err
    assert "annual_return may use decimal units" in err
    assert "SUMMARY_PERCENT_DECIMAL_UNIT" in err
    assert "percentage points" in err


def test_run_log_metric_dry_run_validates_without_request(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("dry-run should not send request")

    monkeypatch.setattr(cli_main, "request", fake_request)
    args = cli_main.build_parser().parse_args(
        [
            "run",
            "log-metric",
            "--run-id",
            "run_1",
            "--namespace",
            "strategy.summary",
            "--values",
            '{"annual_return":18.0,"max_drawdown":-9.0,"sharpe":1.2}',
            "--strict-contract",
            "--dry-run",
        ]
    )

    result = cli_main.dispatch(args)

    assert result["dry_run"] is True
    assert result["kind"] == "metric"
    assert result["validation"]["severity"] == "ok"


def test_artifact_get_and_note_list_dispatch_requests(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"ok": True}

    monkeypatch.setattr(cli_main, "request", fake_request)

    commands = [
        ["artifact", "get", "--artifact-id", "art_1"],
        ["note", "list", "--run-id", "run_1"],
    ]
    for command in commands:
        assert cli_main.dispatch(cli_main.build_parser().parse_args(command)) == {"ok": True}

    assert calls == [
        {"method": "GET", "path": "/api/v1/artifacts/art_1"},
        {"method": "GET", "path": "/api/v1/runs/run_1/notes"},
    ]


def test_run_validate_dispatches_run_detail_validation(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args, kwargs
        calls.append({"method": method, "path": path})
        return {
            "id": "run_1",
            "status": "completed",
            "summary_json": {"strategy.summary": {"sharpe": 1.2}},
            "artifacts": [],
        }

    monkeypatch.setattr(cli_main, "request", fake_request)
    args = cli_main.build_parser().parse_args(["run", "validate", "--run-id", "run_1"])

    report = cli_main.dispatch(args)

    assert calls == [{"method": "GET", "path": "/api/v1/runs/run_1"}]
    assert report["run_id"] == "run_1"
    assert report["severity"] == "error"
    assert report["error_count"] == 2


def test_run_validate_main_exits_nonzero_on_error(monkeypatch, capsys) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args, method, path, kwargs
        return {
            "id": "run_1",
            "status": "completed",
            "summary_json": {"strategy.summary": {"sharpe": 1.2}},
            "artifacts": [],
        }

    monkeypatch.setattr(cli_main, "request", fake_request)

    assert cli_main.main(["run", "validate", "--run-id", "run_1", "--compact"]) == 4
    assert '"severity": "error"' in capsys.readouterr().out


def test_run_validate_checks_expected_primary_series_range(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args, method, path, kwargs
        return {
            "id": "run_1",
            "status": "completed",
            "artifacts": [
                {
                    "id": "art_1",
                    "name": "equity_curve",
                    "kind": "table_csv",
                    "metadata_json": {
                        "series": {"name": "equity_curve", "x": "date", "y": ["series_values"], "mode": "nav"},
                        "result": {"domain": "performance", "role": "primary_curve", "name": "primary_performance"},
                    },
                    "preview_json": {
                        "row_count": 2,
                        "rows": [
                            {"date": "2026-01-01", "series_values": 1.0},
                            {"date": "2026-01-02", "series_values": 1.1},
                        ],
                    },
                }
            ],
        }

    monkeypatch.setattr(cli_main, "request", fake_request)
    args = cli_main.build_parser().parse_args(
        [
            "run",
            "validate",
            "--run-id",
            "run_1",
            "--expected-start",
            "2026-01-01",
            "--expected-end",
            "2026-01-03",
            "--expected-rows",
            "2",
            "--primary-series",
            "equity_curve",
        ]
    )

    report = cli_main.dispatch(args)

    assert report["severity"] == "error"
    assert any(issue["title"] == "Primary curve end does not match expected date" for issue in report["issues"])


def test_artifact_download_writes_content(monkeypatch, tmp_path) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    class FakeResponse:
        status_code = 200
        content = b"date,pnl\n2026-01-01,1.5\n"
        headers = {"content-type": "text/csv"}
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

    monkeypatch.setattr(cli_main.httpx, "Client", FakeClient)
    output_path = tmp_path / "downloads" / "trades.csv"
    args = cli_main.build_parser().parse_args(
        [
            "--endpoint",
            "http://blackbox.local/",
            "--token",
            "secret",
            "artifact",
            "download",
            "--artifact-id",
            "art_1",
            "--output-path",
            str(output_path),
        ]
    )

    result = cli_main.dispatch(args)

    assert output_path.read_bytes() == FakeResponse.content
    assert result == {
        "artifact_id": "art_1",
        "output_path": str(output_path.resolve()),
        "size_bytes": len(FakeResponse.content),
        "content_type": "text/csv",
        "source_url": "https://storage.example/trades.csv",
    }
    assert calls == [
        {"client_kwargs": {"timeout": 30.0, "follow_redirects": True}},
        {"url": "http://blackbox.local/api/v1/artifacts/art_1/content", "headers": {"Authorization": "Bearer secret"}},
    ]


def test_note_add_dispatches_structured_author_payload(monkeypatch, tmp_path) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"id": "note_1"}

    monkeypatch.setattr(cli_main, "request", fake_request)
    structured_file = tmp_path / "decision.json"
    structured_file.write_text('{"baseline":"run_0","candidate":"run_1","promote":true}', encoding="utf-8")
    args = cli_main.build_parser().parse_args(
        [
            "note",
            "add",
            "--run-id",
            "run_1",
            "--kind",
            "decision",
            "--summary",
            "Promote candidate",
            "--content",
            "Agent reviewed the comparison.",
            "--structured-file",
            str(structured_file),
            "--author-type",
            "agent",
            "--client-event-id",
            "note_once",
        ]
    )

    assert cli_main.dispatch(args) == {"id": "note_1"}
    assert calls == [
        {
            "method": "POST",
            "path": "/api/v1/runs/run_1/notes",
                "json": {
                    "kind": "decision",
                    "summary": "Promote candidate",
                    "content": "Agent reviewed the comparison.",
                    "structured": {"baseline": "run_0", "candidate": "run_1", "promote": True},
                    "author_type": "agent",
                    "client_event_id": "note_once",
                },
            }
        ]


def test_artifact_register_external_dispatches_request(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"id": "art_1"}

    monkeypatch.setattr(cli_main, "request", fake_request)
    args = cli_main.build_parser().parse_args(
        [
            "artifact",
            "register-external",
            "--run-id",
            "run_1",
            "--name",
            "hosted_report",
            "--uri",
            "https://example.com/report.html",
            "--kind",
            "report_html",
            "--filename",
            "report.html",
            "--mime-type",
            "text/html",
            "--size-bytes",
            "123",
            "--sha256",
            "abc",
            "--preview",
            '{"title":"Hosted"}',
            "--metadata",
            '{"source":"external"}',
            "--idempotency-key",
            "external-once",
        ]
    )

    assert cli_main.dispatch(args) == {"id": "art_1"}
    assert calls == [
        {
            "method": "POST",
            "path": "/api/v1/runs/run_1/artifacts/register-external",
            "headers": {"Idempotency-Key": "external-once"},
            "json": {
                "name": "hosted_report",
                "uri": "https://example.com/report.html",
                "kind": "report_html",
                "filename": "report.html",
                "mime_type": "text/html",
                "size_bytes": 123,
                "sha256": "abc",
                "preview": {"title": "Hosted"},
                "metadata": {"source": "external"},
            },
        }
    ]


def test_artifact_init_and_complete_upload_dispatch_requests(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"ok": True}

    monkeypatch.setattr(cli_main, "request", fake_request)

    commands = [
        [
            "artifact",
            "init-upload",
            "--run-id",
            "run_1",
            "--name",
            "report",
            "--kind",
            "report_html",
            "--filename",
            "report.html",
            "--metadata",
            '{"stage":"post_cost"}',
        ],
        [
            "artifact",
            "complete-upload",
            "--run-id",
            "run_1",
            "--artifact-id",
            "art_1",
            "--name",
            "report",
            "--kind",
            "report_html",
            "--uri",
            "s3://blackbox/run/run_1/artifacts/art_1/report.html",
            "--filename",
            "report.html",
            "--mime-type",
            "text/html",
            "--size-bytes",
            "123",
            "--sha256",
            "abc",
            "--preview",
            '{"title":"Report"}',
            "--metadata",
            '{"stage":"post_cost"}',
            "--idempotency-key",
            "complete-once",
        ],
    ]
    for command in commands:
        assert cli_main.dispatch(cli_main.build_parser().parse_args(command)) == {"ok": True}

    assert calls == [
        {
            "method": "POST",
            "path": "/api/v1/runs/run_1/artifacts/init-upload",
            "json": {
                "name": "report",
                "kind": "report_html",
                "filename": "report.html",
                "metadata": {"stage": "post_cost"},
            },
        },
        {
            "method": "POST",
            "path": "/api/v1/runs/run_1/artifacts/complete-upload",
            "headers": {"Idempotency-Key": "complete-once"},
            "json": {
                "artifact_id": "art_1",
                "name": "report",
                "kind": "report_html",
                "uri": "s3://blackbox/run/run_1/artifacts/art_1/report.html",
                "filename": "report.html",
                "mime_type": "text/html",
                "size_bytes": 123,
                "sha256": "abc",
                "preview": {"title": "Report"},
                "metadata": {"stage": "post_cost"},
            },
        },
    ]


def test_resource_get_commands_dispatch_requests(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"ok": True}

    monkeypatch.setattr(cli_main, "request", fake_request)

    commands = [
        ["project", "get", "--project-id", "proj_1"],
        ["research", "get", "--research-id", "rsr_1"],
        ["branch", "get", "--branch-id", "br_1"],
        ["run", "finish", "--run-id", "run_1", "--status", "completed"],
    ]
    for command in commands:
        assert cli_main.dispatch(cli_main.build_parser().parse_args(command)) == {"ok": True}

    assert calls == [
        {"method": "GET", "path": "/api/v1/projects/proj_1"},
        {"method": "GET", "path": "/api/v1/researches/rsr_1"},
        {"method": "GET", "path": "/api/v1/branches/br_1"},
        {"method": "POST", "path": "/api/v1/runs/run_1/finish"},
    ]


def test_run_finish_quality_gate_flags_dispatch_params(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"ok": True}

    monkeypatch.setattr(cli_main, "request", fake_request)

    args = cli_main.build_parser().parse_args(
        ["run", "finish", "--run-id", "run_1", "--fail-on-warning", "--skip-quality-gate"]
    )

    assert cli_main.dispatch(args) == {"ok": True}
    assert calls == [
        {
            "method": "POST",
            "path": "/api/v1/runs/run_1/finish",
            "params": {"fail_on_warning": True, "skip_quality_gate": True},
        }
    ]


def test_workspace_commands_dispatch_requests(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"ok": True}

    monkeypatch.setattr(cli_main, "request", fake_request)

    commands = [
        ["workspace", "create", "--id", "research-lab", "--key", "research-lab", "--title", "Research Lab", "--roles", '{"owner":["agent"]}'],
        ["workspace", "list"],
        ["workspace", "get", "--workspace-id", "research-lab"],
        ["workspace", "update", "--workspace-id", "research-lab", "--description", "updated"],
    ]
    for command in commands:
        assert cli_main.dispatch(cli_main.build_parser().parse_args(command)) == {"ok": True}

    assert calls == [
        {"method": "POST", "path": "/api/v1/workspaces", "json": {"id": "research-lab", "key": "research-lab", "title": "Research Lab", "description": None, "roles": {"owner": ["agent"]}}},
        {"method": "GET", "path": "/api/v1/workspaces"},
        {"method": "GET", "path": "/api/v1/workspaces/research-lab"},
        {"method": "PATCH", "path": "/api/v1/workspaces/research-lab", "json": {"description": "updated"}},
    ]


def test_project_create_dispatches_retention_policy(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"ok": True}

    monkeypatch.setattr(cli_main, "request", fake_request)
    args = cli_main.build_parser().parse_args(
        [
            "project",
            "create",
            "--workspace-id",
            "research-lab",
            "--key",
            "alpha",
            "--title",
            "Alpha",
            "--tags",
            '["live"]',
            "--retention-policy",
            '{"raw_artifact_retention_days":90}',
        ]
    )

    assert cli_main.dispatch(args) == {"ok": True}
    assert calls == [
        {
            "method": "POST",
            "path": "/api/v1/projects",
            "json": {
                "key": "alpha",
                "workspace_id": "research-lab",
                "title": "Alpha",
                "description": None,
                "tags": ["live"],
                "retention_policy": {"raw_artifact_retention_days": 90},
            },
        }
    ]


def test_update_commands_dispatch_patch_requests(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"ok": True}

    monkeypatch.setattr(cli_main, "request", fake_request)

    commands = [
        ["project", "update", "--project-id", "proj_1", "--title", "Updated", "--tags", '["live"]', "--retention-policy", '{"preview_retention_days":365}'],
        ["research", "update", "--research-id", "res_1", "--status", "paused", "--hypothesis", "new"],
        ["branch", "update", "--branch-id", "br_1", "--status", "rejected", "--expected-change", '{"sharpe":"down"}'],
        ["run", "update", "--run-id", "run_1", "--title", "patched", "--config", '{"lookback":30}'],
    ]
    for command in commands:
        assert cli_main.dispatch(cli_main.build_parser().parse_args(command)) == {"ok": True}

    assert calls == [
        {"method": "PATCH", "path": "/api/v1/projects/proj_1", "json": {"title": "Updated", "tags": ["live"], "retention_policy": {"preview_retention_days": 365}}},
        {"method": "PATCH", "path": "/api/v1/researches/res_1", "json": {"hypothesis": "new", "status": "paused"}},
        {"method": "PATCH", "path": "/api/v1/branches/br_1", "json": {"expected_change": {"sharpe": "down"}, "status": "rejected"}},
        {"method": "PATCH", "path": "/api/v1/runs/run_1", "json": {"title": "patched", "config": {"lookback": 30}}},
    ]


def test_search_view_commands_dispatch_requests(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"ok": True}

    monkeypatch.setattr(cli_main, "request", fake_request)

    commands = [
        ["search-view", "create", "--project-id", "proj_1", "--name", "winners", "--filters", '{"project_key":"alpha","limit":5}'],
        ["search-view", "list", "--project-id", "proj_1"],
        ["search-view", "run", "--view-id", "svw_1", "--overrides", '{"limit":2}'],
        ["search-view", "update", "--view-id", "svw_1", "--description", "updated"],
    ]
    for command in commands:
        assert cli_main.dispatch(cli_main.build_parser().parse_args(command)) == {"ok": True}

    assert calls == [
        {"method": "POST", "path": "/api/v1/search-views", "json": {"project_id": "proj_1", "name": "winners", "description": None, "filters": {"project_key": "alpha", "limit": 5}}},
        {"method": "GET", "path": "/api/v1/projects/proj_1/search-views"},
        {"method": "POST", "path": "/api/v1/search-views/svw_1/run", "json": {"limit": 2}},
        {"method": "PATCH", "path": "/api/v1/search-views/svw_1", "json": {"description": "updated"}},
    ]


def test_search_researches_dispatches_request(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"ok": True}

    monkeypatch.setattr(cli_main, "request", fake_request)
    args = cli_main.build_parser().parse_args(
        [
            "search",
            "researches",
            "--project",
            "alpha",
            "--status",
            "active",
            "--text",
            "neutralization",
            "--tag",
            "barra",
            "--limit",
            "10",
        ]
    )

    assert cli_main.dispatch(args) == {"ok": True}
    assert calls == [
        {
            "method": "POST",
            "path": "/api/v1/search/researches",
            "json": {
                "project_key": "alpha",
                "project_id": None,
                "status": "active",
                "key": None,
                "text": "neutralization",
                "tags": ["barra"],
                "limit": 10,
            },
        }
    ]


def test_search_runs_dispatches_full_dsl_request(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"ok": True}

    monkeypatch.setattr(cli_main, "request", fake_request)
    args = cli_main.build_parser().parse_args(
        [
            "search",
            "runs",
            "--project",
            "alpha",
            "--research",
            "reversal",
            "--branch",
            "baseline",
            "--status",
            "completed",
            "--author-type",
            "agent",
            "--created-after",
            "2026-01-01T00:00:00Z",
            "--created-before",
            "2026-12-31T23:59:59Z",
            "--context",
            "asset_class=CN_EQ",
            "--config",
            "lookback=20",
            "--metric",
            "strategy.summary.sharpe>=1.2",
            "--has-artifact",
            "report_html",
        ]
    )

    assert cli_main.dispatch(args) == {"ok": True}
    assert calls == [
        {
            "method": "POST",
            "path": "/api/v1/search/runs",
            "json": {
                "project_key": "alpha",
                "research_key": "reversal",
                "branch_key": "baseline",
                "status": "completed",
                "branch_id": None,
                "name": None,
                "author_type": "agent",
                "created_after": "2026-01-01T00:00:00Z",
                "created_before": "2026-12-31T23:59:59Z",
                "updated_after": None,
                "updated_before": None,
                "started_after": None,
                "started_before": None,
                "ended_after": None,
                "ended_before": None,
                "tags": [],
                "metrics": [{"metric": "strategy.summary.sharpe", "op": ">=", "value": 1.2}],
                "config": {"lookback": 20},
                "context": {"asset_class": "CN_EQ"},
                "has_artifact": "report_html",
                "limit": 50,
            },
        }
    ]


def test_search_runs_where_expression_maps_to_search_payload(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"ok": True}

    monkeypatch.setattr(cli_main, "request", fake_request)
    args = cli_main.build_parser().parse_args(
        [
            "search",
            "runs",
            "--project",
            "alpha",
            "--where",
            'metrics.strategy.summary.sharpe > 1.2 and tags contains "baseline" and config.lookback == 20 and context.asset_class = "CN_EQ" and author_type == agent and has_artifact(report_html)',
            "--limit",
            "10",
        ]
    )

    assert cli_main.dispatch(args) == {"ok": True}
    assert calls == [
        {
            "method": "POST",
            "path": "/api/v1/search/runs",
            "json": {
                "project_key": "alpha",
                "research_key": None,
                "branch_key": None,
                "status": None,
                "branch_id": None,
                "name": None,
                "author_type": "agent",
                "created_after": None,
                "created_before": None,
                "updated_after": None,
                "updated_before": None,
                "started_after": None,
                "started_before": None,
                "ended_after": None,
                "ended_before": None,
                "tags": ["baseline"],
                "metrics": [{"metric": "strategy.summary.sharpe", "op": ">", "value": 1.2}],
                "config": {"lookback": 20},
                "context": {"asset_class": "CN_EQ"},
                "has_artifact": "report_html",
                "limit": 10,
            },
        }
    ]


def test_search_runs_where_rejects_unsupported_clauses() -> None:
    cli_main = importlib.import_module("blackbox_cli.main")
    args = cli_main.build_parser().parse_args(["search", "runs", "--where", "tags > baseline"])

    try:
        cli_main.dispatch(args)
    except cli_main.CliError as exc:
        assert exc.payload["code"] == "VALIDATION_ERROR"
        assert "unsupported where clause" in exc.payload["message"]
    else:
        raise AssertionError("invalid where clause should fail before request dispatch")


def test_compare_runs_dispatches_series_request(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"ok": True}

    monkeypatch.setattr(cli_main, "request", fake_request)
    args = cli_main.build_parser().parse_args(
        [
            "compare",
            "runs",
            "--run-ids",
            "run_1,run_2",
            "--metrics",
            "strategy.summary.sharpe,strategy.summary.max_drawdown",
            "--series",
            "equity_curve,drawdown_series",
            "--with-config-diff",
        ]
    )

    assert cli_main.dispatch(args) == {"ok": True}
    assert calls == [
        {
            "method": "POST",
            "path": "/api/v1/compare/runs",
            "json": {
                "run_ids": ["run_1", "run_2"],
                "metrics": ["strategy.summary.sharpe", "strategy.summary.max_drawdown"],
                "series": ["equity_curve", "drawdown_series"],
                "with_config_diff": True,
            },
        }
    ]


def test_compare_runs_quality_gate_flags_dispatch_payload(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"ok": True}

    monkeypatch.setattr(cli_main, "request", fake_request)
    args = cli_main.build_parser().parse_args(
        ["compare", "runs", "--run-ids", "run_1", "--fail-on-warning", "--skip-quality-gate"]
    )

    assert cli_main.dispatch(args) == {"ok": True}
    assert calls == [
        {
            "method": "POST",
            "path": "/api/v1/compare/runs",
            "json": {
                "run_ids": ["run_1"],
                "metrics": [],
                "series": [],
                "with_config_diff": True,
                "fail_on_warning": True,
                "skip_quality_gate": True,
            },
        }
    ]


def test_compare_runs_accepts_space_separated_run_ids(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"ok": True}

    monkeypatch.setattr(cli_main, "request", fake_request)
    args = cli_main.build_parser().parse_args(
        [
            "compare",
            "runs",
            "--run-ids",
            "run_01A",
            "run_01B",
            "run_01C",
            "--metrics",
            "strategy.summary.sharpe",
        ]
    )

    assert cli_main.dispatch(args) == {"ok": True}
    assert calls == [
        {
            "method": "POST",
            "path": "/api/v1/compare/runs",
            "json": {
                "run_ids": ["run_01A", "run_01B", "run_01C"],
                "metrics": ["strategy.summary.sharpe"],
                "series": [],
                "with_config_diff": True,
            },
        }
    ]


def test_compare_runs_can_disable_config_diff(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"ok": True}

    monkeypatch.setattr(cli_main, "request", fake_request)
    args = cli_main.build_parser().parse_args(["compare", "runs", "--run-ids", "run_1,run_2", "--no-config-diff"])

    assert cli_main.dispatch(args) == {"ok": True}
    assert calls == [
        {
            "method": "POST",
            "path": "/api/v1/compare/runs",
            "json": {"run_ids": ["run_1", "run_2"], "metrics": [], "series": [], "with_config_diff": False},
        }
    ]


def test_sweep_summary_dispatches_request(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"rows": [], "heatmap": {}}

    monkeypatch.setattr(cli_main, "request", fake_request)
    args = cli_main.build_parser().parse_args(["sweep", "summary", "--sweep-id", "swp_1"])

    assert cli_main.dispatch(args) == {"rows": [], "heatmap": {}}
    assert calls == [{"method": "GET", "path": "/api/v1/sweeps/swp_1/summary"}]


def test_compare_set_get_and_update_dispatch_requests(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"ok": True}

    monkeypatch.setattr(cli_main, "request", fake_request)

    commands = [
        ["compare-set", "get", "--compare-set-id", "cmp_1"],
        ["compare-set", "update", "--compare-set-id", "cmp_1", "--name", "updated", "--research-id", "rsr_1", "--run-ids", "run_1,run_2", "--layout", '{"metrics":["strategy.summary.sharpe"]}'],
    ]
    for command in commands:
        assert cli_main.dispatch(cli_main.build_parser().parse_args(command)) == {"ok": True}

    assert calls == [
        {"method": "GET", "path": "/api/v1/compare-sets/cmp_1"},
        {
            "method": "PATCH",
            "path": "/api/v1/compare-sets/cmp_1",
            "json": {
                "name": "updated",
                "research_id": "rsr_1",
                "run_ids": ["run_1", "run_2"],
                "layout": {"metrics": ["strategy.summary.sharpe"]},
            },
        },
    ]


def test_compare_set_create_and_batch_compare_accept_space_separated_run_ids(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"ok": True}

    monkeypatch.setattr(cli_main, "request", fake_request)

    create_args = cli_main.build_parser().parse_args(
        ["compare-set", "create", "--project-id", "prj_1", "--research-id", "rsr_1", "--name", "winners", "--run-ids", "run_1", "run_2", "run_3"]
    )
    batch_args = cli_main.build_parser().parse_args(["batch", "compare", "--run-ids", "run_1", "run_2", "--metrics", "strategy.summary.sharpe"])

    assert cli_main.dispatch(create_args) == {"ok": True}
    assert cli_main.dispatch(batch_args)["success_count"] == 1
    assert calls == [
        {
            "method": "POST",
            "path": "/api/v1/compare-sets",
            "json": {"project_id": "prj_1", "research_id": "rsr_1", "name": "winners", "run_ids": ["run_1", "run_2", "run_3"], "layout": {}},
        },
        {
            "method": "POST",
            "path": "/api/v1/compare/runs",
            "json": {"run_ids": ["run_1", "run_2"], "metrics": ["strategy.summary.sharpe"], "series": [], "with_config_diff": True},
        },
    ]


def test_compare_set_run_uses_saved_layout(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        if method == "GET":
            return {
                "id": "cmp_1",
                "run_ids_json": ["run_1", "run_2"],
                "layout_json": {"metrics": ["strategy.summary.sharpe"], "series": ["equity_curve"]},
            }
        return {"ok": True}

    monkeypatch.setattr(cli_main, "request", fake_request)
    args = cli_main.build_parser().parse_args(["compare-set", "run", "--compare-set-id", "cmp_1"])

    assert cli_main.dispatch(args) == {"ok": True}
    assert calls == [
        {"method": "GET", "path": "/api/v1/compare-sets/cmp_1"},
        {
            "method": "POST",
            "path": "/api/v1/compare/runs",
            "json": {
                "run_ids": ["run_1", "run_2"],
                "metrics": ["strategy.summary.sharpe"],
                "series": ["equity_curve"],
                "with_config_diff": True,
            },
        },
    ]


def test_compare_set_run_allows_metric_and_series_overrides(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        if method == "GET":
            return {
                "id": "cmp_1",
                "run_ids_json": ["run_1"],
                "layout_json": {"metrics": ["old.metric"], "series": ["old_series"]},
            }
        return {"ok": True}

    monkeypatch.setattr(cli_main, "request", fake_request)
    args = cli_main.build_parser().parse_args(
        [
            "compare-set",
            "run",
            "--compare-set-id",
            "cmp_1",
            "--metrics",
            "strategy.summary.max_drawdown",
            "--series",
            "drawdown_series",
        ]
    )

    assert cli_main.dispatch(args) == {"ok": True}
    assert calls[-1] == {
        "method": "POST",
        "path": "/api/v1/compare/runs",
        "json": {
            "run_ids": ["run_1"],
            "metrics": ["strategy.summary.max_drawdown"],
            "series": ["drawdown_series"],
            "with_config_diff": True,
        },
    }


def test_compare_set_run_can_disable_config_diff(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        if method == "GET":
            return {
                "id": "cmp_1",
                "run_ids_json": ["run_1"],
                "layout_json": {"metrics": ["strategy.summary.sharpe"], "series": []},
            }
        return {"ok": True}

    monkeypatch.setattr(cli_main, "request", fake_request)
    args = cli_main.build_parser().parse_args(["compare-set", "run", "--compare-set-id", "cmp_1", "--no-config-diff"])

    assert cli_main.dispatch(args) == {"ok": True}
    assert calls[-1]["json"]["with_config_diff"] is False


def test_batch_add_note_and_mark_branch_status_dispatch_requests(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"id": path.rsplit("/", 1)[-1]}

    monkeypatch.setattr(cli_main, "request", fake_request)

    note_args = cli_main.build_parser().parse_args(
        [
            "batch",
            "add-note",
            "--run-ids",
            "run_1,run_2",
            "--kind",
            "decision",
            "--summary",
            "Promote candidate",
            "--content",
            "Both runs beat baseline.",
            "--structured",
            '{"baseline":"run_0","promote":true}',
            "--author-type",
            "agent",
        ]
    )
    branch_args = cli_main.build_parser().parse_args(
        [
            "batch",
            "mark-branch-status",
            "--branch-ids",
            "br_1,br_2",
            "--status",
            "accepted",
        ]
    )

    note_result = cli_main.dispatch(note_args)
    branch_result = cli_main.dispatch(branch_args)

    assert note_result["success_count"] == 2
    assert branch_result["success_count"] == 2
    assert calls == [
        {
            "method": "POST",
            "path": "/api/v1/runs/run_1/notes",
            "json": {"kind": "decision", "summary": "Promote candidate", "content": "Both runs beat baseline.", "structured": {"baseline": "run_0", "promote": True}, "author_type": "agent"},
        },
        {
            "method": "POST",
            "path": "/api/v1/runs/run_2/notes",
            "json": {"kind": "decision", "summary": "Promote candidate", "content": "Both runs beat baseline.", "structured": {"baseline": "run_0", "promote": True}, "author_type": "agent"},
        },
        {
            "method": "PATCH",
            "path": "/api/v1/branches/br_1",
            "json": {"status": "accepted"},
        },
        {
            "method": "PATCH",
            "path": "/api/v1/branches/br_2",
            "json": {"status": "accepted"},
        },
    ]


def test_batch_compare_dispatches_grouped_requests(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"matrix": []}

    monkeypatch.setattr(cli_main, "request", fake_request)
    args = cli_main.build_parser().parse_args(
        [
            "batch",
            "compare",
            "--groups",
            '[{"name":"baseline","run_ids":["run_1","run_2"],"metrics":["strategy.summary.sharpe"]},{"name":"risk","run_ids":"run_3,run_4","series":"drawdown"}]',
            "--metrics",
            "strategy.summary.max_drawdown",
            "--with-config-diff",
        ]
    )

    result = cli_main.dispatch(args)

    assert result["action"] == "compare"
    assert result["success_count"] == 2
    assert calls == [
        {
            "method": "POST",
            "path": "/api/v1/compare/runs",
            "json": {
                "run_ids": ["run_1", "run_2"],
                "metrics": ["strategy.summary.sharpe"],
                "series": [],
                "with_config_diff": True,
            },
        },
        {
            "method": "POST",
            "path": "/api/v1/compare/runs",
            "json": {
                "run_ids": ["run_3", "run_4"],
                "metrics": ["strategy.summary.max_drawdown"],
                "series": ["drawdown"],
                "with_config_diff": True,
            },
        },
    ]


def test_batch_compare_can_disable_config_diff(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"matrix": []}

    monkeypatch.setattr(cli_main, "request", fake_request)
    args = cli_main.build_parser().parse_args(["batch", "compare", "--run-ids", "run_1,run_2", "--no-config-diff"])

    result = cli_main.dispatch(args)

    assert result["success_count"] == 1
    assert calls[0]["json"]["with_config_diff"] is False


def test_lineage_commands_dispatch_requests(monkeypatch) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"ok": True}

    monkeypatch.setattr(cli_main, "request", fake_request)

    commands = [
        ["lineage", "research", "--research-id", "rsr_1"],
        ["lineage", "branch", "--branch-id", "br_1"],
    ]
    for command in commands:
        assert cli_main.dispatch(cli_main.build_parser().parse_args(command)) == {"ok": True}

    assert calls == [
        {"method": "GET", "path": "/api/v1/lineage/researches/rsr_1"},
        {"method": "GET", "path": "/api/v1/lineage/branches/br_1"},
    ]


def test_snapshot_add_and_list_dispatch_requests(monkeypatch, tmp_path) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"ok": True}

    monkeypatch.setattr(cli_main, "request", fake_request)
    payload_file = tmp_path / "env.json"
    payload_file.write_text('{"python_version":"3.11","hostname":"agent-host"}', encoding="utf-8")

    commands = [
        [
            "snapshot",
            "add",
            "--run-id",
            "run_1",
            "--kind",
            "code",
            "--payload",
            '{"git_commit":"abc123","git_dirty":true,"metadata":{"source":"cli"}}',
        ],
        [
            "snapshot",
            "add",
            "--run-id",
            "run_1",
            "--kind",
            "env",
            "--payload-file",
            str(payload_file),
        ],
        ["snapshot", "list", "--run-id", "run_1"],
    ]
    for command in commands:
        assert cli_main.dispatch(cli_main.build_parser().parse_args(command)) == {"ok": True}

    assert calls == [
        {
            "method": "POST",
            "path": "/api/v1/runs/run_1/snapshots/code",
            "json": {"git_commit": "abc123", "git_dirty": True, "metadata": {"source": "cli"}},
        },
        {
            "method": "POST",
            "path": "/api/v1/runs/run_1/snapshots/env",
            "json": {"python_version": "3.11", "hostname": "agent-host"},
        },
        {"method": "GET", "path": "/api/v1/runs/run_1/snapshots"},
    ]


def test_dataset_register_dispatches_data_snapshot(monkeypatch, tmp_path) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    calls: list[dict[str, Any]] = []

    def fake_request(args, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        del args
        calls.append({"method": method, "path": path, **kwargs})
        return {"ok": True}

    monkeypatch.setattr(cli_main, "request", fake_request)
    metadata_file = tmp_path / "metadata.json"
    metadata_file.write_text('{"vendor":"rqdata","adjustment":"post"}', encoding="utf-8")

    args = cli_main.build_parser().parse_args(
        [
            "dataset",
            "register",
            "--run-id",
            "run_1",
            "--dataset-name",
            "csi500_daily",
            "--dataset-version",
            "2026-05-20",
            "--fingerprint",
            "sha256:abc123",
            "--universe",
            "CSI500",
            "--benchmark",
            "000905.XSHG",
            "--calendar",
            "XSHG",
            "--fee-model",
            "stock_cn_v1",
            "--slippage-model",
            "bps_2",
            "--time-range",
            '{"start":"2020-01-01","end":"2026-05-20"}',
            "--metadata-file",
            str(metadata_file),
        ]
    )

    assert cli_main.dispatch(args) == {"ok": True}
    assert calls == [
        {
            "method": "POST",
            "path": "/api/v1/runs/run_1/snapshots/data",
            "json": {
                "dataset_name": "csi500_daily",
                "dataset_version": "2026-05-20",
                "fingerprint": "sha256:abc123",
                "universe": "CSI500",
                "benchmark": "000905.XSHG",
                "calendar": "XSHG",
                "fee_model": "stock_cn_v1",
                "slippage_model": "bps_2",
                "time_range": {"start": "2020-01-01", "end": "2026-05-20"},
                "metadata": {"vendor": "rqdata", "adjustment": "post"},
            },
        }
    ]


def test_output_select_and_table_formatting() -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    data = [
        {"id": "run_1", "name": "baseline", "summary_json": {"strategy.summary": {"sharpe": 1.2}}},
        {"id": "run_2", "name": "candidate", "summary_json": {"strategy.summary": {"sharpe": 1.4}}},
    ]

    selected = cli_main.apply_select(data, "id,summary_json.strategy.summary")
    assert selected == [
        {"id": "run_1", "summary_json.strategy.summary": {"sharpe": 1.2}},
        {"id": "run_2", "summary_json.strategy.summary": {"sharpe": 1.4}},
    ]
    table = cli_main.format_table(cli_main.apply_select(data, "id,name"))
    assert "id" in table
    assert "run_1" in table
    assert "candidate" in table


def test_main_accepts_global_options_after_subcommands(monkeypatch, capsys) -> None:
    cli_main = importlib.import_module("blackbox_cli.main")
    captured: list[dict[str, Any]] = []

    def fake_dispatch(args) -> list[dict[str, Any]]:
        captured.append(vars(args))
        return [{"id": "run_1", "name": "baseline"}]

    monkeypatch.setattr(cli_main, "dispatch", fake_dispatch)

    exit_code = cli_main.main(["search", "runs", "--project", "alpha", "--limit", "1", "--select", "id", "--compact"])

    assert exit_code == 0
    assert captured[0]["group"] == "search"
    assert captured[0]["action"] == "runs"
    assert captured[0]["select"] == "id"
    assert captured[0]["compact"] is True
    assert capsys.readouterr().out.strip() == '{"ok": true, "data": [{"id": "run_1"}], "error": null}'


def test_normalize_global_args_supports_equals_form() -> None:
    cli_main = importlib.import_module("blackbox_cli.main")

    assert cli_main.normalize_global_args(["compare", "runs", "--run-ids", "run_1", "run_2", "--select=id,name", "--output=table"]) == [
        "--select=id,name",
        "--output=table",
        "compare",
        "runs",
        "--run-ids",
        "run_1",
        "run_2",
    ]
