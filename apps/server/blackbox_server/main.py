from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import Sequence
import csv
import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm import Session

from blackbox_common.enums import EventType, RunStatus
from blackbox_common.errors import ApiError, ErrorCode
from blackbox_common.ids import new_id
from blackbox_common.schemas import (
    ArtifactRead,
    ArtifactUploadComplete,
    ArtifactUploadInit,
    BranchCreate,
    BranchRead,
    BranchUpdate,
    CodeSnapshotCreate,
    CodeSnapshotRead,
    CompareSetCreate,
    CompareSetRead,
    CompareSetUpdate,
    DataSnapshotCreate,
    DataSnapshotRead,
    ErrorPayload,
    EnvSnapshotCreate,
    EnvSnapshotRead,
    EventCreate,
    EventRead,
    MetricCreate,
    MetricRead,
    NoteCreate,
    NoteRead,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
    ResearchCreate,
    ResearchRead,
    ResearchUpdate,
    RunCloneCreate,
    RunCreate,
    RunRead,
    RunUpdate,
    SearchViewCreate,
    SearchViewRead,
    SearchViewUpdate,
    SeriesCreate,
    SweepCreate,
    SweepRead,
    SweepRunAttach,
    SweepRunRead,
    WorkspaceCreate,
    WorkspaceRead,
    WorkspaceUpdate,
)

from . import db as db_module
from .db import get_db
from .migrations import migrate_database, schema_status
from .models import (
    Artifact,
    Branch,
    CodeSnapshot,
    CompareSet,
    DataSnapshot,
    EnvSnapshot,
    Project,
    Research,
    Run,
    RunEvent,
    RunMetric,
    RunNote,
    SearchView,
    Sweep,
    SweepRun,
    Workspace,
    utcnow,
)
from .realtime import event_hub, publish_change
from .settings import get_settings
from .storage import get_artifact_content_target, get_storage
from .workers import get_worker


IDEMPOTENCY_METADATA_KEY = "_blackbox_idempotency_key"


