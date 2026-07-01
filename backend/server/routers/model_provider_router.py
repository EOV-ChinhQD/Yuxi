"""Independent model provider configuration routing."""

from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from server.utils.auth_middleware import get_admin_user, get_db, get_required_user
from yuxi.models.providers.service import (
    check_credential_status,
    create_provider_config,
    delete_provider_config,
    fetch_remote_models,
    get_all_model_providers,
    get_model_provider_by_id,
    test_model_status_by_spec,
    update_provider_config,
)
from yuxi.storage.postgres.models_business import User
from yuxi.storage.postgres.manager import pg_manager
from yuxi.utils import logger

model_providers = APIRouter(prefix="/system/model-providers", tags=["model-providers"])


async def _refresh_model_cache() -> None:
    """Refresh model cache (called after CRUD operation)."""
    from yuxi.models.providers.cache import model_cache

    try:
        async with pg_manager.get_async_session_context() as session:
            providers = await get_all_model_providers(session)
            model_cache.rebuild(providers)
            logger.info(f"Model cache refreshed: {len(model_cache.get_all_specs())} models loaded")
    except Exception as e:
        logger.error(f"Failed to refresh model cache: {e}")


class ModelProviderPayload(BaseModel):
    provider_id: str | None = Field(None, description="Mã định danh ổn định nhà cung cấp")
    display_name: str | None = Field(None, description="Tên hiển thị")
    provider_type: str | None = Field(None, description="Loại bộ chuyển đổi nhà cung cấp, mặc định openai")
    default_protocol: str | None = Field(None, description="Giao thức mặc định")
    base_url: str | None = Field(None, description="URL cơ sở API")
    embedding_base_url: str | None = Field(None, description="URL cơ sở yêu cầu mô hình Embedding")
    rerank_base_url: str | None = Field(None, description="URL cơ sở yêu cầu mô hình Rerank")
    models_endpoint: str | None = Field(None, description="Endpoint danh sách mô hình Chat/Chung")
    embedding_models_endpoint: str | None = Field(None, description="Endpoint danh sách mô hình Embedding")
    rerank_models_endpoint: str | None = Field(None, description="Endpoint danh sách mô hình Rerank")
    api_key_env: str | None = Field(None, description="Tên biến môi trường API Key")
    api_key: str | None = Field(None, description="API Key được cấu hình trực tiếp")
    capabilities: list[str] | None = Field(None, description="Khả năng hỗ trợ")
    enabled_models: list[dict[str, Any]] | None = Field(None, description="Cấu hình mô hình đã bật")
    headers_json: dict[str, Any] | None = Field(None, description="Header yêu cầu bổ sung")
    extra_json: dict[str, Any] | None = Field(None, description="Cấu hình mở rộng")
    is_enabled: bool | None = Field(None, description="Có kích hoạt hay không")
    is_builtin: bool | None = Field(None, description="Có tích hợp sẵn hay không")


