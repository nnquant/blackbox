"""Research map API.

A research map is a manually maintained tree of research nodes. Each node carries a
narrative (hypothesis, change, reading, verdict, caveats, next step), a lifecycle
``stage``, a review ``decision``, and at most one *binding* to a Blackbox entity
(run / branch / compare set / research). Structure and narrative are written by
research agents; evidence (metrics, quality gate, artifacts, decision notes) is read
live from the bound entity and never stored in the map.

The map is never derived from runs: nothing here creates nodes, changes a stage or a
decision, or moves the baseline on its own.
"""

from __future__ import annotations

from .representatives import choose_representative, manual_baseline_ids

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, FastAPI, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from blackbox_common.enums import STAGE_ORDER, ResearchMapDecision, ResearchMapStage, research_map_family
from blackbox_common.errors import ApiError, ErrorCode
from blackbox_common.schemas import (
    ResearchMapBaselineSet,
    ResearchMapCreate,
    ResearchMapDocumentImport,
    ResearchMapImportNode,
    ResearchMapNodeAdvance,
    ResearchMapNodeCreate,
    ResearchMapNodeDecide,
    ResearchMapNodeUpdate,
    ResearchMapNodeUpsert,
    ResearchMapNodesImport,
    ResearchMapUpdate,
)

from .db import get_db
from .models import (
    Artifact,
    Branch,
    CompareSet,
    Project,
    Research,
    ResearchMap,
    ResearchMapNode,
    ResearchMapRevision,
    Run,
    RunNote,
    utcnow,
)
from .realtime import publish_change


STANDARD_METRICS = [
    ("annual_return", "strategy.summary.annual_return"),
    ("sharpe", "strategy.summary.sharpe"),
    ("max_drawdown", "strategy.summary.max_drawdown"),
    ("calmar", "strategy.summary.calmar"),
    ("annual_volatility", "strategy.summary.annual_volatility"),
]
NODE_TEXT_FIELDS = ("title", "full_title", "date_label", "hypothesis", "verdict")
MAP_SCALAR_FIELDS = ("title", "subtitle", "description", "status", "primary_metric")
BINDING_MODELS = {"run": Run, "branch": Branch, "compare_set": CompareSet, "research": Research}
STALE_DAYS = 14
LIMITS = {"title": 14, "hypothesis": 50, "change": 3, "reading": 3, "reading_item": 40, "verdict": 60, "caveats": 3, "date_label": 12}


def ok(data: Any) -> dict[str, Any]:
    return {"ok": True, "data": data, "error": None}


# ---------------------------------------------------------------------------
# lookups
# ---------------------------------------------------------------------------


def require_map(db: Session, map_id: str) -> ResearchMap:
    research_map = db.get(ResearchMap, map_id)
    if not research_map:
        raise ApiError(ErrorCode.not_found, "research map not found", "use bbox map list to find map ids")
    return research_map


def find_node(db: Session, research_map: ResearchMap, ref: str | None) -> ResearchMapNode | None:
    if not ref:
        return None
    node = db.scalar(select(ResearchMapNode).where(ResearchMapNode.map_id == research_map.id, ResearchMapNode.key == ref))
    if node:
        return node
    node = db.get(ResearchMapNode, ref)
    return node if node and node.map_id == research_map.id else None


def require_node(db: Session, research_map: ResearchMap, key: str) -> ResearchMapNode:
    node = find_node(db, research_map, key)
    if not node:
        raise ApiError(ErrorCode.not_found, f"research map node {key} not found", "node keys are case-sensitive")
    return node


def resolve_project_ref(db: Session, *refs: str | None) -> Project:
    ref = next((r for r in refs if r), None)
    if not ref:
        raise ApiError(ErrorCode.validation_error, "project is required (id or key)")
    found = db.get(Project, ref) or db.scalar(select(Project).where(Project.key == ref))
    if not found:
        raise ApiError(ErrorCode.not_found, f"project {ref} not found", "create it with bbox project create")
    return found


def resolve_research_ref(db: Session, project: Project, *refs: str | None) -> Research | None:
    ref = next((r for r in refs if r), None)
    if not ref:
        return None
    found = db.get(Research, ref) or db.scalar(select(Research).where(Research.project_id == project.id, Research.key == ref))
    if not found:
        raise ApiError(ErrorCode.not_found, f"research {ref} not found in project {project.key}")
    if found.project_id != project.id:
        raise ApiError(ErrorCode.validation_error, f"research {found.key} belongs to another project")
    return found


def actor(payload: Any, default_type: str = "human") -> tuple[str, str | None]:
    by_type = getattr(payload, "created_by_type", None)
    by_id = getattr(payload, "created_by_id", None)
    if by_id and not by_type:
        by_type = "agent"
    return by_type or default_type, by_id


# ---------------------------------------------------------------------------
# normalization
# ---------------------------------------------------------------------------


def clean_list(values: list[Any] | None) -> list[str]:
    return [str(item).strip() for item in values or [] if str(item).strip()]


def normalize_change(values: list[Any] | None) -> list[Any]:
    rows: list[Any] = []
    for item in values or []:
        if hasattr(item, "model_dump"):
            item = item.model_dump(by_alias=True)
        if isinstance(item, dict):
            what = str(item.get("what") or "").strip()
            to = str(item.get("to") or "").strip()
            frm = item.get("from") if item.get("from") is not None else item.get("from_")
            if not (what or to):
                continue
            row: dict[str, str] = {"what": what, "to": to}
            if frm not in (None, ""):
                row["from"] = str(frm).strip()
            rows.append(row)
        elif str(item).strip():
            rows.append(str(item).strip())
    return rows


def normalize_refs(values: list[Any] | None) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for item in values or []:
        data = item.model_dump() if hasattr(item, "model_dump") else dict(item)
        kind = str(data.get("kind") or "url").strip()
        ref: dict[str, Any] = {"kind": kind}
        for field in ("id", "href", "label"):
            if data.get(field):
                ref[field] = str(data[field])
        if kind in {"url", "file"} and not (ref.get("href") or ref.get("id")):
            raise ApiError(ErrorCode.validation_error, f"ref of kind {kind} requires href")
        if kind not in {"url", "file"} and not ref.get("id"):
            raise ApiError(ErrorCode.validation_error, f"ref of kind {kind} requires an id")
        refs.append(ref)
    return refs


def check_binding(db: Session, binding: Any) -> tuple[str | None, str | None]:
    if binding is None:
        return None, None
    data = binding.model_dump() if hasattr(binding, "model_dump") else dict(binding)
    kind, ident = str(data.get("kind") or ""), str(data.get("id") or "")
    if not kind or not ident:
        return None, None
    model = BINDING_MODELS.get(kind)
    if model is None:
        raise ApiError(ErrorCode.validation_error, f"unsupported binding kind {kind}")
    if not db.get(model, ident):
        raise ApiError(ErrorCode.not_found, f"{kind} {ident} not found", "bind an existing entity; check the id with bbox search runs or bbox branch list")
    return kind, ident


