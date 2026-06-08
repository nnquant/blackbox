from __future__ import annotations

from datetime import datetime
from typing import Any


Issue = dict[str, Any]
PERFORMANCE_RESULT_NAMES = {"equity_curve", "returns_series", "pnl_series", "absolute_return_series"}
PERFORMANCE_MODES = {"nav", "return", "pnl"}
UPLOAD_CONTRACT_HINT = "Read issues[].code, issues[].field, issues[].fix, and issues[].example; fix the payload before retrying unchanged."

ISSUE_GUIDANCE: dict[str, dict[str, str]] = {
    "No typed run results": {
        "code": "RUN_RESULTS_MISSING",
        "field": "metadata.result",
        "fix": "Upload at least one artifact with metadata.result so Run Detail can classify the result.",
        "example": '{"result":{"domain":"performance","name":"primary_performance","role":"primary_curve"}}',
    },
    "Missing primary performance curve": {
        "code": "PERFORMANCE_PRIMARY_CURVE_MISSING",
        "field": "result.role",
        "fix": "Upload equity_curve, returns_series, pnl_series, or absolute_return_series with result.domain=performance and result.role=primary_curve.",
        "example": "bbox run log-series --name equity_curve --x date --y series_values --mode nav --result-domain performance --result-role primary_curve",
    },
    "Results are inferred from legacy artifact names": {
        "code": "RESULT_METADATA_INFERRED",
        "field": "metadata.result",
        "fix": "Add explicit metadata.result to every WebUI result artifact instead of relying on artifact names.",
    },
    "Some result artifacts use legacy inference": {
        "code": "RESULT_METADATA_PARTIAL",
        "field": "metadata.result",
        "fix": "Add explicit metadata.result to the remaining inferred artifacts.",
    },
    "Primary curve does not use series_values": {
        "code": "PRIMARY_CURVE_LEGACY_VALUE_COLUMN",
        "field": "series.y",
        "fix": "Rename or duplicate the plotted value column to series_values and pass --y series_values.",
    },
    "Series data is empty": {
        "code": "SERIES_DATA_EMPTY",
        "field": "data",
        "fix": "Provide a non-empty list of row objects. Do not upload an empty preview or a scalar.",
        "example": '[{"date":"2026-01-01","series_values":1.0}]',
    },
    "Series rows must be objects": {
        "code": "SERIES_ROWS_NOT_OBJECTS",
        "field": "data[]",
        "fix": "Convert every row into a JSON object keyed by column name.",
        "example": '[{"date":"2026-01-01","series_values":1.0}]',
    },
    "Series upload has no x column": {
        "code": "SERIES_X_MISSING",
        "field": "x",
        "fix": "Set x to the timestamp/date column used by plots and tables.",
        "example": "--x date",
    },
    "Series x column is missing": {
        "code": "SERIES_X_COLUMN_NOT_FOUND",
        "field": "x",
        "fix": "Set x to an existing row field or add that field to every uploaded row.",
    },
    "Series y column is missing": {
        "code": "SERIES_Y_COLUMN_NOT_FOUND",
        "field": "y",
        "fix": "Set y to existing numeric column(s), or add series_values to each row.",
        "example": '[{"date":"2026-01-01","series_values":1.0}]',
    },
    "Series y column is not numeric": {
        "code": "SERIES_Y_NOT_NUMERIC",
        "field": "y",
        "fix": "Convert the y column to finite numbers. Do not upload formatted strings like '18%' or '1,234'.",
    },
    "Performance curve name is non-standard": {
        "code": "PERFORMANCE_CURVE_NAME_NON_STANDARD",
        "field": "name",
        "fix": "Use equity_curve, returns_series, pnl_series, or absolute_return_series for primary performance curves.",
    },
    "Performance curve mode is missing or unsupported": {
        "code": "PERFORMANCE_MODE_INVALID",
        "field": "mode",
        "fix": "Set mode to nav for net value levels, return for decimal period returns, or pnl for absolute PnL/change series.",
        "example": "--mode nav",
    },
    "Performance curve does not use series_values": {
        "code": "PERFORMANCE_VALUE_COLUMN_NOT_SERIES_VALUES",
        "field": "y",
        "fix": "Use series_values as the preferred value column for performance curves.",
        "example": '[{"date":"2026-01-01","series_values":1.0}]',
    },
    "Series upload has no result metadata": {
        "code": "SERIES_RESULT_METADATA_MISSING",
        "field": "result",
        "fix": "Add typed result metadata so WebUI Results and Compare can classify this artifact.",
        "example": "--result-domain performance --result-name primary_performance --result-role primary_curve",
    },
    "Performance result metadata is incomplete": {
        "code": "PERFORMANCE_RESULT_METADATA_INCOMPLETE",
        "field": "result",
        "fix": "For primary performance curves set result.domain=performance and result.role=primary_curve.",
        "example": '{"domain":"performance","name":"primary_performance","role":"primary_curve"}',
    },
    "Result role is missing": {
        "code": "RESULT_ROLE_MISSING",
        "field": "result.role",
        "fix": "Set result.role to the role the WebUI should use, such as primary_curve, drawdown, ic_curve, comparison_table, or comparison_curve.",
    },
    "Series mode is not recognized": {
        "code": "SERIES_MODE_UNRECOGNIZED",
        "field": "mode",
        "fix": "Use nav, return, pnl, drawdown, ic, cumulative_ic, or level; otherwise omit mode for custom tables.",
    },
    "Metric values are empty": {
        "code": "METRIC_VALUES_EMPTY",
        "field": "values",
        "fix": "Provide a non-empty JSON object of scalar metric values.",
        "example": '{"sharpe":1.2,"annual_return":18.5}',
    },
}


