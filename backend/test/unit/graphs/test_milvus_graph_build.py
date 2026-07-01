from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from yuxi.knowledge.graphs.extractors import (
    GraphExtractorFactory,
    LLMGraphExtractor,
    normalize_extraction_result,
)
from yuxi.knowledge.graphs.milvus_graph_service import MilvusGraphService


def test_normalize_extraction_result_defaults_and_validates_refs():
    result = normalize_extraction_result(
        {
            "entities": [{"text": "Zhang San"}, {"text": "company"}],
            "relations": [{"source": "Zhang San", "target": "company", "text": "Served in"}],
        },
        "llm",
    )

    assert result["entities"][0]["label"] == "Entity"
    assert result["relations"][0]["label"] == "RELATED_TO"
    assert result["relations"][0]["source"] == {"text": "Zhang San", "label": "Entity", "attributes": []}
    assert result["metadata"] == {"extractor_type": "llm", "schema_version": 1}


def test_normalize_extraction_result_accepts_llm_nested_relation_entities():
    result = normalize_extraction_result(
        {
            "relations": [
                {
                    "source": {
                        "text": "Zhang San",
                        "label": "Person",
                        "attributes": [{"text": "engineer", "label": "Occupation"}],
                    },
                    "target": {"text": "company", "label": "Organization"},
                    "text": "Served in",
                    "label": "WORKS_AT",
                }
            ]
        },
        "llm",
    )

    assert result["entities"] == [
        {"text": "Zhang San", "label": "Person", "attributes": [{"text": "engineer", "label": "Occupation"}]},
        {"text": "company", "label": "Organization", "attributes": []},
    ]
    assert result["relations"][0]["source"]["attributes"] == [{"text": "engineer", "label": "Occupation"}]
    assert result["relations"][0]["target"] == {"text": "company", "label": "Organization", "attributes": []}


@pytest.mark.parametrize(
    "payload",
    [
        {"entities": [{"text": "Zhang San"}], "relations": [{"source": "Zhang San", "target": "không tồn tại", "text": "relation"}]},
        {"entities": [{"text": ""}], "relations": []},
    ],
)
def test_normalize_extraction_result_rejects_invalid_payload(payload):
    with pytest.raises(ValueError):
        normalize_extraction_result(payload, "llm")


def test_llm_graph_extractor_rejects_custom_prompt():
    extractor = LLMGraphExtractor({"model_spec": "test/model", "prompt": "custom"})

    with pytest.raises(ValueError, match="không hỗ trợ Prompt tùy chỉnh đầy đủ"):
        extractor.validate_options()


def test_llm_graph_extractor_appends_schema_to_fixed_prompt():
    extractor = LLMGraphExtractor(
        {
            "model_spec": "test/model",
            "schema": "Entity type can only be Person or Organization",
            "concurrency_count": 5,
            "model_params": {"temperature": 0.1},
        }
    )

    prompt = extractor._build_prompt("Zhang San works in the company")

    assert "Vui lòng trích xuất các thực thể và mối quan hệ thực thể từ văn bản bên dưới" in prompt
    assert "Extract Schema constraints" in prompt
    assert "Entity type can only be Person or Organization" in prompt
    assert "Text:\nZhang San works in the company" in prompt


def test_graph_extractor_factory_supports_only_llm():
    assert GraphExtractorFactory.supported_types() == ["llm"]


def test_graph_extractor_factory_rejects_spacy():
    with pytest.raises(ValueError, match="spacy"):
        GraphExtractorFactory.create("spacy", {"model": "zh_core_web_sm"})


@pytest.mark.asyncio
async def test_milvus_graph_service_configure_rejects_spacy():
    kb = SimpleNamespace(kb_type="milvus", additional_params={})

    class Repo:
        async def get_by_kb_id(self, kb_id):
            return kb

        async def update(self, kb_id, data):
            raise AssertionError("unsupported extractor should not be persisted")

    service = MilvusGraphService(kb_repo=Repo())

    with pytest.raises(ValueError, match="Loại bộ trích xuất đồ thị không được hỗ trợ"):
        await service.configure(
            "kb_test",
            extractor_type="spacy",
            extractor_options={"model": "zh_core_web_sm"},
            created_by="user_1",
        )


