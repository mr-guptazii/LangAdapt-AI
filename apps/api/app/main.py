from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger, new_request_id, request_id_ctx
from app.core.rate_limit import get_redis_client
from app.database.session import get_db

configure_logging(settings.LOG_LEVEL)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app_startup", env=settings.ENV, llm_provider=settings.LLM_PROVIDER)
    yield
    logger.info("app_shutdown")


app = FastAPI(
    title=settings.APP_NAME,
    description="An AI language tutor that adapts to how you actually learn.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("x-request-id", new_request_id())
    token = request_id_ctx.set(rid)
    request.state.request_id = rid
    try:
        response = await call_next(request)
    finally:
        request_id_ctx.reset(token)
    response.headers["x-request-id"] = rid
    return response


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Baseline security headers (section 71). This is a JSON API with no
    cookie-based session (see SECURITY.md), so CSRF headers aren't applicable;
    these guard against MIME sniffing, clickjacking if the API is ever embedded,
    and (in production) enforce HTTPS on repeat visits."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


register_exception_handlers(app)
app.include_router(api_router)


@app.get("/health")
async def health():
    """Liveness probe: fast, no external dependencies. If this process can
    respond at all, it's alive — use /health/ready to check its dependencies."""
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.ENV, "llm_provider": settings.LLM_PROVIDER}


@app.get("/health/ready")
async def health_ready(db: AsyncSession = Depends(get_db)):
    """Readiness probe: actually checks the database and Redis, the two
    external dependencies this app cannot function without. Returns 503 (not
    just a body flag) when not ready, so orchestrators/load balancers can act
    on the status code alone."""
    db_ok = True
    try:
        await db.execute(select(1))
    except Exception:
        db_ok = False

    redis_ok = True
    try:
        client = get_redis_client()
        await client.ping()
    except Exception:
        redis_ok = False

    body = {"status": "ready" if (db_ok and redis_ok) else "not_ready", "database": db_ok, "redis": redis_ok}
    if not (db_ok and redis_ok):
        raise HTTPException(status_code=503, detail=body)
    return body
