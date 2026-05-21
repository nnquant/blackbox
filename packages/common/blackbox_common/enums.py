from enum import StrEnum


class RunStatus(StrEnum):
    created = "created"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class BranchStatus(StrEnum):
    active = "active"
    paused = "paused"
    accepted = "accepted"
    rejected = "rejected"
    archived = "archived"


class ArtifactKind(StrEnum):
    report_html = "report_html"
    image_png = "image_png"
    chart_json = "chart_json"
    table_parquet = "table_parquet"
    table_csv = "table_csv"
    notebook_ipynb = "notebook_ipynb"
    config_yaml = "config_yaml"
    returns_series_parquet = "returns_series_parquet"
    trade_log_parquet = "trade_log_parquet"
    position_log_parquet = "position_log_parquet"
    factor_values_parquet = "factor_values_parquet"
    risk_report_json = "risk_report_json"
    code_patch_txt = "code_patch_txt"
    other = "other"


class EventType(StrEnum):
    run_started = "run_started"
    stage_completed = "stage_completed"
    artifact_uploaded = "artifact_uploaded"
    run_finished = "run_finished"
    run_failed = "run_failed"
    run_cancelled = "run_cancelled"
    note_added = "note_added"


class NoteKind(StrEnum):
    hypothesis = "hypothesis"
    observation = "observation"
    anomaly = "anomaly"
    decision = "decision"
    todo = "todo"
    review = "review"


class PointKind(StrEnum):
    event = "event"
    iteration = "iteration"
    time = "time"
    coordinate = "coordinate"
    summary = "summary"
