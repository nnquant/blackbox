"""Small, scoped read models for the WebUI. Existing SDK endpoints stay unchanged."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import timedelta
from typing import Any

from fastapi import Depends, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import String, case, cast, func, or_, select
from sqlalchemy.orm import Session, load_only

from .db import get_db
from .models import (Artifact, Branch, CompareSet, Project, Research, Run, RunEvent,
                     RunMetric, RunNote, SearchView, Sweep, Workspace, ResearchMap, ResearchMapNode, utcnow)
from .representatives import choose_representative, manual_baseline_ids, representative_rows


def response(request: Request, data: Any):
    payload = jsonable_encoder({"ok": True, "data": data, "error": None})
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    tag = '"' + hashlib.sha256(encoded).hexdigest() + '"'
    headers = {"ETag": tag, "Cache-Control": "private, no-cache"}
    if request.headers.get("if-none-match") == tag:
        return Response(status_code=304, headers=headers)
    return Response(encoded, media_type="application/json", headers=headers)


def fields(row, names):
    return {name: getattr(row, name) for name in names.split()}


def entity(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


RUN_FIELDS = "id branch_id name title status source_run_id sequence_no summary_json tags mode started_at ended_at created_by_type created_by_id created_at updated_at"


def report_condition():
    return or_(func.lower(Artifact.kind).contains("report"), func.lower(Artifact.name).contains("report"), *(func.lower(Artifact.filename).endswith(suffix) for suffix in [".html", ".htm", ".pdf"]))


def compact_runs(db, query):
    names = RUN_FIELDS.replace("summary_json ", "")
    records = db.execute(query.options(load_only(*(getattr(Run, key) for key in names.split()))).add_columns(Run.summary_json["strategy.summary"])).all()
    rows = [row[0] for row in records]
    summaries = {row.id: metrics for row, metrics in records}
    branches = {b.id: b for b in db.scalars(select(Branch).where(Branch.id.in_({r.branch_id for r in rows})))} if rows else {}
    researches = {r.id: r for r in db.scalars(select(Research).where(Research.id.in_({b.research_id for b in branches.values()})))} if branches else {}
    projects = {p.id: p for p in db.scalars(select(Project).where(Project.id.in_({r.project_id for r in researches.values()})))} if researches else {}
    artifacts = {}
    if rows:
        for run_id, kind, count, reports in db.execute(select(Artifact.run_id, Artifact.kind, func.count(), func.sum(case((report_condition(), 1), else_=0))).where(Artifact.run_id.in_([r.id for r in rows])).group_by(Artifact.run_id, Artifact.kind)):
            summary = artifacts.setdefault(run_id, {"artifact_count": 0, "artifact_kinds": [], "has_report_artifact": False})
            summary["artifact_count"] += count
            summary["artifact_kinds"].append(kind)
            summary["has_report_artifact"] |= bool(reports)
    pins = manual_baseline_ids(db)
    result = []
    for run in rows:
        row = fields(run, names)
        row["summary_json"] = {"strategy.summary": summaries.get(run.id) or {}}
        branch = branches.get(run.branch_id)
        research = researches.get(branch.research_id) if branch else None
        project = projects.get(research.project_id) if research else None
        for prefix, item in [("branch", branch), ("research", research), ("project", project)]:
            row.update({f"{prefix}_{key}": getattr(item, key, None) for key in ["id", "key", "title"]})
        row.update(artifacts.get(run.id, {"artifact_count": 0, "artifact_kinds": [], "has_report_artifact": False}))
        row["is_manual_baseline"] = run.id in pins
        result.append(row)
    return result


def representatives(db, research_ids):
    branches = dict(db.execute(select(Branch.id, Branch.research_id).where(Branch.research_id.in_(research_ids))).all())
    if not branches:
        return {}
    pins = manual_baseline_ids(db)
    chosen = {}
    for row in representative_rows(db, branch_ids=list(branches)):
        key = branches[row.branch_id]
        previous = chosen.get(key)
        chosen[key] = choose_representative([previous, row] if previous else [row], pins)
    by_id = {r["id"]: r for r in compact_runs(db, select(Run).where(Run.id.in_([r.id for r in chosen.values()])))}
    return {key: by_id[row.id] for key, row in chosen.items()}


def project_rows(db):
    research_counts = dict(db.execute(select(Research.project_id, func.count()).group_by(Research.project_id)).all())
    branch_counts = dict(db.execute(select(Research.project_id, func.count(Branch.id)).join(Branch).group_by(Research.project_id)).all())
    run_counts = {row[0]: row[1:] for row in db.execute(select(Research.project_id, func.count(Run.id), func.sum(case((Run.status == "running", 1), else_=0))).select_from(Research).join(Branch).join(Run).group_by(Research.project_id))}
    return [{**entity(p), "research_count": research_counts.get(p.id, 0), "branch_count": branch_counts.get(p.id, 0), "run_count": run_counts.get(p.id, (0, 0))[0], "running_run_count": run_counts.get(p.id, (0, 0))[1]} for p in db.scalars(select(Project).order_by(Project.updated_at.desc()))]


def register_ui_routes(app):
    # Import after main's helpers exist; no application startup side effects here.
    from . import main as m
    from . import research_maps as maps

    @app.get("/api/v1/ui/maps/{map_id}")
    def map_canvas(request: Request, map_id: str, db: Session = Depends(get_db)):
        research_map = maps.require_map(db, map_id)
        nodes = maps.map_nodes(db, research_map)
        branch_ids = {n.binding_id for n in nodes if n.binding_kind == "branch"}
        branches = {b.id: b for b in db.scalars(select(Branch).where(Branch.id.in_(branch_ids)))} if branch_ids else {}
        selected = {}
        pins = manual_baseline_ids(db)
        if branches:
            for candidate in representative_rows(db, research_map.primary_metric, list(branches)):
                previous = selected.get(candidate.branch_id)
                selected[candidate.branch_id] = choose_representative([previous, candidate] if previous else [candidate], pins, research_map.primary_metric)
        run_ids = {n.binding_id for n in nodes if n.binding_kind == "run"} | {r.id for r in selected.values()}
        runs = {r.id: r for r in db.scalars(select(Run).where(Run.id.in_(run_ids)).options(load_only(Run.id, Run.branch_id, Run.name, Run.title, Run.status, Run.mode, Run.summary_json, Run.updated_at, Run.started_at, Run.ended_at)))} if run_ids else {}
        keys = {n.id: n.key for n in nodes}
        mainline = maps.mainline_keys(nodes, research_map.baseline_node_key)
        rows = []
        for node in nodes:
            candidate = selected.get(node.binding_id) if node.binding_kind == "branch" else None
            run = runs.get(candidate.id if candidate else node.binding_id) if node.binding_kind in {"branch", "run"} else None
            binding = {"kind": node.binding_kind, "id": node.binding_id, "exists": bool(run) if node.binding_kind == "run" else bool(branches.get(node.binding_id)) if node.binding_kind == "branch" else True} if node.binding_kind else None
            if binding and run:
                binding["run"] = {**fields(run, "id name title branch_id status mode"), "metrics": maps.run_metrics(run, research_map.primary_metric), "quality": {"severity": "not_loaded"}}
            rows.append({"id": node.id, "map_id": node.map_id, "key": node.key, "parent_id": node.parent_id, "parent_key": keys.get(node.parent_id), "position": node.position, "title": node.title, "date_label": node.date_label, "stage": node.stage, "decision": node.decision, "family": maps.research_map_family(node.stage, node.decision), "is_baseline": node.key == research_map.baseline_node_key, "is_mainline": node.key in mainline, "flags": maps.node_flags(node, run, utcnow()), "binding": binding, "created_at": node.created_at, "updated_at": node.updated_at})
        baseline = next((r for r in rows if r["is_baseline"]), None)
        data = fields(research_map, "id project_id research_id key title subtitle description status baseline_node_key primary_metric settings_json updated_at")
        project = db.get(Project, research_map.project_id)
        research = db.get(Research, research_map.research_id) if research_map.research_id else None
        recent = sorted(nodes, key=lambda n: n.updated_at or n.created_at, reverse=True)
        data.update({"project_key": project.key if project else None, "research_key": research.key if research else None, "last_updated_at": recent[0].updated_at if recent else research_map.updated_at, "recent": [fields(n, "key title stage decision updated_at updated_by_type updated_by_id") for n in recent[:4]], "nodes": rows, "mainline_keys": sorted(mainline), "node_count": len(rows), "counts": maps.counts_for(nodes), "baseline": {"key": baseline["key"], "title": baseline["title"], "run": (baseline.get("binding") or {}).get("run")} if baseline else None})
        return response(request, data)

    @app.get("/api/v1/ui/maps/{map_id}/nodes/{node_key}")
    def map_node(request: Request, map_id: str, node_key: str, db: Session = Depends(get_db)):
        research_map = maps.require_map(db, map_id)
        node = maps.find_node(db, research_map, node_key)
        if node is None:
            raise m.ApiError(m.ErrorCode.not_found, "Map node not found")
        db.info["ui_quality_cache"] = True
        db.info["map_detail_cache"] = {}
        try:
            return response(request, maps.single_node(db, research_map, node))
        finally:
            db.info.pop("ui_quality_cache", None)
            db.info.pop("map_detail_cache", None)

    @app.get("/api/v1/ui/context")
    def context(request: Request, view: str = "dashboard", id: str | None = None, db: Session = Depends(get_db)):
        if not id and view in {"research", "branch", "run"}:
            model = {"research": Research, "branch": Branch, "run": Run}[view]
            id = db.scalar(select(model.id).order_by(model.updated_at.desc()).limit(1))
        data = {key: [] for key in ["projects", "researches", "branches", "runs", "workspaces", "sweeps", "compare_sets", "search_views", "notes", "artifacts"]}
        data["summary"] = {}
        # Navigation gets identities only, never descendants, previews or Run bodies.
        data["projects"] = [fields(p, "id key title workspace_id updated_at") for p in db.scalars(select(Project).order_by(Project.updated_at.desc()))]
        research = branch = run = project = None
        if id and view == "run":
            run = m.require_run(db, id)
            branch = m.require_branch(db, run.branch_id)
        elif id and view == "branch":
            branch = m.require_branch(db, id)
        if branch:
            data["branches"] = [entity(branch)]
            research = m.require_research(db, branch.research_id)
        elif id and view == "research":
            research = m.require_research(db, id)
        if research:
            project = m.require_project(db, research.project_id)
            data["researches"] = [{**entity(research), "project_key": project.key}]
        elif id and view == "project":
            project = m.require_project(db, id)
        if project:
            data["projects"] = [entity(project) if p["id"] == project.id else p for p in data["projects"]]
        if run:
            data["runs"] = compact_runs(db, select(Run).where(Run.id == run.id))
        if id and view == "compare":
            data["compare_sets"] = [entity(m.require_compare_set(db, id))]
        if id and view == "search":
            data["search_views"] = [entity(m.require_search_view(db, id))]
        return response(request, data)

    @app.get("/api/v1/ui/catalog")
    def catalog(request: Request, kind: str, parent: str | None = None, purpose: str = "content", q: str = "", page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db)):
        models = {"projects": Project, "workspaces": Workspace, "researches": Research, "branches": Branch, "compare_sets": CompareSet, "search_views": SearchView, "sweeps": Sweep, "maps": ResearchMap}
        if kind not in models:
            raise m.ApiError(m.ErrorCode.validation_error, "Unknown catalog")
        model = models[kind]
        query = select(model)
        if q.strip():
            columns = [getattr(model, key) for key in ["key", "title", "name", "id"] if hasattr(model, key)]
            query = query.where(or_(*(column.icontains(q.strip(), autoescape=True) for column in columns)))
        if parent and kind in {"researches", "compare_sets", "search_views"}:
            query = query.where(model.project_id == parent)
        elif parent and kind == "branches":
            query = query.where(Branch.research_id == parent)
        total = db.scalar(select(func.count()).select_from(query.subquery()))
        rows = db.scalars(query.order_by(model.created_at.desc(), model.id).offset((page - 1) * limit).limit(limit)).all()
        items = [fields(row, "id key title") if purpose == "nav" or kind == "maps" else entity(row) for row in rows]
        if kind in {"branches", "researches"}:
            group = Run.branch_id if kind == "branches" else Branch.research_id
            stats = dict(db.execute(select(group, func.count(Run.id)).select_from(Branch).join(Run).where((Branch.id if kind == "branches" else Branch.research_id).in_([r.id for r in rows])).group_by(group)).all())
            for row in items:
                row["run_count"] = stats.get(row["id"], 0)
        return response(request, {"rows": items, "total": total, "page": page, "limit": limit})

    @app.get("/api/v1/ui/overview")
    def overview(request: Request, section: str = "summary", page: int = Query(1, ge=1), db: Session = Depends(get_db)):
        if section == "activity":
            return response(request, {"run_activity_daily": m.run_activity_daily(db)})
        if section == "projects":
            return response(request, {"projects": project_rows(db), "workspaces": [entity(w) for w in db.scalars(select(Workspace))]})
        if section == "summary":
            now = utcnow()
            row = db.execute(select(func.count(), func.sum(case((Run.created_at >= now.replace(hour=0, minute=0, second=0, microsecond=0), 1), else_=0)), func.sum(case((Run.status == "running", 1), else_=0)), func.sum(case(((Run.status == "failed") & (Run.updated_at >= now - timedelta(days=1)), 1), else_=0))).select_from(Run)).one()
            return response(request, {"summary": dict(zip(["runs", "today_runs", "running_runs", "failed_runs_24h"], [int(v or 0) for v in row])) | {"new_branches_24h": db.scalar(select(func.count()).select_from(Branch).where(Branch.created_at >= now - timedelta(days=1)))}})
        if section in {"recent", "quality"}:
            query = select(Run)
            if section == "quality":
                rows = compact_runs(db, query.order_by(Run.updated_at.desc(), Run.id).limit(200))
                def needs_attention(run):
                    if run["status"] in {"failed", "cancelled"}:
                        return True
                    value = run["summary_json"].get("strategy.summary", {}).get("sharpe")
                    try:
                        finite = math.isfinite(float(value or 0))
                    except (TypeError, ValueError):
                        finite = False
                    return not finite and not run["artifact_count"]
                return response(request, {"runs": [r for r in rows if needs_attention(r)][:8]})
            return response(request, {"runs": compact_runs(db, query.order_by(Run.updated_at.desc(), Run.id).limit(10))})
        if section in {"researches", "decisions"}:
            return research_page(request, page=page, limit=8, activity=section == "researches", db=db)
        if section == "system":
            return response(request, {"workspaces": [entity(w) for w in db.scalars(select(Workspace))], "projects": project_rows(db), "runs": compact_runs(db, select(Run).order_by(Run.updated_at.desc()).limit(20))})
        raise m.ApiError(m.ErrorCode.validation_error, "Unknown overview section")

    @app.get("/api/v1/ui/researches")
    def research_page(request: Request, project: str | None = None, activity: bool = False, page: int = Query(1, ge=1), limit: int = Query(30, ge=1, le=100), db: Session = Depends(get_db)):
        query = select(Research)
        if project:
            query = query.where(Research.project_id == project)
        total = db.scalar(select(func.count()).select_from(query.subquery()))
        if activity:
            latest = select(Branch.research_id.label("research_id"), func.max(Run.updated_at).label("latest")).join(Run).group_by(Branch.research_id).subquery()
            query = query.outerjoin(latest, latest.c.research_id == Research.id).order_by(func.coalesce(latest.c.latest, Research.updated_at).desc())
        rows = db.scalars(query.order_by(Research.updated_at.desc(), Research.id).offset((page - 1) * limit).limit(limit)).all()
        ids = [r.id for r in rows]
        champions = representatives(db, ids)
        since = utcnow() - timedelta(days=7)
        counts = {r[0]: r[1:] for r in db.execute(select(Branch.research_id, func.count(Run.id), func.sum(case((Run.created_at >= since, 1), else_=0)), func.sum(case(((Run.status == "failed") & (Run.updated_at >= since), 1), else_=0)), func.max(Run.updated_at)).join(Run, isouter=True).where(Branch.research_id.in_(ids)).group_by(Branch.research_id))}
        branch_counts = dict(db.execute(select(Branch.research_id, func.count()).where(Branch.research_id.in_(ids)).group_by(Branch.research_id)).all())
        return response(request, {"researches": [{**entity(r), "champion_run": champions.get(r.id), "branch_count": branch_counts.get(r.id, 0), "run_count": counts.get(r.id, (0, 0, 0, None))[0], "run_count_7d": counts.get(r.id, (0, 0, 0, None))[1] or 0, "failed_run_count_7d": counts.get(r.id, (0, 0, 0, None))[2] or 0, "latest_run_at": counts.get(r.id, (0, 0, 0, None))[3]} for r in rows], "total": total, "page": page, "limit": limit})

    @app.get("/api/v1/ui/runs")
    def runs_page(request: Request, project: str | None = None, research: str | None = None, branch: str | None = None, status: str | None = None, creator: str | None = None, artifact: str | None = None, q: str = "", sort: str = "updated", direction: str = "desc", with_config: bool = False, page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db)):
        query = select(Run).join(Branch).join(Research).join(Project)
        for value, id_column, key_column in [(project, Project.id, Project.key), (research, Research.id, Research.key), (branch, Branch.id, Branch.key)]:
            if value:
                query = query.where(or_(id_column == value, key_column == value))
        if status:
            query = query.where(Run.status == status)
        if creator:
            query = query.where(Run.created_by_type == creator)
        if artifact:
            exists = select(Artifact.id).where(Artifact.run_id == Run.id)
            if artifact == "report":
                exists = exists.where(report_condition())
            elif artifact not in {"yes", "none"}:
                exists = exists.where(Artifact.kind == artifact)
            query = query.where(~exists.exists() if artifact == "none" else exists.exists())
        if q.strip():
            text_columns = [Run.name, Run.title, Run.id, Run.status, Run.branch_id, Run.created_by_type, Run.created_by_id, Branch.key, Research.key, Project.key, cast(Run.config_json, String), cast(Run.context_json, String), cast(Run.tags, String)]
            matching_artifact = select(Artifact.id).where(Artifact.run_id == Run.id, Artifact.kind.icontains(q.strip(), autoescape=True)).exists()
            query = query.where(or_(*(column.icontains(q.strip(), autoescape=True) for column in text_columns), matching_artifact))
        runtime = (func.julianday(Run.ended_at) - func.julianday(Run.started_at)) if db.bind.dialect.name == "sqlite" else func.extract('epoch', Run.ended_at - Run.started_at)
        artifact_count = select(func.count()).select_from(Artifact).where(Artifact.run_id == Run.id).correlate(Run).scalar_subquery()
        sort_column = {"updated": Run.updated_at, "created": Run.created_at, "name": Run.name, "project": Project.key, "branch": Branch.key, "creator": Run.created_by_type, "artifacts": artifact_count, "status": Run.status, "sharpe": Run.summary_json['strategy.summary']['sharpe'].as_float(), "max_drawdown": Run.summary_json['strategy.summary']['max_drawdown'].as_float(), "runtime": runtime}.get(sort, Run.updated_at)
        total = db.scalar(select(func.count()).select_from(query.subquery()))
        order = sort_column.asc() if direction == "asc" else sort_column.desc()
        rows = compact_runs(db, query.order_by(order, Run.id).offset((page - 1) * limit).limit(limit))
        if with_config and rows:
            configs = dict(db.execute(select(Run.id, Run.config_json).where(Run.id.in_([r["id"] for r in rows]))).all())
            for row in rows:
                row["config_json"] = configs[row["id"]]
        return response(request, {"runs": rows, "total": total, "page": page, "limit": limit})

    @app.get("/api/v1/ui/runs/{run_id}")
    def run_section(request: Request, run_id: str, section: str = "summary", page: int = Query(1, ge=1), db: Session = Depends(get_db)):
        run = m.require_run(db, run_id)
        data = compact_runs(db, select(Run).where(Run.id == run.id))[0]
        if section in {"results", "metrics", "artifacts"}:
            data["summary_json"] = run.summary_json
            artifacts = db.scalars(select(Artifact).where(Artifact.run_id == run.id).order_by(Artifact.created_at)).all()
            data["artifacts"] = [m.artifact_read_with_full_series(a) if section == "results" else entity(a) for a in artifacts]
            if section in {"results", "metrics"}:
                data["metrics"] = [entity(r) for r in db.scalars(select(RunMetric).where(RunMetric.run_id == run.id).order_by(RunMetric.created_at))]
        elif section == "config":
            data.update(fields(run, "config_json context_json"))
            source = db.get(Run, run.source_run_id) if run.source_run_id else None
            data["source_run"] = {"id": source.id, "name": source.name, "config_json": source.config_json} if source else None
            data["source_config_diff"] = m.build_pair_config_diff(source.config_json if source else {}, run.config_json or {}) if source else []
        elif section == "events":
            data["events"] = [entity(r) for r in db.scalars(select(RunEvent).where(RunEvent.run_id == run.id).order_by(RunEvent.sequence_no.desc()).offset((page - 1) * 100).limit(100))]
            data["section_total"] = db.scalar(select(func.count()).select_from(RunEvent).where(RunEvent.run_id == run.id))
        elif section == "notes":
            data["notes"] = [entity(r) for r in db.scalars(select(RunNote).where(RunNote.run_id == run.id).order_by(RunNote.created_at.desc(), RunNote.id).offset((page - 1) * 100).limit(100))]
            data["section_total"] = db.scalar(select(func.count()).select_from(RunNote).where(RunNote.run_id == run.id))
        elif section == "snapshots":
            data["snapshots"] = m.snapshot_detail(db, run.id)
        elif section != "summary":
            raise m.ApiError(m.ErrorCode.validation_error, "Unknown Run section")
        return response(request, data)

    @app.get("/api/v1/ui/branches/{branch_id}/summary")
    def branch_summary(request: Request, branch_id: str, db: Session = Depends(get_db)):
        branch = m.require_branch(db, branch_id)
        champion = maps.branch_champion(db, branch, "strategy.summary.sharpe")
        counts = dict(db.execute(select(Run.status, func.count()).where(Run.branch_id == branch_id).group_by(Run.status)).all())
        latest = db.scalar(select(Run.name).where(Run.branch_id == branch_id).order_by(Run.updated_at.desc(), Run.id).limit(1))
        return response(request, {"branch": {**entity(branch), "run_count": sum(counts.values()), "completed_run_count": counts.get("completed", 0), "running_run_count": counts.get("running", 0), "failed_run_count": counts.get("failed", 0), "latest_run_name": latest}, "champion": compact_runs(db, select(Run).where(Run.id == champion.id))[0] if champion else None})

    @app.get("/api/v1/ui/branches/{branch_id}/evolution")
    def branch_evolution(request: Request, branch_id: str, page: int = Query(1, ge=1), db: Session = Depends(get_db)):
        m.require_branch(db, branch_id)
        query = select(Run).where(Run.branch_id == branch_id).order_by(Run.updated_at.desc(), Run.id).offset((page - 1) * 50).limit(50)
        rows = compact_runs(db, query)
        configs = {ident: (config, summary) for ident, config, summary in db.execute(select(Run.id, Run.config_json, Run.summary_json).where(Run.id.in_([r["id"] for r in rows])))}
        return response(request, {"runs": sorted([{**r, "config_json": configs[r["id"]][0], "summary_json": configs[r["id"]][1]} for r in rows], key=lambda r: r["created_at"])})

    @app.get("/api/v1/ui/scope-summary")
    def scope_summary(request: Request, project: str | None = None, research: str | None = None, db: Session = Depends(get_db)):
        query = select(Run.status, func.count(Run.id)).join(Branch).join(Research)
        if project:
            item = m.require_project(db, project)
            query = query.where(Research.project_id == project)
            branches = select(func.count()).select_from(Branch).join(Research).where(Research.project_id == project)
            extra = {"research_count": db.scalar(select(func.count()).select_from(Research).where(Research.project_id == project))}
        else:
            item = m.require_research(db, research)
            query = query.where(Research.id == research)
            branches = select(func.count()).select_from(Branch).where(Branch.research_id == research)
            extra = {}
        counts = dict(db.execute(query.group_by(Run.status)).all())
        latest = db.scalar(select(Run.name).join(Branch).join(Research).where(Research.project_id == project if project else Research.id == research).order_by(Run.updated_at.desc()).limit(1))
        return response(request, {**entity(item), **extra, "branch_count": db.scalar(branches), "run_count": sum(counts.values()), "completed_run_count": counts.get("completed", 0), "running_run_count": counts.get("running", 0), "failed_run_count": counts.get("failed", 0), "latest_run_name": latest})

    @app.get("/api/v1/ui/lineage")
    def lineage(request: Request, research: str | None = None, branch: str | None = None, page: int = Query(1, ge=1), db: Session = Depends(get_db)):
        current = m.require_branch(db, branch) if branch else None
        research_id = current.research_id if current else m.require_research(db, research).id
        branches = db.scalars(select(Branch).where(Branch.research_id == research_id).order_by(Branch.created_at)).all()
        by_id = {b.id: b for b in branches}
        ancestors, descendants = [], []
        if current:
            cursor = current.parent_branch_id
            seen = {current.id}
            while cursor in by_id and cursor not in seen:
                seen.add(cursor); ancestors.append(cursor); cursor = by_id[cursor].parent_branch_id
            children = {}
            for b in branches:
                children.setdefault(b.parent_branch_id, []).append(b.id)
            stack = list(children.get(current.id, []))
            while stack:
                ident = stack.pop()
                if ident not in seen:
                    seen.add(ident); descendants.append(ident); stack.extend(children.get(ident, []))
            branches = [b for b in branches if b.id in seen]
        query = select(Run).where(Run.branch_id.in_([b.id for b in branches]))
        total = db.scalar(select(func.count()).select_from(query.subquery()))
        runs = compact_runs(db, query.order_by(Run.created_at.desc(), Run.id).offset((page - 1) * 50).limit(50))
        return response(request, {"branch": entity(current) if current else None, "ancestor_branch_ids": ancestors, "descendant_branch_ids": descendants, "branches": [entity(b) for b in branches], "runs": runs, "total": total, "page": page, "limit": 50, "notes": [entity(n) for n in db.scalars(select(RunNote).where(RunNote.run_id.in_([r['id'] for r in runs])).order_by(RunNote.created_at.desc()).limit(50))], "edges": [{"from_branch_id": b.parent_branch_id, "to_branch_id": b.id, "source_run_id": b.source_run_id, "reason_code": b.reason_code} for b in branches if b.parent_branch_id or b.source_run_id]})
