from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from server.routers.model_provider_router import model_providers
from server.utils.auth_middleware import get_db, get_admin_user
from yuxi.storage.postgres.models_business import Base, Department, User

pytestmark = [pytest.mark.asyncio, pytest.mark.unit]


@pytest_asyncio.fixture()
async def app_client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        dept = Department(name="Default department")
        user = User(
            username="Admin",
            uid="admin",
            password_hash="$argon2id$placeholder",
            role="superadmin",
            department=dept,
        )
        db.add_all([dept, user])
        await db.commit()
        await db.refresh(user)

        app = FastAPI()
        app.include_router(model_providers, prefix="/api")

        async def override_db():
            yield db

        async def override_user():
            return user

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_admin_user] = override_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
    await engine.dispose()


async def test_get_builtin_providers(app_client):
    response = await app_client.get("/api/system/model-providers/builtin")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)

    # Check that nvidia is present in the builtin list
    providers = data["data"]
    nvidia_provider = next((p for p in providers if p["provider_id"] == "nvidia"), None)
    assert nvidia_provider is not None
    assert nvidia_provider["display_name"] == "NVIDIA"
    assert nvidia_provider["base_url"] == "https://integrate.api.nvidia.com/v1"
    assert "chat" in nvidia_provider["capabilities"]
