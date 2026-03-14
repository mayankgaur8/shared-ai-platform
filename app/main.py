"""
SAIB — Shared AI Interface Backend
FastAPI application entrypoint.

Startup: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""
import logging
import logging.config
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config.settings import get_settings
from app.logging_service.middleware import RequestLoggingMiddleware
from app.safety.middleware import SafetyMiddleware

# ── Routers ───────────────────────────────────────────────────────────────────
from app.auth.router import router as auth_router
from app.apps.router import router as apps_router
from app.users.router import router as users_router
from app.prompts.router import router as prompts_router
from app.models_registry.router import router as models_router
from app.orchestration.router import router as orchestration_router
from app.rag.router import router as rag_router
from app.memory.router import router as memory_router
from app.templates.router import router as templates_router
from app.analytics.router import router as analytics_router
from app.admin.router import router as admin_router
from app.ai_router.router import router as ai_router

settings = get_settings()

# ── Logging configuration ─────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("saib")


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup  service=%s  env=%s  debug=%s",
                settings.APP_NAME, settings.ENVIRONMENT, settings.DEBUG)

    # ── Optional: connect to DB / Redis only when URLs are non-default ────────
    # These are skipped in stub mode so the app boots even without infrastructure.
    if "localhost" not in settings.DATABASE_URL or settings.ENVIRONMENT != "production":
        try:
            from app.config.database import init_db
            await init_db()
            logger.info("startup  database=connected")
        except Exception as exc:
            logger.warning("startup  database=unavailable  reason=%s  (continuing in stub mode)", exc)

    try:
        from app.config.redis import init_redis
        await init_redis()
        logger.info("startup  redis=connected")
    except Exception as exc:
        logger.warning("startup  redis=unavailable  reason=%s  (continuing in stub mode)", exc)

    yield

    logger.info("shutdown")


# ── App factory ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Centralized AI Gateway — model routing, prompt registry, "
        "user memory, safety, and analytics for all apps."
    ),
    docs_url="/docs",       # always show docs (restrict in prod via reverse proxy if needed)
    redoc_url="/redoc",
    lifespan=lifespan,
    swagger_ui_parameters={"persistAuthorization": True},
)

# ── Middleware (outermost registered = outermost executed) ────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SafetyMiddleware)

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(auth_router,          prefix="/v1/auth",       tags=["auth"])
app.include_router(apps_router,          prefix="/v1/apps",        tags=["apps"])
app.include_router(users_router,         prefix="/v1/users",       tags=["users"])
app.include_router(prompts_router,       prefix="/v1/prompts",     tags=["prompts"])
app.include_router(models_router,        prefix="/v1/models",      tags=["models"])
app.include_router(orchestration_router, prefix="/v1",             tags=["orchestration"])
app.include_router(rag_router,           prefix="/v1",             tags=["rag"])
app.include_router(memory_router,        prefix="/v1/memory",      tags=["memory"])
app.include_router(templates_router,     prefix="/v1/templates",   tags=["templates"])
app.include_router(analytics_router,     prefix="/v1/analytics",   tags=["analytics"])
app.include_router(admin_router,         prefix="/v1/admin",       tags=["admin"])
app.include_router(ai_router,            prefix="/v1/ai",          tags=["ai-router"])


# ── Platform endpoints ────────────────────────────────────────────────────────
@app.get("/health", tags=["platform"])
async def health():
    """Liveness probe — always returns 200 if the process is running."""
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/ready", tags=["platform"])
async def ready():
    """Readiness probe — checks Ollama reachability."""
    import httpx
    ollama_ok = False
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            ollama_ok = r.status_code == 200
    except Exception:
        pass

    return {
        "status": "ready" if ollama_ok else "degraded",
        "ollama": "up" if ollama_ok else "unreachable",
        "ollama_url": settings.OLLAMA_BASE_URL,
    }


@app.get("/v1/workflows", tags=["orchestration"])
async def list_workflows():
    """Returns all registered workflow names."""
    from app.orchestration.router import WORKFLOW_PROMPTS
    return {"workflows": list(WORKFLOW_PROMPTS.keys())}


# ── Global exception handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception  path=%s  error=%s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "path": request.url.path},
    )
