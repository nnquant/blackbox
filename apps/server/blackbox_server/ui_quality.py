"""Bounded cache for displayed quality hints; never used by write/compare gates."""
import hashlib
import json
import time
from collections import OrderedDict
from threading import RLock

from sqlalchemy import select
from .models import Artifact, RunMetric
from .settings import get_settings
from .storage import get_artifact_content_target

_results = OrderedDict()
_lock = RLock()


def display_quality(db, run, compute):
    artifacts = db.scalars(select(Artifact).where(Artifact.run_id == run.id).order_by(Artifact.id)).all()
    dependencies = [run.updated_at, run.status, run.summary_json, run.config_json, run.context_json]
    dependencies.extend(list(row) for row in db.execute(select(RunMetric.id, RunMetric.point_coord_json).where(RunMetric.run_id == run.id).order_by(RunMetric.id)))
    for artifact in artifacts:
        stamp = None
        try:
            target = get_artifact_content_target(get_settings(), artifact.storage_uri, artifact.mime_type)
            if target.path:
                stat = target.path.stat()
                stamp = (stat.st_mtime_ns, stat.st_size)
        except (OSError, ValueError):
            pass
        dependencies.append([artifact.id, artifact.sha256, artifact.metadata_json, artifact.preview_json, stamp])
    signature = hashlib.sha256(json.dumps(dependencies, default=str, sort_keys=True).encode()).hexdigest()
    key = (str(db.get_bind().url), run.id, signature)
    with _lock:
        entry = _results.get(key)
        if entry and time.monotonic() - entry[0] < 30:
            _results.move_to_end(key)
            return entry[1]
    # Different Runs must not queue behind another Run's file validation.
    result = compute()
    with _lock:
        _results[key] = (time.monotonic(), result)
        while len(_results) > 128:
            _results.popitem(last=False)
        return result
