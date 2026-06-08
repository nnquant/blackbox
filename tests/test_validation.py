from __future__ import annotations

from blackbox_common.validation import validate_metric_upload, validate_run_detail, validate_series_upload


def test_validate_run_detail_flags_incomplete_completed_performance_run() -> None:
    report = validate_run_detail(
        {
            "id": "run_1",
            "status": "completed",
            "summary_json": {"strategy.summary": {"sharpe": 1.2}},
            "artifacts": [],
        }
    )

    assert report["severity"] == "error"
    assert report["error_count"] == 2
    assert {issue["title"] for issue in report["issues"]} >= {
        "No typed run results",
        "Missing primary performance curve",
    }


def test_validate_run_detail_accepts_factor_only_result_without_performance_curve() -> None:
    report = validate_run_detail(
        {
            "id": "run_factor",
            "status": "completed",
            "summary_json": {"factor.summary": {"ic_mean": 0.03}},
            "artifacts": [
                {
                    "id": "art_1",
                    "name": "factor_ic_series",
                    "kind": "table_csv",
                    "metadata_json": {
                        "series": {"name": "factor_ic_series", "x": "date", "y": ["cumulative_ic"], "mode": "nav"},
                        "result": {"domain": "factor", "role": "ic_curve", "name": "primary_ic"},
                    },
                    "preview_json": {
                        "row_count": 2,
                        "rows": [
                            {"date": "2026-01-01", "cumulative_ic": 0.01},
                            {"date": "2026-01-02", "cumulative_ic": 0.02},
                        ],
                    },
                }
            ],
        }
    )

    assert report["severity"] == "ok"
    assert report["issues"] == []


def test_validate_run_detail_warns_on_decimal_percent_summary() -> None:
    report = validate_run_detail(
        {
            "id": "run_1",
            "status": "completed",
            "summary_json": {"strategy.summary": {"annual_return": 0.18}},
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
    )

    assert report["severity"] == "warning"
    issue = next(issue for issue in report["issues"] if issue["title"] == "annual_return may use decimal units")
    assert issue["code"] == "SUMMARY_PERCENT_DECIMAL_UNIT"
    assert issue["field"] == "strategy.summary.annual_return"
    assert "percentage points" in issue["fix"]


def test_validate_series_upload_warns_on_legacy_performance_contract() -> None:
    report = validate_series_upload(
        {
            "name": "equity_curve",
            "data": [{"date": "2026-01-01", "nav": 1.0}, {"date": "2026-01-02", "nav": 1.01}],
            "x": "date",
            "y": "nav",
            "mode": "nav",
            "namespace": "strategy.equity",
        }
    )

    assert report["severity"] == "warning"
    assert {issue["title"] for issue in report["issues"]} >= {
        "Performance curve does not use series_values",
        "Series upload has no result metadata",
    }
    by_title = {issue["title"]: issue for issue in report["issues"]}
    assert by_title["Performance curve does not use series_values"]["code"] == "PERFORMANCE_VALUE_COLUMN_NOT_SERIES_VALUES"
    assert by_title["Performance curve does not use series_values"]["field"] == "y"
    assert "series_values" in by_title["Performance curve does not use series_values"]["fix"]
    assert by_title["Series upload has no result metadata"]["code"] == "SERIES_RESULT_METADATA_MISSING"
    assert "result-domain performance" in by_title["Series upload has no result metadata"]["example"]


def test_validate_series_upload_strict_fails_on_agent_contract_warnings() -> None:
    report = validate_series_upload(
        {
            "name": "equity_curve",
            "data": [{"date": "2026-01-01", "nav": 1.0}, {"date": "2026-01-02", "nav": 1.01}],
            "x": "date",
            "y": "nav",
            "mode": "nav",
            "namespace": "strategy.equity",
        },
        strict=True,
    )

    assert report["severity"] == "error"
    assert report["error_count"] == 2


def test_validate_series_upload_fails_missing_value_column() -> None:
    report = validate_series_upload(
        {
            "name": "returns_series",
            "data": [{"date": "2026-01-01", "ret": 0.01}],
            "x": "date",
            "y": "series_values",
            "mode": "return",
        }
    )

    assert report["severity"] == "error"
    issue = next(issue for issue in report["issues"] if issue["title"] == "Series y column is missing")
    assert issue["code"] == "SERIES_Y_COLUMN_NOT_FOUND"
    assert issue["field"] == "y"
    assert "existing numeric column" in issue["fix"]


def test_validate_metric_upload_strict_fails_decimal_percent_units() -> None:
    report = validate_metric_upload("strategy.summary", {"annual_return": 0.18}, strict=True)

    assert report["severity"] == "error"
    assert any(issue["title"] == "annual_return may use decimal units" for issue in report["issues"])


def test_validate_run_detail_checks_expected_primary_series_range() -> None:
    report = validate_run_detail(
        {
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
        },
        expected_start="2026-01-03",
        expected_end="2026-01-05",
        expected_rows=3,
        primary_series_name="returns_series",
    )

    assert report["severity"] == "error"
    assert {issue["title"] for issue in report["issues"]} >= {
        "Primary curve name does not match expected series",
        "Primary curve row count does not match expected rows",
        "Primary curve start does not match expected date",
        "Primary curve end does not match expected date",
    }
