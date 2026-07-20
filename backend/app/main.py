"""FastAPI application factory.

``create_app()`` is a *factory* (used with ``uvicorn --factory``). Startup opens
the SQLite database and builds the shared services onto ``app.state``; shutdown
closes them. The startup/shutdown steps are exposed as plain functions so tests
can drive them directly under ``httpx.ASGITransport`` (which does not run ASGI
lifespan events).
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.__about__ import APP_NAME, VERSION
from app.api import admin as admin_router
from app.api import config as config_router
from app.api import health as health_router
from app.api import runs as runs_router
from app.db.database import Database
from app.db.repositories import AuditRepo, CredentialRepo
from app.security.crypto import Vault
from app.security.keys import resolve_master_key
from app.services.config_service import ConfigService
from app.services.run_service import RunService
from app.services.vault_service import VaultService
from app.settings import AppSettings, get_settings


async def _startup(app: FastAPI, settings: AppSettings) -> None:
    db = Database(settings.db_path)
    await db.init()
    vault_service = VaultService(
        credentials=CredentialRepo(db),
        audit=AuditRepo(db),
        vault=Vault(resolve_master_key(settings.master_key, settings.app_env)),
    )
    config_service = ConfigService(db, settings, vault=vault_service)
    app.state.settings = settings
    app.state.db = db
    app.state.vault_service = vault_service
    app.state.config_service = config_service
    app.state.run_service = RunService(db, config_service, settings, vault=vault_service)


async def _shutdown(app: FastAPI) -> None:
    await app.state.run_service.aclose()
    await app.state.db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _startup(app, get_settings())
    try:
        yield
    finally:
        await _shutdown(app)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=APP_NAME, version=VERSION, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router.router)
    app.include_router(config_router.router)
    app.include_router(runs_router.router)
    app.include_router(admin_router.router)
    return app
