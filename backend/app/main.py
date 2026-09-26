import sys

# Ensure stdout and stderr use utf-8 on Windows to prevent 'charmap' codec errors
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.api.router import router as api_router
from app.core.config import get_settings
from app.core.ip_blocklist import is_blocked, record_strike
from app.core.rate_limit import limiter
from app.db.init_db import create_database_tables
from app.services.document_events import PostgresEventBridge

settings = get_settings()
_is_postgres = settings.database_url.startswith("postgresql")
# Local dev against SQLite has no migrations to run and no Postgres
# LISTEN/NOTIFY channel to bridge -- auto-create tables instead, and skip
# the bridge entirely.
settings.create_tables_on_startup = not _is_postgres

event_bridge = PostgresEventBridge(settings.database_url) if _is_postgres else None


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if settings.create_tables_on_startup:
        await create_database_tables()
    if event_bridge is not None:
        await event_bridge.start()
    yield
    if event_bridge is not None:
        await event_bridge.stop()


_DESCRIPTION = """
## GenSmile Documents API

Sign-in and patient documents for GenSmile doctors and their staff: create and
edit patient documents, send a fill-in link to the patient, and share a
view-only copy with another doctor.

### Authentication

Most endpoints require a **Bearer JWT** access token. Obtain one via `POST /api/v1/auth/login`
and pass it in the `Authorization` header (`Authorization: Bearer <access_token>`).
Use `POST /api/v1/auth/refresh` with the refresh token to get a new pair without logging in again.

The patient fill-in (`/patient-document/{fill_token}`) and doctor-to-doctor share
(`/doctor-to-doctor/documents/{share_token}`) endpoints need no login -- the token in the link is the key.

### Error format

```json
{ "detail": "Human-readable error message." }
```
"""

_TAGS_METADATA = [
    {"name": "auth", "description": "Login, token refresh, logout, password reset, staff invitation acceptance, and `/me`."},
    {"name": "patient-documents", "description": "Patient documents, attachments, the patient fill-in link, and doctor-to-doctor sharing."},
    {"name": "form-config", "description": "The doctor's default document form layout and logo."},
    {"name": "doctors", "description": "The doctor's patient list (for picking an existing patient)."},
    {"name": "staff", "description": "A staff user's own record and permissions."},
    {"name": "health", "description": "Service health check -- returns the current version and environment."},
]

app = FastAPI(
    title=settings.project_name,
    version=settings.version,
    description=_DESCRIPTION,
    openapi_tags=_TAGS_METADATA,
    contact={"name": "GenSmile Engineering"},
    lifespan=lifespan,
    swagger_ui_parameters={
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "filter": True,
        "docExpansion": "none",
    },
)

app.state.limiter = limiter


async def _rate_limit_exceeded_with_strike(request: Request, exc: RateLimitExceeded):
    # Escalation on top of the per-route rate limit itself: repeatedly
    # tripping ANY rate limit (login, forgot-password, embed-generate, ...)
    # counts toward an outright IP block, not just this one 429.
    record_strike(get_remote_address(request))
    return _rate_limit_exceeded_handler(request, exc)


app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_with_strike)  # type: ignore[arg-type]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://www.gensmile.ai",
        "https://gensmile.ai",
        *[o for o in settings.allowed_origins if o != "*"],
    ],
    allow_origin_regex=r"https://.*\.gensmile\.ai|http://localhost:\d+|http://127\.0\.0\.1:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enforces limiter.default_limits (rate_limit_default, see rate_limit.py) on
# every route that doesn't set its own @limiter.limit(...) -- the decorator
# alone (used by login/forgot-password/embed-generate/ai-process) works
# without this middleware, but default_limits does not.
app.add_middleware(SlowAPIMiddleware)


@app.middleware("http")
async def block_suspicious_ips(request: Request, call_next):
    """Reject blocked IPs before they reach any route -- see
    app.core.ip_blocklist for how an IP ends up blocked (repeated
    rate-limit violations, repeated failed logins, or an admin's manual
    block)."""
    ip = get_remote_address(request)
    if is_blocked(ip):
        return JSONResponse(
            status_code=403,
            content={"detail": "Access temporarily blocked due to suspicious activity. Try again later."},
        )
    return await call_next(request)

# Serve uploaded files from local disk only when S3 is disabled
if not settings.s3_enabled:
    app.mount("/uploads", StaticFiles(directory=settings.uploads_directory), name="uploads")

app.include_router(api_router)
