"""Safe, stable errors for remote operations and MCP outputs."""

from __future__ import annotations


class OperationError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = False):
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(message)


def public_error(exc: Exception) -> dict[str, object]:
    if not isinstance(exc, OperationError):
        exc = OperationError("internal_error", "The operation failed unexpectedly")
    return {
        "success": False,
        "error": {"code": exc.code, "message": exc.message, "retryable": exc.retryable},
    }
