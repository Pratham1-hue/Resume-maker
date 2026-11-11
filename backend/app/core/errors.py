from datetime import datetime, timezone

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard error response format."""
    detail: str
    error_code: str = "internal_error"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def error_404(detail: str = "Not found") -> dict:
    return {"status_code": 404, "content": {"error": detail}}


def error_400(detail: str = "Bad request") -> dict:
    return {"status_code": 400, "content": {"error": detail}}


def error_500(detail: str = "Internal error") -> dict:
    return {"status_code": 500, "content": {"error": detail}}