def validate_run_detail(
    run: dict[str, Any],
    *,
    expected_start: str | None = None,
    expected_end: str | None = None,
    expected_rows: int | None = None,
    primary_series_name: str | None = None,
) -> dict[str, Any]:
    """Validate result data quality for a run detail payload."""
    issues: list[Issue] = []
    artifacts = list(run.get("artifacts") or [])
    result_items = run_result_items(artifacts)
    series_items = run_series_items(artifacts)
    primary_series = primary_series_item(series_items)
    completed = str(run.get("status") or "").lower() == "completed"
    explicit_result_count = sum(1 for artifact in artifacts if has_explicit_result_metadata(artifact))
    inferred_result_count = sum(1 for item in result_items if not has_explicit_result_metadata(item["artifact"]))
    expects_performance = run_expects_performance_result(run, result_items, series_items)

    if completed and not result_items:
        add_issue(issues, "error", "No typed run results", "Completed runs should publish result artifacts with metadata_json.result.")
    if completed and expects_performance and not primary_series:
        add_issue(issues, "error", "Missing primary performance curve", "Completed performance runs should include a chartable equity_curve, returns_series, or pnl_series.")
    if completed and result_items and explicit_result_count == 0:
        add_issue(issues, "warning", "Results are inferred from legacy artifact names", "Add metadata_json.result so WebUI and Compare do not depend on artifact-name guessing.")
    elif inferred_result_count:
        add_issue(issues, "warning", "Some result artifacts use legacy inference", f"{inferred_result_count} result artifact(s) should add explicit metadata_json.result.")

    if primary_series:
        validate_expected_primary_series(
            issues,
            primary_series,
            expected_start=expected_start,
            expected_end=expected_end,
            expected_rows=expected_rows,
            primary_series_name=primary_series_name,
        )
        if not has_series_values_column(primary_series):
            add_issue(issues, "warning", "Primary curve does not use series_values", "New uploads should use series_values with an explicit mode.")
        validate_series_item(issues, primary_series, label="Primary performance curve", critical=True, require_mode=completed, role="primary_curve")
    drawdown = drawdown_series_item(series_items)
    if drawdown and (not primary_series or drawdown.get("artifact_id") != primary_series.get("artifact_id")):
        validate_series_item(issues, drawdown, label="Drawdown series", critical=True, role="drawdown")
    checked = {item.get("artifact_id") for item in [primary_series, drawdown] if item}
    for item in series_items:
        if item.get("artifact_id") in checked:
            continue
        validate_series_item(issues, item, label=item.get("name") or item.get("artifact_name") or "Series artifact", role=(item.get("result") or {}).get("role"))
    validate_summary_units(issues, run)

    return validation_report(issues)


