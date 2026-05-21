from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Engine, JSON, inspect, text
from sqlalchemy.schema import CreateColumn

from .db import Base


CURRENT_SCHEMA_VERSION = 5
MIGRATION_TABLE = "schema_migrations"


def migrate_database(engine: Engine) -> dict[str, Any]:
    """Apply lightweight in-process migrations for local deployments.

    This is intentionally small: it handles first-run schema creation and
    additive table/column changes. It gives us a stable upgrade path for the
    default SQLite deployment without making every startup depend on Alembic.
    """
    load_model_metadata()
    before = schema_status(engine)
    Base.metadata.create_all(bind=engine)
    ensure_migration_table(engine)
    added_columns = ensure_missing_columns(engine)
    ensure_default_workspace(engine)
    applied = stamp_current_version(engine)
    after = schema_status(engine)
    return {
        "before": before,
        "after": after,
        "added_columns": added_columns,
        "applied": applied,
    }


def schema_status(engine: Engine) -> dict[str, Any]:
    load_model_metadata()
    inspector = inspect(engine)
    tables = sorted(inspector.get_table_names())
    version = 0
    if MIGRATION_TABLE in tables:
        with engine.begin() as conn:
            value = conn.execute(text(f"select max(version) from {MIGRATION_TABLE}")).scalar()
            version = int(value or 0)
    missing_tables = sorted(table.name for table in Base.metadata.sorted_tables if table.name not in tables)
    missing_columns: dict[str, list[str]] = {}
    for table in Base.metadata.sorted_tables:
        if table.name not in tables:
            continue
        existing = {column["name"] for column in inspector.get_columns(table.name)}
        missing = [column.name for column in table.columns if column.name not in existing]
        if missing:
            missing_columns[table.name] = missing
    return {
        "current_version": CURRENT_SCHEMA_VERSION,
        "database_version": version,
        "tables": tables,
        "missing_tables": missing_tables,
        "missing_columns": missing_columns,
        "needs_migration": bool(missing_tables or missing_columns or version < CURRENT_SCHEMA_VERSION),
    }


def ensure_migration_table(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                f"""
                create table if not exists {MIGRATION_TABLE} (
                    version integer primary key,
                    name varchar(128) not null,
                    applied_at varchar(64) not null
                )
                """
            )
        )


def stamp_current_version(engine: Engine) -> bool:
    with engine.begin() as conn:
        existing = conn.execute(
            text(f"select version from {MIGRATION_TABLE} where version = :version"),
            {"version": CURRENT_SCHEMA_VERSION},
        ).scalar()
        if existing:
            return False
        conn.execute(
            text(
                f"""
                insert into {MIGRATION_TABLE} (version, name, applied_at)
                values (:version, :name, :applied_at)
                """
            ),
            {
                "version": CURRENT_SCHEMA_VERSION,
                "name": "baseline_schema",
                "applied_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return True


def ensure_missing_columns(engine: Engine) -> list[dict[str, str]]:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    added: list[dict[str, str]] = []
    for table in Base.metadata.sorted_tables:
        if table.name not in tables:
            continue
        existing = {column["name"] for column in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing:
                continue
            ddl = compile_add_column(engine, table.name, column)
            with engine.begin() as conn:
                conn.execute(text(ddl))
            added.append({"table": table.name, "column": column.name})
    return added


def ensure_default_workspace(engine: Engine) -> None:
    inspector = inspect(engine)
    if "workspaces" not in inspector.get_table_names():
        return
    with engine.begin() as conn:
        existing = conn.execute(text("select id from workspaces where id = 'local'")).scalar()
        if existing:
            return
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            text(
                """
                insert into workspaces (id, key, title, description, roles_json, created_at, updated_at)
                values ('local', 'local', 'Local Workspace', null, '{}', :created_at, :updated_at)
                """
            ),
            {"created_at": now, "updated_at": now},
        )


def compile_add_column(engine: Engine, table_name: str, column: Any) -> str:
    compiled = str(CreateColumn(column).compile(dialect=engine.dialect))
    default_clause = sqlite_default_clause(engine, column)
    if default_clause and " DEFAULT " not in compiled.upper():
        compiled = f"{compiled} DEFAULT {default_clause}"
    return f"alter table {table_name} add column {compiled}"


def sqlite_default_clause(engine: Engine, column: Any) -> str | None:
    if engine.dialect.name != "sqlite" or column.nullable:
        return None
    if column.default is None:
        return None
    default_arg = getattr(column.default, "arg", None)
    if callable(default_arg):
        if isinstance(column.type, JSON):
            try:
                value = default_arg()
            except TypeError:
                try:
                    value = default_arg(None)
                except TypeError:
                    value = None
            if value == []:
                return "'[]'"
            if value == {}:
                return "'{}'"
        if default_arg is list:
            return "'[]'"
        if default_arg is dict:
            return "'{}'"
        if isinstance(column.type, DateTime):
            return "'1970-01-01 00:00:00'"
        return None
    if isinstance(column.type, JSON):
        if default_arg == []:
            return "'[]'"
        if default_arg == {}:
            return "'{}'"
    if isinstance(default_arg, str):
        escaped = default_arg.replace("'", "''")
        return f"'{escaped}'"
    if isinstance(default_arg, bool):
        return "1" if default_arg else "0"
    if default_arg is not None:
        return str(default_arg)
    return None


def load_model_metadata() -> None:
    from . import models  # noqa: F401
