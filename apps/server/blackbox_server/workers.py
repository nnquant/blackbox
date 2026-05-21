from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol, TypeVar


T = TypeVar("T")


class WorkerBackend(Protocol):
    def submit(self, name: str, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        ...


@dataclass
class InlineWorker:
    """Small worker boundary for tasks that can later move to a queue backend."""

    def submit(self, name: str, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        del name
        return func(*args, **kwargs)


_worker: WorkerBackend = InlineWorker()


def get_worker() -> WorkerBackend:
    return _worker


def set_worker(worker: WorkerBackend) -> None:
    global _worker
    _worker = worker


def reset_worker() -> None:
    set_worker(InlineWorker())

