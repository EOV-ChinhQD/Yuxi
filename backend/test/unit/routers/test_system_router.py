from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.routers.system_router import system

pytestmark = pytest.mark.unit


def test_discovery_endpoint_is_public(monkeypatch):
    monkeypatch.setattr("server.routers.system_router.get_version", lambda: "0.7.1.dev0")

    app = FastAPI()
    app.include_router(system, prefix="/api")
    response = TestClient(app).get("/api/system/discovery")

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Yuxi"
    assert payload["version"] == "0.7.1.dev0"
    assert payload["api_prefix"] == "/api"
    assert payload["capabilities"]["cli"]["browser_login"] is True
    assert payload["capabilities"]["cli"]["api_key_auth"] is True
    assert payload["capabilities"]["cli"]["kb_upload"] is True
    assert payload["endpoints"]["cli_auth_sessions"] == "/api/auth/cli/sessions"


from unittest.mock import AsyncMock, MagicMock, patch

def test_detailed_health_check(monkeypatch):
    app = FastAPI()
    app.include_router(system, prefix="/api")
    
    from server.utils.auth_middleware import get_admin_user
    app.dependency_overrides[get_admin_user] = lambda: MagicMock(uid="admin_user")

    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_db)
    mock_context.__aexit__ = AsyncMock()

    mock_graph_service = MagicMock()
    mock_graph_service.driver.verify_connectivity = MagicMock()

    mock_store = MagicMock()
    mock_store._init_connection = MagicMock()

    with patch("yuxi.storage.postgres.manager.pg_manager.get_async_session_context", return_value=mock_context), \
         patch("yuxi.knowledge.graphs.milvus_graph_service.MilvusGraphService", return_value=mock_graph_service), \
         patch("yuxi.knowledge.graphs.milvus_graph_vector_store.MilvusGraphVectorStore", return_value=mock_store):
        response = TestClient(app).get("/api/system/health/detailed")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["postgres"] == "healthy"
    assert payload["neo4j"] == "healthy"
    assert payload["milvus"] == "healthy"
