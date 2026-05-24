from __future__ import annotations

import os
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

from fastapi.testclient import TestClient


def test_api_e2e(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "blackbox.db"
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("BLACKBOX_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("BLACKBOX_ARTIFACT_ROOT", str(artifact_root))

    from blackbox_server.main import create_app

    with TestClient(create_app()) as client:
        workspaces = get(client, "/api/v1/workspaces")
        assert any(item["id"] == "local" for item in workspaces)
        workspace = post(
            client,
            "/api/v1/workspaces",
            {"id": "research-lab", "key": "research-lab", "title": "Research Lab", "roles": {"owner": ["agent"]}},
        )
        assert workspace["roles_json"] == {"owner": ["agent"]}
        workspace = patch(client, f"/api/v1/workspaces/{workspace['id']}", {"description": "Quant research workspace"})
        assert workspace["description"] == "Quant research workspace"
        project = post(
            client,
            "/api/v1/projects",
            {
                "workspace_id": workspace["id"],
                "key": "alpha-lab",
                "title": "Alpha Lab",
                "retention_policy": {"preview_retention_days": 365, "raw_artifact_retention_days": 90},
            },
        )
        assert project["workspace_id"] == "research-lab"
        assert project["retention_policy_json"] == {"preview_retention_days": 365, "raw_artifact_retention_days": 90}
        research = post(
            client,
            "/api/v1/researches",
            {"project_key": "alpha-lab", "key": "csi500-reversal", "title": "CSI500 Reversal"},
        )
        branch = post(
            client,
            "/api/v1/branches",
            {"research_id": research["id"], "key": "baseline-v1", "title": "Baseline V1"},
        )
        project = patch(
            client,
            f"/api/v1/projects/{project['id']}",
            {"title": "Alpha Lab Updated", "tags": ["live"], "retention_policy": {"preview_retention_days": 730}},
        )
        research = patch(client, f"/api/v1/researches/{research['id']}", {"status": "paused", "hypothesis": "Updated hypothesis"})
        branch = patch(client, f"/api/v1/branches/{branch['id']}", {"status": "paused", "reason_summary": "Updated branch reason"})
        assert project["title"] == "Alpha Lab Updated"
        assert project["retention_policy_json"] == {"preview_retention_days": 730}
        assert research["status"] == "paused"
        assert branch["reason_summary"] == "Updated branch reason"
        run = post(
            client,
            "/api/v1/runs",
            {
                "project_key": project["key"],
                "research_key": research["key"],
                "branch_key": branch["key"],
                "name": "lb20_hold5_fee10bp",
                "config": {"lookback": 20, "hold_days": 5},
                "context": {"asset_class": "CN_EQ", "frequency": "1d"},
                "tags": ["baseline", "reversal"],
                "created_by_type": "agent",
                "created_by_id": "agent-alpha",
            },
        )
        assert run["created_by_type"] == "agent"
        assert run["created_by_id"] == "agent-alpha"
        keyed_run = client.post(
            "/api/v1/runs",
            headers={"Idempotency-Key": "run-once"},
            json={"branch_id": branch["id"], "name": "idempotent-run-a", "config": {"lookback": 10}},
        )
        assert keyed_run.status_code == 200, keyed_run.text
        keyed_run_retry = client.post(
            "/api/v1/runs",
            headers={"Idempotency-Key": "run-once"},
            json={"branch_id": branch["id"], "name": "idempotent-run-b", "config": {"lookback": 99}},
        )
        assert keyed_run_retry.status_code == 200, keyed_run_retry.text
        assert keyed_run_retry.json()["data"]["id"] == keyed_run.json()["data"]["id"]
        assert keyed_run_retry.json()["data"]["name"] == "idempotent-run-a"
        assert keyed_run_retry.json()["data"]["config_json"] == {"lookback": 10}
        run = patch(client, f"/api/v1/runs/{run['id']}", {"title": "Updated run title", "tags": ["baseline", "reversal", "patched"]})
        assert run["title"] == "Updated run title"
        assert "patched" in run["tags"]
        invalid_event = client.post(
            f"/api/v1/runs/{run['id']}/events",
            json={"event_type": "custom_stage", "stage": "data_loaded", "payload": {"rows": 100}},
        )
        assert invalid_event.status_code == 422
        invalid_event_body = invalid_event.json()
        assert invalid_event_body["ok"] is False
        assert invalid_event_body["error"]["code"] == "VALIDATION_ERROR"
        post(
            client,
            f"/api/v1/runs/{run['id']}/events",
            {"event_type": "stage_completed", "stage": "data_loaded", "payload": {"rows": 100}},
        )
        metrics = post(
            client,
            f"/api/v1/runs/{run['id']}/metrics",
            {
                "namespace": "strategy.summary",
                "values": {"sharpe": 1.42, "max_drawdown": 0.09},
                "point": {"kind": "event", "name": "post_cost_backtest_done"},
            },
        )
        assert len(metrics) == 2
        oversized_metric = client.post(
            f"/api/v1/runs/{run['id']}/metrics",
            json={
                "namespace": "strategy.summary",
                "values": {"raw_frame": "x" * 70000},
                "point": {"kind": "summary"},
            },
        )
        assert oversized_metric.status_code == 422
        oversized_body = oversized_metric.json()
        assert oversized_body["ok"] is False
        assert oversized_body["error"]["code"] == "VALIDATION_ERROR"
        assert "log_series/log_table/log_artifact" in oversized_body["error"]["message"]
        direct_series_response = client.post(
            f"/api/v1/runs/{run['id']}/series",
            headers={"Idempotency-Key": "series-once"},
            json={
                "name": "equity_curve",
                "data": [{"date": f"2026-01-{day:02d}", "nav": round(1 + day * 0.01, 4)} for day in range(1, 26)],
                "x": "date",
                "y": "nav",
                "namespace": "strategy.equity",
                "result": {
                    "domain": "performance",
                    "name": "primary_performance",
                    "role": "primary_curve",
                    "group": "performance.primary",
                    "order": 10,
                },
            },
        )
        assert direct_series_response.status_code == 200, direct_series_response.text
        direct_series = direct_series_response.json()["data"]
        direct_series_retry = client.post(
            f"/api/v1/runs/{run['id']}/series",
            headers={"Idempotency-Key": "series-once"},
            json={
                "name": "equity_curve_retry",
                "data": [{"date": "2026-01-01", "nav": 9.99}],
                "x": "date",
                "y": "nav",
                "namespace": "strategy.equity",
            },
        )
        assert direct_series_retry.status_code == 200, direct_series_retry.text
        assert direct_series_retry.json()["data"]["id"] == direct_series["id"]
        assert direct_series_retry.json()["data"]["name"] == "equity_curve"
        assert direct_series["metadata_json"]["series"] == {"name": "equity_curve", "x": "date", "y": "nav", "mode": None, "namespace": "strategy.equity"}
        assert direct_series["metadata_json"]["result"] == {
            "domain": "performance",
            "name": "primary_performance",
            "role": "primary_curve",
            "group": "performance.primary",
            "order": 10,
        }
        assert direct_series["preview_json"]["columns"] == ["date", "nav"]
        assert direct_series["preview_json"]["row_count"] == 25
        assert len(direct_series["preview_json"]["rows"]) == 20
        parquet_series = post(
            client,
            f"/api/v1/runs/{run['id']}/series",
            {
                "name": "returns_series",
                "data": [{"date": "2026-01-01", "ret": 0.01}],
                "x": "date",
                "y": "ret",
                "namespace": "strategy.returns",
                "kind": "returns_series_parquet",
            },
        )
        assert parquet_series["filename"] == "returns_series.parquet"
        assert parquet_series["mime_type"] == "application/x-parquet"
        assert parquet_series["preview_json"]["format"] == "parquet"
        assert parquet_series["preview_json"]["preview_status"] == "ok"
        assert parquet_series["preview_json"]["columns"] == ["date", "ret"]
        note = post(
            client,
            f"/api/v1/runs/{run['id']}/notes",
            {"kind": "observation", "summary": "looks stable", "content": "Initial smoke conclusion.", "client_event_id": "note_once"},
        )
        repeated_note = post(
            client,
            f"/api/v1/runs/{run['id']}/notes",
            {"kind": "observation", "summary": "duplicate retry", "content": "Should return the original note.", "client_event_id": "note_once"},
        )
        assert note["summary"] == "looks stable"
        assert repeated_note["id"] == note["id"]
        assert repeated_note["summary"] == "looks stable"
        artifact_response = client.post(
            f"/api/v1/runs/{run['id']}/artifacts/upload?name=post_cost_report&kind=report_html&filename=report.html",
            headers={"Idempotency-Key": "artifact-upload-once"},
            content=b"<html><head><title>Report</title></head><body>ok</body></html>",
        )
        assert artifact_response.status_code == 200, artifact_response.text
        artifact = artifact_response.json()["data"]
        artifact_retry = client.post(
            f"/api/v1/runs/{run['id']}/artifacts/upload?name=post_cost_report_retry&kind=report_html&filename=retry.html",
            headers={"Idempotency-Key": "artifact-upload-once"},
            content=b"<html><head><title>Retry</title></head><body>duplicate</body></html>",
        )
        assert artifact_retry.status_code == 200, artifact_retry.text
        assert artifact_retry.json()["data"]["id"] == artifact["id"]
        assert artifact_retry.json()["data"]["name"] == "post_cost_report"
        assert artifact["preview_json"]["title"] == "Report"
        artifact_content = client.get(f"/api/v1/artifacts/{artifact['id']}/content")
        assert artifact_content.status_code == 200, artifact_content.text
        assert "text/html" in artifact_content.headers["content-type"]
        assert "<title>Report</title>" in artifact_content.text
        from blackbox_server.storage import local_path_from_file_uri

        local_path_from_file_uri(artifact["storage_uri"]).unlink()
        missing_artifact_content = client.get(f"/api/v1/artifacts/{artifact['id']}/content")
        assert missing_artifact_content.status_code == 404
        assert missing_artifact_content.json()["ok"] is False
        assert missing_artifact_content.json()["error"]["code"] == "NOT_FOUND"
        csv_artifact = post_bytes(
            client,
            f"/api/v1/runs/{run['id']}/artifacts/upload?name=trades&kind=table_csv&filename=trades.csv",
            b"date,symbol,pnl\n2026-01-01,000001,1.5\n2026-01-02,000002,-0.2\n",
        )
        assert csv_artifact["preview_json"]["format"] == "csv"
        assert csv_artifact["preview_json"]["columns"] == ["date", "symbol", "pnl"]
        assert csv_artifact["preview_json"]["row_count"] == 2
        assert csv_artifact["preview_json"]["rows"][0]["symbol"] == "000001"
        json_artifact = post_bytes(
            client,
            f"/api/v1/runs/{run['id']}/artifacts/upload?name=risk&kind=risk_report_json&filename=risk.json",
            b'{"var": 0.12, "exposure": {"size": 0.3}}',
        )
        assert json_artifact["preview_json"]["format"] == "json"
        assert json_artifact["preview_json"]["keys"] == ["exposure", "var"]
        png_artifact = post_bytes(
            client,
            f"/api/v1/runs/{run['id']}/artifacts/upload?name=plot&kind=image_png&filename=plot.png",
            (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
                b"\x00\x00\x00\x02\x00\x00\x00\x03"
                b"\x08\x02\x00\x00\x00\x00\x00\x00\x00"
            ),
        )
        assert png_artifact["preview_json"]["width"] == 2
        assert png_artifact["preview_json"]["height"] == 3
        init_upload = post(
            client,
            f"/api/v1/runs/{run['id']}/artifacts/init-upload",
            {"name": "external_report", "kind": "report_html", "filename": "external.html"},
        )
        completed_artifact_response = client.post(
            f"/api/v1/runs/{run['id']}/artifacts/complete-upload",
            headers={"Idempotency-Key": "artifact-complete-once"},
            json={
                "artifact_id": init_upload["artifact_id"],
                "name": "external_report",
                "kind": "report_html",
                "uri": "s3://blackbox/example/external.html",
                "filename": "external.html",
                "size_bytes": 123,
                "sha256": "abc",
            },
        )
        assert completed_artifact_response.status_code == 200, completed_artifact_response.text
        completed_artifact = completed_artifact_response.json()["data"]
        completed_artifact_retry = client.post(
            f"/api/v1/runs/{run['id']}/artifacts/complete-upload",
            headers={"Idempotency-Key": "artifact-complete-once"},
            json={
                "artifact_id": init_upload["artifact_id"],
                "name": "external_report_retry",
                "kind": "report_html",
                "uri": "s3://blackbox/example/retry.html",
                "filename": "retry.html",
                "size_bytes": 999,
                "sha256": "retry",
            },
        )
        assert completed_artifact_retry.status_code == 200, completed_artifact_retry.text
        assert completed_artifact_retry.json()["data"]["id"] == completed_artifact["id"]
        assert completed_artifact_retry.json()["data"]["name"] == "external_report"
        assert completed_artifact["id"] == init_upload["artifact_id"]
        external_artifact_response = client.post(
            f"/api/v1/runs/{run['id']}/artifacts/register-external",
            headers={"Idempotency-Key": "artifact-external-once"},
            json={
                "name": "external_report_ref",
                "kind": "report_html",
                "uri": "s3://blackbox/example/external-ref.html",
                "metadata": {"source": "e2e"},
            },
        )
        assert external_artifact_response.status_code == 200, external_artifact_response.text
        external_artifact = external_artifact_response.json()["data"]
        external_artifact_retry = client.post(
            f"/api/v1/runs/{run['id']}/artifacts/register-external",
            headers={"Idempotency-Key": "artifact-external-once"},
            json={
                "name": "external_report_ref_retry",
                "kind": "report_html",
                "uri": "s3://blackbox/example/retry-ref.html",
                "metadata": {"source": "retry"},
            },
        )
        assert external_artifact_retry.status_code == 200, external_artifact_retry.text
        assert external_artifact_retry.json()["data"]["id"] == external_artifact["id"]
        assert external_artifact_retry.json()["data"]["name"] == "external_report_ref"
        assert external_artifact["storage_uri"] == "s3://blackbox/example/external-ref.html"
        http_artifact = post(
            client,
            f"/api/v1/runs/{run['id']}/artifacts/register-external",
            {
                "name": "hosted_report",
                "kind": "report_html",
                "uri": "https://example.com/report.html",
                "metadata": {"source": "external"},
            },
        )
        http_content = client.get(f"/api/v1/artifacts/{http_artifact['id']}/content", follow_redirects=False)
        assert http_content.status_code in {302, 307}
        assert http_content.headers["location"] == "https://example.com/report.html"
        code_snapshot = post(
            client,
            f"/api/v1/runs/{run['id']}/snapshots/code",
            {"git_commit": "abc123", "git_dirty": True, "metadata": {"cwd": "D:/project/blackbox"}},
        )
        env_snapshot = post(
            client,
            f"/api/v1/runs/{run['id']}/snapshots/env",
            {"python_version": "3.12.7", "platform": "Windows", "hostname": "test-host", "packages": {"fastapi": "x"}},
        )
        assert code_snapshot["git_commit"] == "abc123"
        assert env_snapshot["hostname"] == "test-host"
        finished = post(client, f"/api/v1/runs/{run['id']}/finish", None)
        assert finished["status"] == "completed"
        finished_retry = post(client, f"/api/v1/runs/{run['id']}/finish", None)
        assert finished_retry["id"] == run["id"]
        assert finished_retry["status"] == "completed"
        fail_completed = client.post(f"/api/v1/runs/{run['id']}/fail", json={"message": "too late"})
        assert fail_completed.status_code == 409
        update_terminal_config = client.patch(f"/api/v1/runs/{run['id']}", json={"config": {"lookback": 99}})
        assert update_terminal_config.status_code == 409
        update_terminal_metadata = patch(client, f"/api/v1/runs/{run['id']}", {"title": "Reviewed completed run", "tags": ["baseline", "reviewed"]})
        assert update_terminal_metadata["title"] == "Reviewed completed run"
        assert update_terminal_metadata["config_json"] == {"lookback": 20, "hold_days": 5}
        assert update_terminal_metadata["tags"] == ["baseline", "reviewed"]
        terminal_note = post(
            client,
            f"/api/v1/runs/{run['id']}/notes",
            {"kind": "decision", "summary": "keep as baseline", "content": "Terminal runs can still receive review notes."},
        )
        assert terminal_note["summary"] == "keep as baseline"

        detail = get(client, f"/api/v1/runs/{run['id']}")
        assert detail["project_key"] == "alpha-lab"
        assert detail["research_key"] == "csi500-reversal"
        assert detail["branch_key"] == "baseline-v1"
        assert detail["artifact_count"] == 9
        assert detail["has_report_artifact"] is True
        assert "report_html" in detail["artifact_kinds"]
        assert detail["summary_json"]["strategy.summary"]["sharpe"] == 1.42
        assert len(detail["events"]) >= 3
        assert len(detail["artifacts"]) == 9
        detail_equity = next(item for item in detail["artifacts"] if item["name"] == "equity_curve")
        assert detail_equity["preview_json"]["row_count"] == 25
        assert len(detail_equity["preview_json"]["rows"]) == 25
        assert detail_equity["preview_json"]["rows"][-1]["date"] == "2026-01-25"
        assert len(detail["notes"]) == 2
        assert len(detail["snapshots"]["code"]) == 1
        assert len(detail["snapshots"]["env"]) == 1

        compare = post(
            client,
            "/api/v1/compare/runs",
            {"run_ids": [run["id"]], "metrics": ["strategy.summary.sharpe"], "series": ["equity_curve"], "with_config_diff": True},
        )
        assert compare["runs"][0]["project_key"] == "alpha-lab"
        assert compare["runs"][0]["research_key"] == "csi500-reversal"
        assert compare["runs"][0]["branch_key"] == "baseline-v1"
        assert compare["runs"][0]["artifact_count"] == 9
        assert compare["runs"][0]["has_report_artifact"] is True
        assert compare["metrics"]["strategy.summary.sharpe"][run["id"]] == 1.42
        assert compare["series"]["equity_curve"][run["id"]]["rows"][0]["nav"] == "1.01"
        assert len(compare["series"]["equity_curve"][run["id"]]["rows"]) == 25
        assert compare["series"]["equity_curve"][run["id"]]["rows"][-1]["date"] == "2026-01-25"
        quick_compare = post(
            client,
            "/api/v1/quick-compare",
            {
                "targets": [
                    {"type": "project", "id": project["id"]},
                    {"type": "research", "id": research["id"]},
                    {"type": "branch", "id": branch["id"]},
                    {"type": "run", "id": run["id"]},
                ],
                "metrics": ["strategy.summary.sharpe", "strategy.summary.max_drawdown"],
                "series": ["equity_curve", "drawdown"],
            },
        )
        assert [item["resolved_run"]["id"] for item in quick_compare["targets"]] == [run["id"], run["id"], run["id"], run["id"]]
        assert quick_compare["targets"][0]["label"] == "Alpha Lab Updated"
        assert quick_compare["targets"][1]["label"] == "CSI500 Reversal"
        assert quick_compare["targets"][2]["label"] == "Baseline V1"
        assert quick_compare["metrics"]["strategy.summary.sharpe"][run["id"]] == 1.42
        assert len(quick_compare["series"]["equity_curve"][run["id"]]["rows"]) == 25
        assert quick_compare["series"]["equity_curve"][run["id"]]["rows"][-1]["date"] == "2026-01-25"
        compared_report = next(item for item in compare["artifacts"][run["id"]] if item["name"] == "post_cost_report")
        assert compared_report["filename"] == "report.html"
        assert compared_report["preview_json"]["title"] == "Report"
        cloned = post(
            client,
            f"/api/v1/runs/{run['id']}/clone",
            {"name": "lb30_hold5_fee10bp", "config_overrides": {"lookback": 30}, "tags": ["clone"]},
        )
        assert cloned["source_run_id"] == run["id"]
        assert cloned["config_json"] == {"lookback": 30, "hold_days": 5}
        assert cloned["tags"] == ["clone"]
        cloned_detail = get(client, f"/api/v1/runs/{cloned['id']}")
        assert cloned_detail["source_run"]["id"] == run["id"]
        assert cloned_detail["source_run"]["branch_key"] == "baseline-v1"
        assert {"path": "lookback", "before": 20, "after": 30} in cloned_detail["source_config_diff"]
        compare_with_clone = post(
            client,
            "/api/v1/compare/runs",
            {"run_ids": [run["id"], cloned["id"]], "metrics": ["strategy.summary.sharpe"], "with_config_diff": True},
        )
        assert compare_with_clone["config_diff"]["lookback"] == {run["id"]: 20, cloned["id"]: 30}
        cloned_retry = client.post(
            f"/api/v1/runs/{run['id']}/clone",
            headers={"Idempotency-Key": "clone-once"},
            json={"name": "lb40_hold5_fee10bp", "config_overrides": {"lookback": 40}},
        )
        assert cloned_retry.status_code == 200, cloned_retry.text
        cloned_retry_again = client.post(
            f"/api/v1/runs/{run['id']}/clone",
            headers={"Idempotency-Key": "clone-once"},
            json={"name": "lb50_hold5_fee10bp", "config_overrides": {"lookback": 50}},
        )
        assert cloned_retry_again.json()["data"]["id"] == cloned_retry.json()["data"]["id"]
        assert cloned_retry_again.json()["data"]["name"] == "lb40_hold5_fee10bp"
        assert cloned_retry_again.json()["data"]["config_json"]["lookback"] == 40
        cancelled = post(client, f"/api/v1/runs/{cloned['id']}/cancel", {"reason": "superseded"})
        assert cancelled["status"] == "cancelled"
        cancelled_retry = post(client, f"/api/v1/runs/{cloned['id']}/cancel", {"reason": "retry"})
        assert cancelled_retry["id"] == cloned["id"]
        assert cancelled_retry["status"] == "cancelled"
        cancelled_detail = get(client, f"/api/v1/runs/{cloned['id']}")
        assert cancelled_detail["events"][-1]["event_type"] == "run_cancelled"
        assert cancelled_detail["events"][-1]["payload_json"] == {"reason": "superseded"}
        finish_cancelled = client.post(f"/api/v1/runs/{cloned['id']}/finish")
        assert finish_cancelled.status_code == 409
        failed_run = post(
            client,
            "/api/v1/runs",
            {
                "project_key": project["key"],
                "research_key": research["key"],
                "branch_key": branch["key"],
                "name": "failed_retry_contract",
            },
        )
        failed_once = post(client, f"/api/v1/runs/{failed_run['id']}/fail", {"message": "bad input"})
        assert failed_once["status"] == "failed"
        failed_retry = post(client, f"/api/v1/runs/{failed_run['id']}/fail", {"message": "retry"})
        assert failed_retry["id"] == failed_run["id"]
        assert failed_retry["status"] == "failed"
        cancel_failed = client.post(f"/api/v1/runs/{failed_run['id']}/cancel", json={"reason": "too late"})
        assert cancel_failed.status_code == 409
        sweep = post(
            client,
            "/api/v1/sweeps",
            {
                "branch_id": branch["id"],
                "name": "lookback-hold-grid",
                "search_space": {"lookback": [10, 20], "hold_days": [5]},
                "objective": {"metric": "strategy.summary.sharpe", "direction": "max"},
            },
        )
        sweep_run_2_source = post(
            client,
            "/api/v1/runs",
            {
                "project_key": project["key"],
                "research_key": research["key"],
                "branch_key": branch["key"],
                "name": "lb10_hold5_fee10bp",
                "config": {"lookback": 10, "hold_days": 5},
                "tags": ["sweep"],
            },
        )
        post(
            client,
            f"/api/v1/runs/{sweep_run_2_source['id']}/metrics",
            {
                "namespace": "strategy.summary",
                "values": {"sharpe": 1.05, "max_drawdown": 0.11},
                "point": {"kind": "event", "name": "post_cost_backtest_done"},
            },
        )
        post(client, f"/api/v1/runs/{sweep_run_2_source['id']}/finish", None)
        sweep_run = post(
            client,
            f"/api/v1/sweeps/{sweep['id']}/runs",
            {"run_id": run["id"], "coord": {"lookback": 20, "hold_days": 5}, "rank": 1},
        )
        sweep_run_2 = post(
            client,
            f"/api/v1/sweeps/{sweep['id']}/runs",
            {"run_id": sweep_run_2_source["id"], "coord": {"lookback": 10, "hold_days": 5}, "rank": 2},
        )
        assert sweep_run["rank"] == 1
        assert sweep_run_2["rank"] == 2
        sweep_detail = get(client, f"/api/v1/sweeps/{sweep['id']}")
        assert sweep_detail["run_count"] == 2
        assert {member["run_id"] for member in sweep_detail["members"]} == {run["id"], sweep_run_2_source["id"]}
        assert any(item["id"] == run["id"] and item["project_key"] == "alpha-lab" for item in sweep_detail["runs"])
        sweep_summary = get(client, f"/api/v1/sweeps/{sweep['id']}/summary")
        assert sweep_summary["objective"] == {"metric": "strategy.summary.sharpe", "direction": "max"}
        assert sweep_summary["heatmap"]["x_key"] == "lookback"
        assert sweep_summary["heatmap"]["y_key"] == "hold_days"
        assert len(sweep_summary["heatmap"]["cells"]) == 2
        assert sweep_summary["rows"][0]["run_id"] == run["id"]
        assert sweep_summary["rows"][0]["computed_rank"] == 1
        compare_set = post(
            client,
            "/api/v1/compare-sets",
            {"project_id": project["id"], "name": "baseline-compare", "run_ids": [run["id"]]},
        )
        assert compare_set["run_ids_json"] == [run["id"]]
        compare_sets = get(client, f"/api/v1/projects/{project['id']}/compare-sets")
        assert compare_sets[0]["name"] == "baseline-compare"
        compare_set_detail = get(client, f"/api/v1/compare-sets/{compare_set['id']}")
        assert compare_set_detail["id"] == compare_set["id"]
        patched_compare_set = patch(
            client,
            f"/api/v1/compare-sets/{compare_set['id']}",
            {"name": "updated-compare", "run_ids": [run["id"], sweep_run_2_source["id"]], "layout": {"metrics": ["strategy.summary.sharpe"]}},
        )
        assert patched_compare_set["name"] == "updated-compare"
        assert patched_compare_set["run_ids_json"] == [run["id"], sweep_run_2_source["id"]]
        assert patched_compare_set["layout_json"] == {"metrics": ["strategy.summary.sharpe"]}
        search = post(
            client,
            "/api/v1/search/runs",
            {
                "project_key": "alpha-lab",
                "research_key": "csi500-reversal",
                "branch_key": "baseline-v1",
                "tags": ["baseline"],
                "config": {"lookback": 20},
                "context": {"asset_class": "CN_EQ"},
                "author_type": "agent",
                "created_after": "2000-01-01T00:00:00Z",
                "created_before": "2999-01-01T00:00:00Z",
                "metrics": [{"metric": "strategy.summary.sharpe", "op": ">=", "value": 1.4}],
                "has_artifact": "report_html",
            },
        )
        assert [item["id"] for item in search] == [run["id"]]
        assert search[0]["project_key"] == "alpha-lab"
        assert search[0]["research_key"] == "csi500-reversal"
        assert search[0]["branch_key"] == "baseline-v1"
        assert search[0]["artifact_count"] == 9
        assert search[0]["has_report_artifact"] is True
        no_time_match = post(client, "/api/v1/search/runs", {"created_after": "2999-01-01T00:00:00Z"})
        assert no_time_match == []
        research_search = post(
            client,
            "/api/v1/search/researches",
            {"project_key": "alpha-lab", "status": "paused", "text": "updated", "limit": 5},
        )
        assert [item["id"] for item in research_search] == [research["id"]]
        assert research_search[0]["project_key"] == "alpha-lab"
        assert research_search[0]["branch_count"] == 1
        assert research_search[0]["run_count"] >= 1
        assert research_search[0]["champion_run"]["id"] == run["id"]
        search_view = post(
            client,
            "/api/v1/search-views",
            {
                "project_id": project["id"],
                "name": "strong baseline",
                "description": "post-cost sharpe >= 1.4",
                "filters": {
                    "project_key": "alpha-lab",
                    "research_key": "csi500-reversal",
                    "metrics": [{"metric": "strategy.summary.sharpe", "op": ">=", "value": 1.4}],
                    "limit": 10,
                },
            },
        )
        assert search_view["filters_json"]["limit"] == 10
        search_views = get(client, f"/api/v1/projects/{project['id']}/search-views")
        assert search_views[0]["name"] == "strong baseline"
        patched_view = patch(client, f"/api/v1/search-views/{search_view['id']}", {"description": "updated"})
        assert patched_view["description"] == "updated"
        search_view_results = post(client, f"/api/v1/search-views/{search_view['id']}/run", {})
        assert [item["id"] for item in search_view_results] == [run["id"]]
        assert search_view_results[0]["project_key"] == "alpha-lab"
        assert search_view_results[0]["research_key"] == "csi500-reversal"
        assert search_view_results[0]["branch_key"] == "baseline-v1"
        assert search_view_results[0]["artifact_count"] == 9
        assert search_view_results[0]["has_report_artifact"] is True
        dashboard = get(client, "/api/v1/dashboard")
        assert dashboard["summary"]["workspaces"] == 2
        assert dashboard["summary"]["projects"] == 1
        assert dashboard["summary"]["runs"] == 6
        assert dashboard["summary"]["today_runs"] == 6
        assert dashboard["summary"]["running_runs"] == 2
        assert dashboard["summary"]["failed_runs"] == 1
        assert dashboard["summary"]["failed_runs_24h"] == 1
        assert dashboard["summary"]["new_branches_24h"] == 1
        assert dashboard["summary"]["sweeps"] == 1
        assert dashboard["summary"]["compare_sets"] == 1
        assert dashboard["summary"]["search_views"] == 1
        assert dashboard["summary"]["notes"] == 2
        assert {item["key"] for item in dashboard["workspaces"]} == {"local", "research-lab"}
        assert dashboard["projects"][0]["workspace_key"] == "research-lab"
        assert dashboard["projects"][0]["research_count"] == 1
        assert dashboard["projects"][0]["branch_count"] == 1
        assert dashboard["projects"][0]["run_count"] == 6
        assert dashboard["projects"][0]["running_run_count"] == 2
        assert dashboard["projects"][0]["failed_run_count"] == 1
        assert dashboard["researches"][0]["run_count"] == 6
        assert dashboard["researches"][0]["run_count_7d"] == 6
        assert dashboard["researches"][0]["failed_run_count_7d"] == 1
        assert dashboard["researches"][0]["champion_run"]["id"] == run["id"]
        assert dashboard["branches"][0]["run_count"] == 6
        assert dashboard["sweeps"][0]["run_count"] == 2
        assert dashboard["runs"][0]["project_key"] == "alpha-lab"
        assert dashboard["runs"][0]["research_key"] == "csi500-reversal"
        assert any(item["id"] == run["id"] and item["has_report_artifact"] is True for item in dashboard["runs"])
        assert any(item["kind"] == "decision" and item["summary"] == "keep as baseline" and item["run_name"] == run["name"] for item in dashboard["notes"])
        project_detail = get(client, f"/api/v1/projects/{project['id']}")
        assert project_detail["workspace_key"] == "research-lab"
        assert project_detail["research_count"] == 1
        assert project_detail["branch_count"] == 1
        assert project_detail["run_count"] == 6
        assert [item["id"] for item in project_detail["researches"]] == [research["id"]]
        assert [item["id"] for item in project_detail["branches"]] == [branch["id"]]
        assert {item["id"] for item in project_detail["runs"]} >= {run["id"], sweep_run_2_source["id"]}
        assert project_detail["runs"][0]["project_key"] == "alpha-lab"
        assert project_detail["compare_sets"][0]["id"] == compare_set["id"]
        assert project_detail["search_views"][0]["id"] == search_view["id"]
        child_branch = post(
            client,
            "/api/v1/branches",
            {
                "research_id": research["id"],
                "key": "barra-neutralization",
                "title": "Barra Neutralization",
                "parent_branch_id": branch["id"],
                "source_run_id": run["id"],
                "reason_code": "hypothesis_change",
            },
        )
        agent_branch = post(
            client,
            "/api/v1/branches",
            {
                "key": "agent-barras-v2",
                "title": "Agent Barra V2",
                "source_run_id": run["id"],
                "reason_code": "agent_hypothesis",
            },
        )
        assert agent_branch["research_id"] == research["id"]
        assert agent_branch["parent_branch_id"] == branch["id"]
        assert agent_branch["source_run_id"] == run["id"]
        child_run = post(
            client,
            "/api/v1/runs",
            {"branch_id": child_branch["id"], "name": "barra-neutralized-run", "config": {"lookback": 20, "neutralization": "barra"}},
        )
        research_lineage = get(client, f"/api/v1/lineage/researches/{research['id']}")
        assert any(edge["to_branch_id"] == child_branch["id"] and edge["source_run_id"] == run["id"] for edge in research_lineage["edges"])
        assert any(item["id"] == run["id"] and item["branch_key"] == "baseline-v1" for item in research_lineage["runs"])
        branch_lineage = get(client, f"/api/v1/lineage/branches/{child_branch['id']}")
        assert branch_lineage["branch"]["id"] == child_branch["id"]
        assert branch_lineage["research"]["id"] == research["id"]
        assert branch_lineage["ancestor_branch_ids"] == [branch["id"]]
        assert [item["id"] for item in branch_lineage["branches"]] == [branch["id"], child_branch["id"]]
        assert child_run["id"] in {item["id"] for item in branch_lineage["runs"]}
        assert any(item["id"] == child_run["id"] and item["branch_key"] == "barra-neutralization" for item in branch_lineage["runs"])

        import blackbox as bb
        from blackbox.offline import OfflineSpool
        from blackbox_cli.sync import sync_manifest

        spool_dir = tmp_path / "spool"
        offline_report = tmp_path / "offline_report.html"
        offline_report.write_text(
            "<html><head><title>Offline Report</title></head><body>ok</body></html>",
            encoding="utf-8",
        )
        with bb.init(
            project="alpha-lab",
            research="csi500-reversal",
            branch="baseline-v1",
            name="offline-run",
            config={"lookback": 10},
            offline=True,
            spool_dir=spool_dir,
        ):
            bb.log_event("stage_completed", stage="data_loaded", payload={"rows": 10})
            bb.log_backtest_summary({"sharpe": 1.11})
            bb.log_artifact("offline_report", offline_report, kind="report_html")
            bb.log_table("positions", [{"date": "2026-01-01", "weight": 0.5}], kind="table_csv")
            bb.log_series("returns", [{"date": "2026-01-01", "ret": 0.01}], x="date", y="ret")
            bb.register_dataset(
                name="rqdata-cn-eq",
                version="2026-01-01",
                universe="CSI500",
                benchmark="CSI500",
                time_range={"start": "2020-01-01", "end": "2025-12-31"},
            )
            offline_sweep = bb.create_sweep(
                "baseline-v1",
                "offline-grid",
                search_space={"lookback": [10], "hold_days": [5]},
                objective={"metric": "strategy.summary.sharpe", "direction": "max"},
            )
            bb.attach_sweep(sweep["id"], coord={"lookback": 10, "hold_days": 5}, rank=3)
            bb.attach_sweep(offline_sweep["id"], coord={"lookback": 10, "hold_days": 5}, rank=1)

        spool = OfflineSpool(spool_dir)
        manifests = spool.list_manifests()
        assert len(manifests) == 1
        remote_run = sync_manifest(_ClientSyncAdapter(client), manifests[0])
        spool.mark_synced(manifests[0]["local_run_id"], remote_run["id"])

        synced_detail = get(client, f"/api/v1/runs/{remote_run['id']}")
        assert synced_detail["status"] == "completed"
        assert synced_detail["summary_json"]["strategy.summary"]["sharpe"] == 1.11
        offline_report_artifact = next(item for item in synced_detail["artifacts"] if item["name"] == "offline_report")
        assert offline_report_artifact["preview_json"]["title"] == "Offline Report"
        returns_artifact = next(item for item in synced_detail["artifacts"] if item["name"] == "returns")
        assert returns_artifact["metadata_json"]["series"] == {"name": "returns", "x": "date", "y": "ret", "mode": None, "namespace": None}
        series_compare = post(
            client,
            "/api/v1/compare/runs",
            {"run_ids": [remote_run["id"]], "series": ["returns"], "with_config_diff": False},
        )
        assert series_compare["series"]["returns"][remote_run["id"]]["x"] == "date"
        assert series_compare["series"]["returns"][remote_run["id"]]["rows"][0]["ret"] == "0.01"
        assert len(synced_detail["artifacts"]) == 3
        assert len(synced_detail["snapshots"]["code"]) == 1
        assert len(synced_detail["snapshots"]["data"]) == 1
        assert len(synced_detail["snapshots"]["env"]) == 1
        synced_sweep = get(client, f"/api/v1/sweeps/{sweep['id']}")
        assert remote_run["id"] in {item["run_id"] for item in synced_sweep["members"]}
        synced_sweep_summary = get(client, f"/api/v1/sweeps/{sweep['id']}/summary")
        assert any(item["run_id"] == remote_run["id"] and item["coord"] == {"lookback": 10, "hold_days": 5} for item in synced_sweep_summary["rows"])
        branch_sweeps = get(client, f"/api/v1/branches/{branch['id']}/sweeps")
        assert next(item for item in branch_sweeps if item["id"] == sweep["id"])["run_count"] == 3
        offline_remote_sweep = next(item for item in branch_sweeps if item["name"] == "offline-grid")
        assert offline_remote_sweep["run_count"] == 1
        offline_sweep_detail = get(client, f"/api/v1/sweeps/{offline_remote_sweep['id']}")
        assert remote_run["id"] in {item["run_id"] for item in offline_sweep_detail["members"]}
        offline_sweep_summary = get(client, f"/api/v1/sweeps/{offline_remote_sweep['id']}/summary")
        assert offline_sweep_summary["objective"] == {"metric": "strategy.summary.sharpe", "direction": "max"}
        assert offline_sweep_summary["rows"][0]["run_id"] == remote_run["id"]


def test_parquet_preview_uses_optional_pyarrow(monkeypatch) -> None:
    class FakeField:
        def __init__(self, name: str, field_type: str, nullable: bool = True):
            self.name = name
            self.type = field_type
            self.nullable = nullable

    class FakeSchema:
        names = ["date", "ret"]

        def field(self, name: str) -> FakeField:
            return {
                "date": FakeField("date", "date32[day]", False),
                "ret": FakeField("ret", "double", True),
            }[name]

    class FakeTable:
        def __init__(self, rows: list[dict]):
            self.rows = rows

        def slice(self, start: int, length: int):
            return FakeTable(self.rows[start : start + length])

        def to_pylist(self) -> list[dict]:
            return self.rows

    class FakeParquetFile:
        schema_arrow = FakeSchema()
        metadata = SimpleNamespace(num_rows=2, num_row_groups=1)

        def __init__(self, source):
            self.source = source

        def read(self) -> FakeTable:
            return FakeTable([{"date": "2026-01-01", "ret": 0.01}, {"date": "2026-01-02", "ret": -0.02}])

    pyarrow_module = ModuleType("pyarrow")
    pyarrow_module.__path__ = []
    pyarrow_module.BufferReader = lambda content: content
    parquet_module = ModuleType("pyarrow.parquet")
    parquet_module.ParquetFile = FakeParquetFile
    pyarrow_module.parquet = parquet_module
    monkeypatch.setitem(sys.modules, "pyarrow", pyarrow_module)
    monkeypatch.setitem(sys.modules, "pyarrow.parquet", parquet_module)

    from blackbox_server.main import build_preview

    preview = build_preview("returns.parquet", "application/x-parquet", b"PAR1fake")

    assert preview["format"] == "parquet"
    assert preview["preview_status"] == "ok"
    assert preview["columns"] == ["date", "ret"]
    assert preview["row_count"] == 2
    assert preview["row_group_count"] == 1
    assert preview["schema"] == [
        {"name": "date", "type": "date32[day]", "nullable": False},
        {"name": "ret", "type": "double", "nullable": True},
    ]
    assert preview["rows"][0] == {"date": "2026-01-01", "ret": 0.01}


def post(client: TestClient, path: str, payload: dict | None) -> dict:
    response = client.post(path, json=payload) if payload is not None else client.post(path)
    assert response.status_code < 400, response.text
    body = response.json()
    assert body["ok"], body
    return body["data"]


def post_bytes(client: TestClient, path: str, content: bytes) -> dict:
    response = client.post(path, content=content)
    assert response.status_code < 400, response.text
    body = response.json()
    assert body["ok"], body
    return body["data"]


def get(client: TestClient, path: str) -> dict:
    response = client.get(path)
    assert response.status_code < 400, response.text
    body = response.json()
    assert body["ok"], body
    return body["data"]


def patch(client: TestClient, path: str, payload: dict) -> dict:
    response = client.patch(path, json=payload)
    assert response.status_code < 400, response.text
    body = response.json()
    assert body["ok"], body
    return body["data"]


class _ClientSyncAdapter:
    def __init__(self, client: TestClient):
        self.client = client

    def request(self, method: str, path: str, **kwargs) -> dict:
        response = self.client.request(method, path, **kwargs)
        assert response.status_code < 400, response.text
        body = response.json()
        assert body["ok"], body
        return body["data"]
