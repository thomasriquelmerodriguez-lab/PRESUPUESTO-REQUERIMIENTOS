from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete, text

from app.api.deps import DbDep
from app.api.routers import audit, auth, backup, budgets, events, reports, requirements, users
from app.core.config import BASE_DIR, get_settings
from app.core.exceptions import AppError
from app.core.http import SecurityHeadersMiddleware
from app.core.logging import configure_logging
from app.core.security import utcnow
from app.db.base import Base, SessionLocal, engine
from app.db.models import ImportPreviewCache, SessionRecord
from app.seed import seed_database_with_lock

settings = get_settings()
configure_logging()
logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auto_create_schema:
        Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        db.execute(delete(SessionRecord).where(SessionRecord.absolute_expires_at <= utcnow()))
        db.execute(delete(ImportPreviewCache).where(ImportPreviewCache.expires_at <= utcnow()))
        db.commit()
        if settings.seed_on_startup:
            seed_database_with_lock(db)
    yield


app = FastAPI(
    title=settings.app_name,
    version="2.3.0",
    debug=settings.debug,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/openapi.json",
    lifespan=lifespan,
)
app.add_middleware(SecurityHeadersMiddleware)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")

app.include_router(auth.router, prefix="/api")
app.include_router(requirements.router, prefix="/api")
app.include_router(budgets.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(backup.router, prefix="/api")
app.include_router(users.router, prefix="/api")


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    fields = []
    for error in exc.errors()[:20]:
        location = ".".join(str(part) for part in error.get("loc", []) if part not in {"body", "query"})
        fields.append({"field": location, "message": error.get("msg", "Dato inválido")})
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Revise los datos ingresados.",
                "fields": fields,
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled application error")
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": "Ocurrió un error inesperado."}},
    )


@app.get("/health/live")
def liveness():
    return {"status": "ok"}


@app.get("/health/ready")
def readiness(db: DbDep):
    db.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.get("/health")
def health(db: DbDep):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/{path:path}")
def frontend(request: Request, path: str = ""):
    if path.startswith("api/") or path.startswith("static/"):
        return JSONResponse(status_code=404, content={"error": {"code": "not_found", "message": "No encontrado"}})
    return templates.TemplateResponse(request=request, name="index.html", context={"app_name": settings.app_name})
