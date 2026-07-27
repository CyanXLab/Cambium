"""
API Provider Management endpoints.

Provides CRUD for API providers + task assignment.

Main API (id="main"):
  - Cannot be deleted, but can be edited
  - Handles core functions: chat, reasoning, hard tasks
  - Default for all functions unless explicitly assigned

Other providers:
  - Add/delete freely
  - Used for token-saving tasks, simple decisions, etc.
  - Each function selects a provider via dropdown (default = main)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict

from app.config import DB_PATH
from app.logging_config import get_logger
from app.exceptions import NotFoundError, ValidationError
from app import api_providers

log = get_logger(__name__)
router = APIRouter(prefix="/api/v2/providers", tags=["api-providers"])


class ProviderCreate(BaseModel):
    name: str
    base_url: str
    api_key: str
    models: List[str] = []


class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    models: Optional[List[str]] = None


class AssignmentUpdate(BaseModel):
    task: str
    provider_id: str  # "main" or a provider ID


@router.get("")
async def list_providers():
    """List all API providers.

    Main API is always first, with is_main=True.
    Other providers follow in creation order.
    """
    providers = api_providers.get_providers(DB_PATH)
    # Don't expose api_key in list view (mask it)
    for p in providers:
        if p.get("api_key"):
            p["api_key_masked"] = p["api_key"][:8] + "..." + p["api_key"][-4:]
            p["api_key"] = ""  # Don't return actual key in list
    return {"providers": providers, "main_id": api_providers.MAIN_PROVIDER_ID}


@router.post("")
async def add_provider(req: ProviderCreate):
    """Add a new API provider (non-main)."""
    if not req.name.strip():
        raise ValidationError("name is required")
    if not req.base_url.strip():
        raise ValidationError("base_url is required")
    if not req.api_key.strip():
        raise ValidationError("api_key is required")
    provider = api_providers.add_provider(
        DB_PATH,
        name=req.name.strip(),
        base_url=req.base_url.strip(),
        api_key=req.api_key.strip(),
        models=req.models,
    )
    return provider


@router.put("/{provider_id}")
async def update_provider(provider_id: str, req: ProviderUpdate):
    """Update a provider. Main API can be edited too."""
    fields = {k: v for k, v in req.model_dump().items() if v is not None}
    if not fields:
        raise ValidationError("No fields to update")
    result = api_providers.update_provider(DB_PATH, provider_id, **fields)
    if not result:
        raise NotFoundError(f"Provider {provider_id} not found")
    return result


@router.delete("/{provider_id}")
async def delete_provider(provider_id: str):
    """Delete a provider. Main API cannot be deleted."""
    if provider_id == api_providers.MAIN_PROVIDER_ID:
        raise ValidationError("Main API cannot be deleted")
    success = api_providers.delete_provider(DB_PATH, provider_id)
    if not success:
        raise NotFoundError(f"Provider {provider_id} not found")
    return {"deleted": True, "id": provider_id}


@router.post("/{provider_id}/fetch-models")
async def fetch_models(provider_id: str):
    """Fetch available models from the provider's API.

    Calls GET {base_url}/models with the provider's API key.
    """
    provider = api_providers.get_provider(DB_PATH, provider_id)
    if not provider:
        raise NotFoundError(f"Provider {provider_id} not found")
    if not provider.get("api_key") or not provider.get("base_url"):
        raise ValidationError("Provider has no API key or base URL configured")

    import httpx
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{provider['base_url'].rstrip('/')}/models",
                headers={"Authorization": f"Bearer {provider['api_key']}"},
            )
            resp.raise_for_status()
            data = resp.json()
            models = []
            for m in data.get("data", []):
                mid = m.get("id", "")
                if mid:
                    models.append(mid)
            # Update the provider with fetched models
            api_providers.update_provider(DB_PATH, provider_id, models=models)
            return {"models": models, "count": len(models)}
    except Exception as exc:
        log.warning("provider.fetch_models_failed", extra={
            "provider": provider_id, "error": str(exc),
        })
        raise HTTPException(status_code=502, detail=f"Failed to fetch models: {exc}")


@router.get("/assignments")
async def list_assignments():
    """Get all function-to-provider assignments.

    Returns:
      assignments: {task: provider_id}
      tasks: the list of assignable tasks with labels
      providers: list of {id, name, is_main} for dropdown
    """
    assignments = api_providers.get_assignments(DB_PATH)
    providers = api_providers.get_provider_names(DB_PATH)
    return {
        "assignments": assignments,
        "tasks": api_providers.TASK_LIST,
        "providers": providers,
        "main_id": api_providers.MAIN_PROVIDER_ID,
    }


@router.put("/assignments")
async def set_assignment(req: AssignmentUpdate):
    """Assign a function to a specific provider.

    task: one of the keys in TASK_LIST
    provider_id: "main" or a provider ID
    """
    valid_tasks = {t["key"] for t in api_providers.TASK_LIST}
    if req.task not in valid_tasks:
        raise ValidationError(f"Invalid task: {req.task}. Valid: {valid_tasks}")

    # Verify provider exists
    provider = api_providers.get_provider(DB_PATH, req.provider_id)
    if not provider and req.provider_id != api_providers.MAIN_PROVIDER_ID:
        raise NotFoundError(f"Provider {req.provider_id} not found")

    api_providers.set_assignment(DB_PATH, req.task, req.provider_id)
    log.info("provider.assigned", extra={
        "task": req.task, "provider_id": req.provider_id,
    })
    return {"task": req.task, "provider_id": req.provider_id}


@router.get("/tasks")
async def list_tasks():
    """Get the list of assignable tasks with descriptions."""
    return {"tasks": api_providers.TASK_LIST}
