from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .settings import get_settings


class Base(DeclarativeBase):
    pass


def _connect_args(database_url: str) -> dict[str, object]:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def ensure_sqlite_parent(database_url: str) -> None:
    if not database_url.startswith("sqlite:///"):
        return
    path_part = database_url.removeprefix("sqlite:///")
    if path_part in {":memory:", ""}:
        return
    Path(path_part).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def _create_engine(database_url: str) -> Engine:
    ensure_sqlite_parent(database_url)
    return create_engine(database_url, connect_args=_connect_args(database_url))


settings = get_settings()
engine = _create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def configure_engine_from_env() -> Engine:
    global settings, engine, SessionLocal
    current_settings = get_settings()
    if current_settings.database_url == settings.database_url:
        return engine
    engine.dispose()
    settings = current_settings
    engine = _create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return engine


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