def validate_expected_primary_series(
    issues: list[Issue],
    item: dict[str, Any],
    *,
    expected_start: str | None = None,
    expected_end: str | None = None,
    expected_rows: int | None = None,
    primary_series_name: str | None = None,
) -> None:
    rows = item.get("rows") or []
    name = str(item.get("name") or item.get("artifact_name") or "")
    if primary_series_name and name != primary_series_name:
        add_issue(issues, "error", "Primary curve name does not match expected series", f"Expected {primary_series_name}, got {name or 'unknown'}.")
    if expected_rows is not None and len(rows) != expected_rows:
        add_issue(issues, "error", "Primary curve row count does not match expected rows", f"Expected {expected_rows} rows, got {len(rows)}.")
    x_key = item.get("x")
    if not x_key or not rows:
        return
    values = [row.get(str(x_key)) for row in rows if isinstance(row, dict) and row.get(str(x_key)) not in {None, ""}]
    if expected_start and (not values or str(values[0]) != expected_start):
        actual = str(values[0]) if values else "missing"
        add_issue(issues, "error", "Primary curve start does not match expected date", f"Expected {expected_start}, got {actual}.")
    if expected_end and (not values or str(values[-1]) != expected_end):
        actual = str(values[-1]) if values else "missing"
        add_issue(issues, "error", "Primary curve end does not match expected date", f"Expected {expected_end}, got {actual}.")


def validate_series_upload(payload: dict[str, Any], *, strict: bool = False) -> dict[str, Any]:
    """Validate a series upload payload before it is persisted."""
    issues: list[Issue] = []
    name = str(payload.get("name") or "")
    rows = payload.get("data")
    x_key = payload.get("x")
    y_keys = list_or_single(payload.get("y") or "series_values")
    mode = str(payload.get("mode") or "").lower()
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    domain = str(result.get("domain") or "").lower()
    role = str(result.get("role") or "").lower()
    namespace = str(payload.get("namespace") or "").lower()
    is_performance_primary = domain == "performance" and role == "primary_curve"
    is_performance_like = (
        is_performance_primary
        or name.lower() in PERFORMANCE_RESULT_NAMES
        or namespace.startswith(("strategy.equity", "strategy.returns", "strategy.pnl", "strategy.absolute_return"))
        or mode in PERFORMANCE_MODES
    )
    is_drawdown = role == "drawdown" or mode == "drawdown" or "drawdown" in name.lower()

    if not isinstance(rows, list) or not rows:
        add_issue(issues, "error", "Series data is empty", "Series uploads must provide a non-empty list of row objects.")
        return validation_report(issues)
    if any(not isinstance(row, dict) for row in rows):
        add_issue(issues, "error", "Series rows must be objects", "Every series row must be a JSON object with named columns.")
        return validation_report(issues)

    if not x_key:
        add_issue(issues, "error" if strict else "warning", "Series upload has no x column", "Set x to a date, datetime, trade_date, end_date, or time column.")
    elif not column_exists(rows, str(x_key)):
        add_issue(issues, "error", "Series x column is missing", f"Column {x_key} is not present in any uploaded row.")
    else:
        validate_x_values(issues, {"rows": rows, "x": x_key, "artifact_name": name, "name": name}, "Series upload", str(x_key))

    missing_y = [key for key in y_keys if not column_exists(rows, str(key))]
    if missing_y:
        add_issue(issues, "error", "Series y column is missing", f"Column(s) {', '.join(map(str, missing_y))} are not present in uploaded rows.")
    non_numeric_y = [key for key in y_keys if column_exists(rows, str(key)) and not any(is_finite_number(row.get(str(key))) for row in rows)]
    if non_numeric_y:
        add_issue(issues, "error", "Series y column is not numeric", f"Column(s) {', '.join(map(str, non_numeric_y))} do not contain finite numeric values.")

    if is_performance_like:
        if name not in PERFORMANCE_RESULT_NAMES:
            add_issue(issues, "warning", "Performance curve name is non-standard", "Use equity_curve, returns_series, pnl_series, or absolute_return_series for primary performance curves.")
        if mode not in PERFORMANCE_MODES:
            add_issue(issues, "error" if strict else "warning", "Performance curve mode is missing or unsupported", "Set mode to nav, return, or pnl.")
        if "series_values" not in {str(key).lower() for key in y_keys}:
            add_issue(issues, "error" if strict else "warning", "Performance curve does not use series_values", "Agent uploads should use series_values as the value column.")
        if not result:
            add_issue(issues, "error" if strict else "warning", "Series upload has no result metadata", "Add metadata.result so WebUI Results and Compare can classify this artifact.")
        elif not is_performance_primary:
            add_issue(issues, "error" if strict else "warning", "Performance result metadata is incomplete", "Set result.domain=performance and result.role=primary_curve for primary performance curves.")
    elif strict and domain and not role:
        add_issue(issues, "warning", "Result role is missing", "Typed result uploads should include result.role.")

    if mode and mode not in PERFORMANCE_MODES | {"drawdown", "ic", "cumulative_ic", "level"}:
        add_issue(issues, "warning", "Series mode is not recognized", "Use nav, return, pnl, or drawdown for performance-style series.")

    value_key = choose_upload_value_key(y_keys)
    if value_key:
        values = [number for number in (to_number(row.get(value_key)) for row in rows) if number is not None]
        if is_performance_like:
            validate_primary_mode(issues, {"artifact_name": name, "name": name}, "Series upload", value_key, values, mode)
        if is_drawdown:
            validate_drawdown_values(issues, {"artifact_name": name, "name": name}, "Series upload", values)

    return validation_report(issues)