# ---------------------------------------------------------------------------
# metrics / evidence (read live from bound entities; never stored on the map)
# ---------------------------------------------------------------------------


def metric_value(summary: dict[str, Any], path: str) -> float | None:
    from .main import get_metric_value  # local import: main imports this module

    value = get_metric_value(summary or {}, path)
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def run_metrics(run: Run, primary_metric: str) -> dict[str, Any]:
    summary = run.summary_json or {}
    metrics: dict[str, Any] = {key: metric_value(summary, path) for key, path in STANDARD_METRICS}
    metrics["primary"] = {"metric": primary_metric, "value": metric_value(summary, primary_metric)}
    metrics["periods_per_year"] = metric_value(summary, "strategy.summary.periods_per_year")
    return metrics


def run_quality(db: Session, run: Run) -> dict[str, Any]:
    if run.status != "completed":
        return {"severity": "pending", "error_count": 0, "warning_count": 0}
    from .main import run_quality_gate_report

    try:
        report = run_quality_gate_report(db, run)
    except Exception:  # pragma: no cover - evidence must never break the map
        return {"severity": "unknown", "error_count": 0, "warning_count": 0}
    return {"severity": report.get("severity"), "error_count": report.get("error_count", 0), "warning_count": report.get("warning_count", 0)}


def run_evidence(db: Session, run: Run, primary_metric: str, *, with_notes: bool = True) -> dict[str, Any]:
    artifacts = db.scalars(select(Artifact).where(Artifact.run_id == run.id)).all()
    notes: list[dict[str, Any]] = []
    if with_notes:
        rows = db.scalars(
            select(RunNote).where(RunNote.run_id == run.id, RunNote.kind.in_(["decision", "review"])).order_by(RunNote.created_at.desc()).limit(5)
        ).all()
        notes = [
            {"id": n.id, "kind": n.kind, "summary": n.summary, "author_type": n.author_type, "author_id": n.author_id, "created_at": n.created_at.isoformat()}
            for n in rows
        ]
    has_summary = bool(run.summary_json) and any(metric_value(run.summary_json, path) is not None for _, path in STANDARD_METRICS)
    return {
        "id": run.id,
        "name": run.name,
        "title": run.title,
        "status": run.status,
        "mode": run.mode,
        "branch_id": run.branch_id,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "ended_at": run.ended_at.isoformat() if run.ended_at else None,
        "metrics": run_metrics(run, primary_metric) if has_summary else None,
        "quality": run_quality(db, run),
        "artifacts": [{"id": a.id, "kind": a.kind, "name": a.name} for a in artifacts],
        "notes": notes,
    }


def branch_champion(db: Session, branch: Branch, primary_metric: str) -> Run | None:
    runs = db.scalars(select(Run).where(Run.branch_id == branch.id)).all()
    return choose_representative(runs, manual_baseline_ids(db), primary_metric)


def resolve_binding(db: Session, node: ResearchMapNode, primary_metric: str) -> dict[str, Any] | None:
    kind, ident = node.binding_kind, node.binding_id
    if not kind or not ident:
        return None
    base: dict[str, Any] = {"kind": kind, "id": ident, "exists": True}
    if kind == "run":
        run = db.get(Run, ident)
        if not run:
            return {**base, "exists": False}
        return {**base, "label": run.name, "run": run_evidence(db, run, primary_metric)}
    if kind == "branch":
        branch = db.get(Branch, ident)
        if not branch:
            return {**base, "exists": False}
        champion = branch_champion(db, branch, primary_metric)
        run_count = db.scalar(select(func.count(Run.id)).where(Run.branch_id == branch.id)) or 0
        return {
            **base,
            "label": branch.key,
            "branch": {"id": branch.id, "key": branch.key, "title": branch.title, "status": branch.status, "research_id": branch.research_id, "run_count": int(run_count), "champion_run_id": champion.id if champion else None},
            "run": run_evidence(db, champion, primary_metric) if champion else None,
        }
    if kind == "compare_set":
        compare_set = db.get(CompareSet, ident)
        if not compare_set:
            return {**base, "exists": False}
        runs = [db.get(Run, run_id) for run_id in compare_set.run_ids_json or []]
        return {
            **base,
            "label": compare_set.name,
            "compare_set": {"id": compare_set.id, "name": compare_set.name, "research_id": compare_set.research_id, "run_ids": compare_set.run_ids_json},
            "runs": [run_evidence(db, run, primary_metric, with_notes=False) for run in runs if run],
        }
    research = db.get(Research, ident)
    if not research:
        return {**base, "exists": False}
    return {**base, "label": research.key, "research": {"id": research.id, "key": research.key, "title": research.title, "status": research.status, "goal": research.goal}}


def bound_run(db: Session, node: ResearchMapNode, primary_metric: str) -> Run | None:
    if node.binding_kind == "run" and node.binding_id:
        return db.get(Run, node.binding_id)
    if node.binding_kind == "branch" and node.binding_id:
        branch = db.get(Branch, node.binding_id)
        return branch_champion(db, branch, primary_metric) if branch else None
    return None


# ---------------------------------------------------------------------------
# serialization
# ---------------------------------------------------------------------------


def map_nodes(db: Session, research_map: ResearchMap) -> list[ResearchMapNode]:
    return list(
        db.scalars(
            select(ResearchMapNode)
            .where(ResearchMapNode.map_id == research_map.id)
            .order_by(ResearchMapNode.position.asc(), ResearchMapNode.created_at.asc(), ResearchMapNode.key.asc())
        ).all()
    )


def mainline_keys(nodes: list[ResearchMapNode], baseline_key: str | None) -> set[str]:
    by_key = {node.key: node for node in nodes}
    by_id = {node.id: node for node in nodes}
    keys: set[str] = set()
    cursor = by_key.get(baseline_key) if baseline_key else None
    while cursor:
        keys.add(cursor.key)
        cursor = by_id.get(cursor.parent_id) if cursor.parent_id else None
    return keys


def node_flags(node: ResearchMapNode, run: Run | None, now: datetime) -> list[str]:
    flags: list[str] = []
    undecided = not node.decision
    updated = node.updated_at or node.created_at or now
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    age = now - updated
    if undecided and node.stage == ResearchMapStage.experiment.value and run and run.status == "completed":
        flags.append("ready")
    if undecided and node.stage in {"hypothesis", "experiment"} and age > timedelta(days=STALE_DAYS) and not (run and run.status == "completed"):
        flags.append("stale")
    if node.decision == ResearchMapDecision.accepted.value and node.stage == ResearchMapStage.experiment.value and age > timedelta(days=STALE_DAYS):
        flags.append("not_advanced")
    return flags


