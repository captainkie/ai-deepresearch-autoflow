"""FastAPI dependency providers backed by ``request.app.state`` singletons.

The ``Database``, ``ConfigService``, and ``RunService`` are created once during
app startup (see ``main._startup``) and shared across requests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request

from app.db.database import Database
from app.services.config_service import ConfigService

if TYPE_CHECKING:
    from app.services.auth_service import AuthService
    from app.services.run_service import RunService
    from app.services.vault_service import VaultService
    from app.settings import AppSettings


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_app_settings(request: Request) -> "AppSettings":
    return request.app.state.settings


def get_config_service(request: Request) -> ConfigService:
    return request.app.state.config_service


def get_run_service(request: Request) -> "RunService":
    return request.app.state.run_service


def get_vault_service(request: Request) -> "VaultService":
    return request.app.state.vault_service


def get_auth_service(request: Request) -> "AuthService":
    return request.app.state.auth_service
