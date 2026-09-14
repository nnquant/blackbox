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


class RunMode(StrEnum):
    backtest = "backtest"
    paper = "paper"
    sim = "sim"
    live = "live"


class ResearchMapStatus(StrEnum):
    active = "active"
    archived = "archived"


class ResearchMapStage(StrEnum):
    """Where a research-map node is in the research lifecycle (ordered, normally advances only)."""

    idea = "idea"
    hypothesis = "hypothesis"
    experiment = "experiment"
    validation = "validation"
    tracking = "tracking"
    simulation = "simulation"
    live = "live"
    retired = "retired"


STAGE_ORDER = [stage.value for stage in ResearchMapStage]


class ResearchMapDecision(StrEnum):
    """What review decided about a node. Empty means undecided."""

    pending = "pending"
    kept = "kept"
    accepted = "accepted"
    rejected = "rejected"
    superseded = "superseded"


def research_map_family(stage: str | None, decision: str | None) -> str:
    """Colour family shown on the map: active / accepted / kept / ended."""
    if stage == ResearchMapStage.retired.value or decision in {ResearchMapDecision.rejected.value, ResearchMapDecision.superseded.value}:
        return "ended"
    if decision == ResearchMapDecision.accepted.value:
        return "accepted"
    if decision == ResearchMapDecision.kept.value:
        return "kept"
    return "active"
