"""
Integration tests for knowledge router endpoints.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from yuxi.knowledge.chunking.ragflow_like.presets import CHUNK_PRESET_IDS

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


def _assert_forbidden_response(response):
    """Verify the format of the 403 Forbidden response"""
    assert response.status_code == 403
    payload = response.json()
    assert "detail" in payload
    assert isinstance(payload["detail"], str)


async def _create_test_department(test_client, admin_headers, prefix="pytest_dept"):
    suffix = uuid.uuid4().hex[:8]
    admin_uid = f"deptadmin_{suffix}"
    response = await test_client.post(
        "/api/departments",
        json={
            "name": f"{prefix}_{suffix}",
            "description": "pytest department",
            "admin_uid": admin_uid,
            "admin_password": f"Pw!{suffix}",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    payload["admin_uid"] = admin_uid
    return payload


async def _create_test_user(test_client, admin_headers, department_id):
    suffix = uuid.uuid4().hex[:8]
    password = f"Pw!{suffix}"
    response = await test_client.post(
        "/api/auth/users",
        json={
            "username": f"pytest_user_{suffix}",
            "password": password,
            "role": "user",
            "department_id": department_id,
        },
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    user = response.json()

    login_response = await test_client.post(
        "/api/auth/token",
        data={"username": user["uid"], "password": password},
    )
    assert login_response.status_code == 200, login_response.text
    return {"user": user, "headers": {"Authorization": f"Bearer {login_response.json()['access_token']}"}}


async def _delete_user_by_id(test_client, admin_headers, user_id):
    response = await test_client.delete(f"/api/auth/users/{user_id}", headers=admin_headers)
    assert response.status_code in (200, 404), response.text


async def _find_user_id_by_uid(test_client, admin_headers, uid):
    response = await test_client.get("/api/auth/users", headers=admin_headers)
    assert response.status_code == 200, response.text
    for user in response.json():
        if user["uid"] == uid:
            return user["id"]
    return None


async def _delete_department_with_admin(test_client, admin_headers, department):
    admin_user_id = await _find_user_id_by_uid(test_client, admin_headers, department["admin_uid"])
    if admin_user_id:
        await _delete_user_by_id(test_client, admin_headers, admin_user_id)
    response = await test_client.delete(f"/api/departments/{department['id']}", headers=admin_headers)
    assert response.status_code in (200, 404), response.text


async def _create_test_database(test_client, admin_headers, share_config=None):
    response = await test_client.post(
        "/api/knowledge/databases",
        json={
            "database_name": f"pytest_acl_{uuid.uuid4().hex[:8]}",
            "description": "Knowledge permission test",
            "embedding_model_spec": "siliconflow-cn:Pro/BAAI/bge-m3",
            "kb_type": "milvus",
            "additional_params": {},
            "share_config": share_config,
        },
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _accessible_kb_ids(test_client, headers):
    response = await test_client.get("/api/knowledge/databases/accessible", headers=headers)
    assert response.status_code == 200, response.text
    return {item["kb_id"] for item in response.json().get("databases", [])}


async def test_admin_can_manage_knowledge_databases(test_client, admin_headers, knowledge_database):
    kb_id = knowledge_database["kb_id"]

    list_response = await test_client.get("/api/knowledge/databases", headers=admin_headers)
    assert list_response.status_code == 200, list_response.text
    databases = list_response.json().get("databases", [])
    assert any(entry["kb_id"] == kb_id for entry in databases)

    get_response = await test_client.get(f"/api/knowledge/databases/{kb_id}", headers=admin_headers)
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["kb_id"] == kb_id

    update_response = await test_client.put(
        f"/api/knowledge/databases/{kb_id}",
        json={"name": knowledge_database["name"], "description": "Updated by pytest"},
        headers=admin_headers,
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["database"]["description"] == "Updated by pytest"


async def test_document_exists_returns_false_for_missing_relative_path(test_client, admin_headers, knowledge_database):
    kb_id = knowledge_database["kb_id"]
    filename = f"google_drive/shared_drives/engineering/serving-runtime/dsid_{uuid.uuid4().hex}__missing-playbook.txt"

    response = await test_client.get(
        f"/api/knowledge/databases/{kb_id}/documents/exists",
        params={"filename": filename},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"kb_id": kb_id, "filename": filename, "exists": False}


async def test_create_database_with_chunk_preset(test_client, admin_headers):
    db_name = f"pytest_chunk_preset_{uuid.uuid4().hex[:6]}"
    payload = {
        "database_name": db_name,
        "description": "Chunk preset create test",
        "embedding_model_spec": "siliconflow-cn:Pro/BAAI/bge-m3",
        "kb_type": "milvus",
        "additional_params": {"chunk_preset_id": "book"},
    }

    create_response = await test_client.post("/api/knowledge/databases", json=payload, headers=admin_headers)
    assert create_response.status_code == 200, create_response.text
    kb_id = create_response.json()["kb_id"]

    info_response = await test_client.get(f"/api/knowledge/databases/{kb_id}", headers=admin_headers)
    assert info_response.status_code == 200, info_response.text
    assert info_response.json()["additional_params"]["chunk_preset_id"] == "book"

    delete_response = await test_client.delete(f"/api/knowledge/databases/{kb_id}", headers=admin_headers)
    assert delete_response.status_code == 200, delete_response.text


async def test_get_chunk_presets_returns_configured_options(test_client, admin_headers):
    response = await test_client.get("/api/knowledge/chunk-presets", headers=admin_headers)
    assert response.status_code == 200, response.text

    payload = response.json()
    options = payload["chunk_presets"]
    assert payload["message"] == "success"
    assert {option["value"] for option in options} == CHUNK_PRESET_IDS
    assert all(set(option) == {"value", "label", "description"} for option in options)
    assert all(option["label"] and option["description"] for option in options)


async def test_update_database_additional_params_merge_keeps_chunk_preset(
    test_client, admin_headers, knowledge_database
):
    kb_id = knowledge_database["kb_id"]

    first_update = await test_client.put(
        f"/api/knowledge/databases/{kb_id}",
        json={
            "name": knowledge_database["name"],
            "description": "update with chunk preset",
            "additional_params": {"chunk_preset_id": "qa"},
        },
        headers=admin_headers,
    )
    assert first_update.status_code == 200, first_update.text

    second_update = await test_client.put(
        f"/api/knowledge/databases/{kb_id}",
        json={
            "name": knowledge_database["name"],
            "description": "update without additional params",
        },
        headers=admin_headers,
    )
    assert second_update.status_code == 200, second_update.text

    info_response = await test_client.get(f"/api/knowledge/databases/{kb_id}", headers=admin_headers)
    assert info_response.status_code == 200, info_response.text
    assert info_response.json()["additional_params"]["chunk_preset_id"] == "qa"


async def test_knowledge_routes_enforce_permissions(test_client, standard_user, knowledge_database):
    kb_id = knowledge_database["kb_id"]

    forbidden_create = await test_client.post(
        "/api/knowledge/databases",
        json={
            "database_name": "unauthorized_db",
            "description": "Should not succeed",
            "embedding_model_spec": "siliconflow-cn:Pro/BAAI/bge-m3",
        },
        headers=standard_user["headers"],
    )
    _assert_forbidden_response(forbidden_create)

    forbidden_list = await test_client.get("/api/knowledge/databases", headers=standard_user["headers"])
    _assert_forbidden_response(forbidden_list)

    forbidden_chunk_presets = await test_client.get("/api/knowledge/chunk-presets", headers=standard_user["headers"])
    _assert_forbidden_response(forbidden_chunk_presets)

    forbidden_get = await test_client.get(f"/api/knowledge/databases/{kb_id}", headers=standard_user["headers"])
    _assert_forbidden_response(forbidden_get)

    forbidden_exists = await test_client.get(
        f"/api/knowledge/databases/{kb_id}/documents/exists",
        params={"filename": "demo.txt"},
        headers=standard_user["headers"],
    )
    _assert_forbidden_response(forbidden_exists)


async def test_admin_can_create_vector_db_with_reranker(test_client, admin_headers):
    """Test create vector library and configure reranker parameters (via query_params.options）

    Note: database cleanup is performed by conftest.py The session fixture in .
    """
    db_name = f"pytest_rerank_{uuid.uuid4().hex[:6]}"
    payload = {
        "database_name": db_name,
        "description": "Vector DB with reranker",
        "embedding_model_spec": "siliconflow-cn:Pro/BAAI/bge-m3",
        "kb_type": "milvus",
        "additional_params": {},
    }

    create_response = await test_client.post("/api/knowledge/databases", json=payload, headers=admin_headers)
    assert create_response.status_code == 200, create_response.text

    db_payload = create_response.json()
    kb_id = db_payload["kb_id"]

    # Get query parameter configuration
    params_response = await test_client.get(f"/api/knowledge/databases/{kb_id}/query-params", headers=admin_headers)
    assert params_response.status_code == 200, params_response.text

    params_payload = params_response.json()
    options = params_payload.get("params", {}).get("options", [])
    option_keys = {option.get("key") for option in options}

    # Verify new parameter names
    assert "final_top_k" in option_keys
    assert "use_reranker" in option_keys
    assert "recall_top_k" in option_keys
    assert "reranker_model" in option_keys

    # Verify parameter configuration
    final_top_k_option = next((opt for opt in options if opt.get("key") == "final_top_k"), None)
    assert final_top_k_option is not None
    assert final_top_k_option.get("default") == 10

    use_reranker_option = next((opt for opt in options if opt.get("key") == "use_reranker"), None)
    assert use_reranker_option is not None
    assert use_reranker_option.get("default") is False

    # Save query parameters (simulated front-end configuration)
    update_params = {
        "final_top_k": 5,
        "use_reranker": True,
        "recall_top_k": 20,
    }
    update_response = await test_client.put(
        f"/api/knowledge/databases/{kb_id}/query-params", json=update_params, headers=admin_headers
    )
    assert update_response.status_code == 200, update_response.text

    # Get the parameters again and verify that the save is successful.
    params_response2 = await test_client.get(f"/api/knowledge/databases/{kb_id}/query-params", headers=admin_headers)
    assert params_response2.status_code == 200, params_response2.text

    params_payload2 = params_response2.json()
    options2 = params_payload2.get("params", {}).get("options", [])

    # Verify saved value
    final_top_k_option2 = next((opt for opt in options2 if opt.get("key") == "final_top_k"), None)
    assert final_top_k_option2 is not None
    assert final_top_k_option2.get("default") == 5  # saved value

    use_reranker_option2 = next((opt for opt in options2 if opt.get("key") == "use_reranker"), None)
    assert use_reranker_option2 is not None
    assert use_reranker_option2.get("default") is True  # saved value


async def test_create_dify_database_success(test_client, admin_headers):
    db_name = f"pytest_dify_{uuid.uuid4().hex[:6]}"
    payload = {
        "database_name": db_name,
        "description": "Dify KB create test",
        "kb_type": "dify",
        "additional_params": {
            "dify_api_url": "https://api.dify.ai/v1",
            "dify_token": "test-token",
            "dify_dataset_id": "dataset-123",
        },
    }

    create_response = await test_client.post("/api/knowledge/databases", json=payload, headers=admin_headers)
    assert create_response.status_code == 200, create_response.text
    created_payload = create_response.json()
    kb_id = created_payload["kb_id"]
    assert created_payload["embedding_model_spec"] is None
    assert "chunk_preset_id" not in created_payload["metadata"]

    info_response = await test_client.get(f"/api/knowledge/databases/{kb_id}", headers=admin_headers)
    assert info_response.status_code == 200, info_response.text
    additional_params = info_response.json()["additional_params"]
    assert additional_params["dify_api_url"] == "https://api.dify.ai/v1"
    assert additional_params["dify_token"] == "test-token"
    assert additional_params["dify_dataset_id"] == "dataset-123"


async def test_create_dify_database_missing_params_failed(test_client, admin_headers):
    payload = {
        "database_name": f"pytest_dify_missing_{uuid.uuid4().hex[:6]}",
        "description": "Dify KB missing params",
        "kb_type": "dify",
        "additional_params": {
            "dify_api_url": "https://api.dify.ai/v1",
            "dify_token": "",
            "dify_dataset_id": "",
        },
    }

    response = await test_client.post("/api/knowledge/databases", json=payload, headers=admin_headers)
    assert response.status_code == 400, response.text
    assert "Thiếu tham số Dify" in response.json()["detail"]


async def test_create_dify_database_invalid_api_url_failed(test_client, admin_headers):
    payload = {
        "database_name": f"pytest_dify_bad_url_{uuid.uuid4().hex[:6]}",
        "description": "Dify KB invalid api url",
        "kb_type": "dify",
        "additional_params": {
            "dify_api_url": "https://api.dify.ai",
            "dify_token": "test-token",
            "dify_dataset_id": "dataset-123",
        },
    }

    response = await test_client.post("/api/knowledge/databases", json=payload, headers=admin_headers)
    assert response.status_code == 400, response.text
    assert "/v1" in response.json()["detail"]


async def test_dify_query_params_and_documents_readonly(test_client, admin_headers):
    payload = {
        "database_name": f"pytest_dify_ro_{uuid.uuid4().hex[:6]}",
        "description": "Dify readonly routes",
        "kb_type": "dify",
        "additional_params": {
            "dify_api_url": "https://api.dify.ai/v1",
            "dify_token": "test-token",
            "dify_dataset_id": "dataset-123",
        },
    }

    create_response = await test_client.post("/api/knowledge/databases", json=payload, headers=admin_headers)
    assert create_response.status_code == 200, create_response.text
    kb_id = create_response.json()["kb_id"]

    params_response = await test_client.get(f"/api/knowledge/databases/{kb_id}/query-params", headers=admin_headers)
    assert params_response.status_code == 200, params_response.text
    options = params_response.json().get("params", {}).get("options", [])
    option_keys = {item.get("key") for item in options}
    assert option_keys == {"search_mode", "final_top_k", "score_threshold_enabled", "similarity_threshold"}

    add_response = await test_client.post(
        f"/api/knowledge/databases/{kb_id}/documents",
        json={"items": ["/tmp/demo.txt"], "params": {"content_type": "file"}},
        headers=admin_headers,
    )
    assert add_response.status_code == 400, add_response.text
    assert "chỉ hỗ trợ tìm kiếm" in add_response.json()["detail"]

    parse_response = await test_client.post(
        f"/api/knowledge/databases/{kb_id}/documents/parse",
        json=["file_id_1"],
        headers=admin_headers,
    )
    assert parse_response.status_code == 400, parse_response.text
    assert "chỉ hỗ trợ tìm kiếm" in parse_response.json()["detail"]

    index_response = await test_client.post(
        f"/api/knowledge/databases/{kb_id}/documents/index",
        json={"file_ids": ["file_id_1"], "params": {}},
        headers=admin_headers,
    )
    assert index_response.status_code == 400, index_response.text
    assert "chỉ hỗ trợ tìm kiếm" in index_response.json()["detail"]


# =============================================================================
# === Mindmap Tests ===
# =============================================================================


async def test_get_databases_overview(test_client, admin_headers, knowledge_database):
    """Test Get an overview of all knowledge bases"""
    response = await test_client.get("/api/knowledge/mindmap/databases", headers=admin_headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["message"] == "success"
    assert "databases" in payload
    assert "total" in payload

    # Verify that the knowledge base is in the list
    kb_ids = [db["kb_id"] for db in payload["databases"]]
    assert knowledge_database["kb_id"] in kb_ids


async def test_get_database_files(test_client, admin_headers, knowledge_database):
    """Test to obtain the knowledge base file list"""
    kb_id = knowledge_database["kb_id"]
    response = await test_client.get(f"/api/knowledge/databases/{kb_id}/mindmap/files", headers=admin_headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["message"] == "success"
    assert payload["kb_id"] == kb_id
    assert "files" in payload
    assert "total" in payload
    assert payload["db_name"] == knowledge_database["name"]


async def test_get_database_files_not_found(test_client, admin_headers):
    """Test to obtain a list of non-existent knowledge base files"""
    response = await test_client.get("/api/knowledge/databases/nonexistent_kb_id/mindmap/files", headers=admin_headers)
    assert response.status_code == 404


async def test_generate_mindmap_empty_files(test_client, admin_headers, knowledge_database):
    """Test empty file list to generate mind map"""
    kb_id = knowledge_database["kb_id"]
    response = await test_client.post(
        f"/api/knowledge/databases/{kb_id}/mindmap/generate",
        json={"file_ids": [], "user_prompt": ""},
        headers=admin_headers,
    )
    # Empty files should return a 400 error
    assert response.status_code == 400
    assert "Không có file trong kho kiến thức" in response.json()["detail"]


async def test_get_database_mindmap_not_exists(test_client, admin_headers, knowledge_database):
    """Test to obtain a mind map that does not exist"""
    kb_id = knowledge_database["kb_id"]
    response = await test_client.get(f"/api/knowledge/databases/{kb_id}/mindmap", headers=admin_headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["kb_id"] == kb_id
    assert payload["mindmap"] is None  # No mind map has been generated yet


async def test_generate_and_get_mindmap(test_client, admin_headers, knowledge_database):
    """testgenerate and get the mind guide picture

    Note: This test requires a document in the knowledge base to fully testCore functions.
    Since there is no pre-ofdocument upload fixture, the test will first verify the Empty file scenario (expected 400).
    Then use xfail mark to wait for subsequent improvement.
    """
    kb_id = knowledge_database["kb_id"]

    # Empty file scenario - expected return of 400 error
    generate_response = await test_client.post(
        f"/api/knowledge/databases/{kb_id}/mindmap/generate",
        json={"file_ids": [], "user_prompt": ""},
        headers=admin_headers,
    )
    assert generate_response.status_code == 400
    assert "Không có file trong kho kiến thức" in generate_response.json()["detail"]

    # Flag this test requires file upload support for full execution
    pytest.skip("You need to upload the file first to fully test the mind map generation function")


# =============================================================================
# === Knowledge Router Additional Tests ===
# =============================================================================


async def test_get_accessible_databases(test_client, admin_headers, knowledge_database):
    """Test to get the list of accessible knowledge bases"""
    response = await test_client.get("/api/knowledge/databases/accessible", headers=admin_headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert "databases" in payload

    # Verify that the knowledge base is in the list
    kb_ids = [db["kb_id"] for db in payload["databases"]]
    assert knowledge_database["kb_id"] in kb_ids


async def test_create_database_defaults_to_global_share_config(test_client, admin_headers):
    database = await _create_test_database(test_client, admin_headers)
    kb_id = database["kb_id"]
    try:
        assert database["share_config"] == {"access_level": "global", "department_ids": [], "user_uids": []}
    finally:
        await test_client.delete(f"/api/knowledge/databases/{kb_id}", headers=admin_headers)


async def test_department_share_config_filters_accessible_databases(test_client, admin_headers):
    department_a = await _create_test_department(test_client, admin_headers, "pytest_dept_a")
    department_b = await _create_test_department(test_client, admin_headers, "pytest_dept_b")
    user_a = user_b = None
    database = None

    try:
        user_a = await _create_test_user(test_client, admin_headers, department_a["id"])
        user_b = await _create_test_user(test_client, admin_headers, department_b["id"])
        database = await _create_test_database(
            test_client,
            admin_headers,
            {"access_level": "department", "department_ids": [department_a["id"]], "user_uids": []},
        )

        saved_config = database["share_config"]
        assert saved_config["access_level"] == "department"
        assert department_a["id"] in saved_config["department_ids"]

        assert database["kb_id"] in await _accessible_kb_ids(test_client, user_a["headers"])
        assert database["kb_id"] not in await _accessible_kb_ids(test_client, user_b["headers"])
    finally:
        if database:
            await test_client.delete(f"/api/knowledge/databases/{database['kb_id']}", headers=admin_headers)
        if user_a:
            await _delete_user_by_id(test_client, admin_headers, user_a["user"]["id"])
        if user_b:
            await _delete_user_by_id(test_client, admin_headers, user_b["user"]["id"])
        await _delete_department_with_admin(test_client, admin_headers, department_a)
        await _delete_department_with_admin(test_client, admin_headers, department_b)


async def test_user_share_config_filters_accessible_databases(test_client, admin_headers):
    department_a = await _create_test_department(test_client, admin_headers, "pytest_dept_a")
    department_b = await _create_test_department(test_client, admin_headers, "pytest_dept_b")
    user_a = user_b = None
    database = None

    try:
        user_a = await _create_test_user(test_client, admin_headers, department_a["id"])
        user_b = await _create_test_user(test_client, admin_headers, department_b["id"])
        database = await _create_test_database(
            test_client,
            admin_headers,
            {"access_level": "user", "department_ids": [], "user_uids": [user_a["user"]["uid"]]},
        )

        saved_config = database["share_config"]
        assert saved_config["access_level"] == "user"
        assert user_a["user"]["uid"] in saved_config["user_uids"]

        assert database["kb_id"] in await _accessible_kb_ids(test_client, user_a["headers"])
        assert database["kb_id"] not in await _accessible_kb_ids(test_client, user_b["headers"])
    finally:
        if database:
            await test_client.delete(f"/api/knowledge/databases/{database['kb_id']}", headers=admin_headers)
        if user_a:
            await _delete_user_by_id(test_client, admin_headers, user_a["user"]["id"])
        if user_b:
            await _delete_user_by_id(test_client, admin_headers, user_b["user"]["id"])
        await _delete_department_with_admin(test_client, admin_headers, department_a)
        await _delete_department_with_admin(test_client, admin_headers, department_b)


async def test_user_access_options_include_all_departments_for_admin(test_client, admin_headers):
    department = await _create_test_department(test_client, admin_headers, "pytest_access_options")
    user = None

    try:
        user = await _create_test_user(test_client, admin_headers, department["id"])
        response = await test_client.get("/api/auth/users/access-options", headers=admin_headers)
        assert response.status_code == 200, response.text
        uids = {item["uid"] for item in response.json()}
        assert user["user"]["uid"] in uids
        assert department["admin_uid"] in uids
    finally:
        if user:
            await _delete_user_by_id(test_client, admin_headers, user["user"]["id"])
        await _delete_department_with_admin(test_client, admin_headers, department)


async def test_get_knowledge_base_types(test_client, admin_headers):
    """Test to obtain supported knowledge base types"""
    response = await test_client.get("/api/knowledge/types", headers=admin_headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["message"] == "success"
    assert "kb_types" in payload
    assert "default_config" not in payload["kb_types"]["dify"]
    assert payload["kb_types"]["dify"]["name"] == "Dify"
    assert payload["kb_types"]["dify"]["description"] == "Connect to Dify Dataset's read-only search knowledge base"
    assert payload["kb_types"]["dify"]["requires_embedding_model"] is False
    assert payload["kb_types"]["dify"]["supports_documents"] is False
    assert [option["key"] for option in payload["kb_types"]["dify"]["create_params"]["options"]] == [
        "dify_api_url",
        "dify_token",
        "dify_dataset_id",
    ]
    assert "default_config" not in payload["kb_types"]["notion"]
    assert payload["kb_types"]["notion"]["name"] == "Notion"
    assert (
        payload["kb_types"]["notion"]["description"]
        == "Read-only knowledge base connected to Notion Data Source, supporting retrieval, page opening and in-page search"
    )
    assert payload["kb_types"]["notion"]["requires_embedding_model"] is False
    assert payload["kb_types"]["notion"]["supports_documents"] is False
    assert [option["key"] for option in payload["kb_types"]["notion"]["create_params"]["options"]] == [
        "notion_token",
        "notion_data_source_id",
        "notion_version",
    ]


async def test_get_knowledge_base_statistics(test_client, admin_headers):
    """Test to obtain knowledge base statistics"""
    response = await test_client.get("/api/knowledge/stats", headers=admin_headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["message"] == "success"
    assert "stats" in payload


async def test_get_supported_file_types(test_client, admin_headers):
    """Test to obtain supported file types"""
    response = await test_client.get("/api/knowledge/files/supported-types", headers=admin_headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["message"] == "success"
    assert "file_types" in payload
    assert isinstance(payload["file_types"], list)


async def test_markdown_endpoint_parses_uploaded_text_file(test_client, admin_headers):
    """test /files/markdown Can parse uploaded files and return markdown."""
    data_dir = Path(__file__).resolve().parents[2] / "data"
    test_file = data_dir / "A_Dream_of_Red_Mansions_10hui.txt"

    assert test_file.exists(), f"Test file does not exist: {test_file}"

    with test_file.open("rb") as f:
        response = await test_client.post(
            "/api/knowledge/files/markdown",
            headers=admin_headers,
            files={"file": (test_file.name, f, "text/plain")},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["message"] == "success"
    assert isinstance(payload.get("markdown_content"), str)
    assert payload["markdown_content"].strip()


async def test_duplicate_database_name(test_client, admin_headers, knowledge_database):
    """Test repeatedly creates a knowledge base with the same name"""
    db_name = knowledge_database["name"]
    response = await test_client.post(
        "/api/knowledge/databases",
        json={
            "database_name": db_name,
            "description": "Duplicate name test",
            "embedding_model_spec": "siliconflow-cn:Pro/BAAI/bge-m3",
            "kb_type": "milvus",
            "additional_params": {},
        },
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert "đã tồn tại" in response.json()["detail"]


async def test_create_lightrag_knowledge_base_is_unsupported(test_client, admin_headers):
    db_name = f"pytest_lightrag_{uuid.uuid4().hex[:6]}"
    response = await test_client.post(
        "/api/knowledge/databases",
        json={
            "database_name": db_name,
            "description": "Unsupported LightRAG knowledge base",
            "embedding_model_spec": "siliconflow-cn:Pro/BAAI/bge-m3",
            "kb_type": "lightrag",
            "additional_params": {},
        },
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert "Unsupported knowledge base type: lightrag" in response.json()["detail"]


async def test_create_milvus_knowledge_base(test_client, admin_headers):
    """test creates Milvus knowledge base

    Note: database cleanup is performed by conftest.py The session fixture in .
    """
    db_name = f"pytest_milvus_{uuid.uuid4().hex[:6]}"
    payload = {
        "database_name": db_name,
        "description": "Pytest Milvus knowledge base",
        "embedding_model_spec": "siliconflow-cn:Pro/BAAI/bge-m3",
        "kb_type": "milvus",
        "additional_params": {},
    }

    create_response = await test_client.post("/api/knowledge/databases", json=payload, headers=admin_headers)
    assert create_response.status_code == 200, create_response.text

    db_payload = create_response.json()
    assert db_payload["kb_type"] == "milvus"


async def test_sample_questions_endpoints(test_client, admin_headers, knowledge_database):
    """Test sample problem interface (expected return of 400 when empty file)"""
    kb_id = knowledge_database["kb_id"]

    # Get sample questions (an empty knowledge base should return an empty list)
    get_response = await test_client.get(f"/api/knowledge/databases/{kb_id}/sample-questions", headers=admin_headers)
    assert get_response.status_code == 200, get_response.text
    get_payload = get_response.json()
    assert get_payload["kb_id"] == kb_id
    assert "questions" in get_payload
    assert get_payload["count"] == 0  # There is no problem with an empty knowledge base

    # Generate example questions (an empty knowledge base should return 400)
    generate_response = await test_client.post(
        f"/api/knowledge/databases/{kb_id}/sample-questions",
        json={"count": 5},
        headers=admin_headers,
    )
    assert generate_response.status_code == 400
    assert "Không có file trong kho kiến thức" in generate_response.json()["detail"]


async def test_mindmap_permissions(test_client, standard_user, knowledge_database):
    """Test permission control of mind map interface"""
    kb_id = knowledge_database["kb_id"]

    # Ordinary users should not be able to access
    forbidden_list = await test_client.get("/api/knowledge/mindmap/databases", headers=standard_user["headers"])
    _assert_forbidden_response(forbidden_list)

    forbidden_files = await test_client.get(
        f"/api/knowledge/databases/{kb_id}/mindmap/files", headers=standard_user["headers"]
    )
    _assert_forbidden_response(forbidden_files)

    forbidden_generate = await test_client.post(
        f"/api/knowledge/databases/{kb_id}/mindmap/generate",
        json={"file_ids": []},
        headers=standard_user["headers"],
    )
    _assert_forbidden_response(forbidden_generate)
