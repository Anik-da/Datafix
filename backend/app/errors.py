"""Shared application exceptions for request validation and ingestion."""

from typing import Any


class InputProblem(Exception):
    """Expected client or dataset error with safe HTTP details."""

    def __init__(
        self, status: int, code: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.details = details or {}
