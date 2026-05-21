from __future__ import annotations

import secrets
import time


PREFIXES = {
    "workspace": "wks",
    "project": "prj",
    "research": "rsr",
    "branch": "br",
    "run": "run",
    "event": "evt",
    "metric": "met",
    "note": "note",
    "artifact": "art",
    "snapshot": "snp",
    "sweep": "swp",
    "sweep_run": "swr",
    "compare_set": "cmp",
    "search_view": "svw",
    "idempotency": "idem",
}


def new_id(kind: str) -> str:
    prefix = PREFIXES.get(kind, kind[:4])
    timestamp = base36(int(time.time() * 1000))
    suffix = secrets.token_hex(5)
    return f"{prefix}_{timestamp}_{suffix}"


def base36(value: int) -> str:
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    if value == 0:
        return "0"
    result = ""
    while value:
        value, rem = divmod(value, 36)
        result = chars[rem] + result
    return result
