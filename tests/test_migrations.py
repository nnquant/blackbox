from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, inspect, text


def test_migrate_adds_missing_columns_and_stamps_version(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                create table projects (
                    id varchar(64) primary key,
                    key varchar(128) not null unique,
                    title varchar(256) not null,
                    description text,
                    tags json not null,
                    created_at datetime not null,
                    updated_at datetime not null
                )
                """
            )
        )
        conn.execute(
            text(
                """
                insert into projects (id, key, title, description, tags, created_at, updated_at)
                values ('prj_legacy', 'legacy', 'Legacy', null, '[]', '2026-01-01 00:00:00', '2026-01-01 00:00:00')
                """
            )
        )

    from blackbox_server.migrations import CURRENT_SCHEMA_VERSION, migrate_database, schema_status

    before = schema_status(engine)
    assert before["needs_migration"]
    assert "workspaces" in before["missing_tables"]
    assert before["missing_columns"]["projects"] == ["workspace_id", "retention_policy_json"]

    result = migrate_database(engine)
    assert result["after"]["database_version"] == CURRENT_SCHEMA_VERSION
    assert result["after"]["missing_columns"] == {}
    assert {"table": "projects", "column": "workspace_id"} in result["added_columns"]
    assert {"table": "projects", "column": "retention_policy_json"} in result["added_columns"]

    columns = {column["name"] for column in inspect(engine).get_columns("projects")}
    assert "workspace_id" in columns
    assert "retention_policy_json" in columns
    with engine.begin() as conn:
        workspace_id = conn.execute(text("select workspace_id from projects where id = 'prj_legacy'")).scalar_one()
        retention_policy = conn.execute(text("select retention_policy_json from projects where id = 'prj_legacy'")).scalar_one()
        local_workspace = conn.execute(text("select key from workspaces where id = 'local'")).scalar_one()
        version = conn.execute(text("select max(version) from schema_migrations")).scalar_one()
    assert workspace_id == "local"
    assert retention_policy == "{}"
    assert local_workspace == "local"
    assert version == CURRENT_SCHEMA_VERSION

    second = migrate_database(engine)
    assert second["added_columns"] == []
    assert second["applied"] is False