def validate_metric_upload(namespace: str, values: dict[str, Any], *, strict: bool = False) -> dict[str, Any]:
    issues: list[Issue] = []
    if not isinstance(values, dict) or not values:
        add_issue(issues, "error", "Metric values are empty", "Metric uploads must provide a non-empty JSON object.")
        return validation_report(issues)
    if str(namespace or "").lower() == "strategy.summary":
        before = len(issues)
        validate_summary_units(issues, {"summary_json": {"strategy.summary": values}})
        if strict:
            for issue in issues[before:]:
                issue["severity"] = "error"
    return validation_report(issues)


def validation_report(issues: list[Issue]) -> dict[str, Any]:
    ordered = sorted(issues, key=lambda item: (severity_rank(item["severity"]), item["title"]))
    error_count = sum(1 for item in ordered if item["severity"] == "error")
    warning_count = sum(1 for item in ordered if item["severity"] == "warning")
    report = {
        "schema_version": 1,
        "severity": "error" if error_count else "warning" if warning_count else "ok",
        "error_count": error_count,
        "warning_count": warning_count,
        "issues": ordered,
    }
    if ordered:
        report["hint"] = UPLOAD_CONTRACT_HINT
    return report


def run_result_items(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for artifact in artifacts:
        result = artifact_result_metadata(artifact)
        if not result:
            continue
        domain = str(result.get("domain") or "custom").lower()
        role = str(result.get("role") or "artifact").lower()
        items.append({"artifact": artifact, "result": result, "domain": domain, "role": role})
    return items


def run_series_items(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for artifact in artifacts:
        metadata = artifact.get("metadata_json") or {}
        series = metadata.get("series") if isinstance(metadata.get("series"), dict) else None
        rows = (artifact.get("preview_json") or {}).get("rows")
        if not series or not isinstance(rows, list) or not rows:
            continue
        y_keys = series.get("y")
        if not isinstance(y_keys, list):
            y_keys = [y_keys or "series_values"]
        numeric_y = [key for key in y_keys if any(is_finite_number((row or {}).get(key)) for row in rows if isinstance(row, dict))]
        if not numeric_y:
            continue
        items.append(
            {
                "artifact": artifact,
                "artifact_id": artifact.get("id"),
                "artifact_name": artifact.get("name"),
                "name": series.get("name") or artifact.get("name"),
                "namespace": series.get("namespace"),
                "x": series.get("x"),
                "y": numeric_y,
                "mode": series.get("mode"),
                "rows": rows,
                "preview_row_count": (artifact.get("preview_json") or {}).get("row_count"),
                "result": artifact_result_metadata(artifact),
            }
        )
    return items


def artifact_result_metadata(artifact: dict[str, Any]) -> dict[str, Any] | None:
    metadata = artifact.get("metadata_json") or {}
    result = metadata.get("result")
    if isinstance(result, dict):
        return result
    series = metadata.get("series") if isinstance(metadata.get("series"), dict) else None
    metric = metadata.get("metric") if isinstance(metadata.get("metric"), dict) else None
    name = str((series or {}).get("name") or artifact.get("name") or "").lower()
    namespace = str((series or {}).get("namespace") or (metric or {}).get("namespace") or "").lower()
    kind = str(artifact.get("kind") or "").lower()
    if name in {"equity_curve", "returns_series", "returns", "pnl_series", "absolute_return_series"} or namespace.startswith(("strategy.returns", "strategy.pnl", "strategy.equity")):
        return {"domain": "performance", "name": "primary_performance", "role": "primary_curve"}
    if name in {"drawdown_series", "drawdown"} or "drawdown" in namespace or (series or {}).get("mode") == "drawdown":
        return {"domain": "performance", "name": "primary_drawdown", "role": "drawdown"}
    if "factor_ic" in name or namespace.startswith("factor.ic"):
        return {"domain": "factor", "name": (metric or {}).get("key") or "primary_ic", "role": "ic_curve"}
    if "quantile" in name or "group_return" in name or namespace.startswith("factor.quantile"):
        return {"domain": "factor", "name": (metric or {}).get("key") or "primary_quantile_returns", "role": "quantile_returns"}
    if "factor_comparison" in name or "factor_rank" in name or namespace.startswith("factor.batch"):
        return {"domain": "factor_batch", "name": (metric or {}).get("key") or name or "factor_comparison", "role": "comparison_curve" if series else "comparison_table"}
    if metric:
        domain = namespace.split(".")[0] or "custom"
        return {"domain": domain, "name": metric.get("key") or artifact.get("name"), "role": "metric_series" if metric.get("kind") == "series" else "metric_table"}
    if "report" in kind or "risk" in kind or "position" in kind or "trade" in kind:
        return {"domain": "risk" if "risk" in kind else "diagnostic", "name": artifact.get("name"), "role": "report" if "report" in kind else "table"}
    return None


def primary_series_item(series_items: list[dict[str, Any]]) -> dict[str, Any] | None:
    keys = ["series_values", "nav", "net_value", "equity", "value", "cumulative_return", "cum_return", "total_return", "return", "ret", "pnl", "profit", "delta", "change", "amount"]
    result = find_result_series(series_items, "performance", "primary_curve", keys)
    if result:
        return result
    names = ["equity_curve", "nav", "net_value", "cumulative_return", "returns_series", "returns", "pnl_series", "absolute_return_series", "pnl", "profit_series", "delta_series"]
    normalized = [name.lower() for name in names]
    for item in series_items:
        name = str(item.get("name") or "").lower()
        namespace = str(item.get("namespace") or "").lower()
        if (any(candidate in name for candidate in normalized) or namespace.startswith("strategy.")) and choose_series_key(item, keys):
            return item
    return None


def drawdown_series_item(series_items: list[dict[str, Any]]) -> dict[str, Any] | None:
    result = find_result_series(series_items, "performance", "drawdown", ["drawdown", "max_drawdown", "dd", "series_values"])
    if result:
        return result
    for item in series_items:
        name = str(item.get("name") or "").lower()
        namespace = str(item.get("namespace") or "").lower()
        mode = str(item.get("mode") or "").lower()
        if ("drawdown" in name or name == "dd" or "drawdown" in namespace or mode == "drawdown") and choose_series_key(item, ["drawdown", "max_drawdown", "dd", "series_values"]):
            return item
    return None


def find_result_series(items: list[dict[str, Any]], domain: str, role: str, keys: list[str]) -> dict[str, Any] | None:
    for item in items:
        result = item.get("result") or {}
        if str(result.get("domain") or "").lower() == domain and str(result.get("role") or "").lower() == role and choose_series_key(item, keys):
            return item
    return None


def find_series(items: list[dict[str, Any]], names: list[str], keys: list[str]) -> dict[str, Any] | None:
    normalized = [name.lower() for name in names]
    for item in items:
        name = str(item.get("name") or "").lower()
        if any(candidate in name for candidate in normalized) and choose_series_key(item, keys):
            return item
    for item in items:
        if choose_series_key(item, keys):
            return item
    return None


def choose_series_key(item: dict[str, Any], preferred: list[str]) -> str | None:
    keys = [key for key in item.get("y") or [] if any(is_finite_number((row or {}).get(key)) for row in item.get("rows") or [] if isinstance(row, dict))]
    if not keys:
        return None
    normalized = [key.lower() for key in preferred]
    for key in keys:
        if str(key).lower() in normalized:
            return key
    for key in keys:
        if any(pref in str(key).lower() for pref in normalized):
            return key
    return keys[0]


def choose_upload_value_key(y_keys: list[str]) -> str | None:
    if not y_keys:
        return None
    normalized = {str(key).lower(): str(key) for key in y_keys}
    for key in ["series_values", "nav", "return", "ret", "pnl", "change", "drawdown"]:
        if key in normalized:
            return normalized[key]
    return str(y_keys[0])


def validate_series_item(issues: list[Issue], item: dict[str, Any], *, label: str, critical: bool = False, require_mode: bool = False, role: str | None = None) -> None:
    rows = item.get("rows") or []
    row_count = to_number(item.get("preview_row_count"))
    if row_count is not None and row_count > len(rows):
        add_issue(issues, "error" if critical else "warning", f"{label} only has preview rows loaded", f"{item.get('artifact_name') or item.get('name')} exposes {len(rows)} of {int(row_count)} rows.")
    if len(rows) < 2:
        add_issue(issues, "error" if critical else "warning", f"{label} has too few rows", f"{item.get('artifact_name') or item.get('name')} has {len(rows)} row(s).")
    x_key = item.get("x")
    if not x_key:
        add_issue(issues, "warning", f"{label} has no x column", f"{item.get('artifact_name') or item.get('name')} should declare metadata.series.x or result.view.x.")
    else:
        validate_x_values(issues, item, label, str(x_key))
    value_key = choose_series_key(item, ["series_values", "nav", "return", "ret", "pnl", "change", "drawdown"])
    if not value_key:
        add_issue(issues, "error" if critical else "warning", f"{label} has no numeric value column", f"{item.get('artifact_name') or item.get('name')} should include numeric series_values or another declared y column.")
        return
    values = [number for number in (to_number((row or {}).get(value_key)) for row in rows if isinstance(row, dict)) if number is not None]
    mode = str(item.get("mode") or ((item.get("result") or {}).get("view") or {}).get("mode") or "").lower()
    if require_mode and not mode:
        add_issue(issues, "warning", f"{label} has no mode", f"{item.get('artifact_name') or item.get('name')} should declare mode=nav, return, or pnl.")
    if role == "primary_curve":
        validate_primary_mode(issues, item, label, value_key, values, mode)
    if role == "drawdown" or mode == "drawdown":
        validate_drawdown_values(issues, item, label, values)


def validate_x_values(issues: list[Issue], item: dict[str, Any], label: str, x_key: str) -> None:
    values = [(row or {}).get(x_key) for row in item.get("rows") or [] if isinstance(row, dict) and (row or {}).get(x_key) not in {None, ""}]
    if not values:
        add_issue(issues, "warning", f"{label} x column is empty", f"{item.get('artifact_name') or item.get('name')}.{x_key} has no non-empty values.")
        return
    seen: dict[str, int] = {}
    for value in values:
        key = str(value)
        seen[key] = seen.get(key, 0) + 1
    duplicates = sum(1 for count in seen.values() if count > 1)
    if duplicates:
        add_issue(issues, "warning", f"{label} has duplicate x values", f"{item.get('artifact_name') or item.get('name')}.{x_key} has {duplicates} duplicated timestamp/date value(s).")
    if is_date_like_column(x_key):
        invalid = sum(1 for value in values if parse_datetime(value) is None)
        if invalid:
            add_issue(issues, "warning", f"{label} has invalid date values", f"{item.get('artifact_name') or item.get('name')}.{x_key} has {invalid} value(s) that cannot be parsed as date/datetime.")


def validate_primary_mode(issues: list[Issue], item: dict[str, Any], label: str, value_key: str, values: list[float], mode: str) -> None:
    if not values:
        return
    if mode in {"nav", "equity", "net_value", "level"} and min(values) <= 0:
        add_issue(issues, "error", f"{label} has non-positive nav values", f"{item.get('artifact_name') or item.get('name')}.{value_key} declares mode={mode} but includes values <= 0.")
    if mode in {"return", "returns", "period_return", "periodic_return"} and max(abs(value) for value in values) > 1:
        add_issue(issues, "warning", f"{label} return values look too large", f"{item.get('artifact_name') or item.get('name')}.{value_key} declares return mode but has absolute values above 1.")


def validate_drawdown_values(issues: list[Issue], item: dict[str, Any], label: str, values: list[float]) -> None:
    if not values:
        return
    if max(values) > 0:
        add_issue(issues, "warning", f"{label} has positive drawdown values", f"{item.get('artifact_name') or item.get('name')} drawdown should usually be zero or negative.")
    if min(values) < -1.5:
        add_issue(issues, "warning", f"{label} drawdown unit looks suspicious", f"{item.get('artifact_name') or item.get('name')} drawdown is below -1.5. For nav/return runs use decimals such as -0.09.")


def validate_summary_units(issues: list[Issue], run: dict[str, Any]) -> None:
    for key in ["annual_return", "annualized_return", "annual_volatility", "annualized_volatility", "max_drawdown"]:
        value = first_summary_metric(run, [key])
        number = to_number(value)
        if number is None:
            continue
        if key != "max_drawdown" and 0 < abs(number) < 1:
            add_issue(issues, "warning", f"{key} may use decimal units", f"Summary {key} is {number}; percentage metrics should use percentage points, e.g. 18.5 means 18.50%.")
        if key == "max_drawdown" and -1 < number < 0:
            add_issue(issues, "warning", "max_drawdown may use decimal units", f"Summary max_drawdown is {number}; percentage metrics should use percentage points, e.g. -9.0 means -9.00%.")


def run_expects_performance_result(run: dict[str, Any], result_items: list[dict[str, Any]], series_items: list[dict[str, Any]]) -> bool:
    if any(item.get("domain") == "performance" for item in result_items):
        return True
    for item in series_items:
        name = str(item.get("name") or "").lower()
        namespace = str(item.get("namespace") or "").lower()
        if any(token in name for token in ["equity", "return", "pnl", "profit", "nav", "net_value"]) or namespace.startswith("strategy."):
            return True
    return any(first_summary_metric(run, [key]) is not None for key in ["sharpe", "annual_return", "annualized_return", "max_drawdown", "total_pnl", "annualized_pnl"])


def first_summary_metric(run: dict[str, Any], keys: list[str]) -> Any:
    summary = run.get("summary_json") or {}
    strategy = summary.get("strategy.summary") if isinstance(summary.get("strategy.summary"), dict) else {}
    for key in keys:
        if isinstance(strategy, dict) and key in strategy:
            return strategy[key]
    for namespace_values in summary.values() if isinstance(summary, dict) else []:
        if isinstance(namespace_values, dict):
            for key in keys:
                if key in namespace_values:
                    return namespace_values[key]
    return None


def has_explicit_result_metadata(artifact: dict[str, Any]) -> bool:
    result = (artifact.get("metadata_json") or {}).get("result")
    return isinstance(result, dict)


def has_series_values_column(item: dict[str, Any]) -> bool:
    return any(str(key).lower() == "series_values" for key in item.get("y") or [])


def list_or_single(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item not in {None, ""}]
    if value in {None, ""}:
        return []
    return [str(value)]


def column_exists(rows: list[dict[str, Any]], column: str) -> bool:
    return any(column in row for row in rows)


def add_issue(
    issues: list[Issue],
    severity: str,
    title: str,
    detail: str,
    *,
    code: str | None = None,
    field: str | None = None,
    fix: str | None = None,
    example: str | None = None,
) -> None:
    issue = {"severity": severity, "title": title, "detail": detail}
    guidance = issue_guidance(title)
    issue["code"] = code or guidance.get("code") or stable_issue_code(title)
    if field or guidance.get("field"):
        issue["field"] = field or guidance.get("field")
    if fix or guidance.get("fix"):
        issue["fix"] = fix or guidance.get("fix")
    if example or guidance.get("example"):
        issue["example"] = example or guidance.get("example")
    issues.append(issue)


def issue_guidance(title: str) -> dict[str, str]:
    if title in ISSUE_GUIDANCE:
        return ISSUE_GUIDANCE[title]
    if title.endswith("may use decimal units"):
        metric = title.removesuffix(" may use decimal units")
        return {
            "code": "SUMMARY_PERCENT_DECIMAL_UNIT",
            "field": f"strategy.summary.{metric}",
            "fix": "Upload percentage-style summary metrics in percentage points, not decimals.",
            "example": '{"annual_return":18.5,"annual_volatility":12.0,"max_drawdown":-9.0}',
        }
    if " only has preview rows loaded" in title:
        return {
            "code": "SERIES_PREVIEW_TRUNCATED",
            "field": "preview_json.rows",
            "fix": "Upload or expose the full series content for charting; preview rows must not be the only data source for curves.",
        }
    if " has too few rows" in title:
        return {"code": "SERIES_TOO_FEW_ROWS", "field": "data", "fix": "Upload at least two ordered rows for chartable series."}
    if " has no x column" in title:
        return {"code": "SERIES_X_MISSING", "field": "series.x", "fix": "Declare the x/date column in metadata.series.x or result.view.x."}
    if " x column is empty" in title:
        return {"code": "SERIES_X_EMPTY", "field": "x", "fix": "Populate non-empty timestamp/date values in the x column."}
    if " has duplicate x values" in title:
        return {"code": "SERIES_X_DUPLICATED", "field": "x", "fix": "Deduplicate or aggregate rows so each timestamp/date appears once per series."}
    if " has invalid date values" in title:
        return {"code": "SERIES_X_INVALID_DATE", "field": "x", "fix": "Use parseable ISO dates/datetimes such as 2026-01-01 or 2026-01-01T09:31:00."}
    if " has no numeric value column" in title:
        return {"code": "SERIES_VALUE_COLUMN_MISSING", "field": "series.y", "fix": "Declare y column(s) and make sure at least one contains finite numeric values."}
    if " has no mode" in title:
        return {"code": "SERIES_MODE_MISSING", "field": "mode", "fix": "Set mode=nav, return, or pnl for primary performance curves."}
    if " has non-positive nav values" in title:
        return {"code": "NAV_NON_POSITIVE", "field": "series_values", "fix": "For mode=nav, upload positive net-value levels. Use mode=pnl for absolute changes that can cross zero."}
    if " return values look too large" in title:
        return {"code": "RETURN_VALUES_TOO_LARGE", "field": "series_values", "fix": "For mode=return, upload decimal period returns such as 0.012. Use mode=pnl for absolute changes."}
    if " has positive drawdown values" in title:
        return {"code": "DRAWDOWN_POSITIVE", "field": "series_values", "fix": "Drawdown should usually be 0 or negative. Flip the sign if you uploaded positive drawdown magnitudes."}
    if " drawdown unit looks suspicious" in title:
        return {"code": "DRAWDOWN_UNIT_SUSPICIOUS", "field": "series_values", "fix": "For nav/return runs use decimal drawdowns such as -0.09. Use mode=pnl only for absolute drawdown values."}
    if "does not match expected" in title:
        return {"code": "PRIMARY_SERIES_EXPECTATION_MISMATCH", "field": "primary_series", "fix": "Regenerate or re-upload the primary curve so name, row count, and first/last x values match the run spec."}
    return {}


def stable_issue_code(title: str) -> str:
    chars: list[str] = []
    previous_underscore = False
    for char in title.upper():
        if char.isalnum():
            chars.append(char)
            previous_underscore = False
        elif not previous_underscore:
            chars.append("_")
            previous_underscore = True
    return "".join(chars).strip("_") or "VALIDATION_ISSUE"


def upload_report_failed(report: dict[str, Any], *, fail_on_warning: bool = False) -> bool:
    return report.get("severity") == "error" or (fail_on_warning and report.get("severity") == "warning")


def format_issue_for_agent(issue: dict[str, Any]) -> str:
    code = issue.get("code") or stable_issue_code(str(issue.get("title") or "validation issue"))
    parts = [f"[{code}] {issue.get('title') or 'Validation issue'}"]
    if issue.get("field"):
        parts.append(f"field={issue['field']}")
    if issue.get("detail"):
        parts.append(str(issue["detail"]))
    if issue.get("fix"):
        parts.append(f"Fix: {issue['fix']}")
    if issue.get("example"):
        parts.append(f"Example: {issue['example']}")
    return " | ".join(parts)


def format_upload_report_for_agent(report: dict[str, Any], *, limit: int = 5) -> str:
    issues = list(report.get("issues") or [])
    if not issues:
        return "upload preflight validation failed"
    rendered = [format_issue_for_agent(issue) for issue in issues[:limit] if isinstance(issue, dict)]
    remaining = len(issues) - len(rendered)
    if remaining > 0:
        rendered.append(f"... {remaining} more issue(s)")
    return "upload preflight validation failed: " + " ; ".join(rendered)


def severity_rank(severity: str) -> int:
    return {"error": 0, "warning": 1}.get(severity, 2)


def is_finite_number(value: Any) -> bool:
    return to_number(value) is not None


def to_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in {float("inf"), float("-inf")}:
        return None
    return number


def is_date_like_column(column: str) -> bool:
    return str(column).strip().upper() in {"DATE", "DATETIME", "TRADE_DATE", "END_DATE", "TIME"}


def parse_datetime(value: Any) -> datetime | None:
    text = str(value).strip()
    if not text:
        return None
    for candidate in [text, text.replace("Z", "+00:00")]:
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            pass
    for fmt in ["%Y%m%d", "%Y-%m-%d", "%Y/%m/%d", "%H:%M:%S", "%H:%M"]:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return None
