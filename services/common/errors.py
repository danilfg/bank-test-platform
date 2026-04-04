from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import Request
from fastapi.responses import JSONResponse


@dataclass
class ErrorBody:
    code: str
    message: str
    details: dict = field(default_factory=dict)


class DomainError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: dict | None = None):
        self.status_code = status_code
        self.body = ErrorBody(code=code, message=message, details=details or {})
        super().__init__(message)


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "")
    trace_id = request.headers.get("x-trace-id", "")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.body.code,
                "message": exc.body.message,
                "details": exc.body.details,
                "request_id": request_id,
                "trace_id": trace_id,
            }
        },
    )