def node_read(db: Session, node: ResearchMapNode, key_by_id: dict[str, str], research_map: ResearchMap, mainline: set[str], now: datetime) -> dict[str, Any]:
    binding = resolve_binding(db, node, research_map.primary_metric)
    run = bound_run(db, node, research_map.primary_metric)
    return {
        "id": node.id,
        "map_id": node.map_id,
        "key": node.key,
        "parent_id": node.parent_id,
        "parent_key": key_by_id.get(node.parent_id) if node.parent_id else None,
        "position": node.position,
        "title": node.title,
        "full_title": node.full_title,
        "date_label": node.date_label,
        "stage": node.stage,
        "decision": node.decision,
        "family": research_map_family(node.stage, node.decision),
        "is_baseline": research_map.baseline_node_key == node.key,
        "is_mainline": node.key in mainline,
        "flags": node_flags(node, run, now),
        "hypothesis": node.hypothesis,
        "change": node.change_json or [],
        "reading": node.reading_json or [],
        "verdict": node.verdict,
        "caveats": node.caveats_json or [],
        "next": node.next_step,
        "binding": binding,
        "refs": node.refs_json or [],
        "meta": node.meta_json or {},
        "created_by_type": node.created_by_type,
        "created_by_id": node.created_by_id,
        "updated_by_type": node.updated_by_type,
        "updated_by_id": node.updated_by_id,
        "created_at": node.created_at.isoformat(),
        "updated_at": node.updated_at.isoformat(),
    }


