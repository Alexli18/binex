"""Structured API error handling for Binex Web UI."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Structured error response returned by all API endpoints.

    The ``error`` field contains a human-readable message for backward
    compatibility with existing consumers.  The ``error_code`` field
    provides a stable, machine-readable identifier for programmatic
    error handling (e.g. ``"workflow_not_found"``).
    """

    error: str  # human-readable message (backward compat)
    error_code: str  # machine-readable code, e.g. "workflow_not_found"
    message: str  # same as error (explicit alias kept for OpenAPI docs)
    details: dict[str, Any] | None = None


class APIError(Exception):
    """Raise from any API endpoint to return a structured JSON error.

    Usage::

        raise APIError(404, "workflow_not_found", "Workflow 'x.yaml' not found")
        raise APIError(422, "validation_error", "Invalid spec", details={"field": "nodes"})
    """

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details

    def to_response_body(self) -> dict[str, Any]:
        """Serialize to the dict that will become the JSON response.

        ``error`` contains the human-readable message for backward
        compatibility.  ``error_code`` is the stable machine-readable
        identifier.
        """
        body: dict[str, Any] = {
            "error": self.message,
            "error_code": self.code,
            "message": self.message,
        }
        if self.details is not None:
            body["details"] = self.details
        return body
