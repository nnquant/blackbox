from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from .enums import BranchStatus, EventType, NoteKind, RunStatus

T = TypeVar("T")


class ErrorPayload(BaseModel):
    code: str
    message: str
    hint: str | None = None
    details: Any = None


class ApiResponse(BaseModel, Generic[T]):
    ok: bool
    data: T | None = None
    error: ErrorPayload | None = None


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class WorkspaceCreate(BaseModel):
    id: str | None = None
    key: str
    title: str
    description: str | None = None
    roles: dict[str, Any] = Field(default_factory=dict)


class WorkspaceUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    roles: dict[str, Any] | None = None


class WorkspaceRead(ORMModel):
    id: str
    key: str
    title: str
    description: str | None = None
    roles_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ProjectCreate(BaseModel):
    workspace_id: str = "local"
    key: str
    title: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    retention_policy: dict[str, Any] = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    retention_policy: dict[str, Any] | None = None


class ProjectRead(ORMModel):
    id: str
    workspace_id: str
    key: str
    title: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    retention_policy_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ResearchCreate(BaseModel):
    project_id: str | None = None
    project_key: str | None = None
    key: str
    title: str
    goal: str | None = None
    hypothesis: str | None = None
    status: str = "active"
    tags: list[str] = Field(default_factory=list)


class ResearchUpdate(BaseModel):
    title: str | None = None
    goal: str | None = None
    hypothesis: str | None = None
    status: str | None = None
    tags: list[str] | None = None


class ResearchRead(ORMModel):
    id: str
    project_id: str
    key: str
    title: str
    goal: str | None = None
    hypothesis: str | None = None
    status: str
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class BranchCreate(BaseModel):
    research_id: str | None = None
    research_key: str | None = None
    key: str
    title: str
    parent_branch_id: str | None = None
    source_run_id: str | None = None
    reason_code: str | None = None
    reason_summary: str | None = None
    hypothesis: str | None = None
    expected_change: dict[str, Any] = Field(default_factory=dict)
    status: BranchStatus = BranchStatus.active
    created_by_type: str = "human"
    created_by_id: str | None = None


class BranchUpdate(BaseModel):
    title: str | None = None
    parent_branch_id: str | None = None
    source_run_id: str | None = None
    reason_code: str | None = None
    reason_summary: str | None = None
    hypothesis: str | None = None
    expected_change: dict[str, Any] | None = None
    status: BranchStatus | None = None


class BranchRead(ORMModel):
    id: str
    research_id: str
    key: str
    title: str
    parent_branch_id: str | None = None
    source_run_id: str | None = None
    reason_code: str | None = None
    reason_summary: str | None = None
    hypothesis: str | None = None
    expected_change: dict[str, Any] = Field(default_factory=dict)
    status: str
    created_by_type: str
    created_by_id: str | None = None
    created_at: datetime
    updated_at: datetime


class RunCreate(BaseModel):
    project_key: str | None = None
    research_key: str | None = None
    branch_key: str | None = None
    branch_id: str | None = None
    name: str
    title: str | None = None
    source_run_id: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    created_by_type: str = "human"
    created_by_id: str | None = None


class RunUpdate(BaseModel):
    name: str | None = None
    title: str | None = None
    source_run_id: str | None = None
    config: dict[str, Any] | None = None
    context: dict[str, Any] | None = None
    tags: list[str] | None = None


class RunCloneCreate(BaseModel):
    branch_id: str | None = None
    name: str | None = None
    title: str | None = None
    config_overrides: dict[str, Any] = Field(default_factory=dict)
    context_overrides: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] | None = None
    created_by_type: str = "human"
    created_by_id: str | None = None


class RunRead(ORMModel):
    id: str
    branch_id: str
    name: str
    title: str | None = None
    status: str
    source_run_id: str | None = None
    sequence_no: int
    config_json: dict[str, Any] = Field(default_factory=dict)
    context_json: dict[str, Any] = Field(default_factory=dict)
    summary_json: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_by_type: str
    created_by_id: str | None = None
    created_at: datetime
    updated_at: datetime


class EventCreate(BaseModel):
    event_type: EventType
    stage: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    client_event_id: str | None = None


class EventRead(ORMModel):
    id: str
    run_id: str
    sequence_no: int
    event_type: str
    stage: str | None = None
    payload_json: dict[str, Any] = Field(default_factory=dict)
    client_event_id: str | None = None
    created_at: datetime


class MetricPoint(BaseModel):
    kind: str = "summary"
    name: str | None = None
    step: int | None = None
    timestamp: datetime | None = None
    coord: dict[str, Any] | None = None


class MetricCreate(BaseModel):
    namespace: str
    values: dict[str, Any]
    point: MetricPoint = Field(default_factory=MetricPoint)
    client_event_id: str | None = None


