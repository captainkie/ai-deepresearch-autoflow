"""Templates + runtime provider config endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api import API_V1
from app.api.deps import forbid_in_demo, get_config_service
from app.api.schemas_api import (
    ConfigResponse,
    ConfigUpdate,
    EntityFieldOut,
    TemplateOut,
    TemplatesResponse,
)
from app.prompts.templates import TEMPLATES
from app.security.rbac import get_current_user, require_admin
from app.services.config_service import ConfigService

router = APIRouter(prefix=API_V1, tags=["config"])


@router.get("/templates")
async def list_templates() -> TemplatesResponse:
    return TemplatesResponse(
        templates=[
            TemplateOut(
                id=t.id,
                name=t.name,
                description=t.description,
                audience=t.audience,
                entity_mode=t.entity_mode,
                entity_schema=[
                    EntityFieldOut(key=f.key, label=f.label, type=f.type) for f in t.entity_schema
                ],
                verification_level=t.verification_level,
            )
            for t in TEMPLATES.values()
        ]
    )


@router.get("/config", dependencies=[Depends(get_current_user)])
async def get_config(svc: ConfigService = Depends(get_config_service)) -> ConfigResponse:
    return ConfigResponse(**await svc.current())


@router.post("/config", dependencies=[Depends(require_admin), Depends(forbid_in_demo)])
async def update_config(
    patch: ConfigUpdate, svc: ConfigService = Depends(get_config_service)
) -> ConfigResponse:
    return ConfigResponse(**await svc.update(patch.model_dump(exclude_none=True)))
