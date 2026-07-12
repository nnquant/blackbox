from .enums import ArtifactKind, BranchStatus, EventType, NoteKind, PointKind, RunStatus
from .errors import ApiError, ErrorCode
from .ids import new_id

__all__ = [
    "ApiError",
    "ApiResponse",
    "ArtifactKind",
    "BranchStatus",
    "ErrorCode",
    "EventType",
    "NoteKind",
    "PointKind",
    "RunStatus",
    "compute_performance_summary",
    "new_id",
    "performance_metadata",
    "validate_metric_upload",
    "validate_run_detail",
    "validate_series_upload",
]


def __getattr__(name: str):
    if name == "ApiResponse":
        from .schemas import ApiResponse

        return ApiResponse
    if name == "validate_run_detail":
        from .validation import validate_run_detail

        return validate_run_detail
    if name == "validate_series_upload":
        from .validation import validate_series_upload

        return validate_series_upload
    if name == "validate_metric_upload":
        from .validation import validate_metric_upload

        return validate_metric_upload
    if name in {"compute_performance_summary", "performance_metadata"}:
        from .performance import compute_performance_summary, performance_metadata

        return {
            "compute_performance_summary": compute_performance_summary,
            "performance_metadata": performance_metadata,
        }[name]
    raise AttributeError(name)