class MetricRead(ORMModel):
    id: str
    run_id: str
    namespace: str
    key: str
    value_number: float | None = None
    value_string: str | None = None
    value_bool: bool | None = None
    point_kind: str
    point_event_name: str | None = None
    point_step: int | None = None
    point_timestamp: datetime | None = None
    point_coord_json: dict[str, Any] | None = None
    client_event_id: str | None = None
    created_at: datetime


class NoteCreate(BaseModel):
    kind: NoteKind = NoteKind.observation
    summary: str
    content: str | None = None
    structured: dict[str, Any] = Field(default_factory=dict)
    author_type: str = "human"
    client_event_id: str | None = None


class NoteRead(ORMModel):
    id: str
    run_id: str
    kind: str
    summary: str
    content_md: str | None = None
    structured_json: dict[str, Any] = Field(default_factory=dict)
    author_type: str
    client_event_id: str | None = None
    created_at: datetime


class ArtifactRead(ORMModel):
    id: str
    run_id: str
    kind: str
    name: str
    storage_uri: str
    filename: str
    mime_type: str | None = None
    size_bytes: int
    sha256: str
    preview_json: dict[str, Any] = Field(default_factory=dict)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ArtifactUploadInit(BaseModel):
    kind: str = "other"
    name: str
    filename: str = "artifact.bin"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArtifactUploadComplete(BaseModel):
    artifact_id: str | None = None
    kind: str = "other"
    name: str
    uri: str
    filename: str | None = None
    mime_type: str | None = None
    size_bytes: int = 0
    sha256: str = ""
    preview: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SeriesCreate(BaseModel):
    name: str
    data: list[dict[str, Any]]
    x: str | None = None
    y: str | list[str] | None = None
    mode: str | None = None
    namespace: str | None = None
    metric: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    kind: str = "table_csv"
    filename: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CodeSnapshotCreate(BaseModel):
    repo_url: str | None = None
    git_commit: str | None = None
    git_dirty: bool = False
    patch_artifact_id: str | None = None
    requirements_hash: str | None = None
    container_image: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CodeSnapshotRead(ORMModel):
    id: str
    run_id: str
    repo_url: str | None = None
    git_commit: str | None = None
    git_dirty: bool = False
    patch_artifact_id: str | None = None
    requirements_hash: str | None = None
    container_image: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class DataSnapshotCreate(BaseModel):
    dataset_name: str | None = None
    dataset_version: str | None = None
    fingerprint: str | None = None
    universe: str | None = None
    benchmark: str | None = None
    calendar: str | None = None
    fee_model: str | None = None
    slippage_model: str | None = None
    time_range: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DataSnapshotRead(ORMModel):
    id: str
    run_id: str
    dataset_name: str | None = None
    dataset_version: str | None = None
    fingerprint: str | None = None
    universe: str | None = None
    benchmark: str | None = None
    calendar: str | None = None
    fee_model: str | None = None
    slippage_model: str | None = None
    time_range: dict[str, Any] = Field(default_factory=dict)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class EnvSnapshotCreate(BaseModel):
    python_version: str | None = None
    platform: str | None = None
    hostname: str | None = None
    packages: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EnvSnapshotRead(ORMModel):
    id: str
    run_id: str
    python_version: str | None = None
    platform: str | None = None
    hostname: str | None = None
    packages_json: dict[str, Any] = Field(default_factory=dict)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class SweepCreate(BaseModel):
    branch_id: str
    name: str
    search_space: dict[str, Any] = Field(default_factory=dict)
    objective: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"


class SweepRead(ORMModel):
    id: str
    branch_id: str
    name: str
    search_space_json: dict[str, Any] = Field(default_factory=dict)
    objective_json: dict[str, Any] = Field(default_factory=dict)
    status: str
    created_at: datetime
    updated_at: datetime


class SweepRunAttach(BaseModel):
    run_id: str
    coord: dict[str, Any] = Field(default_factory=dict)
    rank: int | None = None


class SweepRunRead(ORMModel):
    id: str
    sweep_id: str
    run_id: str
    coord_json: dict[str, Any] = Field(default_factory=dict)
    rank: int | None = None
    created_at: datetime


class CompareSetCreate(BaseModel):
    project_id: str
    name: str
    run_ids: list[str]
    layout: dict[str, Any] = Field(default_factory=dict)


class CompareSetUpdate(BaseModel):
    name: str | None = None
    run_ids: list[str] | None = None
    layout: dict[str, Any] | None = None


class CompareSetRead(ORMModel):
    id: str
    project_id: str
    name: str
    run_ids_json: list[str] = Field(default_factory=list)
    layout_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class SearchViewCreate(BaseModel):
    project_id: str
    name: str
    description: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)


class SearchViewUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    filters: dict[str, Any] | None = None


class SearchViewRead(ORMModel):
    id: str
    project_id: str
    name: str
    description: str | None = None
    filters_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
