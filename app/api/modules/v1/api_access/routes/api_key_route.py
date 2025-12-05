from typing import List
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.api_access.enums.api_key_scope import Scopes
from app.api.modules.v1.api_access.schemas.api_access_schema import (
    APIKeyCreateSchema,
    APIKeyOutSchema,
    PaginatedAPIKeys,
    ScopeOut,
)
from app.api.modules.v1.api_access.service.api_key_crud import APIKeyCRUD
from app.api.modules.v1.api_access.service.api_key_service import APIKeyService
from app.api.utils.pagination import calculate_pagination

router = APIRouter(prefix="/organization/{organization_id}/api-keys", tags=["API Keys"])

crud = APIKeyCRUD()
service = APIKeyService(crud)


@router.post("/", response_model=APIKeyOutSchema)
async def create_api_key(
    organization_id: UUID,
    api_key_in: APIKeyCreateSchema,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user_permissions: dict = Depends(get_current_user),
):
    if not service.can_generate_key(current_user_permissions):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    if api_key_in.organization_id != organization_id:
        raise HTTPException(status_code=400, detail="Organization mismatch")

    requested_scopes = api_key_in.scope.split(",")
    service.validate_scope(requested_scopes)

    api_key_obj, raw_key = await service.generate_and_hash_api_key(
        db=db,
        key_name=api_key_in.key_name,
        organization_id=organization_id,
        user_id=api_key_in.user_id,
        receiver_email=api_key_in.receiver_email,
        generated_by=api_key_in.generated_by,
        scopes=requested_scopes,
        expires_at=api_key_in.expires_at,
    )

    if api_key_in.receiver_email:
        background_tasks.add_task(
            service.send_api_key_onboarding_email,
            db,
            api_key_obj,
            24,
        )

    return APIKeyOutSchema(
        key_name=api_key_obj.key_name,
        organization_name=api_key_obj.organization.name,
        user_name=api_key_obj.user.name if api_key_obj.user else None,
        receiver_email=api_key_obj.receiver_email,
        hashed_key=api_key_obj.hashed_key,
        scope=api_key_obj.scope,
        generated_by=(api_key_obj.generated_by_user.name if api_key_obj.generated_by_user else ""),
        is_active=api_key_obj.is_active,
        created_at=api_key_obj.created_at,
        expires_at=api_key_obj.expires_at,
        last_used_at=api_key_obj.last_used_at,
        rotation_enabled=getattr(api_key_obj, "rotation_enabled", False),
        rotation_interval_days=getattr(api_key_obj, "rotation_interval_days", None),
        last_rotated_at=getattr(api_key_obj, "last_rotated_at", None),
    )


@router.get("/", response_model=List[APIKeyOutSchema])
async def list_api_keys(
    organization_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user_permissions: dict = Depends(get_current_user),
):
    if not service.can_generate_key(current_user_permissions):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    total_keys = await crud.count_keys_by_org(db, organization_id)
    pagination = calculate_pagination(total_keys, page, limit)

    api_keys = await crud.get_keys_by_org_paginated(
        db, organization_id, offset=(page - 1) * limit, limit=limit
    )

    results = [
        APIKeyOutSchema(
            key_name=k.key_name,
            organization_name=k.organization.name,
            user_name=k.user.name if k.user else None,
            receiver_email=k.receiver_email,
            hashed_key=k.hashed_key,
            scope=k.scope,
            generated_by=(k.generated_by_user.name if k.generated_by_user else ""),
            is_active=k.is_active,
            created_at=k.created_at,
            expires_at=k.expires_at,
            last_used_at=k.last_used_at,
            rotation_enabled=getattr(k, "rotation_enabled", False),
            rotation_interval_days=getattr(k, "rotation_interval_days", None),
            last_rotated_at=getattr(k, "last_rotated_at", None),
        )
        for k in api_keys
    ]

    return PaginatedAPIKeys(items=results, pagination=pagination)


