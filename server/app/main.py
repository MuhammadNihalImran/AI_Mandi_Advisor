import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import get_settings
from app.logging_config import setup_logging
from app.db.database import engine, Base, SessionLocal
from app.db.models import MandiPrice
from app.rate_limiter import limiter
from app.routers import history, predict, advice, weather, stats as stats_router
from app.services.stats_collector import record_request

settings = get_settings()

# ---------------------------------------------------------------------------
# Structured JSON logging – must be configured before any other logging
# ---------------------------------------------------------------------------
setup_logging(debug=settings.debug)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifespan – startup: create tables + auto-seed if empty
# ---------------------------------------------------------------------------
def _auto_seed() -> None:
    """
    Seed mandi_prices from CSV if the table is empty.
    Idempotent: skips when rows already exist.
    """
    from app.db.seed import seed as run_seed

    db = SessionLocal()
    try:
        count = db.query(MandiPrice).count()
    finally:
        db.close()

    if count > 0:
        logger.info("auto_seed_skipped", extra={"row_count": count})
        return

    logger.info("auto_seed_started")
    try:
        run_seed()
        logger.info("auto_seed_completed")
    except FileNotFoundError as exc:
        logger.critical("auto_seed_failed: %s", exc)
    except Exception:
        logger.exception("auto_seed_failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all tables
    Base.metadata.create_all(bind=engine)
    # Auto-seed if mandi_prices is empty
    _auto_seed()
    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware (added in reverse execution order – last added runs first)
# ---------------------------------------------------------------------------

# 1. CORS (innermost – runs closest to the route handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Trusted host – reject requests with unrecognised Host headers
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"],  # tighten in production, e.g. ["mandi.example.com"]
)

# 3. Rate limiting (slowapi)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


# 4. Security headers (outermost – first to touch the response)
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


# 5. Request logging + stats collection (outermost – wraps everything)
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start = time.perf_counter()

    response = await call_next(request)

    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    is_error = response.status_code >= 400

    # Record to in-memory stats
    record_request(duration_ms=duration_ms, is_error=is_error)

    # Structured JSON log line
    logger.info(
        "request_completed",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "client_ip": request.client.host if request.client else None,
        },
    )

    return response


# ---------------------------------------------------------------------------
# Rate-limit exception handler
# ---------------------------------------------------------------------------
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    logger.warning(
        "rate_limit_exceeded",
        extra={
            "method": request.method,
            "path": request.url.path,
            "detail": exc.detail,
        },
    )
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "detail": f"Bohot zyada requests ho gaye. "
                      f"{exc.detail}. Thodi der baad try karein.",
        },
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(history.router)
app.include_router(predict.router)
app.include_router(advice.router)
app.include_router(weather.router)
app.include_router(stats_router.router)


# ---------------------------------------------------------------------------
# Global exception handler – clean JSON, no stack trace in production
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(
        "unhandled_exception",
        extra={
            "method": request.method,
            "path": request.url.path,
            "error_type": type(exc).__name__,
        },
    )

    if settings.debug:
        detail = {"message": str(exc), "type": type(exc).__name__}
    else:
        detail = {"message": "An internal server error occurred."}

    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "detail": detail},
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/")
async def root():
    return {
        "app": settings.app_name,
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
