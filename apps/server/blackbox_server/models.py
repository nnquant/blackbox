from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from blackbox_common.enums import BranchStatus, RunStatus
from blackbox_common.ids import new_id

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class Workspace(TimestampMixin, Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("workspace"))
    key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    roles_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("project"))
    workspace_id: Mapped[str] = mapped_column(String(64), default="local", nullable=False)
    key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    retention_policy_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    researches: Mapped[list["Research"]] = relationship(back_populates="project")


class Research(TimestampMixin, Base):
    __tablename__ = "researches"
    __table_args__ = (UniqueConstraint("project_id", "key", name="uq_research_project_key"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("research"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    goal: Mapped[str | None] = mapped_column(Text)
    hypothesis: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    project: Mapped[Project] = relationship(back_populates="researches")
    branches: Mapped[list["Branch"]] = relationship(back_populates="research")


class Branch(TimestampMixin, Base):
    __tablename__ = "branches"
    __table_args__ = (UniqueConstraint("research_id", "key", name="uq_branch_research_key"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("branch"))
    research_id: Mapped[str] = mapped_column(ForeignKey("researches.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    parent_branch_id: Mapped[str | None] = mapped_column(ForeignKey("branches.id"), index=True)
    source_run_id: Mapped[str | None] = mapped_column(String(64), index=True)
    reason_code: Mapped[str | None] = mapped_column(String(128))
    reason_summary: Mapped[str | None] = mapped_column(Text)
    hypothesis: Mapped[str | None] = mapped_column(Text)
    expected_change: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=BranchStatus.active.value, nullable=False)
    created_by_type: Mapped[str] = mapped_column(String(32), default="human", nullable=False)
    created_by_id: Mapped[str | None] = mapped_column(String(128))

    research: Mapped[Research] = relationship(back_populates="branches")
    runs: Mapped[list["Run"]] = relationship(back_populates="branch")


class Run(TimestampMixin, Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("run"))
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(32), default=RunStatus.running.value, nullable=False, index=True)
    source_run_id: Mapped[str | None] = mapped_column(String(64), index=True)
    sequence_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    context_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_type: Mapped[str] = mapped_column(String(32), default="human", nullable=False)
    created_by_id: Mapped[str | None] = mapped_column(String(128))

    branch: Mapped[Branch] = relationship(back_populates="runs")


class RunEvent(Base):
    __tablename__ = "run_events"
    __table_args__ = (UniqueConstraint("run_id", "client_event_id", name="uq_event_client_event"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("event"))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    stage: Mapped[str | None] = mapped_column(String(128), index=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    client_event_id: Mapped[str | None] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class RunMetric(Base):
    __tablename__ = "run_metrics"
    __table_args__ = (UniqueConstraint("run_id", "client_event_id", "key", name="uq_metric_client_key"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("metric"))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    namespace: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    value_number: Mapped[float | None] = mapped_column(Float)
    value_string: Mapped[str | None] = mapped_column(Text)
    value_bool: Mapped[bool | None] = mapped_column(Boolean)
    point_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    point_event_name: Mapped[str | None] = mapped_column(String(128))
    point_step: Mapped[int | None] = mapped_column(Integer)
    point_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    point_coord_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    client_event_id: Mapped[str | None] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class RunNote(Base):
    __tablename__ = "run_notes"
    __table_args__ = (UniqueConstraint("run_id", "client_event_id", name="uq_note_client_event"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("note"))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str] = mapped_column(String(512), nullable=False)
    content_md: Mapped[str | None] = mapped_column(Text)
    structured_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    author_type: Mapped[str] = mapped_column(String(32), default="human", nullable=False)
    author_id: Mapped[str | None] = mapped_column(String(128))
    client_event_id: Mapped[str | None] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class RunActivityDailyStat(Base):
    __tablename__ = "run_activity_daily_stats"

    date: Mapped[str] = mapped_column(String(10), primary_key=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("artifact"))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    preview_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class CodeSnapshot(Base):
    __tablename__ = "code_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("snapshot"))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    repo_url: Mapped[str | None] = mapped_column(Text)
    git_commit: Mapped[str | None] = mapped_column(String(128), index=True)
    git_dirty: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    patch_artifact_id: Mapped[str | None] = mapped_column(ForeignKey("artifacts.id"))
    requirements_hash: Mapped[str | None] = mapped_column(String(128))
    container_image: Mapped[str | None] = mapped_column(String(256))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class DataSnapshot(Base):
    __tablename__ = "data_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("snapshot"))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    dataset_name: Mapped[str | None] = mapped_column(String(256), index=True)
    dataset_version: Mapped[str | None] = mapped_column(String(128))
    fingerprint: Mapped[str | None] = mapped_column(String(128), index=True)
    universe: Mapped[str | None] = mapped_column(String(256))
    benchmark: Mapped[str | None] = mapped_column(String(128))
    calendar: Mapped[str | None] = mapped_column(String(128))
    fee_model: Mapped[str | None] = mapped_column(String(256))
    slippage_model: Mapped[str | None] = mapped_column(String(256))
    time_range: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class EnvSnapshot(Base):
    __tablename__ = "env_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("snapshot"))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    python_version: Mapped[str | None] = mapped_column(String(128))
    platform: Mapped[str | None] = mapped_column(String(256))
    hostname: Mapped[str | None] = mapped_column(String(256))
    packages_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Sweep(TimestampMixin, Base):
    __tablename__ = "sweeps"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("sweep"))
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    search_space_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    objective_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)


class SweepRun(Base):
    __tablename__ = "sweep_runs"
    __table_args__ = (UniqueConstraint("sweep_id", "run_id", name="uq_sweep_run"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("sweep_run"))
    sweep_id: Mapped[str] = mapped_column(ForeignKey("sweeps.id"), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    coord_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    rank: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class CompareSet(Base):
    __tablename__ = "compare_sets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("compare_set"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    research_id: Mapped[str | None] = mapped_column(ForeignKey("researches.id"), index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    run_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    layout_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class SearchView(Base):
    __tablename__ = "search_views"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("search_view"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    filters_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
