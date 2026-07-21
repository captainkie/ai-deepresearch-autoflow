"""FastAPI application factory.

``create_app()`` is a *factory* (used with ``uvicorn --factory``). Startup opens
the SQLite database and builds the shared services onto ``app.state``; shutdown
closes them. The startup/shutdown steps are exposed as plain functions so tests
can drive them directly under ``httpx.ASGITransport`` (which does not run ASGI
lifespan events).
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.__about__ import APP_NAME, VERSION
from app.api import admin as admin_router
from app.api import auth as auth_router
from app.api import config as config_router
from app.api import health as health_router
from app.api import runs as runs_router
from app.api import setup as setup_router
from app.db.database import Database
from app.db.repositories import AuditRepo, CredentialRepo, RefreshTokenRepo, UserRepo
from app.security.crypto import Vault
from app.security.keys import resolve_jwt_secret, resolve_master_key
from app.services.auth_service import AuthService
from app.services.config_service import ConfigService
from app.services.oauth_service import GoogleOAuthService
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
    auth_service = AuthService(
        users=UserRepo(db),
        refresh_tokens=RefreshTokenRepo(db),
        jwt_secret=resolve_jwt_secret(settings.jwt_secret, settings.app_env),
    )
    config_service = ConfigService(db, settings, vault=vault_service)

    oauth_http: httpx.AsyncClient | None = None
    oauth_service: GoogleOAuthService | None = None
    if settings.google_client_id and settings.google_client_secret and settings.google_redirect_uri:
        oauth_http = httpx.AsyncClient(timeout=15.0)
        oauth_service = GoogleOAuthService(
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            redirect_uri=settings.google_redirect_uri,
            http=oauth_http,
        )

    app.state.settings = settings
    app.state.db = db
    app.state.vault_service = vault_service
    app.state.auth_service = auth_service
    app.state.oauth_http = oauth_http
    app.state.oauth_service = oauth_service
    app.state.config_service = config_service
    app.state.run_service = RunService(db, config_service, settings, vault=vault_service)

    await _seed_demo_admin(db, auth_service, settings)


async def _seed_demo_admin(db: Database, auth_service: AuthService, settings: AppSettings) -> None:
    """Seed a superadmin on an ephemeral-DB demo so it isn't stuck on /setup after
    a restart. No-op unless both demo-admin env vars are set and the DB is empty."""
    if not (settings.demo_admin_email and settings.demo_admin_password):
        return
    if await UserRepo(db).list():
        return
    await auth_service.register(
        email=settings.demo_admin_email,
        name="Demo Admin",
        password=settings.demo_admin_password,
        role="superadmin",
    )


async def _shutdown(app: FastAPI) -> None:
    await app.state.run_service.aclose()
    if getattr(app.state, "oauth_http", None) is not None:
        await app.state.oauth_http.aclose()
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
    app.include_router(setup_router.router)
    app.include_router(auth_router.router)
    app.include_router(config_router.router)
    app.include_router(runs_router.router)
    app.include_router(admin_router.router)
    return app
