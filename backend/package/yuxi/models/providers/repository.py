"""The model provider configures the data access layer."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.storage.postgres.models_business import ModelProvider


async def list_model_providers(db: AsyncSession) -> list[ModelProvider]:
    """Get all model supplier configurations."""
    result = await db.execute(
        select(ModelProvider).order_by(ModelProvider.is_enabled.desc(), ModelProvider.provider_id.asc())
    )
    return list(result.scalars().all())


async def get_model_provider(db: AsyncSession, provider_id: str) -> ModelProvider | None:
    """Get model provider configuration by provider_id."""
    result = await db.execute(select(ModelProvider).where(ModelProvider.provider_id == provider_id))
    return result.scalar_one_or_none()


async def create_model_provider(db: AsyncSession, data: dict) -> ModelProvider:
    """Create a model supplier configuration."""
    provider = ModelProvider(**data)
    db.add(provider)
    await db.flush()
    await db.refresh(provider)
    return provider


async def update_model_provider(db: AsyncSession, provider: ModelProvider, data: dict) -> ModelProvider:
    """Update model provider configuration."""
    for key, value in data.items():
        if key != "provider_id":
            setattr(provider, key, value)
    await db.flush()
    await db.refresh(provider)
    return provider


async def delete_model_provider(db: AsyncSession, provider: ModelProvider) -> None:
    """Delete model supplier configuration."""
    await db.delete(provider)
    await db.flush()
