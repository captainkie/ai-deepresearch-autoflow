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
    from app.services.run_service import RunService


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_config_service(request: Request) -> ConfigService:
    return request.app.state.config_service


def get_run_service(request: Request) -> "RunService":
    return request.app.state.run_service