@asynccontextmanager
async def lifespan(_: FastAPI):
    engine = db_module.configure_engine_from_env()
    migrate_database(engine)
    get_storage(get_settings()).ensure_ready()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="blackbox", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def api_token_auth(request: Request, call_next):
        settings = get_settings()
        if request.method == "OPTIONS":
            return await call_next(request)
        if not settings.auth_enabled or not request.url.path.startswith("/api/"):
            return await call_next(request)
        if request.url.path == "/api/v1/auth/status":
            return await call_next(request)
        if not settings.api_token:
            return JSONResponse(
                status_code=500,
                content={
                    "ok": False,
                    "data": None,
                    "error": {
                        "code": ErrorCode.auth_error.value,
                        "message": "BLACKBOX_AUTH_ENABLED is true but BLACKBOX_API_TOKEN is not set",
                    },
                },
            )
        provided = extract_api_token(request)
        if provided != settings.api_token:
            return JSONResponse(
                status_code=401,
                content={
                    "ok": False,
                    "data": None,
                    "error": {
                        "code": ErrorCode.auth_error.value,
                        "message": "invalid or missing API token",
                    },
                },
            )
        return await call_next(request)

    @app.exception_handler(ApiError)
    async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
        status = {
            ErrorCode.validation_error: 422,
            ErrorCode.not_found: 404,
            ErrorCode.conflict: 409,
            ErrorCode.state_error: 409,
            ErrorCode.auth_error: 401,
            ErrorCode.storage_error: 500,
            ErrorCode.network_error: 502,
        }[exc.code]
        return JSONResponse(
            status_code=status,
            content={"ok": False, "data": None, "error": ErrorPayload(
                code=exc.code.value,
                message=exc.message,
                hint=exc.hint,
                details=exc.details,
            ).model_dump()},
        )

    @app.exception_handler(HTTPException)
    async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"ok": False, "data": None, "error": {"code": "HTTP_ERROR", "message": str(exc.detail)}},
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder({
                "ok": False,
                "data": None,
                "error": ErrorPayload(
                    code=ErrorCode.validation_error.value,
                    message="request validation failed",
                    details={"errors": exc.errors()},
                ).model_dump(),
            }),
        )

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return ok({"status": "ok"})

    @app.get("/api/v1/auth/status")
    def auth_status() -> dict[str, Any]:
        settings = get_settings()
        return ok({"auth_enabled": settings.auth_enabled, "token_configured": bool(settings.api_token)})

    @app.get("/api/v1/system/db-status")
    def database_status(db: Session = Depends(get_db)) -> dict[str, Any]:
        return ok(schema_status(db.get_bind()))

    @app.get("/api/v1/system/runtime-status")
    def runtime_status() -> dict[str, Any]:
        settings = get_settings()
        worker = get_worker()
        return ok(
            {
                "worker_backend": type(worker).__name__,
                "artifact_storage": settings.artifact_storage,
                "artifact_root": str(settings.artifact_root) if settings.artifact_storage == "local" else None,
                "s3_bucket": settings.s3_bucket if settings.artifact_storage == "s3" else None,
                "s3_prefix": settings.s3_prefix if settings.artifact_storage == "s3" else None,
            }
        )

    @app.websocket("/api/v1/ws")
    async def websocket_events(websocket: WebSocket, token: str | None = Query(None)) -> None:
        settings = get_settings()
        if settings.auth_enabled:
            provided = token or websocket.headers.get("x-blackbox-token")
            authorization = websocket.headers.get("authorization") or ""
            scheme, _, bearer = authorization.partition(" ")
            if not provided and scheme.lower() == "bearer":
                provided = bearer
            if not settings.api_token or provided != settings.api_token:
                await websocket.close(code=1008)
                return
        await event_hub.connect(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            event_hub.disconnect(websocket)

    @app.get("/api/v1/dashboard")
    def dashboard(db: Session = Depends(get_db)) -> dict[str, Any]:
        workspaces = db.scalars(select(Workspace).order_by(Workspace.updated_at.desc())).all()
        projects = db.scalars(select(Project).order_by(Project.updated_at.desc())).all()
        researches = db.scalars(select(Research).order_by(Research.updated_at.desc())).all()
        branches = db.scalars(select(Branch).order_by(Branch.updated_at.desc())).all()
        runs = db.scalars(select(Run).order_by(Run.updated_at.desc()).limit(200)).all()
        all_runs = db.scalars(select(Run)).all()
        artifacts = db.scalars(select(Artifact).order_by(Artifact.created_at.desc()).limit(200)).all()
        notes = db.scalars(select(RunNote).order_by(RunNote.created_at.desc()).limit(200)).all()
        workspace_by_id = {item.id: item for item in workspaces}
        project_by_id = {item.id: item for item in projects}
        research_by_id = {item.id: item for item in researches}
        branch_by_id = {item.id: item for item in branches}
        run_by_id = {item.id: item for item in runs}
        artifact_summary_by_run = artifact_summary_by_run_id(artifacts)
        now = utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        since_24h = now - timedelta(hours=24)
        since_7d = now - timedelta(days=7)
        return ok(
            {
                "summary": {
                    "workspaces": len(workspaces),
                    "projects": len(projects),
                    "researches": len(researches),
                    "branches": len(branches),
                    "runs": db.scalar(select(func.count(Run.id))) or 0,
                    "today_runs": db.scalar(select(func.count(Run.id)).where(Run.created_at >= today_start)) or 0,
                    "running_runs": db.scalar(select(func.count(Run.id)).where(Run.status == RunStatus.running.value)) or 0,
                    "failed_runs": db.scalar(select(func.count(Run.id)).where(Run.status == RunStatus.failed.value)) or 0,
                    "failed_runs_24h": db.scalar(select(func.count(Run.id)).where(Run.status == RunStatus.failed.value, Run.updated_at >= since_24h)) or 0,
                    "new_branches_24h": db.scalar(select(func.count(Branch.id)).where(Branch.created_at >= since_24h)) or 0,
                    "artifacts": db.scalar(select(func.count(Artifact.id))) or 0,
                    "notes": db.scalar(select(func.count(RunNote.id))) or 0,
                    "sweeps": db.scalar(select(func.count(Sweep.id))) or 0,
                    "compare_sets": db.scalar(select(func.count(CompareSet.id))) or 0,
                    "search_views": db.scalar(select(func.count(SearchView.id))) or 0,
                },
                "workspaces": [WorkspaceRead.model_validate(item).model_dump(mode="json") for item in workspaces],
                "projects": [
                    project_summary_for_dashboard(item, workspace_by_id, researches, branches, all_runs)
                    for item in projects
                ],
                "researches": [
                    research_summary_for_dashboard(
                        item,
                        project_by_id,
                        [branch for branch in branches if branch.research_id == item.id],
                        all_runs,
                        since_7d=since_7d,
                    )
                    for item in researches
                ],
                "branches": [
                    {
                        **BranchRead.model_validate(item).model_dump(mode="json"),
                        "research_key": research_by_id[item.research_id].key if item.research_id in research_by_id else None,
                        "run_count": sum(1 for run in all_runs if run.branch_id == item.id),
                    }
                    for item in branches
                ],
                "runs": [run_summary_for_dashboard(run, branch_by_id, research_by_id, project_by_id, artifact_summary_by_run) for run in runs],
                "artifacts": [ArtifactRead.model_validate(item).model_dump(mode="json") for item in artifacts],
                "notes": [note_summary_for_dashboard(item, run_by_id, branch_by_id, research_by_id) for item in notes],
                "sweeps": [
                    {
                        **SweepRead.model_validate(item).model_dump(mode="json"),
                        "run_count": db.scalar(select(func.count(SweepRun.id)).where(SweepRun.sweep_id == item.id)) or 0,
                    }
                    for item in db.scalars(select(Sweep).order_by(Sweep.updated_at.desc()).limit(100)).all()
                ],
                "compare_sets": [
                    CompareSetRead.model_validate(item).model_dump(mode="json")
                    for item in db.scalars(select(CompareSet).order_by(CompareSet.created_at.desc()).limit(100)).all()
                ],
                "search_views": [
                    SearchViewRead.model_validate(item).model_dump(mode="json")
                    for item in db.scalars(select(SearchView).order_by(SearchView.updated_at.desc()).limit(100)).all()
                ],
            }
        )

    @app.post("/api/v1/workspaces")
    def create_workspace(payload: WorkspaceCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
        existing = db.scalar(select(Workspace).where(Workspace.key == payload.key))
        if existing:
            return ok(WorkspaceRead.model_validate(existing).model_dump(mode="json"))
        workspace = Workspace(
            id=payload.id or new_id("workspace"),
            key=payload.key,
            title=payload.title,
            description=payload.description,
            roles_json=payload.roles,
        )
        db.add(workspace)
        db.commit()
        db.refresh(workspace)
        publish_change("workspace.created", workspace_id=workspace.id, workspace_key=workspace.key)
        return ok(WorkspaceRead.model_validate(workspace).model_dump(mode="json"))

    @app.get("/api/v1/workspaces")
    def list_workspaces(db: Session = Depends(get_db)) -> dict[str, Any]:
        workspaces = db.scalars(select(Workspace).order_by(Workspace.created_at.desc())).all()
        return ok([WorkspaceRead.model_validate(item).model_dump(mode="json") for item in workspaces])

    @app.get("/api/v1/workspaces/{workspace_id}")
    def get_workspace(workspace_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        return ok(WorkspaceRead.model_validate(require_workspace(db, workspace_id)).model_dump(mode="json"))

    @app.patch("/api/v1/workspaces/{workspace_id}")
    def update_workspace(workspace_id: str, payload: WorkspaceUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
        workspace = require_workspace(db, workspace_id)
        update_fields(workspace, payload, {"title", "description"})
        if payload.roles is not None:
            workspace.roles_json = payload.roles
        workspace.updated_at = utcnow()
        db.commit()
        db.refresh(workspace)
        publish_change("workspace.updated", workspace_id=workspace.id, workspace_key=workspace.key)
        return ok(WorkspaceRead.model_validate(workspace).model_dump(mode="json"))

    @app.post("/api/v1/projects")
    def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
        require_workspace(db, payload.workspace_id)
        existing = db.scalar(select(Project).where(Project.key == payload.key))
        if existing:
            return ok(ProjectRead.model_validate(existing).model_dump(mode="json"))
        project = Project(
            workspace_id=payload.workspace_id,
            key=payload.key,
            title=payload.title,
            description=payload.description,
            tags=payload.tags,
            retention_policy_json=payload.retention_policy,
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        publish_change("project.created", project_id=project.id, project_key=project.key)
        return ok(ProjectRead.model_validate(project).model_dump(mode="json"))

    @app.get("/api/v1/projects")
    def list_projects(db: Session = Depends(get_db)) -> dict[str, Any]:
        projects = db.scalars(select(Project).order_by(Project.created_at.desc())).all()
        return ok([ProjectRead.model_validate(item).model_dump(mode="json") for item in projects])

    @app.get("/api/v1/projects/{project_id}")
    def get_project(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        project = require_project(db, project_id)
        workspace = require_workspace(db, project.workspace_id)
        researches = db.scalars(select(Research).where(Research.project_id == project.id).order_by(Research.updated_at.desc())).all()
        research_ids = [research.id for research in researches]
        branches = (
            db.scalars(select(Branch).where(Branch.research_id.in_(research_ids)).order_by(Branch.updated_at.desc())).all()
            if research_ids
            else []
        )
        branch_ids = [branch.id for branch in branches]
        runs = (
            db.scalars(select(Run).where(Run.branch_id.in_(branch_ids)).order_by(Run.updated_at.desc())).all()
            if branch_ids
            else []
        )
        compare_sets = db.scalars(select(CompareSet).where(CompareSet.project_id == project.id).order_by(CompareSet.created_at.desc())).all()
        search_views = db.scalars(select(SearchView).where(SearchView.project_id == project.id).order_by(SearchView.updated_at.desc())).all()
        return ok(
            {
                **project_summary_for_dashboard(project, {workspace.id: workspace}, researches, branches, runs),
                "researches": [
                    research_summary_for_dashboard(
                        research,
                        {project.id: project},
                        [branch for branch in branches if branch.research_id == research.id],
                        runs,
                    )
                    for research in researches
                ],
                "branches": [
                    {
                        **BranchRead.model_validate(branch).model_dump(mode="json"),
                        "research_key": next((research.key for research in researches if research.id == branch.research_id), None),
                        "run_count": sum(1 for run in runs if run.branch_id == branch.id),
                    }
                    for branch in branches
                ],
                "runs": run_summaries(db, runs),
                "compare_sets": [CompareSetRead.model_validate(item).model_dump(mode="json") for item in compare_sets],
                "search_views": [SearchViewRead.model_validate(item).model_dump(mode="json") for item in search_views],
            }
        )

    @app.patch("/api/v1/projects/{project_id}")
    def update_project(project_id: str, payload: ProjectUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
        project = require_project(db, project_id)
        update_fields(project, payload, {"title", "description", "tags"})
        if payload.retention_policy is not None:
            project.retention_policy_json = payload.retention_policy
        project.updated_at = utcnow()
        db.commit()
        db.refresh(project)
        publish_change("project.updated", project_id=project.id, project_key=project.key)
        return ok(ProjectRead.model_validate(project).model_dump(mode="json"))

    @app.post("/api/v1/researches")
    def create_research(payload: ResearchCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
        project = resolve_project(db, project_id=payload.project_id, project_key=payload.project_key)
        existing = db.scalar(
            select(Research).where(Research.project_id == project.id, Research.key == payload.key)
        )
        if existing:
            return ok(ResearchRead.model_validate(existing).model_dump(mode="json"))
        research = Research(
            project_id=project.id,
            key=payload.key,
            title=payload.title,
            goal=payload.goal,
            hypothesis=payload.hypothesis,
            status=payload.status,
            tags=payload.tags,
        )
        db.add(research)
        db.commit()
        db.refresh(research)
        publish_change("research.created", project_id=project.id, research_id=research.id, research_key=research.key)
        return ok(ResearchRead.model_validate(research).model_dump(mode="json"))

    @app.get("/api/v1/projects/{project_id}/researches")
    def list_researches(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        require_project(db, project_id)
        items = db.scalars(select(Research).where(Research.project_id == project_id).order_by(Research.updated_at.desc()))
        return ok([ResearchRead.model_validate(item).model_dump(mode="json") for item in items])

    @app.get("/api/v1/researches/{research_id}")
    def get_research(research_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        return ok(ResearchRead.model_validate(require_research(db, research_id)).model_dump(mode="json"))

    @app.patch("/api/v1/researches/{research_id}")
    def update_research(research_id: str, payload: ResearchUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
        research = require_research(db, research_id)
        update_fields(research, payload, {"title", "goal", "hypothesis", "status", "tags"})
        research.updated_at = utcnow()
        db.commit()
        db.refresh(research)
        publish_change("research.updated", project_id=research.project_id, research_id=research.id, research_key=research.key)
        return ok(ResearchRead.model_validate(research).model_dump(mode="json"))

    @app.post("/api/v1/branches")
    def create_branch(payload: BranchCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
        source_run = require_run(db, payload.source_run_id) if payload.source_run_id else None
        source_branch = require_branch(db, source_run.branch_id) if source_run else None
        research = (
            resolve_research(db, research_id=payload.research_id, research_key=payload.research_key)
            if payload.research_id or payload.research_key
            else require_research(db, source_branch.research_id) if source_branch
            else resolve_research(db, research_id=None, research_key=None)
        )
        parent_branch_id = payload.parent_branch_id if payload.parent_branch_id is not None else source_branch.id if source_branch else None
        existing = db.scalar(select(Branch).where(Branch.research_id == research.id, Branch.key == payload.key))
        if existing:
            return ok(BranchRead.model_validate(existing).model_dump(mode="json"))
        branch = Branch(
            research_id=research.id,
            key=payload.key,
            title=payload.title,
            parent_branch_id=parent_branch_id,
            source_run_id=payload.source_run_id,
            reason_code=payload.reason_code,
            reason_summary=payload.reason_summary,
            hypothesis=payload.hypothesis,
            expected_change=payload.expected_change,
            status=payload.status.value if hasattr(payload.status, "value") else str(payload.status),
            created_by_type=payload.created_by_type,
            created_by_id=payload.created_by_id,
        )
        db.add(branch)
        db.commit()
        db.refresh(branch)
        publish_change("branch.created", research_id=research.id, branch_id=branch.id, branch_key=branch.key)
        return ok(BranchRead.model_validate(branch).model_dump(mode="json"))

    @app.get("/api/v1/researches/{research_id}/branches")
    def list_branches(research_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        require_research(db, research_id)
        items = db.scalars(select(Branch).where(Branch.research_id == research_id).order_by(Branch.updated_at.desc()))
        return ok([BranchRead.model_validate(item).model_dump(mode="json") for item in items])

    @app.get("/api/v1/branches/{branch_id}")
    def get_branch(branch_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        return ok(BranchRead.model_validate(require_branch(db, branch_id)).model_dump(mode="json"))

    @app.patch("/api/v1/branches/{branch_id}")
    def update_branch(branch_id: str, payload: BranchUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
        branch = require_branch(db, branch_id)
        update_fields(
            branch,
            payload,
            {"title", "parent_branch_id", "source_run_id", "reason_code", "reason_summary", "hypothesis", "expected_change", "status"},
        )
        if hasattr(branch.status, "value"):
            branch.status = branch.status.value
        branch.updated_at = utcnow()
        db.commit()
        db.refresh(branch)
        publish_change("branch.updated", research_id=branch.research_id, branch_id=branch.id, branch_key=branch.key)
        return ok(BranchRead.model_validate(branch).model_dump(mode="json"))

    @app.post("/api/v1/runs")
    def create_run(
        payload: RunCreate,
        db: Session = Depends(get_db),
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> dict[str, Any]:
        branch = resolve_branch(
            db,
            branch_id=payload.branch_id,
            project_key=payload.project_key,
            research_key=payload.research_key,
            branch_key=payload.branch_key,
        )
        if idempotency_key:
            existing = db.scalar(
                select(Run).where(Run.branch_id == branch.id, Run.summary_json["idempotency_key"].as_string() == idempotency_key)
            )
            if existing:
                return ok(RunRead.model_validate(existing).model_dump(mode="json"))
        sequence_no = next_run_sequence(db, branch.id)
        summary = {"idempotency_key": idempotency_key} if idempotency_key else {}
        run = Run(
            branch_id=branch.id,
            name=payload.name,
            title=payload.title,
            status=RunStatus.running.value,
            source_run_id=payload.source_run_id,
            sequence_no=sequence_no,
            config_json=payload.config,
            context_json=payload.context,
            summary_json=summary,
            tags=payload.tags,
            created_by_type=payload.created_by_type,
            created_by_id=payload.created_by_id,
            started_at=utcnow(),
        )
        db.add(run)
        db.flush()
        db.add(RunEvent(run_id=run.id, sequence_no=1, event_type=EventType.run_started.value, stage="run_started"))
        db.commit()
        db.refresh(run)
        publish_change("run.created", branch_id=branch.id, run_id=run.id, run_name=run.name)
        return ok(RunRead.model_validate(run).model_dump(mode="json"))

    @app.get("/api/v1/runs/{run_id}")
    def get_run(run_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        run = require_run(db, run_id)
        return ok(run_detail(db, run))

    @app.patch("/api/v1/runs/{run_id}")
    def update_run(run_id: str, payload: RunUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
        run = require_run(db, run_id)
        if "config" in payload.model_fields_set and run.status in {RunStatus.completed.value, RunStatus.failed.value, RunStatus.cancelled.value}:
            raise ApiError(ErrorCode.state_error, f"run {run_id} config is immutable after terminal status")
        update_fields(run, payload, {"name", "title", "source_run_id", "tags"})
        if "config" in payload.model_fields_set:
            run.config_json = payload.config or {}
            flag_modified(run, "config_json")
        if "context" in payload.model_fields_set:
            run.context_json = payload.context or {}
            flag_modified(run, "context_json")
        run.updated_at = utcnow()
        db.commit()
        db.refresh(run)
        publish_change("run.updated", branch_id=run.branch_id, run_id=run.id, run_name=run.name)
        return ok(RunRead.model_validate(run).model_dump(mode="json"))

    @app.post("/api/v1/runs/{run_id}/clone")
    def clone_run(
        run_id: str,
        payload: RunCloneCreate | None = None,
        db: Session = Depends(get_db),
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> dict[str, Any]:
        source = require_run(db, run_id)
        payload = payload or RunCloneCreate()
        branch = require_branch(db, payload.branch_id) if payload.branch_id else require_branch(db, source.branch_id)
        name = payload.name or f"{source.name}_clone"
        if idempotency_key:
            existing = db.scalar(
                select(Run).where(Run.branch_id == branch.id, Run.summary_json["idempotency_key"].as_string() == idempotency_key)
            )
            if existing:
                return ok(RunRead.model_validate(existing).model_dump(mode="json"))
        sequence_no = next_run_sequence(db, branch.id)
        summary = {"idempotency_key": idempotency_key} if idempotency_key else {}
        run = Run(
            branch_id=branch.id,
            name=name,
            title=payload.title if payload.title is not None else source.title,
            status=RunStatus.running.value,
            source_run_id=source.id,
            sequence_no=sequence_no,
            config_json={**(source.config_json or {}), **payload.config_overrides},
            context_json={**(source.context_json or {}), **payload.context_overrides},
            summary_json=summary,
            tags=payload.tags if payload.tags is not None else list(source.tags or []),
            created_by_type=payload.created_by_type,
            created_by_id=payload.created_by_id,
            started_at=utcnow(),
        )
        db.add(run)
        db.flush()
        db.add(
            RunEvent(
                run_id=run.id,
                sequence_no=1,
                event_type=EventType.run_started.value,
                stage="run_started",
                payload_json={"cloned_from_run_id": source.id},
            )
        )
        db.commit()
        db.refresh(run)
        publish_change("run.cloned", branch_id=branch.id, run_id=run.id, source_run_id=source.id)
        return ok(RunRead.model_validate(run).model_dump(mode="json"))

    @app.post("/api/v1/runs/{run_id}/events")
    def add_event(run_id: str, payload: EventCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
        require_run(db, run_id)
        existing = get_existing_event(db, run_id, payload.client_event_id)
        if existing:
            return ok(EventRead.model_validate(existing).model_dump(mode="json"))
        event = RunEvent(
            run_id=run_id,
            sequence_no=next_event_sequence(db, run_id),
            event_type=payload.event_type.value,
            stage=payload.stage,
            payload_json=payload.payload,
            client_event_id=payload.client_event_id,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        publish_change("run.event_added", run_id=run_id, event_id=event.id, event_type=event.event_type)
        return ok(EventRead.model_validate(event).model_dump(mode="json"))

    @app.get("/api/v1/runs/{run_id}/events")
    def list_events(run_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        require_run(db, run_id)
        items = db.scalars(select(RunEvent).where(RunEvent.run_id == run_id).order_by(RunEvent.sequence_no))
        return ok([EventRead.model_validate(item).model_dump(mode="json") for item in items])

    @app.post("/api/v1/runs/{run_id}/metrics")
    def add_metrics(run_id: str, payload: MetricCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
        run = require_run(db, run_id)
        validate_metric_payload_size(payload)
        existing = get_existing_metrics(db, run_id, payload.client_event_id)
        if existing:
            return ok([MetricRead.model_validate(item).model_dump(mode="json") for item in existing])
        metrics: list[RunMetric] = []
        for key, value in payload.values.items():
            value_number, value_string, value_bool = split_metric_value(value)
            metric = RunMetric(
                run_id=run_id,
                namespace=payload.namespace,
                key=key,
                value_number=value_number,
                value_string=value_string,
                value_bool=value_bool,
                point_kind=payload.point.kind,
                point_event_name=payload.point.name,
                point_step=payload.point.step,
                point_timestamp=payload.point.timestamp,
                point_coord_json=payload.point.coord,
                client_event_id=payload.client_event_id,
            )
            db.add(metric)
            metrics.append(metric)
            if value_number is not None or value_string is not None or value_bool is not None:
                update_summary(run.summary_json, payload.namespace, key, value)
                flag_modified(run, "summary_json")
        run.updated_at = utcnow()
        db.add(run)
        db.commit()
        for metric in metrics:
            db.refresh(metric)
        publish_change("run.metrics_added", run_id=run_id, metric_ids=[metric.id for metric in metrics])
        return ok([MetricRead.model_validate(item).model_dump(mode="json") for item in metrics])

    @app.get("/api/v1/runs/{run_id}/metrics")
    def list_metrics(run_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        require_run(db, run_id)
        items = db.scalars(select(RunMetric).where(RunMetric.run_id == run_id).order_by(RunMetric.created_at))
        return ok([MetricRead.model_validate(item).model_dump(mode="json") for item in items])

    @app.post("/api/v1/runs/{run_id}/series")
    def log_series(
        run_id: str,
        payload: SeriesCreate,
        db: Session = Depends(get_db),
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> dict[str, Any]:
        require_run(db, run_id)
        existing = get_existing_artifact(db, run_id, idempotency_key)
        if existing:
            return ok(ArtifactRead.model_validate(existing).model_dump(mode="json"))
        content = serialize_series(payload.data, payload.kind)
        filename = payload.filename or default_artifact_filename(payload.name, payload.kind)
        stored = get_storage(get_settings()).put_bytes(run_id=run_id, artifact_id=None, filename=filename, content=content)
        mime_type = stored.mime_type or default_artifact_mime_type(stored.filename, payload.kind)
        metadata = with_idempotency_metadata({
            **payload.metadata,
            "series": {"name": payload.name, "x": payload.x, "y": payload.y, "namespace": payload.namespace},
        }, idempotency_key)
        artifact = Artifact(
            run_id=run_id,
            kind=payload.kind,
            name=payload.name,
            storage_uri=stored.storage_uri,
            filename=stored.filename,
            mime_type=mime_type,
            size_bytes=stored.size_bytes,
            sha256=stored.sha256,
            preview_json=build_artifact_preview(stored.filename, mime_type, content),
            metadata_json=metadata,
        )
        db.add(artifact)
        db.commit()
        db.refresh(artifact)
        publish_change("series.logged", run_id=run_id, artifact_id=artifact.id, series_name=payload.name)
        return ok(ArtifactRead.model_validate(artifact).model_dump(mode="json"))

    @app.post("/api/v1/runs/{run_id}/notes")
    def add_note(run_id: str, payload: NoteCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
        require_run(db, run_id)
        existing = get_existing_note(db, run_id, payload.client_event_id)
        if existing:
            return ok(NoteRead.model_validate(existing).model_dump(mode="json"))
        note = RunNote(
            run_id=run_id,
            kind=payload.kind.value if hasattr(payload.kind, "value") else str(payload.kind),
            summary=payload.summary,
            content_md=payload.content,
            structured_json=payload.structured,
            author_type=payload.author_type,
            client_event_id=payload.client_event_id,
        )
        db.add(note)
        db.commit()
        db.refresh(note)
        publish_change("run.note_added", run_id=run_id, note_id=note.id)
        return ok(NoteRead.model_validate(note).model_dump(mode="json"))

    @app.get("/api/v1/runs/{run_id}/notes")
    def list_notes(run_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        require_run(db, run_id)
        items = db.scalars(select(RunNote).where(RunNote.run_id == run_id).order_by(RunNote.created_at))
        return ok([NoteRead.model_validate(item).model_dump(mode="json") for item in items])

    @app.post("/api/v1/runs/{run_id}/finish")
    def finish_run(run_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        run = require_run(db, run_id)
        if run.status == RunStatus.completed.value:
            return ok(RunRead.model_validate(run).model_dump(mode="json"))
        if run.status in {RunStatus.failed.value, RunStatus.cancelled.value}:
            raise ApiError(ErrorCode.state_error, f"run {run_id} is already terminal")
        run.status = RunStatus.completed.value
        run.ended_at = utcnow()
        run.updated_at = utcnow()
        db.add(RunEvent(run_id=run.id, sequence_no=next_event_sequence(db, run.id), event_type=EventType.run_finished.value, stage="run_finished"))
        db.commit()
        db.refresh(run)
        publish_change("run.finished", run_id=run.id)
        return ok(RunRead.model_validate(run).model_dump(mode="json"))

    @app.post("/api/v1/runs/{run_id}/fail")
    def fail_run(run_id: str, payload: dict[str, Any] | None = None, db: Session = Depends(get_db)) -> dict[str, Any]:
        run = require_run(db, run_id)
        if run.status == RunStatus.failed.value:
            return ok(RunRead.model_validate(run).model_dump(mode="json"))
        if run.status in {RunStatus.completed.value, RunStatus.cancelled.value}:
            raise ApiError(ErrorCode.state_error, f"run {run_id} is already terminal")
        run.status = RunStatus.failed.value
        run.ended_at = utcnow()
        run.updated_at = utcnow()
        db.add(
            RunEvent(
                run_id=run.id,
                sequence_no=next_event_sequence(db, run.id),
                event_type=EventType.run_failed.value,
                stage="run_failed",
                payload_json=payload or {},
            )
        )
        db.commit()
        db.refresh(run)
        publish_change("run.failed", run_id=run.id)
        return ok(RunRead.model_validate(run).model_dump(mode="json"))

    @app.post("/api/v1/runs/{run_id}/cancel")
    def cancel_run(run_id: str, payload: dict[str, Any] | None = None, db: Session = Depends(get_db)) -> dict[str, Any]:
        run = require_run(db, run_id)
        if run.status == RunStatus.cancelled.value:
            return ok(RunRead.model_validate(run).model_dump(mode="json"))
        if run.status in {RunStatus.completed.value, RunStatus.failed.value}:
            raise ApiError(ErrorCode.state_error, f"run {run_id} is already terminal")
        run.status = RunStatus.cancelled.value
        run.ended_at = utcnow()
        run.updated_at = utcnow()
        db.add(
            RunEvent(
                run_id=run.id,
                sequence_no=next_event_sequence(db, run.id),
                event_type=EventType.run_cancelled.value,
                stage="run_cancelled",
                payload_json=payload or {},
            )
        )
        db.commit()
        db.refresh(run)
        publish_change("run.cancelled", run_id=run.id)
        return ok(RunRead.model_validate(run).model_dump(mode="json"))

    @app.post("/api/v1/runs/{run_id}/artifacts/upload")
    async def upload_artifact(
        run_id: str,
        request: Request,
        name: str = Query(...),
        kind: str = Query("other"),
        filename: str = Query("artifact.bin"),
        artifact_id: str | None = Query(None),
        metadata: str | None = Query(None),
        db: Session = Depends(get_db),
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> dict[str, Any]:
        require_run(db, run_id)
        existing = get_existing_artifact(db, run_id, idempotency_key, artifact_id)
        if existing:
            return ok(ArtifactRead.model_validate(existing).model_dump(mode="json"))
        content = await request.body()
        if not content:
            raise ApiError(ErrorCode.validation_error, "artifact body is empty")
        artifact_id = artifact_id or new_id("artifact")
        stored = get_storage(get_settings()).put_bytes(
            run_id=run_id,
            artifact_id=artifact_id,
            filename=filename,
            content=content,
        )
        artifact = Artifact(
            id=artifact_id,
            run_id=run_id,
            kind=kind,
            name=name,
            storage_uri=stored.storage_uri,
            filename=stored.filename,
            mime_type=stored.mime_type,
            size_bytes=stored.size_bytes,
            sha256=stored.sha256,
            preview_json=build_artifact_preview(stored.filename, stored.mime_type, content),
            metadata_json=with_idempotency_metadata(parse_metadata_query(metadata), idempotency_key),
        )
        db.add(artifact)
        db.add(RunEvent(run_id=run_id, sequence_no=next_event_sequence(db, run_id), event_type=EventType.artifact_uploaded.value, stage="artifact_uploaded", payload_json={"artifact_id": artifact_id, "kind": kind, "name": name}))
        db.commit()
        db.refresh(artifact)
        publish_change("run.artifact_added", run_id=run_id, artifact_id=artifact.id, artifact_kind=artifact.kind)
        return ok(ArtifactRead.model_validate(artifact).model_dump(mode="json"))

    @app.post("/api/v1/runs/{run_id}/artifacts/init-upload")
    def init_artifact_upload(run_id: str, payload: ArtifactUploadInit, db: Session = Depends(get_db)) -> dict[str, Any]:
        require_run(db, run_id)
        artifact_id = new_id("artifact")
        target = get_storage(get_settings()).init_upload(
            run_id=run_id,
            artifact_id=artifact_id,
            name=payload.name,
            kind=payload.kind,
            filename=payload.filename,
            metadata={key: str(value) for key, value in payload.metadata.items()},
        )
        return ok(
            {
                "artifact_id": target.artifact_id,
                "method": target.method,
                "upload_path": target.upload_path,
                "upload_url": target.upload_url,
                "storage_uri": target.storage_uri,
                "headers": target.headers,
                "metadata": target.metadata or payload.metadata,
            }
        )

    @app.post("/api/v1/runs/{run_id}/artifacts/complete-upload")
    def complete_artifact_upload(
        run_id: str,
        payload: ArtifactUploadComplete,
        db: Session = Depends(get_db),
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> dict[str, Any]:
        require_run(db, run_id)
        existing = get_existing_artifact(db, run_id, idempotency_key, payload.artifact_id)
        if existing:
            return ok(ArtifactRead.model_validate(existing).model_dump(mode="json"))
        artifact = Artifact(
            id=payload.artifact_id or new_id("artifact"),
            run_id=run_id,
            kind=payload.kind,
            name=payload.name,
            storage_uri=payload.uri,
            filename=payload.filename or payload.name,
            mime_type=payload.mime_type,
            size_bytes=payload.size_bytes,
            sha256=payload.sha256,
            preview_json=payload.preview,
            metadata_json=with_idempotency_metadata(payload.metadata, idempotency_key),
        )
        db.add(artifact)
        db.add(
            RunEvent(
                run_id=run_id,
                sequence_no=next_event_sequence(db, run_id),
                event_type=EventType.artifact_uploaded.value,
                stage="artifact_uploaded",
                payload_json={"artifact_id": artifact.id, "kind": artifact.kind, "name": artifact.name},
            )
        )
        db.commit()
        db.refresh(artifact)
        publish_change("run.artifact_added", run_id=run_id, artifact_id=artifact.id, artifact_kind=artifact.kind)
        return ok(ArtifactRead.model_validate(artifact).model_dump(mode="json"))

    @app.post("/api/v1/runs/{run_id}/artifacts/register-external")
    def register_external_artifact(
        run_id: str,
        payload: dict[str, Any],
        db: Session = Depends(get_db),
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> dict[str, Any]:
        require_run(db, run_id)
        existing = get_existing_artifact(db, run_id, idempotency_key)
        if existing:
            return ok(ArtifactRead.model_validate(existing).model_dump(mode="json"))
        artifact = Artifact(
            run_id=run_id,
            kind=payload.get("kind", "other"),
            name=payload["name"],
            storage_uri=payload["uri"],
            filename=payload.get("filename", payload["name"]),
            mime_type=payload.get("mime_type"),
            size_bytes=int(payload.get("size_bytes", 0)),
            sha256=payload.get("sha256", ""),
            preview_json=payload.get("preview", {}),
            metadata_json=with_idempotency_metadata(payload.get("metadata", {}), idempotency_key),
        )
        db.add(artifact)
        db.add(
            RunEvent(
                run_id=run_id,
                sequence_no=next_event_sequence(db, run_id),
                event_type=EventType.artifact_uploaded.value,
                stage="artifact_registered",
                payload_json={"artifact_id": artifact.id, "kind": artifact.kind, "name": artifact.name, "uri": artifact.storage_uri},
            )
        )
        db.commit()
        db.refresh(artifact)
        publish_change("run.artifact_added", run_id=run_id, artifact_id=artifact.id, artifact_kind=artifact.kind)
        return ok(ArtifactRead.model_validate(artifact).model_dump(mode="json"))

    @app.post("/api/v1/runs/{run_id}/snapshots/code")
    def add_code_snapshot(run_id: str, payload: CodeSnapshotCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
        require_run(db, run_id)
        snapshot = CodeSnapshot(
            run_id=run_id,
            repo_url=payload.repo_url,
            git_commit=payload.git_commit,
            git_dirty=payload.git_dirty,
            patch_artifact_id=payload.patch_artifact_id,
            requirements_hash=payload.requirements_hash,
            container_image=payload.container_image,
            metadata_json=payload.metadata,
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        publish_change("run.snapshot_added", run_id=run_id, snapshot_id=snapshot.id, snapshot_kind="code")
        return ok(CodeSnapshotRead.model_validate(snapshot).model_dump(mode="json"))

    @app.post("/api/v1/runs/{run_id}/snapshots/data")
    def add_data_snapshot(run_id: str, payload: DataSnapshotCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
        require_run(db, run_id)
        snapshot = DataSnapshot(
            run_id=run_id,
            dataset_name=payload.dataset_name,
            dataset_version=payload.dataset_version,
            fingerprint=payload.fingerprint,
            universe=payload.universe,
            benchmark=payload.benchmark,
            calendar=payload.calendar,
            fee_model=payload.fee_model,
            slippage_model=payload.slippage_model,
            time_range=payload.time_range,
            metadata_json=payload.metadata,
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        publish_change("run.snapshot_added", run_id=run_id, snapshot_id=snapshot.id, snapshot_kind="data")
        return ok(DataSnapshotRead.model_validate(snapshot).model_dump(mode="json"))

    @app.post("/api/v1/runs/{run_id}/snapshots/env")
    def add_env_snapshot(run_id: str, payload: EnvSnapshotCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
        require_run(db, run_id)
        snapshot = EnvSnapshot(
            run_id=run_id,
            python_version=payload.python_version,
            platform=payload.platform,
            hostname=payload.hostname,
            packages_json=payload.packages,
            metadata_json=payload.metadata,
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        publish_change("run.snapshot_added", run_id=run_id, snapshot_id=snapshot.id, snapshot_kind="env")
        return ok(EnvSnapshotRead.model_validate(snapshot).model_dump(mode="json"))

    @app.get("/api/v1/runs/{run_id}/snapshots")
    def list_snapshots(run_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        require_run(db, run_id)
        return ok(snapshot_detail(db, run_id))

    @app.get("/api/v1/runs/{run_id}/artifacts")
    def list_artifacts(run_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        require_run(db, run_id)
        items = db.scalars(select(Artifact).where(Artifact.run_id == run_id).order_by(Artifact.created_at))
        return ok([ArtifactRead.model_validate(item).model_dump(mode="json") for item in items])

    @app.get("/api/v1/artifacts/{artifact_id}")
    def get_artifact(artifact_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        artifact = db.get(Artifact, artifact_id)
        if not artifact:
            raise ApiError(ErrorCode.not_found, f"artifact {artifact_id} not found")
        return ok(ArtifactRead.model_validate(artifact).model_dump(mode="json"))

    @app.get("/api/v1/artifacts/{artifact_id}/content")
    def get_artifact_content(artifact_id: str, db: Session = Depends(get_db)) -> Response:
        artifact = db.get(Artifact, artifact_id)
        if not artifact:
            raise ApiError(ErrorCode.not_found, f"artifact {artifact_id} not found")
        target = get_artifact_content_target(get_settings(), artifact.storage_uri, artifact.mime_type)
        if target.path:
            return FileResponse(target.path, media_type=artifact.mime_type, filename=artifact.filename)
        if target.redirect_url:
            return RedirectResponse(target.redirect_url)
        raise ApiError(ErrorCode.storage_error, f"artifact {artifact_id} has no readable content target")

    @app.post("/api/v1/sweeps")
    def create_sweep(payload: SweepCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
        require_branch(db, payload.branch_id)
        existing = db.scalar(select(Sweep).where(Sweep.branch_id == payload.branch_id, Sweep.name == payload.name))
        if existing:
            return ok(SweepRead.model_validate(existing).model_dump(mode="json"))
        sweep = Sweep(
            branch_id=payload.branch_id,
            name=payload.name,
            search_space_json=payload.search_space,
            objective_json=payload.objective,
            status=payload.status,
        )
        db.add(sweep)
        db.commit()
        db.refresh(sweep)
        publish_change("sweep.created", branch_id=sweep.branch_id, sweep_id=sweep.id)
        return ok(SweepRead.model_validate(sweep).model_dump(mode="json"))

    @app.get("/api/v1/branches/{branch_id}/sweeps")
    def list_branch_sweeps(branch_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        require_branch(db, branch_id)
        sweeps = db.scalars(select(Sweep).where(Sweep.branch_id == branch_id).order_by(Sweep.updated_at.desc())).all()
        return ok(
            [
                {
                    **SweepRead.model_validate(item).model_dump(mode="json"),
                    "run_count": db.scalar(select(func.count(SweepRun.id)).where(SweepRun.sweep_id == item.id)) or 0,
                }
                for item in sweeps
            ]
        )

    @app.get("/api/v1/sweeps/{sweep_id}")
    def get_sweep(sweep_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        sweep = require_sweep(db, sweep_id)
        members = db.scalars(select(SweepRun).where(SweepRun.sweep_id == sweep_id).order_by(SweepRun.rank, SweepRun.created_at)).all()
        runs = [require_run(db, member.run_id) for member in members]
        branch_by_id, research_by_id, project_by_id = hierarchy_maps_for_runs(db, runs)
        return ok(
            {
                **SweepRead.model_validate(sweep).model_dump(mode="json"),
                "run_count": len(members),
                "runs": [run_summary_for_dashboard(run, branch_by_id, research_by_id, project_by_id) for run in runs],
                "members": [SweepRunRead.model_validate(item).model_dump(mode="json") for item in members],
            }
        )

    @app.get("/api/v1/sweeps/{sweep_id}/summary")
    def get_sweep_summary(sweep_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        sweep = require_sweep(db, sweep_id)
        members = db.scalars(select(SweepRun).where(SweepRun.sweep_id == sweep_id).order_by(SweepRun.rank, SweepRun.created_at)).all()
        runs = [require_run(db, member.run_id) for member in members]
        return ok(build_sweep_summary(sweep, members, runs))

    @app.post("/api/v1/sweeps/{sweep_id}/runs")
    def attach_sweep_run(sweep_id: str, payload: SweepRunAttach, db: Session = Depends(get_db)) -> dict[str, Any]:
        require_sweep(db, sweep_id)
        require_run(db, payload.run_id)
        existing = db.scalar(select(SweepRun).where(SweepRun.sweep_id == sweep_id, SweepRun.run_id == payload.run_id))
        if existing:
            existing.coord_json = payload.coord
            existing.rank = payload.rank
            db.commit()
            db.refresh(existing)
            publish_change("sweep.run_attached", sweep_id=sweep_id, run_id=payload.run_id, sweep_run_id=existing.id)
            return ok(SweepRunRead.model_validate(existing).model_dump(mode="json"))
        item = SweepRun(sweep_id=sweep_id, run_id=payload.run_id, coord_json=payload.coord, rank=payload.rank)
        db.add(item)
        db.commit()
        db.refresh(item)
        publish_change("sweep.run_attached", sweep_id=sweep_id, run_id=payload.run_id, sweep_run_id=item.id)
        return ok(SweepRunRead.model_validate(item).model_dump(mode="json"))

    @app.post("/api/v1/compare-sets")
    def create_compare_set(payload: CompareSetCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
        require_project(db, payload.project_id)
        for run_id in payload.run_ids:
            require_run(db, run_id)
        compare_set = CompareSet(
            project_id=payload.project_id,
            name=payload.name,
            run_ids_json=payload.run_ids,
            layout_json=payload.layout,
        )
        db.add(compare_set)
        db.commit()
        db.refresh(compare_set)
        publish_change("compare_set.created", project_id=payload.project_id, compare_set_id=compare_set.id)
        return ok(CompareSetRead.model_validate(compare_set).model_dump(mode="json"))

    @app.get("/api/v1/projects/{project_id}/compare-sets")
    def list_compare_sets(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        require_project(db, project_id)
        items = db.scalars(select(CompareSet).where(CompareSet.project_id == project_id).order_by(CompareSet.created_at.desc())).all()
        return ok([CompareSetRead.model_validate(item).model_dump(mode="json") for item in items])

    @app.get("/api/v1/compare-sets/{compare_set_id}")
    def get_compare_set(compare_set_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        return ok(CompareSetRead.model_validate(require_compare_set(db, compare_set_id)).model_dump(mode="json"))

    @app.patch("/api/v1/compare-sets/{compare_set_id}")
    def update_compare_set(compare_set_id: str, payload: CompareSetUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
        compare_set = require_compare_set(db, compare_set_id)
        if payload.run_ids is not None:
            for run_id in payload.run_ids:
                require_run(db, run_id)
            compare_set.run_ids_json = payload.run_ids
        if payload.name is not None:
            compare_set.name = payload.name
        if payload.layout is not None:
            compare_set.layout_json = payload.layout
        db.commit()
        db.refresh(compare_set)
        publish_change("compare_set.updated", project_id=compare_set.project_id, compare_set_id=compare_set.id)
        return ok(CompareSetRead.model_validate(compare_set).model_dump(mode="json"))

    @app.post("/api/v1/search/runs")
    def search_runs(payload: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
        return ok(run_summaries(db, search_run_records(db, payload)))

    @app.post("/api/v1/search/researches")
    def search_researches(payload: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
        researches = search_research_records(db, payload)
        all_branches = db.scalars(select(Branch)).all()
        all_runs = db.scalars(select(Run)).all()
        projects = db.scalars(select(Project)).all()
        return ok(
            [
                research_summary_for_dashboard(
                    research,
                    {item.id: item for item in projects},
                    [branch for branch in all_branches if branch.research_id == research.id],
                    all_runs,
                )
                for research in researches
            ]
        )

    @app.post("/api/v1/search-views")
    def create_search_view(payload: SearchViewCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
        require_project(db, payload.project_id)
        view = SearchView(
            project_id=payload.project_id,
            name=payload.name,
            description=payload.description,
            filters_json=payload.filters,
        )
        db.add(view)
        db.commit()
        db.refresh(view)
        publish_change("search_view.created", project_id=view.project_id, search_view_id=view.id)
        return ok(SearchViewRead.model_validate(view).model_dump(mode="json"))

    @app.get("/api/v1/projects/{project_id}/search-views")
    def list_search_views(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        require_project(db, project_id)
        items = db.scalars(select(SearchView).where(SearchView.project_id == project_id).order_by(SearchView.updated_at.desc())).all()
        return ok([SearchViewRead.model_validate(item).model_dump(mode="json") for item in items])

    @app.get("/api/v1/search-views/{view_id}")
    def get_search_view(view_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        return ok(SearchViewRead.model_validate(require_search_view(db, view_id)).model_dump(mode="json"))

    @app.patch("/api/v1/search-views/{view_id}")
    def update_search_view(view_id: str, payload: SearchViewUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
        view = require_search_view(db, view_id)
        update_fields(view, payload, {"name", "description"})
        if "filters" in payload.model_fields_set:
            view.filters_json = payload.filters or {}
            flag_modified(view, "filters_json")
        view.updated_at = utcnow()
        db.commit()
        db.refresh(view)
        publish_change("search_view.updated", project_id=view.project_id, search_view_id=view.id)
        return ok(SearchViewRead.model_validate(view).model_dump(mode="json"))

    @app.post("/api/v1/search-views/{view_id}/run")
    def run_search_view(view_id: str, payload: dict[str, Any] | None = None, db: Session = Depends(get_db)) -> dict[str, Any]:
        view = require_search_view(db, view_id)
        search_payload = dict(view.filters_json or {})
        search_payload.update(payload or {})
        runs = search_run_records(db, search_payload)
        return ok(run_summaries(db, runs))

    @app.post("/api/v1/compare/runs")
    def compare_runs(payload: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
        run_ids = payload.get("run_ids") or []
        metrics = payload.get("metrics") or []
        if not run_ids:
            raise ApiError(ErrorCode.validation_error, "run_ids is required")
        runs = [require_run(db, run_id) for run_id in run_ids]
        return ok(
            {
                "runs": run_summaries(db, runs),
                "metrics": build_metric_matrix(runs, metrics),
                "config_diff": build_config_diff(runs) if payload.get("with_config_diff", True) else {},
                "artifacts": build_artifact_refs(db, run_ids),
                "series": build_series_refs(db, run_ids, payload.get("series") or []),
            }
        )

    @app.post("/api/v1/quick-compare")
    def quick_compare(payload: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
        targets = payload.get("targets") or []
        if not isinstance(targets, list) or not targets:
            raise ApiError(ErrorCode.validation_error, "targets is required")
        resolved_targets = [resolve_compare_target(db, target) for target in targets]
        resolved_runs = [item["run"] for item in resolved_targets if item["run"] is not None]
        run_ids = list(dict.fromkeys(run.id for run in resolved_runs))
        runs = [require_run(db, run_id) for run_id in run_ids]
        metrics = payload.get("metrics") or default_quick_compare_metrics()
        series = payload.get("series") or ["equity_curve", "returns_series"]
        return ok(
            {
                "targets": [
                    {
                        "type": item["type"],
                        "id": item["id"],
                        "label": item["label"],
                        "resolved_run": run_summary_for_quick_compare(db, item["run"]) if item["run"] else None,
                    }
                    for item in resolved_targets
                ],
                "runs": run_summaries(db, runs),
                "metrics": build_metric_matrix(runs, metrics),
                "series": build_series_refs(db, run_ids, series),
            }
        )

    @app.get("/api/v1/lineage/researches/{research_id}")
    def research_lineage(research_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        require_research(db, research_id)
        branches = db.scalars(select(Branch).where(Branch.research_id == research_id)).all()
        runs = db.scalars(select(Run).where(Run.branch_id.in_([branch.id for branch in branches]))).all() if branches else []
        return ok(
            {
                "branches": [BranchRead.model_validate(branch).model_dump(mode="json") for branch in branches],
                "runs": run_summaries(db, runs),
                "edges": [
                    {
                        "from_branch_id": branch.parent_branch_id,
                        "to_branch_id": branch.id,
                        "source_run_id": branch.source_run_id,
                        "reason_code": branch.reason_code,
                    }
                    for branch in branches
                    if branch.parent_branch_id or branch.source_run_id
                ],
            }
        )

    @app.get("/api/v1/lineage/branches/{branch_id}")
    def branch_lineage(branch_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
        branch = require_branch(db, branch_id)
        research = require_research(db, branch.research_id)
        branches = db.scalars(select(Branch).where(Branch.research_id == research.id).order_by(Branch.created_at.asc())).all()
        branch_by_id = {item.id: item for item in branches}

        ancestor_ids: list[str] = []
        current = branch
        seen = {branch.id}
        while current.parent_branch_id and current.parent_branch_id in branch_by_id and current.parent_branch_id not in seen:
            parent = branch_by_id[current.parent_branch_id]
            ancestor_ids.append(parent.id)
            seen.add(parent.id)
            current = parent

        child_ids_by_parent: dict[str, list[str]] = {}
        for item in branches:
            if item.parent_branch_id:
                child_ids_by_parent.setdefault(item.parent_branch_id, []).append(item.id)

        descendant_ids: list[str] = []
        stack = list(child_ids_by_parent.get(branch.id, []))
        seen = {branch.id}
        while stack:
            child_id = stack.pop(0)
            if child_id in seen:
                continue
            seen.add(child_id)
            descendant_ids.append(child_id)
            stack.extend(child_ids_by_parent.get(child_id, []))

        lineage_ids = set(ancestor_ids + [branch.id] + descendant_ids)
        lineage_branches = [item for item in branches if item.id in lineage_ids]
        lineage_id_list = [item.id for item in lineage_branches]
        runs = db.scalars(select(Run).where(Run.branch_id.in_(lineage_id_list)).order_by(Run.created_at.asc())).all() if lineage_id_list else []

        return ok(
            {
                "branch": BranchRead.model_validate(branch).model_dump(mode="json"),
                "research": ResearchRead.model_validate(research).model_dump(mode="json"),
                "branches": [BranchRead.model_validate(item).model_dump(mode="json") for item in lineage_branches],
                "runs": run_summaries(db, runs),
                "ancestor_branch_ids": list(reversed(ancestor_ids)),
                "descendant_branch_ids": descendant_ids,
                "edges": [
                    {
                        "from_branch_id": item.parent_branch_id,
                        "to_branch_id": item.id,
                        "source_run_id": item.source_run_id,
                        "reason_code": item.reason_code,
                    }
                    for item in lineage_branches
                    if item.parent_branch_id or item.source_run_id
                ],
            }
        )

    webui_dist = Path(__file__).resolve().parents[3] / "webui" / "dist"
    if webui_dist.exists():
        app.mount("/", StaticFiles(directory=webui_dist, html=True), name="webui")

    return app


app = create_app()


def ok(data: Any) -> dict[str, Any]:
    return {"ok": True, "data": data, "error": None}


def update_fields(target: Any, payload: Any, fields: set[str]) -> None:
    for field in fields.intersection(payload.model_fields_set):
        value = getattr(payload, field)
        if hasattr(value, "value"):
            value = value.value
        setattr(target, field, value)


def extract_api_token(request: Request) -> str | None:
    header_token = request.headers.get("x-blackbox-token") or request.headers.get("x-api-key")
    if header_token:
        return header_token
    authorization = request.headers.get("authorization") or ""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token:
        return token
    query_token = request.query_params.get("token")
    if query_token:
        return query_token
    return None


def run_summary_for_dashboard(
    run: Run,
    branch_by_id: dict[str, Branch],
    research_by_id: dict[str, Research],
    project_by_id: dict[str, Project],
    artifact_summary_by_run: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    branch = branch_by_id.get(run.branch_id)
    research = research_by_id.get(branch.research_id) if branch else None
    project = project_by_id.get(research.project_id) if research else None
    artifact_summary = artifact_summary_by_run.get(run.id, empty_artifact_summary()) if artifact_summary_by_run is not None else empty_artifact_summary()
    return {
        **RunRead.model_validate(run).model_dump(mode="json"),
        "branch_key": branch.key if branch else None,
        "branch_title": branch.title if branch else None,
        "research_id": research.id if research else None,
        "research_key": research.key if research else None,
        "research_title": research.title if research else None,
        "project_id": project.id if project else None,
        "project_key": project.key if project else None,
        "project_title": project.title if project else None,
        **artifact_summary,
    }


def run_summaries(db: Session, runs: list[Run]) -> list[dict[str, Any]]:
    if not runs:
        return []
    branch_ids = {run.branch_id for run in runs}
    branches = db.scalars(select(Branch).where(Branch.id.in_(branch_ids))).all()
    research_ids = {branch.research_id for branch in branches}
    researches = db.scalars(select(Research).where(Research.id.in_(research_ids))).all() if research_ids else []
    project_ids = {research.project_id for research in researches}
    projects = db.scalars(select(Project).where(Project.id.in_(project_ids))).all() if project_ids else []
    artifacts = db.scalars(select(Artifact).where(Artifact.run_id.in_([run.id for run in runs]))).all()
    return run_summaries_with_maps(runs, branches, researches, projects, artifact_summary_by_run_id(artifacts))


def run_summaries_with_maps(
    runs: list[Run],
    branches: list[Branch],
    researches: list[Research],
    projects: list[Project],
    artifact_summary_by_run: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    branch_by_id = {item.id: item for item in branches}
    research_by_id = {item.id: item for item in researches}
    project_by_id = {item.id: item for item in projects}
    return [run_summary_for_dashboard(run, branch_by_id, research_by_id, project_by_id, artifact_summary_by_run) for run in runs]


def artifact_summary_by_run_id(artifacts: list[Artifact]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[Artifact]] = {}
    for artifact in artifacts:
        grouped.setdefault(artifact.run_id, []).append(artifact)
    return {run_id: summarize_artifacts(items) for run_id, items in grouped.items()}


def summarize_artifacts(artifacts: list[Artifact]) -> dict[str, Any]:
    kinds = sorted({artifact.kind for artifact in artifacts})
    return {
        "artifact_count": len(artifacts),
        "artifact_kinds": kinds,
        "has_report_artifact": any(is_report_artifact(artifact) for artifact in artifacts),
    }


def empty_artifact_summary() -> dict[str, Any]:
    return {"artifact_count": 0, "artifact_kinds": [], "has_report_artifact": False}


def is_report_artifact(artifact: Artifact) -> bool:
    kind = (artifact.kind or "").lower()
    name = (artifact.name or "").lower()
    filename = (artifact.filename or "").lower()
    return "report" in kind or "report" in name or filename.endswith((".html", ".htm", ".pdf"))


def note_summary_for_dashboard(
    note: RunNote,
    run_by_id: dict[str, Run],
    branch_by_id: dict[str, Branch],
    research_by_id: dict[str, Research],
) -> dict[str, Any]:
    run = run_by_id.get(note.run_id)
    branch = branch_by_id.get(run.branch_id) if run else None
    research = research_by_id.get(branch.research_id) if branch else None
    return {
        **NoteRead.model_validate(note).model_dump(mode="json"),
        "run_name": run.name if run else None,
        "branch_id": branch.id if branch else None,
        "branch_key": branch.key if branch else None,
        "research_id": research.id if research else None,
        "research_key": research.key if research else None,
    }


def project_summary_for_dashboard(
    project: Project,
    workspace_by_id: dict[str, Workspace],
    researches: list[Research],
    branches: list[Branch],
    runs: list[Run],
) -> dict[str, Any]:
    project_researches = [research for research in researches if research.project_id == project.id]
    research_ids = {research.id for research in project_researches}
    project_branches = [branch for branch in branches if branch.research_id in research_ids]
    branch_ids = {branch.id for branch in project_branches}
    project_runs = [run for run in runs if run.branch_id in branch_ids]
    workspace = workspace_by_id.get(project.workspace_id)
    return {
        **ProjectRead.model_validate(project).model_dump(mode="json"),
        "workspace_key": workspace.key if workspace else None,
        "research_count": len(project_researches),
        "branch_count": len(project_branches),
        "run_count": len(project_runs),
        "running_run_count": sum(1 for run in project_runs if run.status == RunStatus.running.value),
        "failed_run_count": sum(1 for run in project_runs if run.status == RunStatus.failed.value),
    }


def research_summary_for_dashboard(
    research: Research,
    project_by_id: dict[str, Project],
    branches: list[Branch],
    runs: list[Run],
    since_7d: datetime | None = None,
) -> dict[str, Any]:
    branch_ids = {branch.id for branch in branches}
    research_runs = [run for run in runs if run.branch_id in branch_ids]
    seven_day_cutoff = comparable_datetime(since_7d or (utcnow() - timedelta(days=7)))
    research_runs_7d = [run for run in research_runs if is_on_or_after(run.created_at, seven_day_cutoff)]
    failed_runs_7d = [
        run for run in research_runs
        if run.status == RunStatus.failed.value and is_on_or_after(run.updated_at or run.ended_at or run.created_at, seven_day_cutoff)
    ]
    champion = sorted(
        [run for run in research_runs if run.status == RunStatus.completed.value],
        key=lambda run: float(get_metric_value(run.summary_json, "strategy.summary.sharpe") or float("-inf")),
        reverse=True,
    )
    project = project_by_id.get(research.project_id)
    return {
        **ResearchRead.model_validate(research).model_dump(mode="json"),
        "project_key": project.key if project else None,
        "branch_count": len(branches),
        "run_count": len(research_runs),
        "run_count_7d": len(research_runs_7d),
        "failed_run_count_7d": len(failed_runs_7d),
        "champion_run": RunRead.model_validate(champion[0]).model_dump(mode="json") if champion else None,
    }


def comparable_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def is_on_or_after(value: datetime | None, cutoff: datetime | None) -> bool:
    current = comparable_datetime(value)
    if current is None or cutoff is None:
        return False
    return current >= cutoff


def require_project(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise ApiError(ErrorCode.not_found, f"project {project_id} not found")
    return project


def require_workspace(db: Session, workspace_id: str) -> Workspace:
    workspace = db.get(Workspace, workspace_id)
    if not workspace:
        raise ApiError(ErrorCode.not_found, f"workspace {workspace_id} not found")
    return workspace


def require_research(db: Session, research_id: str) -> Research:
    research = db.get(Research, research_id)
    if not research:
        raise ApiError(ErrorCode.not_found, f"research {research_id} not found")
    return research


def require_branch(db: Session, branch_id: str) -> Branch:
    branch = db.get(Branch, branch_id)
    if not branch:
        raise ApiError(ErrorCode.not_found, f"branch {branch_id} not found")
    return branch


def require_run(db: Session, run_id: str) -> Run:
    run = db.get(Run, run_id)
    if not run:
        raise ApiError(ErrorCode.not_found, f"run {run_id} not found")
    return run


def require_sweep(db: Session, sweep_id: str) -> Sweep:
    sweep = db.get(Sweep, sweep_id)
    if not sweep:
        raise ApiError(ErrorCode.not_found, f"sweep {sweep_id} not found")
    return sweep


def require_compare_set(db: Session, compare_set_id: str) -> CompareSet:
    compare_set = db.get(CompareSet, compare_set_id)
    if not compare_set:
        raise ApiError(ErrorCode.not_found, f"compare set {compare_set_id} not found")
    return compare_set


def default_quick_compare_metrics() -> list[str]:
    return [
        "strategy.summary.annual_return",
        "strategy.summary.annual_volatility",
        "strategy.summary.max_drawdown",
        "strategy.summary.sharpe",
        "strategy.summary.sortino",
        "strategy.summary.calmar",
        "strategy.summary.turnover",
    ]


def resolve_compare_target(db: Session, target: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(target, dict):
        raise ApiError(ErrorCode.validation_error, "compare target must be an object")
    target_type = str(target.get("type") or "").lower()
    target_id = target.get("id")
    if target_type not in {"project", "research", "branch", "run"} or not target_id:
        raise ApiError(ErrorCode.validation_error, "compare target requires type project/research/branch/run and id")
    if target_type == "run":
        run = require_run(db, str(target_id))
        return {"type": target_type, "id": run.id, "label": run.name, "run": run}
    if target_type == "branch":
        branch = require_branch(db, str(target_id))
        return {"type": target_type, "id": branch.id, "label": branch.title or branch.key, "run": representative_run_for_branches(db, [branch.id])}
    if target_type == "research":
        research = require_research(db, str(target_id))
        branches = db.scalars(select(Branch).where(Branch.research_id == research.id)).all()
        return {"type": target_type, "id": research.id, "label": research.title or research.key, "run": representative_run_for_branches(db, [branch.id for branch in branches])}
    project = require_project(db, str(target_id))
    researches = db.scalars(select(Research).where(Research.project_id == project.id)).all()
    branches = db.scalars(select(Branch).where(Branch.research_id.in_([research.id for research in researches]))).all() if researches else []
    return {"type": target_type, "id": project.id, "label": project.title or project.key, "run": representative_run_for_branches(db, [branch.id for branch in branches])}


def representative_run_for_branches(db: Session, branch_ids: list[str]) -> Run | None:
    if not branch_ids:
        return None
    runs = db.scalars(select(Run).where(Run.branch_id.in_(branch_ids))).all()
    if not runs:
        return None
    completed = [run for run in runs if run.status == RunStatus.completed.value]
    candidates = completed or runs
    return sorted(
        candidates,
        key=lambda run: (
            sortable_metric_value(run, "strategy.summary.sharpe"),
            comparable_datetime(run.updated_at or run.ended_at or run.created_at) or datetime.min,
        ),
        reverse=True,
    )[0]


def sortable_metric_value(run: Run, metric: str) -> float:
    value = get_metric_value(run.summary_json or {}, metric)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("-inf")


def run_summary_for_quick_compare(db: Session, run: Run | None) -> dict[str, Any] | None:
    if run is None:
        return None
    summaries = run_summaries(db, [run])
    return summaries[0] if summaries else RunRead.model_validate(run).model_dump(mode="json")


def require_search_view(db: Session, view_id: str) -> SearchView:
    view = db.get(SearchView, view_id)
    if not view:
        raise ApiError(ErrorCode.not_found, f"search view {view_id} not found")
    return view


def hierarchy_maps_for_runs(
    db: Session,
    runs: list[Run],
) -> tuple[dict[str, Branch], dict[str, Research], dict[str, Project]]:
    branch_ids = {run.branch_id for run in runs}
    branches = db.scalars(select(Branch).where(Branch.id.in_(branch_ids))).all() if branch_ids else []
    research_ids = {branch.research_id for branch in branches}
    researches = db.scalars(select(Research).where(Research.id.in_(research_ids))).all() if research_ids else []
    project_ids = {research.project_id for research in researches}
    projects = db.scalars(select(Project).where(Project.id.in_(project_ids))).all() if project_ids else []
    return (
        {item.id: item for item in branches},
        {item.id: item for item in researches},
        {item.id: item for item in projects},
    )


def resolve_project(db: Session, *, project_id: str | None, project_key: str | None) -> Project:
    if project_id:
        return require_project(db, project_id)
    if project_key:
        project = db.scalar(select(Project).where(Project.key == project_key))
        if project:
            return project
    raise ApiError(ErrorCode.not_found, "project not found", "provide project_id or project_key")


def resolve_research(db: Session, *, research_id: str | None, research_key: str | None) -> Research:
    if research_id:
        return require_research(db, research_id)
    if research_key:
        research = db.scalar(select(Research).where(Research.key == research_key))
        if research:
            return research
    raise ApiError(ErrorCode.not_found, "research not found", "provide research_id or research_key")


def resolve_branch(
    db: Session,
    *,
    branch_id: str | None,
    project_key: str | None,
    research_key: str | None,
    branch_key: str | None,
) -> Branch:
    if branch_id:
        return require_branch(db, branch_id)
    if not (project_key and research_key and branch_key):
        raise ApiError(ErrorCode.validation_error, "branch_id or project_key/research_key/branch_key is required")
    project = db.scalar(select(Project).where(Project.key == project_key))
    if not project:
        raise ApiError(ErrorCode.not_found, f"project {project_key} not found")
    research = db.scalar(select(Research).where(Research.project_id == project.id, Research.key == research_key))
    if not research:
        raise ApiError(ErrorCode.not_found, f"research {research_key} not found")
    branch = db.scalar(select(Branch).where(Branch.research_id == research.id, Branch.key == branch_key))
    if not branch:
        raise ApiError(ErrorCode.not_found, f"branch {branch_key} not found")
    return branch


def next_run_sequence(db: Session, branch_id: str) -> int:
    value = db.scalar(select(func.max(Run.sequence_no)).where(Run.branch_id == branch_id))
    return int(value or 0) + 1


def next_event_sequence(db: Session, run_id: str) -> int:
    value = db.scalar(select(func.max(RunEvent.sequence_no)).where(RunEvent.run_id == run_id))
    return int(value or 0) + 1


def get_existing_event(db: Session, run_id: str, client_event_id: str | None) -> RunEvent | None:
    if not client_event_id:
        return None
    return db.scalar(select(RunEvent).where(RunEvent.run_id == run_id, RunEvent.client_event_id == client_event_id))


def get_existing_metrics(db: Session, run_id: str, client_event_id: str | None) -> Sequence[RunMetric]:
    if not client_event_id:
        return []
    return db.scalars(select(RunMetric).where(RunMetric.run_id == run_id, RunMetric.client_event_id == client_event_id)).all()


def get_existing_note(db: Session, run_id: str, client_event_id: str | None) -> RunNote | None:
    if not client_event_id:
        return None
    return db.scalar(select(RunNote).where(RunNote.run_id == run_id, RunNote.client_event_id == client_event_id))


def get_existing_artifact(db: Session, run_id: str, idempotency_key: str | None, artifact_id: str | None = None) -> Artifact | None:
    if artifact_id:
        existing = db.get(Artifact, artifact_id)
        if existing and existing.run_id == run_id:
            return existing
    if not idempotency_key:
        return None
    return db.scalar(
        select(Artifact).where(
            Artifact.run_id == run_id,
            Artifact.metadata_json[IDEMPOTENCY_METADATA_KEY].as_string() == idempotency_key,
        )
    )


def with_idempotency_metadata(metadata: dict[str, Any], idempotency_key: str | None) -> dict[str, Any]:
    if not idempotency_key:
        return metadata
    return {**metadata, IDEMPOTENCY_METADATA_KEY: idempotency_key}


def split_metric_value(value: Any) -> tuple[float | None, str | None, bool | None]:
    if isinstance(value, bool):
        return None, None, value
    if isinstance(value, int | float):
        return float(value), None, None
    return None, str(value), None


def validate_metric_payload_size(payload: MetricCreate) -> None:
    encoded = json.dumps(jsonable_encoder(payload), ensure_ascii=False, default=str).encode("utf-8")
    limit = get_settings().max_metric_payload_bytes
    if len(encoded) > limit:
        raise ApiError(
            ErrorCode.validation_error,
            f"metric payload is too large ({len(encoded)} bytes > {limit} bytes); use log_series/log_table/log_artifact for large data",
        )


def update_summary(summary: dict[str, Any], namespace: str, key: str, value: Any) -> None:
    section = summary.setdefault(namespace, {})
    section[key] = value


def build_artifact_preview(filename: str, mime_type: str | None, content: bytes) -> dict[str, Any]:
    return get_worker().submit("artifact.preview", build_preview, filename, mime_type, content)


def build_preview(filename: str, mime_type: str | None, content: bytes) -> dict[str, Any]:
    lower_name = filename.lower()
    preview: dict[str, Any] = {"filename": filename, "size_bytes": len(content)}
    if mime_type:
        preview["mime_type"] = mime_type
    if lower_name.endswith(".csv") or mime_type in {"text/csv", "application/csv"}:
        preview.update(build_csv_preview(content))
    if lower_name.endswith(".json") or mime_type == "application/json":
        preview.update(build_json_preview(content))
    if is_image_file(lower_name, mime_type):
        dimensions = image_dimensions(content)
        if dimensions:
            preview.update(dimensions)
    if lower_name.endswith(".parquet") or mime_type in {"application/x-parquet", "application/vnd.apache.parquet"}:
        preview.update(build_parquet_preview(content))
    if lower_name.endswith(".html") or mime_type == "text/html":
        text = content[:2048].decode("utf-8", errors="replace")
        preview["title"] = extract_title(text)
    return preview


def build_csv_preview(content: bytes, max_rows: int = 20) -> dict[str, Any]:
    text = content.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict[str, Any]] = []
    for row in reader:
        if len(rows) < max_rows:
            rows.append(dict(row))
    return {
        "format": "csv",
        "columns": list(reader.fieldnames or []),
        "row_count": max(len(lines) - 1, 0) if reader.fieldnames else 0,
        "rows": rows,
        "head": lines[: max_rows + 1],
    }


def build_json_preview(content: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(content.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return {"format": "json", "preview_status": "invalid json"}
    if isinstance(parsed, list):
        rows = parsed[:20]
        columns = sorted({key for row in rows if isinstance(row, dict) for key in row})
        return {"format": "json", "json_type": "array", "row_count": len(parsed), "columns": columns, "rows": rows}
    if isinstance(parsed, dict):
        return {"format": "json", "json_type": "object", "keys": sorted(parsed.keys())[:50]}
    return {"format": "json", "json_type": type(parsed).__name__, "value": parsed}


def build_parquet_preview(content: bytes, max_rows: int = 20) -> dict[str, Any]:
    preview: dict[str, Any] = {"format": "parquet"}
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        preview["preview_status"] = "pyarrow is not installed"
        return preview
    try:
        parquet_file = pq.ParquetFile(pa.BufferReader(content))
        schema = parquet_file.schema_arrow
        columns = list(getattr(schema, "names", []))
        preview["columns"] = columns
        preview["schema"] = parquet_schema_fields(schema, columns)
        metadata = getattr(parquet_file, "metadata", None)
        if metadata is not None:
            preview["row_count"] = int(getattr(metadata, "num_rows", 0))
            preview["row_group_count"] = int(getattr(metadata, "num_row_groups", 0))
        if max_rows > 0 and preview.get("row_count", 1):
            table = parquet_file.read()
            if hasattr(table, "slice"):
                table = table.slice(0, max_rows)
            if hasattr(table, "to_pylist"):
                preview["rows"] = table.to_pylist()
        preview["preview_status"] = "ok"
    except Exception as exc:
        preview["preview_status"] = f"parquet preview failed: {type(exc).__name__}"
    return preview


def parquet_schema_fields(schema: Any, columns: list[str]) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for name in columns:
        field = schema.field(name) if hasattr(schema, "field") else None
        item: dict[str, Any] = {"name": name}
        if field is not None:
            if hasattr(field, "type"):
                item["type"] = str(field.type)
            if hasattr(field, "nullable"):
                item["nullable"] = bool(field.nullable)
        fields.append(item)
    return fields


def is_image_file(filename: str, mime_type: str | None) -> bool:
    return filename.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")) or bool(mime_type and mime_type.startswith("image/"))


def image_dimensions(content: bytes) -> dict[str, Any] | None:
    if content.startswith(b"\x89PNG\r\n\x1a\n") and len(content) >= 24:
        return {"format": "image", "width": int.from_bytes(content[16:20], "big"), "height": int.from_bytes(content[20:24], "big")}
    if content[:6] in {b"GIF87a", b"GIF89a"} and len(content) >= 10:
        return {"format": "image", "width": int.from_bytes(content[6:8], "little"), "height": int.from_bytes(content[8:10], "little")}
    if content.startswith(b"\xff\xd8"):
        return jpeg_dimensions(content)
    return None


def jpeg_dimensions(content: bytes) -> dict[str, Any] | None:
    index = 2
    while index + 9 < len(content):
        if content[index] != 0xFF:
            index += 1
            continue
        marker = content[index + 1]
        index += 2
        if marker in {0xD8, 0xD9}:
            continue
        if index + 2 > len(content):
            return None
        segment_length = int.from_bytes(content[index : index + 2], "big")
        if segment_length < 2:
            return None
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF} and index + 7 < len(content):
            return {
                "format": "image",
                "width": int.from_bytes(content[index + 5 : index + 7], "big"),
                "height": int.from_bytes(content[index + 3 : index + 5], "big"),
            }
        index += segment_length
    return None


def serialize_series_csv(rows: list[dict[str, Any]]) -> bytes:
    if not rows:
        return b""
    fieldnames = sorted({key for row in rows for key in row})
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def serialize_series(rows: list[dict[str, Any]], kind: str | None = None) -> bytes:
    if is_parquet_kind(kind):
        return serialize_series_parquet(rows)
    return serialize_series_csv(rows)


def serialize_series_parquet(rows: list[dict[str, Any]]) -> bytes:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ApiError(
            ErrorCode.validation_error,
            "pyarrow is required to serialize parquet series artifacts",
            "install pyarrow or use kind=table_csv",
        ) from exc
    output = io.BytesIO()
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, output)
    return output.getvalue()


def default_artifact_filename(name: str, kind: str | None = None) -> str:
    if is_parquet_kind(kind):
        return f"{name}.parquet"
    if kind and kind.endswith("_json"):
        return f"{name}.json"
    return f"{name}.csv"


def default_artifact_mime_type(filename: str, kind: str | None = None) -> str:
    if is_parquet_kind(kind) or filename.lower().endswith(".parquet"):
        return "application/x-parquet"
    if filename.lower().endswith(".json") or (kind and kind.endswith("_json")):
        return "application/json"
    return "text/csv"


def is_parquet_kind(kind: str | None) -> bool:
    return bool(kind and kind.endswith("_parquet"))


def parse_metadata_query(metadata: str | None) -> dict[str, Any]:
    if not metadata:
        return {}
    try:
        parsed = json.loads(metadata)
    except json.JSONDecodeError as exc:
        raise ApiError(ErrorCode.validation_error, "artifact metadata must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ApiError(ErrorCode.validation_error, "artifact metadata must be a JSON object")
    return parsed


def extract_title(text: str) -> str | None:
    lower = text.lower()
    start = lower.find("<title>")
    end = lower.find("</title>")
    if start >= 0 and end > start:
        return text[start + len("<title>") : end].strip()
    return None


def run_detail(db: Session, run: Run) -> dict[str, Any]:
    source_run = db.get(Run, run.source_run_id) if run.source_run_id else None
    run_items = [item for item in [run, source_run] if item is not None]
    run_by_id = {item["id"]: item for item in run_summaries(db, run_items)}
    artifacts = db.scalars(select(Artifact).where(Artifact.run_id == run.id).order_by(Artifact.created_at)).all()
    return {
        **run_by_id[run.id],
        "source_run": run_by_id.get(source_run.id) if source_run else None,
        "source_config_diff": build_pair_config_diff(source_run.config_json if source_run else {}, run.config_json or {}) if source_run else [],
        "events": [EventRead.model_validate(item).model_dump(mode="json") for item in db.scalars(select(RunEvent).where(RunEvent.run_id == run.id).order_by(RunEvent.sequence_no))],
        "metrics": [MetricRead.model_validate(item).model_dump(mode="json") for item in db.scalars(select(RunMetric).where(RunMetric.run_id == run.id).order_by(RunMetric.created_at))],
        "artifacts": [artifact_read_with_full_series(item) for item in artifacts],
        "notes": [NoteRead.model_validate(item).model_dump(mode="json") for item in db.scalars(select(RunNote).where(RunNote.run_id == run.id).order_by(RunNote.created_at))],
        "snapshots": snapshot_detail(db, run.id),
    }


def snapshot_detail(db: Session, run_id: str) -> dict[str, Any]:
    return {
        "code": [
            CodeSnapshotRead.model_validate(item).model_dump(mode="json")
            for item in db.scalars(select(CodeSnapshot).where(CodeSnapshot.run_id == run_id).order_by(CodeSnapshot.created_at))
        ],
        "data": [
            DataSnapshotRead.model_validate(item).model_dump(mode="json")
            for item in db.scalars(select(DataSnapshot).where(DataSnapshot.run_id == run_id).order_by(DataSnapshot.created_at))
        ],
        "env": [
            EnvSnapshotRead.model_validate(item).model_dump(mode="json")
            for item in db.scalars(select(EnvSnapshot).where(EnvSnapshot.run_id == run_id).order_by(EnvSnapshot.created_at))
        ],
    }


def build_metric_matrix(runs: list[Run], metrics: list[str]) -> dict[str, dict[str, Any]]:
    matrix: dict[str, dict[str, Any]] = {}
    for metric in metrics:
        namespace, _, key = metric.rpartition(".")
        row: dict[str, Any] = {}
        for run in runs:
            row[run.id] = (run.summary_json.get(namespace, {}) if namespace else run.summary_json).get(key)
        matrix[metric] = row
    if not metrics:
        keys = sorted({f"{namespace}.{key}" for run in runs for namespace, values in run.summary_json.items() if isinstance(values, dict) for key in values})
        return build_metric_matrix(runs, keys)
    return matrix


def build_config_diff(runs: list[Run]) -> dict[str, dict[str, Any]]:
    if not runs:
        return {}
    flattened = {run.id: flatten_json(run.config_json or {}) for run in runs}
    all_keys = sorted({key for values in flattened.values() for key in values})
    diff: dict[str, dict[str, Any]] = {}
    for key in all_keys:
        values = {run.id: flattened[run.id].get(key) for run in runs}
        if len({json.dumps(value, sort_keys=True, ensure_ascii=False, default=str) for value in values.values()}) > 1:
            diff[key] = values
    return diff


def build_pair_config_diff(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    before_flat = flatten_json(before)
    after_flat = flatten_json(after)
    rows: list[dict[str, Any]] = []
    for path in sorted(set(before_flat) | set(after_flat)):
        before_value = before_flat.get(path)
        after_value = after_flat.get(path)
        if json.dumps(before_value, sort_keys=True, ensure_ascii=False, default=str) != json.dumps(after_value, sort_keys=True, ensure_ascii=False, default=str):
            rows.append({"path": path, "before": before_value, "after": after_value})
    return rows


def flatten_json(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        if not value:
            return {prefix: {}} if prefix else {}
        result: dict[str, Any] = {}
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            result.update(flatten_json(item, path))
        return result
    if isinstance(value, list):
        if not value:
            return {prefix: []}
        result: dict[str, Any] = {}
        for index, item in enumerate(value):
            result.update(flatten_json(item, f"{prefix}[{index}]"))
        return result
    return {prefix: value}


def build_artifact_refs(db: Session, run_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for run_id in run_ids:
        artifacts = db.scalars(select(Artifact).where(Artifact.run_id == run_id).order_by(Artifact.created_at)).all()
        result[run_id] = [
            ArtifactRead.model_validate(item).model_dump(mode="json")
            for item in artifacts
        ]
    return result


def search_run_records(db: Session, payload: dict[str, Any]) -> list[Run]:
    query = select(Run)
    if status := payload.get("status"):
        query = query.where(Run.status == status)
    if branch_id := payload.get("branch_id"):
        query = query.where(Run.branch_id == branch_id)
    if author_type := payload.get("author_type"):
        query = query.where(Run.created_by_type == author_type)
    if name := payload.get("name"):
        query = query.where(Run.name.contains(name))
    query = apply_datetime_query_filters(query, Run, payload)
    max_scan = int(payload.get("max_scan", 1000))
    limit = int(payload.get("limit", 50))
    candidates = db.scalars(query.order_by(Run.created_at.desc()).limit(max_scan)).all()
    runs = [run for run in candidates if run_matches_search(db, run, payload)]
    return runs[:limit]


def search_research_records(db: Session, payload: dict[str, Any]) -> list[Research]:
    query = select(Research)
    if status := payload.get("status"):
        query = query.where(Research.status == status)
    if project_id := payload.get("project_id"):
        query = query.where(Research.project_id == project_id)
    if project_key := payload.get("project_key"):
        project = db.scalar(select(Project).where(Project.key == project_key))
        if not project:
            return []
        query = query.where(Research.project_id == project.id)
    max_scan = int(payload.get("max_scan", 1000))
    limit = int(payload.get("limit", 50))
    candidates = db.scalars(query.order_by(Research.updated_at.desc()).limit(max_scan)).all()
    researches = [research for research in candidates if research_matches_search(research, payload)]
    return researches[:limit]


def build_series_refs(db: Session, run_ids: list[str], requested_series: list[str]) -> dict[str, dict[str, Any]]:
    requested = set(requested_series)
    result: dict[str, dict[str, Any]] = {}
    for run_id in run_ids:
        artifacts = db.scalars(select(Artifact).where(Artifact.run_id == run_id).order_by(Artifact.created_at)).all()
        for artifact in artifacts:
            series_meta = extract_series_metadata(artifact)
            if not series_meta:
                continue
            series_name = str(series_meta.get("name") or artifact.name)
            namespace = series_meta.get("namespace")
            if requested and not series_matches_request(series_name, namespace, requested):
                continue
            result.setdefault(series_name, {})[run_id] = {
                "artifact_id": artifact.id,
                "artifact_name": artifact.name,
                "kind": artifact.kind,
                "x": series_meta.get("x"),
                "y": series_meta.get("y"),
                "namespace": namespace,
                "columns": artifact.preview_json.get("columns", []),
                "rows": full_rows_from_artifact(artifact),
            }
    return result


def extract_series_metadata(artifact: Artifact) -> dict[str, Any] | None:
    metadata = artifact.metadata_json or {}
    series = metadata.get("series") if isinstance(metadata, dict) else None
    if isinstance(series, dict):
        return {"name": artifact.name, **series}
    legacy_keys = {"x", "y", "namespace"}
    if isinstance(metadata, dict) and legacy_keys.intersection(metadata):
        return {"name": artifact.name, **metadata}
    return None


def artifact_read_with_full_series(artifact: Artifact) -> dict[str, Any]:
    data = ArtifactRead.model_validate(artifact).model_dump(mode="json")
    if not extract_series_metadata(artifact):
        return data
    preview = dict(data.get("preview_json") or {})
    rows = full_rows_from_artifact(artifact)
    if rows:
        preview["rows"] = rows
        preview["row_count"] = len(rows)
        data["preview_json"] = preview
    return data


def series_matches_request(series_name: str, namespace: Any, requested: set[str]) -> bool:
    if series_name in requested or namespace in requested:
        return True
    aliases = {
        "drawdown": "drawdown_series",
        "dd": "drawdown_series",
        "returns": "returns_series",
        "return": "returns_series",
    }
    return any(aliases.get(item) == series_name for item in requested)


def full_rows_from_artifact(artifact: Artifact) -> list[dict[str, Any]]:
    content = artifact_content_bytes(artifact)
    if content is None:
        return preview_rows_from_artifact(artifact)
    rows = rows_from_content(artifact.filename or artifact.name, artifact.mime_type, content)
    return rows if rows else preview_rows_from_artifact(artifact)


def artifact_content_bytes(artifact: Artifact) -> bytes | None:
    try:
        target = get_artifact_content_target(get_settings(), artifact.storage_uri, artifact.mime_type)
    except ApiError:
        return None
    if target.path and target.path.is_file():
        return target.path.read_bytes()
    return None


def rows_from_content(filename: str, mime_type: str | None, content: bytes) -> list[dict[str, Any]]:
    lower_name = filename.lower()
    if lower_name.endswith(".csv") or mime_type in {"text/csv", "application/csv"}:
        return csv_rows_from_content(content)
    if lower_name.endswith(".json") or mime_type == "application/json":
        return json_rows_from_content(content)
    if lower_name.endswith(".parquet") or mime_type in {"application/x-parquet", "application/vnd.apache.parquet"}:
        return parquet_rows_from_content(content)
    return []


def csv_rows_from_content(content: bytes) -> list[dict[str, Any]]:
    text = content.decode("utf-8-sig", errors="replace")
    return [dict(row) for row in csv.DictReader(io.StringIO(text))]


def json_rows_from_content(content: bytes) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(content.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, list):
        return [row for row in parsed if isinstance(row, dict)]
    return []


def parquet_rows_from_content(content: bytes) -> list[dict[str, Any]]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        return []
    try:
        table = pq.ParquetFile(pa.BufferReader(content)).read()
        return table.to_pylist() if hasattr(table, "to_pylist") else []
    except Exception:
        return []


def preview_rows_from_artifact(artifact: Artifact) -> list[dict[str, Any]]:
    if isinstance(artifact.preview_json.get("rows"), list):
        return artifact.preview_json["rows"]
    lines = artifact.preview_json.get("head") or []
    if not lines:
        return []
    reader = csv.DictReader(io.StringIO("\n".join(lines)))
    return [dict(row) for row in reader]


def build_sweep_summary(sweep: Sweep, members: list[SweepRun], runs: list[Run]) -> dict[str, Any]:
    run_by_id = {run.id: run for run in runs}
    objective_metric = (sweep.objective_json or {}).get("metric") or "strategy.summary.sharpe"
    direction = ((sweep.objective_json or {}).get("direction") or "max").lower()
    coord_keys = ordered_coord_keys(members, sweep.search_space_json or {})
    heatmap_axes = coord_keys[:2]
    rows: list[dict[str, Any]] = []
    for member in members:
        run = run_by_id.get(member.run_id)
        value = get_metric_value(run.summary_json, objective_metric) if run else None
        rows.append(
            {
                "sweep_run_id": member.id,
                "run_id": member.run_id,
                "run_name": run.name if run else None,
                "coord": member.coord_json or {},
                "rank": member.rank,
                "metric": objective_metric,
                "value": value,
            }
        )

    rows.sort(key=lambda item: sweep_sort_key(item, direction))
    for index, row in enumerate(rows, start=1):
        row["computed_rank"] = index if row["value"] is not None else None

    cells = [
        {
            "x": row["coord"].get(heatmap_axes[0]),
            "y": row["coord"].get(heatmap_axes[1]),
            "value": row["value"],
            "run_id": row["run_id"],
            "run_name": row["run_name"],
            "rank": row["rank"] if row["rank"] is not None else row["computed_rank"],
            "coord": row["coord"],
        }
        for row in rows
        if len(heatmap_axes) == 2 and heatmap_axes[0] in row["coord"] and heatmap_axes[1] in row["coord"]
    ]
    return {
        "sweep_id": sweep.id,
        "objective": {"metric": objective_metric, "direction": direction},
        "coord_keys": coord_keys,
        "heatmap": {
            "x_key": heatmap_axes[0] if len(heatmap_axes) == 2 else None,
            "y_key": heatmap_axes[1] if len(heatmap_axes) == 2 else None,
            "x_values": sorted_unique([cell["x"] for cell in cells]),
            "y_values": sorted_unique([cell["y"] for cell in cells]),
            "cells": cells,
        },
        "rows": rows,
    }


def ordered_coord_keys(members: list[SweepRun], search_space: dict[str, Any]) -> list[str]:
    keys: list[str] = list(search_space.keys())
    for member in members:
        for key in (member.coord_json or {}).keys():
            if key not in keys:
                keys.append(key)
    return keys


def sweep_sort_key(row: dict[str, Any], direction: str) -> tuple[int, float, str]:
    value = row.get("value")
    if value is None:
        return (1, 0.0, row.get("run_id") or "")
    try:
        number = float(value)
    except (TypeError, ValueError):
        return (1, 0.0, row.get("run_id") or "")
    return (0, number if direction == "min" else -number, row.get("run_id") or "")


def sorted_unique(values: Sequence[Any]) -> list[Any]:
    unique: dict[str, Any] = {}
    for value in values:
        unique.setdefault(repr(value), value)
    return [unique[key] for key in sorted(unique, key=lambda item: str(unique[item]))]


def apply_datetime_query_filters(query: Any, model: Any, payload: dict[str, Any]) -> Any:
    for field in ("created", "updated", "started", "ended"):
        column_name = "updated_at" if field == "updated" else "started_at" if field == "started" else "ended_at" if field == "ended" else "created_at"
        column = getattr(model, column_name)
        if after := payload.get(f"{field}_after"):
            query = query.where(column >= parse_filter_datetime(after))
        if before := payload.get(f"{field}_before"):
            query = query.where(column <= parse_filter_datetime(before))
    return query


def parse_filter_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ApiError(ErrorCode.validation_error, f"invalid datetime filter: {value}") from exc
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    raise ApiError(ErrorCode.validation_error, f"invalid datetime filter: {value}")


def run_matches_search(db: Session, run: Run, payload: dict[str, Any]) -> bool:
    branch = db.get(Branch, run.branch_id)
    if not branch:
        return False
    research = db.get(Research, branch.research_id)
    if not research:
        return False
    project = db.get(Project, research.project_id)
    if not project:
        return False

    if payload.get("project_key") and project.key != payload["project_key"]:
        return False
    if payload.get("research_key") and research.key != payload["research_key"]:
        return False
    if payload.get("branch_key") and branch.key != payload["branch_key"]:
        return False

    tags = payload.get("tags") or []
    if tags and not set(tags).issubset(set(run.tags or [])):
        return False

    for key, expected in (payload.get("config") or {}).items():
        if get_path(run.config_json, key) != expected:
            return False

    for key, expected in (payload.get("context") or {}).items():
        if get_path(run.context_json, key) != expected:
            return False

    for metric_filter in payload.get("metrics") or []:
        metric_value = get_metric_value(run.summary_json, metric_filter.get("metric", ""))
        if not compare_values(metric_value, metric_filter.get("op", "=="), metric_filter.get("value")):
            return False

    if artifact_kind := payload.get("has_artifact"):
        artifact = db.scalar(select(Artifact).where(Artifact.run_id == run.id, Artifact.kind == artifact_kind))
        if not artifact:
            return False

    return True


def research_matches_search(research: Research, payload: dict[str, Any]) -> bool:
    tags = payload.get("tags") or []
    if tags and not set(tags).issubset(set(research.tags or [])):
        return False
    if key := payload.get("key"):
        if research.key != key:
            return False
    if text := payload.get("text"):
        haystack = " ".join(
            str(value or "")
            for value in [research.key, research.title, research.goal, research.hypothesis, research.status]
        ).lower()
        if str(text).lower() not in haystack:
            return False
    return True


def get_metric_value(summary: dict[str, Any], metric: str) -> Any:
    namespace, _, key = metric.rpartition(".")
    if namespace and isinstance(summary.get(namespace), dict):
        return summary[namespace].get(key)
    return get_path(summary, metric)


def get_path(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def compare_values(actual: Any, op: str, expected: Any) -> bool:
    if op in {"=", "=="}:
        return actual == expected
    if op == "!=":
        return actual != expected
    if actual is None:
        return False
    if op in {">", ">=", "<", "<="}:
        try:
            actual_number = float(actual)
            expected_number = float(expected)
        except (TypeError, ValueError):
            return False
        if op == ">":
            return actual_number > expected_number
        if op == ">=":
            return actual_number >= expected_number
        if op == "<":
            return actual_number < expected_number
        if op == "<=":
            return actual_number <= expected_number
    if op == "contains":
        return str(expected) in str(actual)
    raise ApiError(ErrorCode.validation_error, f"unsupported metric operator: {op}")
