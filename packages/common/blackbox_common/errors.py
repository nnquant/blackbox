from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    validation_error = "VALIDATION_ERROR"
    not_found = "NOT_FOUND"
    conflict = "CONFLICT"
    state_error = "STATE_ERROR"
    auth_error = "AUTH_ERROR"
    storage_error = "STORAGE_ERROR"
    network_error = "NETWORK_ERROR"


class ApiError(Exception):
    def __init__(self, code: ErrorCode, message: str, hint: str | None = None, details: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.details = details

