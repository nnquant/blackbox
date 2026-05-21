from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from .client import BlackboxClient, current_run


def default_client(
    endpoint: str | None = None,
    token: str | None = None,
    offline: bool | None = None,
    spool_dir: str | Path | None = None,
) -> BlackboxClient:
    return BlackboxClient(endpoint=endpoint, token=token, offline=offline, spool_dir=spool_dir)


def dashboard(endpoint: str | None = None, token: str | None = None) -> dict[str, Any]:
    return default_client(endpoint=endpoint, token=token).dashboard()


def get_run(run_id: str, endpoint: str | None = None, token: str | None = None) -> dict[str, Any]:
    return default_client(endpoint=endpoint, token=token).get_run(run_id)


def search_runs(endpoint: str | None = None, token: str | None = None, **filters: Any) -> list[dict[str, Any]]:
    return default_client(endpoint=endpoint, token=token).search_runs(**filters)


def search_researches(endpoint: str | None = None, token: str | None = None, **filters: Any) -> list[dict[str, Any]]:
    return default_client(endpoint=endpoint, token=token).search_researches(**filters)


def compare_runs(
    run_ids: list[str],
    metrics: list[str] | None = None,
    series: list[str] | None = None,
    with_config_diff: bool = True,
    endpoint: str | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    return default_client(endpoint=endpoint, token=token).compare_runs(run_ids, metrics=metrics, series=series, with_config_diff=with_config_diff)


def create_compare_set(
    project_id: str,
    name: str,
    run_ids: list[str],
    layout: dict[str, Any] | None = None,
    endpoint: str | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    return default_client(endpoint=endpoint, token=token).create_compare_set(project_id, name, run_ids, layout=layout)


def list_compare_sets(project_id: str, endpoint: str | None = None, token: str | None = None) -> list[dict[str, Any]]:
    return default_client(endpoint=endpoint, token=token).list_compare_sets(project_id)


def get_compare_set(compare_set_id: str, endpoint: str | None = None, token: str | None = None) -> dict[str, Any]:
    return default_client(endpoint=endpoint, token=token).get_compare_set(compare_set_id)


def update_compare_set(
    compare_set_id: str,
    *,
    name: str | None = None,
    run_ids: list[str] | None = None,
    layout: dict[str, Any] | None = None,
    endpoint: str | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    return default_client(endpoint=endpoint, token=token).update_compare_set(compare_set_id, name=name, run_ids=run_ids, layout=layout)


def run_compare_set(
    compare_set_id: str,
    metrics: list[str] | None = None,
    series: list[str] | None = None,
    with_config_diff: bool = True,
    endpoint: str | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    return default_client(endpoint=endpoint, token=token).run_compare_set(compare_set_id, metrics=metrics, series=series, with_config_diff=with_config_diff)


def create_search_view(
    project_id: str,
    name: str,
    filters: dict[str, Any],
    description: str | None = None,
    endpoint: str | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    return default_client(endpoint=endpoint, token=token).create_search_view(project_id, name, filters, description=description)


def list_search_views(project_id: str, endpoint: str | None = None, token: str | None = None) -> list[dict[str, Any]]:
    return default_client(endpoint=endpoint, token=token).list_search_views(project_id)


def get_search_view(view_id: str, endpoint: str | None = None, token: str | None = None) -> dict[str, Any]:
    return default_client(endpoint=endpoint, token=token).get_search_view(view_id)


def update_search_view(
    view_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    filters: dict[str, Any] | None = None,
    endpoint: str | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    return default_client(endpoint=endpoint, token=token).update_search_view(view_id, name=name, description=description, filters=filters)


def run_search_view(view_id: str, overrides: dict[str, Any] | None = None, endpoint: str | None = None, token: str | None = None) -> list[dict[str, Any]]:
    return default_client(endpoint=endpoint, token=token).run_search_view(view_id, overrides=overrides)


def research_lineage(research_id: str, endpoint: str | None = None, token: str | None = None) -> dict[str, Any]:
    return default_client(endpoint=endpoint, token=token).research_lineage(research_id)


def branch_lineage(branch_id: str, endpoint: str | None = None, token: str | None = None) -> dict[str, Any]:
    return default_client(endpoint=endpoint, token=token).branch_lineage(branch_id)


def get_sweep(sweep_id: str, endpoint: str | None = None, token: str | None = None) -> dict[str, Any]:
    return default_client(endpoint=endpoint, token=token).get_sweep(sweep_id)


def get_sweep_summary(sweep_id: str, endpoint: str | None = None, token: str | None = None) -> dict[str, Any]:
    return default_client(endpoint=endpoint, token=token).get_sweep_summary(sweep_id)


def log(
    values: dict[str, Any],
    namespace: str | None = None,
    point: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    client_event_id: str | None = None,
) -> list[dict[str, Any]]:
    del tags
    return current_run().log(values, namespace or "strategy.summary", point, client_event_id=client_event_id)


def log_params(params: dict[str, Any]) -> dict[str, Any]:
    return current_run().log_params(params)


def flush() -> list[Any]:
    return current_run().client.flush()


def set_tags(tags: list[str]) -> dict[str, Any]:
    return current_run().set_tags(tags)


def set_summary(values: dict[str, Any], namespace: str = "strategy.summary") -> list[dict[str, Any]]:
    return current_run().set_summary(values, namespace=namespace)


def log_event(
    event_type: str,
    stage: str | None = None,
    payload: dict[str, Any] | None = None,
    client_event_id: str | None = None,
) -> dict[str, Any]:
    return current_run().log_event(event_type, stage, payload, client_event_id=client_event_id)


def log_note(
    kind: str,
    summary: str,
    content: str | None = None,
    structured: dict[str, Any] | None = None,
    author_type: str = "agent",
    client_event_id: str | None = None,
) -> dict[str, Any]:
    run = current_run()
    return run.client.log_note(run.id, kind, summary, content, structured, author_type=author_type, client_event_id=client_event_id)


def log_artifact(
    name: str,
    path: str | Path,
    kind: str | None = None,
    metadata: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    return current_run().log_artifact(name, path, kind, metadata, idempotency_key=idempotency_key)


def download_artifact(
    artifact_id: str,
    path: str | Path,
    endpoint: str | None = None,
    token: str | None = None,
    offline: bool | None = None,
    spool_dir: str | Path | None = None,
) -> dict[str, Any]:
    try:
        client = current_run().client
    except RuntimeError:
        client = BlackboxClient(endpoint=endpoint, token=token, offline=offline, spool_dir=spool_dir)
    return client.download_artifact(artifact_id, path)


def log_bytes(
    name: str,
    content: bytes | str,
    kind: str | None = None,
    filename: str | None = None,
    metadata: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    run = current_run()
    data = content.encode("utf-8") if isinstance(content, str) else content
    return run.log_bytes(name, data, kind, filename, metadata, idempotency_key=idempotency_key)


def log_table(name: str, data: Any, kind: str = "table_parquet", filename: str | None = None) -> dict[str, Any]:
    content = serialize_table(data, kind)
    return log_bytes(name, content, kind=kind, filename=filename or default_artifact_filename(name, kind))


def log_series(
    name: str,
    data: Any,
    x: str | None = None,
    y: str | list[str] | None = None,
    namespace: str | None = None,
    kind: str = "table_csv",
    filename: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    rows = normalize_rows(data)
    run = current_run()
    if hasattr(run, "client"):
        return run.client.log_series(
            run.id,
            name,
            rows,
            x=x,
            y=y,
            namespace=namespace,
            kind=kind,
            filename=filename or default_artifact_filename(name, kind),
            idempotency_key=idempotency_key,
        )
    metadata = {"series": {"name": name, "x": x, "y": y, "namespace": namespace}}
    content = serialize_table(rows, kind)
    return run.log_bytes(name, content, kind=kind, filename=filename or default_artifact_filename(name, kind), metadata=metadata)


def register_external_artifact(
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
    run = current_run()
    return run.client.register_external_artifact(
        run.id,
        name,
        uri,
        kind,
        metadata,
        filename=filename,
        mime_type=mime_type,
        size_bytes=size_bytes,
        sha256=sha256,
        preview=preview,
        idempotency_key=idempotency_key,
    )


def register_dataset(**kwargs: Any) -> dict[str, Any]:
    run = current_run()
    return run.client.register_dataset(run.id, **kwargs)


def attach_sweep(sweep_id: str, coord: dict[str, Any] | None = None, rank: int | None = None) -> dict[str, Any]:
    run = current_run()
    return run.client.attach_sweep(run.id, sweep_id, coord, rank)


def create_sweep(
    branch_id: str,
    name: str,
    search_space: dict[str, Any] | None = None,
    objective: dict[str, Any] | None = None,
    status: str = "active",
    endpoint: str | None = None,
    token: str | None = None,
    offline: bool | None = None,
    spool_dir: str | Path | None = None,
) -> dict[str, Any]:
    try:
        client = current_run().client
    except RuntimeError:
        client = BlackboxClient(endpoint=endpoint, token=token, offline=offline, spool_dir=spool_dir)
    return client.create_sweep(branch_id, name, search_space=search_space, objective=objective, status=status)


def log_factor_summary(values: dict[str, Any]) -> list[dict[str, Any]]:
    return log(values, namespace="factor.summary", point={"kind": "event", "name": "factor_eval_done"})


def log_factor_ic_series(data: Any, x: str = "date", y: str | list[str] = "ic") -> dict[str, Any]:
    return log_series("factor_ic_series", data, x=x, y=y, namespace="factor.ic", kind="table_csv")


def log_quantile_returns(data: Any) -> dict[str, Any]:
    return log_table("factor_quantile_returns", data, kind="table_parquet", filename="factor_quantile_returns.parquet")


def log_factor_turnover(data: Any) -> dict[str, Any] | list[dict[str, Any]]:
    if isinstance(data, dict) and is_scalar_dict(data):
        return log(data, namespace="factor.turnover", point={"kind": "event", "name": "factor_eval_done"})
    return log_table("factor_turnover", data, kind="table_parquet", filename="factor_turnover.parquet")


def log_factor_coverage(data: Any) -> dict[str, Any] | list[dict[str, Any]]:
    if isinstance(data, dict) and is_scalar_dict(data):
        return log(data, namespace="factor.coverage", point={"kind": "event", "name": "factor_eval_done"})
    return log_table("factor_coverage", data, kind="table_parquet", filename="factor_coverage.parquet")


def log_backtest_summary(values: dict[str, Any]) -> list[dict[str, Any]]:
    return log(values, namespace="strategy.summary", point={"kind": "event", "name": "post_cost_backtest_done"})


def log_returns_series(data: Any, x: str = "date", y: str | list[str] = "return") -> dict[str, Any]:
    return log_series(
        "returns_series",
        data,
        x=x,
        y=y,
        namespace="strategy.returns",
        kind="returns_series_parquet",
        filename="returns_series.parquet",
    )


def log_drawdown_series(data: Any, x: str = "date", y: str | list[str] = "drawdown") -> dict[str, Any]:
    return log_series(
        "drawdown_series",
        data,
        x=x,
        y=y,
        namespace="strategy.drawdown",
        kind="returns_series_parquet",
        filename="drawdown_series.parquet",
    )


def log_positions(data: Any) -> dict[str, Any]:
    return log_table("positions", data, kind="position_log_parquet", filename="positions.parquet")


def log_trades(data: Any) -> dict[str, Any]:
    return log_table("trades", data, kind="trade_log_parquet", filename="trades.parquet")


def log_cost_breakdown(data: Any) -> dict[str, Any] | list[dict[str, Any]]:
    if isinstance(data, dict) and is_scalar_dict(data):
        return log(data, namespace="cost.breakdown", point={"kind": "event", "name": "post_cost_backtest_done"})
    return log_table("cost_breakdown", data, kind="table_csv", filename="cost_breakdown.csv")


def log_risk_exposure(data: Any) -> dict[str, Any]:
    return log_bytes("risk_exposure", serialize_json(data), kind="risk_report_json", filename="risk_exposure.json")


def log_sweep_coord(coord: dict[str, Any]) -> list[dict[str, Any]]:
    return log({"sweep_coord": json.dumps(coord, sort_keys=True, ensure_ascii=False)}, namespace="sweep.coord", point={"kind": "coordinate", "coord": coord})


def serialize_table(data: Any, kind: str) -> bytes:
    if is_parquet_kind(kind):
        return serialize_table_parquet(data)
    return serialize_table_csv(data)


def serialize_table_parquet(data: Any) -> bytes:
    if isinstance(data, bytes):
        return data
    if isinstance(data, str):
        raise TypeError("parquet table data must be structured rows or parquet bytes")
    output = io.BytesIO()
    if hasattr(data, "to_parquet"):
        data.to_parquet(output, index=False)
        return output.getvalue()
    rows = normalize_rows(data)
    try:
        import pandas as pd
    except ImportError:
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise RuntimeError("pandas or pyarrow is required to serialize parquet table artifacts") from exc
        table = pa.Table.from_pylist(rows)
        pq.write_table(table, output)
        return output.getvalue()
    pd.DataFrame(rows).to_parquet(output, index=False)
    return output.getvalue()


def default_artifact_filename(name: str, kind: str | None = None) -> str:
    if is_parquet_kind(kind):
        return f"{name}.parquet"
    if kind and kind.endswith("_json"):
        return f"{name}.json"
    return f"{name}.csv"


def is_parquet_kind(kind: str | None) -> bool:
    return bool(kind and kind.endswith("_parquet"))


def serialize_table_csv(data: Any) -> bytes:
    if hasattr(data, "to_csv"):
        return data.to_csv(index=False).encode("utf-8")
    if isinstance(data, bytes):
        return data
    if isinstance(data, str):
        return data.encode("utf-8")
    if isinstance(data, list):
        return serialize_list_csv(data)
    if isinstance(data, dict):
        return serialize_list_csv([data])
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


def normalize_rows(data: Any) -> list[dict[str, Any]]:
    if hasattr(data, "to_dict"):
        data = data.to_dict(orient="records")
    if isinstance(data, list):
        if all(isinstance(row, dict) for row in data):
            return data
        return [{"value": row} for row in data]
    if isinstance(data, dict):
        return [data]
    raise TypeError("series data must be a DataFrame, list, or dict")


def serialize_json(data: Any) -> bytes:
    if isinstance(data, bytes):
        return data
    if isinstance(data, str):
        return data.encode("utf-8")
    if hasattr(data, "to_dict"):
        data = data.to_dict(orient="records")
    return json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")


def is_scalar_dict(data: dict[str, Any]) -> bool:
    return all(not isinstance(value, (dict, list, tuple, set)) and not hasattr(value, "to_dict") for value in data.values())


def serialize_list_csv(rows: list[Any]) -> bytes:
    if not rows:
        return b""
    if all(isinstance(row, dict) for row in rows):
        fieldnames = sorted({key for row in rows for key in row})
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue().encode("utf-8")
    output = io.StringIO()
    writer = csv.writer(output)
    for row in rows:
        if isinstance(row, (list, tuple)):
            writer.writerow(row)
        else:
            writer.writerow([row])
    return output.getvalue().encode("utf-8")