@router.get("/{api_key_id}", response_model=APIKeyOutSchema)
async def get_api_key(
    organization_id: UUID,
    api_key_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user_permissions: dict = Depends(get_current_user),
):
    if not service.can_generate_key(current_user_permissions):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    api_key = await crud.get_key_by_id(db, api_key_id)
    if not api_key or api_key.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="API key not found")

    return APIKeyOutSchema(
        key_name=api_key.key_name,
        organization_name=api_key.organization.name,
        user_name=api_key.user.name if api_key.user else None,
        receiver_email=api_key.receiver_email,
        hashed_key=api_key.hashed_key,
        scope=api_key.scope,
        generated_by=(api_key.generated_by_user.name if api_key.generated_by_user else ""),
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
        rotation_enabled=getattr(api_key, "rotation_enabled", False),
        rotation_interval_days=getattr(api_key, "rotation_interval_days", None),
        last_rotated_at=getattr(api_key, "last_rotated_at", None),
    )


@router.patch("/{api_key_id}", response_model=APIKeyOutSchema)
async def update_api_key(
    organization_id: UUID,
    api_key_id: UUID,
    updates: dict,
    db: AsyncSession = Depends(get_db),
    current_user_permissions: dict = Depends(get_current_user),
):
    if not service.can_generate_key(current_user_permissions):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    api_key = await crud.get_key_by_id(db, api_key_id)
    if not api_key or api_key.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="API key not found")

    updated_key = await crud.update_key(db, api_key_id, **updates)
    return updated_key


@router.delete("/{api_key_id}", status_code=204)
async def delete_api_key(
    organization_id: UUID,
    api_key_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user_permissions: dict = Depends(get_current_user),
):
    if not service.can_generate_key(current_user_permissions):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    api_key = await crud.get_key_by_id(db, api_key_id)
    if not api_key or api_key.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="API key not found")

    await crud.delete_key(db, api_key_id)
    return {"detail": "API key revoked"}


@router.post("/{api_key_id}/rotate", response_model=str)
async def rotate_api_key(
    organization_id: UUID,
    api_key_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user_permissions: dict = Depends(get_current_user),
):
    if not service.can_generate_key(current_user_permissions):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    api_key = await crud.get_key_by_id(db, api_key_id)
    if not api_key or api_key.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="API key not found")

    new_key = await service.api_key_rotation(db, api_key_id)
    return new_key


class RotationToggleSchema(BaseModel):
    rotation_enabled: bool
    rotation_interval_days: int | None = None


@router.patch("/{api_key_id}/rotation", response_model=APIKeyOutSchema)
async def set_rotation(
    organization_id: UUID,
    api_key_id: UUID,
    payload: RotationToggleSchema,
    db: AsyncSession = Depends(get_db),
    current_user_permissions: dict = Depends(get_current_user),
):
    if not service.can_generate_key(current_user_permissions):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    api_key = await crud.get_key_by_id(db, api_key_id)
    if not api_key or api_key.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="API key not found")

    updates = {
        "rotation_enabled": payload.rotation_enabled,
        "rotation_interval_days": payload.rotation_interval_days,
    }

    updated = await crud.update_key(db, api_key_id, **updates)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update API key rotation settings")

    return APIKeyOutSchema(
        key_name=updated.key_name,
        organization_name=updated.organization.name,
        user_name=updated.user.name if updated.user else None,
        receiver_email=updated.receiver_email,
        hashed_key=updated.hashed_key,
        scope=updated.scope,
        generated_by=(updated.generated_by_user.name if updated.generated_by_user else ""),
        is_active=updated.is_active,
        created_at=updated.created_at,
        expires_at=updated.expires_at,
        last_used_at=updated.last_used_at,
        rotation_enabled=getattr(updated, "rotation_enabled", False),
        rotation_interval_days=getattr(updated, "rotation_interval_days", None),
        last_rotated_at=getattr(updated, "last_rotated_at", None),
    )


@router.get("/scopes", response_model=List[ScopeOut])
async def get_api_key_scopes(
    organization_id: UUID,
    current_user_permissions: dict = Depends(get_current_user),
):
    """Return available API key scopes for the UI dropdown."""
    if not service.can_generate_key(current_user_permissions):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    def friendly_label(value: str) -> str:
        if value == "*":
            return "All"
        parts = value.split(":")
        if len(parts) == 2:
            action, resource = parts
            return f"{action.replace('_', ' ').title()} {resource.replace('_', ' ').title()}"
        return value

    results = [ScopeOut(value=s.value, label=friendly_label(s.value)) for s in Scopes]

    return results