@pytest.mark.asyncio
async def test_milvus_graph_service_configure_persists_updated_concurrency():
    kb = SimpleNamespace(
        kb_type="milvus",
        additional_params={
            "graph_build_config": {
                "locked": True,
                "extractor_type": "llm",
                "extractor_options": {"model_spec": "test/model", "concurrency_count": 5},
            }
        },
    )

    class Repo:
        async def get_by_kb_id(self, kb_id):
            return kb

        async def update(self, kb_id, data):
            kb.additional_params = data["additional_params"]
            return kb

    chunk_repo = SimpleNamespace(
        count_by_kb_id=AsyncMock(return_value=0),
        count_graph_pending_by_kb_id=AsyncMock(return_value=0),
        count_graph_indexed_by_kb_id=AsyncMock(return_value=0),
    )
    graph_repo = SimpleNamespace(count_by_kb_id=AsyncMock(return_value=(3, 2)))
    service = MilvusGraphService(kb_repo=Repo(), chunk_repo=chunk_repo, graph_repo=graph_repo)

    await service.configure(
        "kb_test",
        extractor_type="llm",
        extractor_options={"model_spec": "test/model", "concurrency_count": 9},
        created_by="user_1",
    )
    status = await service.get_status("kb_test")

    assert status["config"]["extractor_options"]["concurrency_count"] == 9
    assert status["entity_count"] == 3
    assert status["relationship_count"] == 2


def test_milvus_graph_service_writes_chunk_entity_and_relation():
    tx = MagicMock()
    session = MagicMock()
    session.__enter__.return_value = session
    session.execute_write.side_effect = lambda func: func(tx)
    driver = MagicMock()
    driver.session.return_value = session
    connection = SimpleNamespace(driver=driver)
    service = MilvusGraphService(neo4j_connection=connection)
    chunk = SimpleNamespace(
        chunk_id="chunk_1",
        file_id="file_1",
        kb_id="kb_test",
        chunk_index=1,
        content="Zhang San works in the company",
        start_char_pos=0,
        end_char_pos=8,
    )

    entities, triples = service.write_chunk_graph(
        "kb_test",
        chunk,
        normalize_extraction_result(
            {
                "relations": [
                    {
                        "source": {
                            "text": "Zhang San",
                            "label": "Person",
                            "attributes": [{"text": "engineer", "label": "Occupation"}],
                        },
                        "target": {"text": "company", "label": "Organization"},
                        "text": "Served in",
                        "label": "WORKS_AT",
                    }
                ],
            },
            "llm",
        ),
    )

    assert [entity["name"] for entity in entities] == ["Zhang San", "company"]
    assert {entity["label"] for entity in entities} == {"Person", "Organization"}
    assert triples[0]["relation_type"] == "WORKS_AT"
    queries = [call.args[0] for call in tx.run.call_args_list]
    assert any("MERGE (c:Chunk:MilvusKB:`kb_test`" in query for query in queries)
    assert any("MERGE (e:Entity:MilvusKB:`kb_test`" in query for query in queries)
    assert any("MERGE (source)-[r:RELATION" in query for query in queries)
    entity_call = next(call for call in tx.run.call_args_list if "MERGE (e:Entity" in call.args[0])
    assert entity_call.kwargs["attributes"] == '[{"text": "engineer", "label": "Occupation"}]'


@pytest.mark.asyncio
async def test_milvus_graph_service_query_nodes_empty_kb_id():
    service = MilvusGraphService()
    result = await service.query_nodes(kb_id=None, keyword="test")
    assert result == {"nodes": [], "edges": []}


@pytest.mark.asyncio
async def test_milvus_graph_service_get_labels_empty_kb_id():
    service = MilvusGraphService()
    result = await service.get_labels(kb_id=None)
    assert result == []


@pytest.mark.asyncio
async def test_milvus_graph_service_get_stats_empty_kb_id():
    service = MilvusGraphService()
    result = await service.get_stats(kb_id=None)
    assert result == {"total_nodes": 0, "total_edges": 0, "entity_types": []}
