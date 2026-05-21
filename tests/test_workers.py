from __future__ import annotations

from typing import Any, Callable


def test_artifact_preview_uses_worker_boundary() -> None:
    from blackbox_server.main import build_artifact_preview
    from blackbox_server.workers import reset_worker, set_worker

    calls: list[dict[str, Any]] = []

    class RecordingWorker:
        def submit(self, name: str, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
            calls.append({"name": name, "args": args})
            return func(*args, **kwargs)

    set_worker(RecordingWorker())
    try:
        preview = build_artifact_preview("trades.csv", "text/csv", b"date,pnl\n2026-01-01,1.5\n")
    finally:
        reset_worker()

    assert calls == [{"name": "artifact.preview", "args": ("trades.csv", "text/csv", b"date,pnl\n2026-01-01,1.5\n")}]
    assert preview["format"] == "csv"
    assert preview["columns"] == ["date", "pnl"]

