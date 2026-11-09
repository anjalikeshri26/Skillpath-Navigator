import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import models  # noqa: F401  (registers tables)
from .ai.groq_client import AIError
from .core.config import settings, signing_key
from .core.errors import ServiceError
from .routers import admin, assistant, auth, dashboard, health, interview, notes, profile, quiz, resume, roadmap, study
from .seed import seed

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("skillpath.http")
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


@asynccontextmanager
async def lifespan(_: FastAPI):
    signing_key()  # fail fast on a missing production secret
    seed()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="2.1.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        """Tag every request with an id and log one line per API call. Bodies and tokens are never logged."""
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        started = time.perf_counter()
        response = await call_next(request)
        if request.url.path.startswith("/api"):
            log.info("%s %s -> %s in %.0f ms [%s]", request.method, request.url.path, response.status_code,
                     (time.perf_counter() - started) * 1000, request_id)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    @app.exception_handler(ServiceError)
    async def service_error(_: Request, exc: ServiceError):
        return JSONResponse({"detail": exc.message}, status_code=exc.status_code)

    @app.exception_handler(AIError)
    async def ai_error(_: Request, exc: AIError):
        return JSONResponse({"detail": str(exc)}, status_code=exc.status_code)

    for module in (health, auth, profile, dashboard, quiz, roadmap, resume, study, notes, interview, assistant, admin):
        app.include_router(module.router)

    if settings.serve_frontend and FRONTEND_DIR.is_dir():
        app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")  # must be mounted last
    return app


app = create_app()
