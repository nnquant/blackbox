"""Representative selection, without changing research decisions or execution state."""
from datetime import datetime, timezone
import math
from types import SimpleNamespace

from sqlalchemy import select

from .models import ResearchMap, ResearchMapNode
from .models import Run


def representative_rows(db, metric="strategy.summary.sharpe", branch_ids=None):
    namespace, _, _ = metric.rpartition(".")
    query = select(Run.id, Run.branch_id, Run.status, Run.updated_at, Run.created_at,
                   Run.summary_json[namespace].label("metrics"))
    if branch_ids is not None:
        query = query.where(Run.branch_id.in_(branch_ids))
    for row in db.execute(query.execution_options(yield_per=200)):
        yield SimpleNamespace(id=row.id, branch_id=row.branch_id, status=row.status,
                              updated_at=row.updated_at, created_at=row.created_at,
                              summary_json={namespace: row.metrics or {}})


def manual_baseline_ids(db):
    # Only an explicit Run binding identifies a pinned Run. Branch/research bindings
    # are dynamic evidence, and must not be treated as a manually chosen Run.
    return set(db.scalars(
        select(ResearchMapNode.binding_id).join(ResearchMap, ResearchMapNode.map_id == ResearchMap.id)
        .where(ResearchMap.status == "active", ResearchMapNode.key == ResearchMap.baseline_node_key,
               ResearchMapNode.binding_kind == "run")
    ).all())


def run_score(run, metric="strategy.summary.sharpe"):
    namespace, _, key = metric.rpartition(".")
    value = (run.summary_json or {}).get(namespace, {}).get(key)
    if value is None or isinstance(value, bool) or value == "":
        return float("-inf")
    try:
        value = float(value)
        return value if math.isfinite(value) else float("-inf")
    except (TypeError, ValueError):
        return float("-inf")


def run_recency(run):
    value = run.updated_at or run.created_at or datetime.min
    if value.tzinfo:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value, run.id


def choose_representative(runs, manual_ids=(), metric="strategy.summary.sharpe"):
    manual = [run for run in runs if run.id in manual_ids]
    if manual:
        return max(manual, key=run_recency)
    scored = [run for run in runs if run.status == "completed" and math.isfinite(run_score(run, metric))]
    if scored:
        return max(scored, key=lambda run: (run_score(run, metric), run_recency(run)))
    return max(runs, key=run_recency) if runs else None
