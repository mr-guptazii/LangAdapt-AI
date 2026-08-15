import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


def _error_body(code: str, message: str, request_id: str) -> dict:
    return {"success": False, "error": {"code": code, "message": message}, "request_id": request_id}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        request_id = getattr(request.state, "request_id", uuid.uuid4().hex[:16])
        code = getattr(exc, "error_code", None) or f"HTTP_{exc.status_code}"
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(code, exc.detail if isinstance(exc.detail, str) else "Request failed", request_id),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", uuid.uuid4().hex[:16])
        return JSONResponse(
            status_code=422,
            content=_error_body("VALIDATION_ERROR", "One or more fields are invalid.", request_id),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", uuid.uuid4().hex[:16])
        logger.error("unhandled_exception", error=str(exc), path=str(request.url), request_id=request_id)
        return JSONResponse(
            status_code=500,
            content=_error_body("INTERNAL_ERROR", "An unexpected error occurred.", request_id),
        )