def build_tree(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {row["id"]: {**row, "children": []} for row in rows}
    roots: list[dict[str, Any]] = []
    for row in rows:
        entry = by_id[row["id"]]
        parent = by_id.get(row["parent_id"]) if row.get("parent_id") else None
        (parent["children"] if parent else roots).append(entry)
    return roots


def counts_for(nodes: list[ResearchMapNode]) -> dict[str, Any]:
    stages: dict[str, int] = {}
    decisions: dict[str, int] = {}
    families: dict[str, int] = {}
    for node in nodes:
        stages[node.stage] = stages.get(node.stage, 0) + 1
        if node.decision:
            decisions[node.decision] = decisions.get(node.decision, 0) + 1
        fam = research_map_family(node.stage, node.decision)
        families[fam] = families.get(fam, 0) + 1
    return {"stages": stages, "decisions": decisions, "families": families, "undecided": sum(1 for n in nodes if not n.decision)}


def map_summary(db: Session, research_map: ResearchMap, nodes: list[ResearchMapNode] | None = None) -> dict[str, Any]:
    nodes = map_nodes(db, research_map) if nodes is None else nodes
    project = db.get(Project, research_map.project_id)
    research = db.get(Research, research_map.research_id) if research_map.research_id else None
    baseline = next((n for n in nodes if n.key == research_map.baseline_node_key), None)
    baseline_summary = None
    if baseline:
        run = bound_run(db, baseline, research_map.primary_metric)
        baseline_summary = {"key": baseline.key, "title": baseline.title, "stage": baseline.stage, "decision": baseline.decision, "run": run_evidence(db, run, research_map.primary_metric, with_notes=False) if run else None}
    latest = sorted(nodes, key=lambda n: n.updated_at or n.created_at, reverse=True)
    return {
        "id": research_map.id,
        "project_id": research_map.project_id,
        "project_key": project.key if project else None,
        "research_id": research_map.research_id,
        "research_key": research.key if research else None,
        "key": research_map.key,
        "title": research_map.title,
        "subtitle": research_map.subtitle,
        "description": research_map.description,
        "status": research_map.status,
        "baseline_node_key": research_map.baseline_node_key,
        "primary_metric": research_map.primary_metric,
        "settings_json": research_map.settings_json or {},
        "created_by_type": research_map.created_by_type,
        "created_by_id": research_map.created_by_id,
        "created_at": research_map.created_at.isoformat(),
        "updated_at": research_map.updated_at.isoformat(),
        "node_count": len(nodes),
        "counts": counts_for(nodes),
        "baseline": baseline_summary,
        "mainline_keys": sorted(mainline_keys(nodes, research_map.baseline_node_key)),
        "recent": [
            {"key": n.key, "title": n.title, "stage": n.stage, "decision": n.decision, "family": research_map_family(n.stage, n.decision), "updated_at": n.updated_at.isoformat(), "updated_by_type": n.updated_by_type, "updated_by_id": n.updated_by_id}
            for n in latest[:4]
        ],
        "last_updated_at": latest[0].updated_at.isoformat() if latest else research_map.updated_at.isoformat(),
    }


def map_detail(db: Session, research_map: ResearchMap) -> dict[str, Any]:
    nodes = map_nodes(db, research_map)
    key_by_id = {node.id: node.key for node in nodes}
    mainline = mainline_keys(nodes, research_map.baseline_node_key)
    now = datetime.now(timezone.utc)
    rows = [node_read(db, node, key_by_id, research_map, mainline, now) for node in nodes]
    data = map_summary(db, research_map, nodes)
    data["nodes"] = rows
    data["tree"] = build_tree(rows)
    return data


def single_node(db: Session, research_map: ResearchMap, node: ResearchMapNode) -> dict[str, Any]:
    nodes = map_nodes(db, research_map)
    key_by_id = {n.id: n.key for n in nodes}
    return node_read(db, node, key_by_id, research_map, mainline_keys(nodes, research_map.baseline_node_key), datetime.now(timezone.utc))


def export_node(node: ResearchMapNode, children: dict[str, list[ResearchMapNode]]) -> dict[str, Any]:
    doc: dict[str, Any] = {"key": node.key, "title": node.title, "stage": node.stage}
    optional = {
        "full_title": node.full_title,
        "date_label": node.date_label,
        "decision": node.decision,
        "hypothesis": node.hypothesis,
        "change": node.change_json or None,
        "reading": node.reading_json or None,
        "verdict": node.verdict,
        "caveats": node.caveats_json or None,
        "next": node.next_step,
        "binding": {"kind": node.binding_kind, "id": node.binding_id} if node.binding_kind else None,
        "refs": node.refs_json or None,
        "meta": node.meta_json or None,
    }
    doc.update({k: v for k, v in optional.items() if v not in (None, "", [], {})})
    kids = children.get(node.id, [])
    if kids:
        doc["children"] = [export_node(child, children) for child in kids]
    return doc


def export_document(db: Session, research_map: ResearchMap) -> dict[str, Any]:
    nodes = map_nodes(db, research_map)
    children: dict[str, list[ResearchMapNode]] = {}
    roots: list[ResearchMapNode] = []
    for node in nodes:
        if node.parent_id:
            children.setdefault(node.parent_id, []).append(node)
        else:
            roots.append(node)
    project = db.get(Project, research_map.project_id)
    research = db.get(Research, research_map.research_id) if research_map.research_id else None
    doc: dict[str, Any] = {"project": project.key if project else research_map.project_id, "key": research_map.key, "title": research_map.title}
    if research:
        doc["research"] = research.key
    for field in ("subtitle", "description"):
        if getattr(research_map, field):
            doc[field] = getattr(research_map, field)
    doc["status"] = research_map.status
    if research_map.baseline_node_key:
        doc["baseline"] = research_map.baseline_node_key
    doc["primary_metric"] = research_map.primary_metric
    if research_map.settings_json:
        doc["settings"] = research_map.settings_json
    doc["nodes"] = [export_node(root, children) for root in roots]
    return doc


# ---------------------------------------------------------------------------
# revisions
# ---------------------------------------------------------------------------


def record(db: Session, research_map: ResearchMap, action: str, summary: str, *, by: tuple[str, str | None], node_key: str | None = None, changes: dict[str, Any] | None = None) -> None:
    db.add(ResearchMapRevision(map_id=research_map.id, node_key=node_key, action=action, summary=summary[:512], changes_json=changes or {}, by_type=by[0], by_id=by[1]))


def snapshot(node: ResearchMapNode) -> dict[str, Any]:
    return {
        "title": node.title, "full_title": node.full_title, "date_label": node.date_label, "stage": node.stage, "decision": node.decision,
        "hypothesis": node.hypothesis, "change": list(node.change_json or []), "reading": list(node.reading_json or []), "verdict": node.verdict,
        "caveats": list(node.caveats_json or []), "next": node.next_step, "binding": {"kind": node.binding_kind, "id": node.binding_id} if node.binding_kind else None,
        "refs": list(node.refs_json or []), "parent_id": node.parent_id, "position": node.position,
    }


def diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    return {key: {"from": before.get(key), "to": after.get(key)} for key in after if before.get(key) != after.get(key)}


# ---------------------------------------------------------------------------
# mutations
# ---------------------------------------------------------------------------


def apply_map_fields(research_map: ResearchMap, payload: Any) -> dict[str, Any]:
    before = {f: getattr(research_map, f) for f in MAP_SCALAR_FIELDS}
    before["settings"] = dict(research_map.settings_json or {})
    fields = payload.model_fields_set
    for field in MAP_SCALAR_FIELDS:
        if field in fields and getattr(payload, field) is not None:
            value = getattr(payload, field)
            setattr(research_map, field, value.value if hasattr(value, "value") else value)
    if "settings" in fields and payload.settings is not None:
        research_map.settings_json = dict(payload.settings)
    research_map.updated_at = utcnow()
    after = {f: getattr(research_map, f) for f in MAP_SCALAR_FIELDS}
    after["settings"] = dict(research_map.settings_json or {})
    return diff(before, after)


def next_position(db: Session, research_map: ResearchMap, parent_id: str | None) -> int:
    parent_filter = ResearchMapNode.parent_id.is_(None) if parent_id is None else ResearchMapNode.parent_id == parent_id
    current = db.scalar(select(func.max(ResearchMapNode.position)).where(ResearchMapNode.map_id == research_map.id, parent_filter))
    return int(current) + 1 if current is not None else 0


def ensure_no_cycle(db: Session, node: ResearchMapNode, parent: ResearchMapNode | None) -> None:
    cursor = parent
    while cursor is not None:
        if cursor.id == node.id:
            raise ApiError(ErrorCode.validation_error, f"node {node.key} cannot be its own ancestor")
        cursor = db.get(ResearchMapNode, cursor.parent_id) if cursor.parent_id else None


def stage_index(value: str | None) -> int:
    return STAGE_ORDER.index(value) if value in STAGE_ORDER else -1


def apply_node_fields(db: Session, node: ResearchMapNode, payload: Any, *, regress_reason: str | None = None) -> None:
    fields = payload.model_fields_set
    for field in NODE_TEXT_FIELDS:
        if field in fields and getattr(payload, field) is not None:
            setattr(node, field, getattr(payload, field))
    if "stage" in fields and payload.stage is not None:
        new_stage = payload.stage.value if hasattr(payload.stage, "value") else str(payload.stage)
        if stage_index(new_stage) < stage_index(node.stage) and not regress_reason:
            raise ApiError(
                ErrorCode.validation_error,
                f"stage moves backwards ({node.stage} -> {new_stage}); a reason is required",
                "stages normally only advance; pass --reason to move back",
            )
        node.stage = new_stage
    if "decision" in fields:
        node.decision = payload.decision.value if hasattr(payload.decision, "value") else payload.decision
    if "change" in fields and payload.change is not None:
        node.change_json = normalize_change(payload.change)
    if "reading" in fields and payload.reading is not None:
        node.reading_json = clean_list(payload.reading)
    if "caveats" in fields and payload.caveats is not None:
        node.caveats_json = clean_list(payload.caveats)
    if "next" in fields:
        node.next_step = payload.next
    if "binding" in fields:
        node.binding_kind, node.binding_id = check_binding(db, payload.binding)
    if "refs" in fields and payload.refs is not None:
        node.refs_json = normalize_refs(payload.refs)
    if "meta" in fields and payload.meta is not None:
        node.meta_json = dict(payload.meta)
    node.updated_at = utcnow()


def set_parent(db: Session, research_map: ResearchMap, node: ResearchMapNode, parent_key: str | None, position: int | None) -> None:
    parent = None
    if parent_key:
        parent = find_node(db, research_map, parent_key)
        if not parent:
            raise ApiError(ErrorCode.not_found, f"parent node {parent_key} not found", "create the parent node first")
        ensure_no_cycle(db, node, parent)
    parent_id = parent.id if parent else None
    changed = node.parent_id != parent_id
    node.parent_id = parent_id
    if position is not None:
        node.position = int(position)
    elif changed:
        node.position = next_position(db, research_map, parent_id)


def current_parent_key(db: Session, node: ResearchMapNode) -> str | None:
    if not node.parent_id:
        return None
    parent = db.get(ResearchMapNode, node.parent_id)
    return parent.key if parent else None


def create_node(db: Session, research_map: ResearchMap, payload: ResearchMapNodeCreate, by: tuple[str, str | None]) -> ResearchMapNode:
    node = ResearchMapNode(map_id=research_map.id, key=payload.key, title=payload.title, stage=payload.stage.value, created_by_type=by[0], created_by_id=by[1], updated_by_type=by[0], updated_by_id=by[1])
    apply_node_fields(db, node, payload)
    parent_id = None
    if payload.parent_key:
        parent = find_node(db, research_map, payload.parent_key)
        if not parent:
            raise ApiError(ErrorCode.not_found, f"parent node {payload.parent_key} not found", "create the parent node first")
        parent_id = parent.id
    node.parent_id = parent_id
    node.position = int(payload.position) if payload.position is not None else next_position(db, research_map, parent_id)
    db.add(node)
    db.flush()
    record(db, research_map, "node.create", f"创建节点 {node.title}", node_key=node.key, changes={"after": snapshot(node)}, by=by)
    research_map.updated_at = utcnow()
    return node


def update_node(db: Session, research_map: ResearchMap, node: ResearchMapNode, payload: Any, by: tuple[str, str | None], *, action: str = "node.update", summary: str | None = None) -> dict[str, Any]:
    before = snapshot(node)
    apply_node_fields(db, node, payload, regress_reason=getattr(payload, "reason", None))
    if "parent_key" in payload.model_fields_set or getattr(payload, "position", None) is not None:
        parent_key = payload.parent_key if "parent_key" in payload.model_fields_set else current_parent_key(db, node)
        set_parent(db, research_map, node, parent_key, getattr(payload, "position", None))
    changes = diff(before, snapshot(node))
    if changes:
        node.updated_by_type, node.updated_by_id = by
        text = summary or ("更新 " + "、".join(changes.keys()))
        if getattr(payload, "reason", None):
            text += f"（{payload.reason}）"
        record(db, research_map, action, text, node_key=node.key, changes=changes, by=by)
        research_map.updated_at = utcnow()
    return changes


def upsert_node(db: Session, research_map: ResearchMap, key: str, payload: ResearchMapNodeUpsert, by: tuple[str, str | None]) -> tuple[ResearchMapNode, bool]:
    node = find_node(db, research_map, key)
    if node is None:
        if not payload.title:
            raise ApiError(ErrorCode.validation_error, f"node {key} does not exist yet; title is required to create it")
        data = payload.model_dump(exclude_unset=True, exclude={"created_by_type", "created_by_id"}, by_alias=True)
        if data.get("stage") is None:
            data.pop("stage", None)
        return create_node(db, research_map, ResearchMapNodeCreate(key=key, **data), by), True
    update_node(db, research_map, node, payload, by)
    return node, False


def flatten_import_nodes(nodes: list[ResearchMapImportNode], parent_key: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, node in enumerate(nodes):
        data = node.model_dump(exclude_unset=True, exclude={"children"}, by_alias=True)
        data["key"] = node.key
        if data.get("parent_key") is None:
            data["parent_key"] = parent_key
        if data.get("position") is None:
            data["position"] = index
        rows.append(data)
        rows.extend(flatten_import_nodes(node.children, node.key))
    return rows


def import_nodes(db: Session, research_map: ResearchMap, nodes: list[ResearchMapImportNode], *, mode: str, by: tuple[str, str | None]) -> dict[str, Any]:
    rows = flatten_import_nodes(nodes)
    seen: set[str] = set()
    for row in rows:
        if row["key"] in seen:
            raise ApiError(ErrorCode.validation_error, f"duplicate node key in import: {row['key']}")
        seen.add(row["key"])
    created = updated = unchanged = 0
    for row in rows:
        node = find_node(db, research_map, row["key"])
        fields = {k: v for k, v in row.items() if k not in {"key", "parent_key", "position", "children"}}
        if node is None:
            if not fields.get("title"):
                raise ApiError(ErrorCode.validation_error, f"node {row['key']} is new and requires a title")
            if fields.get("stage") is None:
                fields.pop("stage", None)
            create_node(db, research_map, ResearchMapNodeCreate(key=row["key"], **fields), by)
            created += 1
        else:
            fields["reason"] = "import"
            if update_node(db, research_map, node, ResearchMapNodeUpdate(**fields), by, action="node.import"):
                updated += 1
            else:
                unchanged += 1
    for row in rows:
        node = require_node(db, research_map, row["key"])
        before_parent, before_pos = node.parent_id, node.position
        set_parent(db, research_map, node, row.get("parent_key"), row.get("position"))
        if (before_parent, before_pos) != (node.parent_id, node.position) and node.key not in {r["key"] for r in rows if find_node(db, research_map, r["key"]) is None}:
            pass
    deleted = 0
    if mode == "replace":
        stale = [node for node in map_nodes(db, research_map) if node.key not in seen]
        deleted = delete_nodes(db, research_map, stale, by)
    return {"created": created, "updated": updated, "unchanged": unchanged, "deleted": deleted, "total": len(rows)}


def descendants(db: Session, research_map: ResearchMap, node: ResearchMapNode) -> list[ResearchMapNode]:
    children_by_parent: dict[str, list[ResearchMapNode]] = {}
    for item in map_nodes(db, research_map):
        if item.parent_id:
            children_by_parent.setdefault(item.parent_id, []).append(item)
    result: list[ResearchMapNode] = []
    stack = list(children_by_parent.get(node.id, []))
    while stack:
        current = stack.pop()
        result.append(current)
        stack.extend(children_by_parent.get(current.id, []))
    return result


def delete_nodes(db: Session, research_map: ResearchMap, nodes: list[ResearchMapNode], by: tuple[str, str | None]) -> int:
    ids = {node.id for node in nodes}
    if ids:
        for survivor in db.scalars(select(ResearchMapNode).where(ResearchMapNode.parent_id.in_(ids), ResearchMapNode.id.not_in(ids))).all():
            survivor.parent_id = None
    for node in nodes:
        record(db, research_map, "node.delete", f"删除节点 {node.title}", node_key=node.key, changes={"before": snapshot(node)}, by=by)
        db.delete(node)
    db.flush()
    keys = {node.key for node in nodes}
    if research_map.baseline_node_key in keys:
        research_map.baseline_node_key = None
    return len(nodes)


def set_baseline(db: Session, research_map: ResearchMap, node_key: str | None, reason: str | None, by: tuple[str, str | None]) -> None:
    previous = research_map.baseline_node_key
    if node_key:
        require_node(db, research_map, node_key)
    research_map.baseline_node_key = node_key
    research_map.updated_at = utcnow()
    if previous != node_key:
        text = f"基准 {previous or '—'} → {node_key or '—'}" + (f"：{reason}" if reason else "")
        record(db, research_map, "map.baseline", text, node_key=node_key, changes={"baseline": {"from": previous, "to": node_key}, "reason": reason}, by=by)


def write_decision_note(db: Session, research_map: ResearchMap, node: ResearchMapNode, by: tuple[str, str | None]) -> dict[str, Any] | None:
    # Only run-bound nodes get a note: a branch's champion run may belong to a different node.
    if node.binding_kind != "run" or not node.verdict:
        return None
    run = db.get(Run, node.binding_id)
    if not run:
        return None
    note = RunNote(
        run_id=run.id,
        kind="decision",
        summary=node.verdict[:512],
        content_md="\n".join(f"- {line}" for line in (node.reading_json or [])) or None,
        structured_json={"research_map": research_map.key, "node": node.key, "decision": node.decision, "stage": node.stage},
        author_type=by[0],
        author_id=by[1],
        client_event_id=f"map:{research_map.key}:{node.key}:decide:{int(utcnow().timestamp() * 1000)}",
    )
    db.add(note)
    db.flush()
    return {"id": note.id, "run_id": run.id, "summary": note.summary}


def publish_map_change(research_map: ResearchMap, message_type: str = "research_map.updated") -> None:
    publish_change(message_type, project_id=research_map.project_id, research_id=research_map.research_id, research_map_id=research_map.id, research_map_key=research_map.key)


# ---------------------------------------------------------------------------
# status / lint
# ---------------------------------------------------------------------------


def brief(node: ResearchMapNode) -> dict[str, Any]:
    return {"key": node.key, "title": node.title, "stage": node.stage, "decision": node.decision, "updated_at": node.updated_at.isoformat()}


def map_status(db: Session, research_map: ResearchMap) -> dict[str, Any]:
    nodes = map_nodes(db, research_map)
    now = datetime.now(timezone.utc)
    results_without_decision: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    not_advanced: list[dict[str, Any]] = []
    failed_quality: list[dict[str, Any]] = []
    broken_bindings: list[dict[str, Any]] = []
    bound_run_ids: set[str] = set()
    for node in nodes:
        run = bound_run(db, node, research_map.primary_metric)
        if run:
            bound_run_ids.add(run.id)
        flags = node_flags(node, run, now)
        if "ready" in flags:
            results_without_decision.append(brief(node))
        if "stale" in flags:
            stale.append(brief(node))
        if "not_advanced" in flags:
            not_advanced.append(brief(node))
        if node.binding_kind and node.binding_id and not db.get(BINDING_MODELS[node.binding_kind], node.binding_id):
            broken_bindings.append({**brief(node), "binding": {"kind": node.binding_kind, "id": node.binding_id}})
        if run and run.status == "completed" and node.decision == ResearchMapDecision.accepted.value and run_quality(db, run).get("severity") == "error":
            failed_quality.append({**brief(node), "run_id": run.id})
    runs_without_node: list[dict[str, Any]] = []
    if research_map.research_id:
        branch_ids = [b.id for b in db.scalars(select(Branch).where(Branch.research_id == research_map.research_id)).all()]
        if branch_ids:
            candidates = db.scalars(select(Run).where(Run.branch_id.in_(branch_ids), Run.status == "completed").order_by(Run.updated_at.desc()).limit(50)).all()
            runs_without_node = [{"id": r.id, "name": r.name, "branch_id": r.branch_id, "updated_at": r.updated_at.isoformat()} for r in candidates if r.id not in bound_run_ids][:20]
    return {
        "map_id": research_map.id,
        "key": research_map.key,
        "nodes": len(nodes),
        "baseline": research_map.baseline_node_key,
        "mainline": len(mainline_keys(nodes, research_map.baseline_node_key)),
        "counts": counts_for(nodes),
        "results_without_decision": results_without_decision,
        "stale": stale,
        "accepted_not_advanced": not_advanced,
        "bound_runs_failed_quality": failed_quality,
        "broken_bindings": broken_bindings,
        "unbound": [brief(n) for n in nodes if not n.binding_kind],
        "runs_without_node": runs_without_node,
        "last_updated_at": max((n.updated_at for n in nodes), default=research_map.updated_at).isoformat(),
    }


def lint_map(db: Session, research_map: ResearchMap) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    nodes = map_nodes(db, research_map)

    def add(node: ResearchMapNode, code: str, severity: str, message: str, fix: str | None = None) -> None:
        issues.append({"node_key": node.key, "code": code, "severity": severity, "message": message, "fix": fix})

    for node in nodes:
        if len(node.title or "") > LIMITS["title"]:
            add(node, "title_too_long", "warning", f"标题 {len(node.title)} 字，建议 ≤ {LIMITS['title']}", "缩成名词短语，结论放到 verdict")
        if node.hypothesis and len(node.hypothesis) > LIMITS["hypothesis"]:
            add(node, "hypothesis_too_long", "warning", f"假设 {len(node.hypothesis)} 字，建议一句 ≤ {LIMITS['hypothesis']}", "只写这个节点要验证的一件事")
        if len(node.change_json or []) > LIMITS["change"]:
            add(node, "too_many_changes", "warning", f"改动 {len(node.change_json)} 条，建议 ≤ {LIMITS['change']}", "只写相对父节点不同的地方")
        if len(node.reading_json or []) > LIMITS["reading"]:
            add(node, "too_many_readings", "warning", f"解读 {len(node.reading_json)} 条，建议 ≤ {LIMITS['reading']}")
        if any(len(item) > LIMITS["reading_item"] for item in node.reading_json or []):
            add(node, "reading_too_long", "warning", f"解读条目超过 {LIMITS['reading_item']} 字", "每条一个事实，带数字")
        if node.verdict and len(node.verdict) > LIMITS["verdict"]:
            add(node, "verdict_too_long", "warning", f"结论 {len(node.verdict)} 字，建议一句 ≤ {LIMITS['verdict']}")
        if len(node.caveats_json or []) > LIMITS["caveats"]:
            add(node, "too_many_caveats", "warning", f"短板 {len(node.caveats_json)} 条，建议 ≤ {LIMITS['caveats']}")
        if node.date_label and len(node.date_label) > LIMITS["date_label"]:
            add(node, "date_label_too_long", "info", f"日期标签 {len(node.date_label)} 字，建议 ≤ {LIMITS['date_label']}")
        if node.decision and not node.verdict:
            add(node, "decision_without_verdict", "warning", "写了去向但没有结论", "用 bbox map node decide --verdict 补一句结论")
        run = bound_run(db, node, research_map.primary_metric)
        if node.decision == ResearchMapDecision.accepted.value:
            if not node.binding_kind:
                add(node, "accepted_without_binding", "warning", "采纳的节点没有绑定实体", "绑定 run / 分支 / 对比集作为证据")
            elif run and run.status == "completed" and run_quality(db, run).get("severity") == "error":
                add(node, "accepted_failed_quality", "error", "采纳的节点绑定的 run 未过质量门")
            if run and not db.scalar(select(RunNote.id).where(RunNote.run_id == run.id, RunNote.kind == "decision").limit(1)):
                add(node, "accepted_without_note", "info", "采纳的节点在 run 上没有 decision note", "decide 时加 --note")
        if node.stage in {"tracking", "simulation", "live"} and node.decision != ResearchMapDecision.accepted.value:
            add(node, "stage_requires_accepted", "warning", f"阶段 {node.stage} 通常要求去向为采纳")
        if node.binding_kind and node.binding_id and not db.get(BINDING_MODELS[node.binding_kind], node.binding_id):
            add(node, "binding_missing", "error", f"绑定的 {node.binding_kind} {node.binding_id} 不存在")
    if research_map.baseline_node_key and not any(n.key == research_map.baseline_node_key for n in nodes):
        issues.append({"node_key": None, "code": "baseline_missing", "severity": "error", "message": "基准指向不存在的节点", "fix": None})
    counts = {"error": 0, "warning": 0, "info": 0}
    for issue in issues:
        counts[issue["severity"]] = counts.get(issue["severity"], 0) + 1
    return {"map_id": research_map.id, "key": research_map.key, "issues": issues, "counts": counts, "severity": "error" if counts["error"] else "warning" if counts["warning"] else "ok"}


def maps_for_research(db: Session, research: Research) -> list[ResearchMap]:
    ids = {m.id for m in db.scalars(select(ResearchMap).where(ResearchMap.research_id == research.id)).all()}
    branch_ids = {b.id for b in db.scalars(select(Branch).where(Branch.research_id == research.id)).all()}
    run_ids = {r.id for r in db.scalars(select(Run).where(Run.branch_id.in_(list(branch_ids)))).all()} if branch_ids else set()
    compare_ids = {c.id for c in db.scalars(select(CompareSet).where(CompareSet.research_id == research.id)).all()}
    targets = list(branch_ids | run_ids | compare_ids | {research.id})
    for node in db.scalars(select(ResearchMapNode).where(ResearchMapNode.binding_id.in_(targets))).all():
        ids.add(node.map_id)
    if not ids:
        return []
    return list(db.scalars(select(ResearchMap).where(ResearchMap.id.in_(list(ids))).order_by(ResearchMap.updated_at.desc())).all())


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------


def register_research_map_routes(app: FastAPI) -> None:
    @app.post("/api/v1/research-maps")
    def create_research_map(payload: ResearchMapCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
        project = resolve_project_ref(db, payload.project_id, payload.project_key, payload.project)
        research = resolve_research_ref(db, project, payload.research_id, payload.research_key, payload.research)
        existing = db.scalar(select(ResearchMap).where(ResearchMap.project_id == project.id, ResearchMap.key == payload.key))
        if existing:
            return ok(map_summary(db, existing))
        by = actor(payload)
        research_map = ResearchMap(project_id=project.id, research_id=research.id if research else None, key=payload.key, title=payload.title, status=payload.status.value, created_by_type=by[0], created_by_id=by[1])
        apply_map_fields(research_map, payload)
        db.add(research_map)
        db.flush()
        record(db, research_map, "map.create", f"创建地图 {research_map.title}", by=by)
        db.commit()
        db.refresh(research_map)
        publish_map_change(research_map, "research_map.created")
        return ok(map_summary(db, research_map))

    @app.get("/api/v1/research-maps")
    def list_research_maps(
        project: str | None = Query(default=None, description="project id or key"),
        project_id: str | None = None,
        research: str | None = Query(default=None, description="research id or key"),
        research_id: str | None = None,
        key: str | None = None,
        status: str | None = None,
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        query = select(ResearchMap)
        if project or project_id:
            query = query.where(ResearchMap.project_id == resolve_project_ref(db, project_id, project).id)
        if research or research_id:
            ref = research_id or research
            found = db.get(Research, ref) or db.scalar(select(Research).where(Research.key == ref))
            if not found:
                raise ApiError(ErrorCode.not_found, f"research {ref} not found")
            related = [m.id for m in maps_for_research(db, found)]
            query = query.where(ResearchMap.id.in_(related)) if related else query.where(ResearchMap.id.is_(None))
        if key:
            query = query.where(ResearchMap.key == key)
        if status:
            query = query.where(ResearchMap.status == status)
        items = db.scalars(query.order_by(ResearchMap.updated_at.desc())).all()
        return ok([map_summary(db, item) for item in items])

    @app.get("/api/v1/projects/{project_id}/research-maps")
    def list_project_research_maps(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        project = resolve_project_ref(db, project_id)
        items = db.scalars(select(ResearchMap).where(ResearchMap.project_id == project.id).order_by(ResearchMap.updated_at.desc())).all()
        return ok([map_summary(db, item) for item in items])

    @app.get("/api/v1/researches/{research_id}/research-maps")
    def list_research_research_maps(research_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        research = db.get(Research, research_id)
        if not research:
            raise ApiError(ErrorCode.not_found, "research not found")
        return ok([map_summary(db, item) for item in maps_for_research(db, research)])

    @app.post("/api/v1/research-maps/import")
    def import_research_map_document(payload: ResearchMapDocumentImport, db: Session = Depends(get_db)) -> dict[str, Any]:
        project = resolve_project_ref(db, payload.project_id, payload.project_key, payload.project)
        research = resolve_research_ref(db, project, payload.research_id, payload.research_key, payload.research)
        by = actor(payload)
        research_map = db.scalar(select(ResearchMap).where(ResearchMap.project_id == project.id, ResearchMap.key == payload.key))
        created_map = False
        if research_map is None:
            if not payload.title:
                raise ApiError(ErrorCode.validation_error, "title is required when the research map does not exist yet")
            research_map = ResearchMap(project_id=project.id, research_id=research.id if research else None, key=payload.key, title=payload.title, status=(payload.status.value if payload.status else "active"), created_by_type=by[0], created_by_id=by[1])
            db.add(research_map)
            db.flush()
            record(db, research_map, "map.create", f"导入创建地图 {research_map.title}", by=by)
            created_map = True
        elif research is not None:
            research_map.research_id = research.id
        apply_map_fields(research_map, payload)
        summary = import_nodes(db, research_map, payload.nodes, mode=payload.mode, by=by)
        if "baseline" in payload.model_fields_set:
            set_baseline(db, research_map, payload.baseline, "import", by)
        if research_map.baseline_node_key and not find_node(db, research_map, research_map.baseline_node_key):
            raise ApiError(ErrorCode.validation_error, f"baseline {research_map.baseline_node_key} does not match any node")
        record(db, research_map, "map.import", f"导入：新增 {summary['created']}，更新 {summary['updated']}，删除 {summary['deleted']}", changes=summary, by=by)
        db.commit()
        db.refresh(research_map)
        publish_map_change(research_map, "research_map.created" if created_map else "research_map.updated")
        return ok({"map": map_detail(db, research_map), "map_created": created_map, "nodes": summary})

    @app.get("/api/v1/research-maps/{map_id}")
    def get_research_map(map_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        return ok(map_detail(db, require_map(db, map_id)))

    @app.get("/api/v1/research-maps/{map_id}/export")
    def export_research_map(map_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        return ok(export_document(db, require_map(db, map_id)))

    @app.get("/api/v1/research-maps/{map_id}/status")
    def research_map_status(map_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        return ok(map_status(db, require_map(db, map_id)))

    @app.get("/api/v1/research-maps/{map_id}/lint")
    def research_map_lint(map_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        return ok(lint_map(db, require_map(db, map_id)))

    @app.get("/api/v1/research-maps/{map_id}/revisions")
    def research_map_revisions(map_id: str, node_key: str | None = None, limit: int = 50, db: Session = Depends(get_db)) -> dict[str, Any]:
        research_map = require_map(db, map_id)
        query = select(ResearchMapRevision).where(ResearchMapRevision.map_id == research_map.id)
        if node_key:
            query = query.where(ResearchMapRevision.node_key == node_key)
        rows = db.scalars(query.order_by(ResearchMapRevision.created_at.desc()).limit(max(1, min(limit, 500)))).all()
        return ok([
            {"id": r.id, "node_key": r.node_key, "action": r.action, "summary": r.summary, "changes": r.changes_json, "by_type": r.by_type, "by_id": r.by_id, "created_at": r.created_at.isoformat()}
            for r in rows
        ])

    @app.patch("/api/v1/research-maps/{map_id}")
    def update_research_map(map_id: str, payload: ResearchMapUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
        research_map = require_map(db, map_id)
        by = actor(payload)
        changes = apply_map_fields(research_map, payload)
        if "research_id" in payload.model_fields_set:
            project = db.get(Project, research_map.project_id)
            research = resolve_research_ref(db, project, payload.research_id) if payload.research_id else None
            changes["research_id"] = {"from": research_map.research_id, "to": research.id if research else None}
            research_map.research_id = research.id if research else None
        if changes:
            record(db, research_map, "map.update", "更新 " + "、".join(changes.keys()), changes=changes, by=by)
        db.commit()
        db.refresh(research_map)
        publish_map_change(research_map)
        return ok(map_summary(db, research_map))

    @app.post("/api/v1/research-maps/{map_id}/baseline")
    def set_research_map_baseline(map_id: str, payload: ResearchMapBaselineSet, db: Session = Depends(get_db)) -> dict[str, Any]:
        research_map = require_map(db, map_id)
        set_baseline(db, research_map, payload.node_key, payload.reason, actor(payload))
        db.commit()
        db.refresh(research_map)
        publish_map_change(research_map)
        return ok(map_summary(db, research_map))

    @app.post("/api/v1/research-maps/{map_id}/nodes")
    def create_research_map_node(map_id: str, payload: ResearchMapNodeCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
        research_map = require_map(db, map_id)
        existing = find_node(db, research_map, payload.key)
        if existing:
            return ok(single_node(db, research_map, existing))
        node = create_node(db, research_map, payload, actor(payload))
        db.commit()
        db.refresh(node)
        publish_map_change(research_map)
        return ok(single_node(db, research_map, node))

    @app.get("/api/v1/research-maps/{map_id}/nodes")
    def list_research_map_nodes(map_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        return ok(map_detail(db, require_map(db, map_id))["nodes"])

    @app.post("/api/v1/research-maps/{map_id}/nodes/import")
    def import_research_map_nodes(map_id: str, payload: ResearchMapNodesImport, db: Session = Depends(get_db)) -> dict[str, Any]:
        research_map = require_map(db, map_id)
        by = actor(payload)
        summary = import_nodes(db, research_map, payload.nodes, mode=payload.mode, by=by)
        record(db, research_map, "map.import", f"导入节点：新增 {summary['created']}，更新 {summary['updated']}，删除 {summary['deleted']}", changes=summary, by=by)
        research_map.updated_at = utcnow()
        db.commit()
        publish_map_change(research_map)
        return ok({"map": map_detail(db, research_map), "nodes": summary})

    @app.get("/api/v1/research-maps/{map_id}/nodes/{node_key}")
    def get_research_map_node(map_id: str, node_key: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        research_map = require_map(db, map_id)
        return ok(single_node(db, research_map, require_node(db, research_map, node_key)))

    @app.put("/api/v1/research-maps/{map_id}/nodes/{node_key}")
    def upsert_research_map_node(map_id: str, node_key: str, payload: ResearchMapNodeUpsert, db: Session = Depends(get_db)) -> dict[str, Any]:
        research_map = require_map(db, map_id)
        node, created = upsert_node(db, research_map, node_key, payload, actor(payload))
        db.commit()
        db.refresh(node)
        publish_map_change(research_map)
        return ok({**single_node(db, research_map, node), "created": created})

    @app.patch("/api/v1/research-maps/{map_id}/nodes/{node_key}")
    def update_research_map_node(map_id: str, node_key: str, payload: ResearchMapNodeUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
        research_map = require_map(db, map_id)
        node = require_node(db, research_map, node_key)
        update_node(db, research_map, node, payload, actor(payload))
        db.commit()
        db.refresh(node)
        publish_map_change(research_map)
        return ok(single_node(db, research_map, node))

    @app.post("/api/v1/research-maps/{map_id}/nodes/{node_key}/decide")
    def decide_research_map_node(map_id: str, node_key: str, payload: ResearchMapNodeDecide, db: Session = Depends(get_db)) -> dict[str, Any]:
        research_map = require_map(db, map_id)
        node = require_node(db, research_map, node_key)
        by = actor(payload)
        update = ResearchMapNodeUpdate(**payload.model_dump(exclude_unset=True, exclude={"note"}))
        update_node(db, research_map, node, update, by, action="node.decide", summary=f"去向 {payload.decision.value}" + (f"：{payload.verdict}" if payload.verdict else ""))
        note = write_decision_note(db, research_map, node, by) if payload.note else None
        db.commit()
        db.refresh(node)
        publish_map_change(research_map)
        return ok({**single_node(db, research_map, node), "note": note})

    @app.post("/api/v1/research-maps/{map_id}/nodes/{node_key}/advance")
    def advance_research_map_node(map_id: str, node_key: str, payload: ResearchMapNodeAdvance, db: Session = Depends(get_db)) -> dict[str, Any]:
        research_map = require_map(db, map_id)
        node = require_node(db, research_map, node_key)
        fields: dict[str, Any] = {"stage": payload.stage, "reason": payload.reason}
        if payload.date_label:
            fields["date_label"] = payload.date_label
        update_node(db, research_map, node, ResearchMapNodeUpdate(**fields), actor(payload), action="node.advance", summary=f"阶段 → {payload.stage.value}")
        db.commit()
        db.refresh(node)
        publish_map_change(research_map)
        return ok(single_node(db, research_map, node))

    @app.delete("/api/v1/research-maps/{map_id}/nodes/{node_key}")
    def delete_research_map_node(map_id: str, node_key: str, cascade: bool = False, created_by_type: str | None = None, created_by_id: str | None = None, db: Session = Depends(get_db)) -> dict[str, Any]:
        research_map = require_map(db, map_id)
        node = require_node(db, research_map, node_key)
        children = descendants(db, research_map, node)
        if children and not cascade:
            raise ApiError(ErrorCode.state_error, f"node {node.key} has {len(children)} descendant node(s)", "pass cascade=true to delete the whole subtree, or move the children first")
        removed = [node.key] + [child.key for child in children]
        by = (created_by_type or ("agent" if created_by_id else "human"), created_by_id)
        delete_nodes(db, research_map, [node] + children, by)
        research_map.updated_at = utcnow()
        db.commit()
        publish_map_change(research_map)
        return ok({"deleted": removed, "count": len(removed)})