@model_providers.get("")
async def list_providers(
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a list of independent model vendor configurations."""
    providers = await get_all_model_providers(db)
    data = []
    for p in providers:
        d = p.to_dict()
        d["credential_status"] = check_credential_status(p)
        data.append(d)
    return {"success": True, "data": data}


@model_providers.post("")
async def create_provider(
    payload: ModelProviderPayload,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a standalone model supplier configuration."""
    try:
        provider = await create_provider_config(
            db,
            payload.model_dump(exclude_none=True),
            current_user.username,
        )
        await db.commit()
        await _refresh_model_cache()
        return {"success": True, "data": provider.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create model supplier: {e}")
        raise HTTPException(status_code=500, detail="Tạo nhà cung cấp mô hình thất bại")


@model_providers.get("/{provider_id}")
async def get_provider(
    provider_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single standalone model supplier configuration."""
    provider = await get_model_provider_by_id(db, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail=f"Nhà cung cấp {provider_id} không tồn tại")
    data = provider.to_dict()
    data["credential_status"] = check_credential_status(provider)
    return {"success": True, "data": data}


@model_providers.put("/{provider_id}")
async def update_provider(
    provider_id: str,
    payload: ModelProviderPayload,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Update standalone model vendor configuration."""
    try:
        # Get fields that have been explicitly set by the user (even if the value is None) so that clearing operations are handled correctly
        unset_fields = payload.model_fields_set
        data = payload.model_dump(exclude_none=True)
        for nullable_field in (
            "api_key_env",
            "api_key",
            "default_protocol",
            "embedding_base_url",
            "rerank_base_url",
            "models_endpoint",
            "embedding_models_endpoint",
            "rerank_models_endpoint",
        ):
            if nullable_field in unset_fields and getattr(payload, nullable_field) is None:
                data[nullable_field] = None
        provider = await update_provider_config(db, provider_id, data, current_user.username)
        if provider is None:
            raise HTTPException(status_code=404, detail=f"Nhà cung cấp {provider_id} không tồn tại")
        await db.commit()
        await _refresh_model_cache()
        return {"success": True, "data": provider.to_dict()}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Update model provider failed {provider_id}: {e}")
        raise HTTPException(status_code=500, detail="Cập nhật nhà cung cấp mô hình thất bại")


@model_providers.delete("/{provider_id}")
async def delete_provider(
    provider_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove standalone model vendor configuration."""
    deleted = await delete_provider_config(db, provider_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Nhà cung cấp {provider_id} không tồn tại")
    await db.commit()
    await _refresh_model_cache()
    return {"success": True}


@model_providers.get("/{provider_id}/remote-models")
async def get_remote_models(
    provider_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Pull the remote end in real time /models, do not fall into the library."""
    provider = await get_model_provider_by_id(db, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail=f"Nhà cung cấp {provider_id} không tồn tại")
    try:
        models = await fetch_remote_models(provider)
        return {"success": True, "data": models}
    except httpx.HTTPStatusError as e:
        # The error returned by the remote API does not transparently transmit the status code to avoid the front-end misjudgment as a system authentication failure.
        detail = e.response.text
        if e.response.status_code == 401:
            raise HTTPException(status_code=502, detail="Xác thực API từ xa thất bại, vui lòng kiểm tra cấu hình API Key")
        raise HTTPException(status_code=e.response.status_code, detail=f"Yêu cầu Models thất bại: {detail}")
    except Exception as e:
        logger.error(f"Failed to pull remote model {provider_id}: {e}")
        raise HTTPException(status_code=400, detail=f"Lấy mô hình từ xa thất bại: {e}")


@model_providers.post("/models/cache/refresh")
async def refresh_model_cache(
    current_user: User = Depends(get_admin_user),
):
    """Force a refresh of the model cache to reload all provider configurations from the database into Redis."""
    await _refresh_model_cache()
    from yuxi.models.providers.cache import model_cache

    return {"success": True, "message": "Bộ nhớ đệm đã được làm mới", "model_count": len(model_cache.get_all_specs())}


@model_providers.get("/models/v2")
async def get_v2_models(
    model_type: str = "chat",
    _current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """Get v2 FormatofModel column surface, by provider point group.

    v2 Model spec Format: provider_id:model_id (separated by colon point)
    Return data for use by the front-end Model selector.
    """
    from yuxi.models.providers.cache import model_cache

    grouped = model_cache.get_specs_grouped_by_provider(model_type)
    providers = await get_all_model_providers(db)
    provider_name_by_id = {
        provider.provider_id: provider.display_name or provider.provider_id for provider in providers
    }

    result = {}
    for provider_id, models in grouped.items():
        result[provider_id] = {
            "provider_id": provider_id,
            "provider_display_name": provider_name_by_id.get(provider_id, provider_id),
            "models": [
                {
                    "spec": m.spec,
                    "model_id": m.model_id,
                    "display_name": m.display_name,
                    "dimension": m.dimension,
                    "batch_size": m.batch_size,
                }
                for m in models
            ]
        }

    return {"success": True, "data": result}


@model_providers.get("/models/status")
async def get_model_status_by_spec(
    spec: str,
    current_user: User = Depends(get_admin_user),
):
    """Check model status against full spec (auto-recognize V1/V2、Chat/Embedding）。"""
    try:
        result = await test_model_status_by_spec(spec)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Test model status failed {spec}: {e}")
        return {"success": False, "data": {"spec": spec, "status": "error", "message": str(e)}}
