from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from yuxi.knowledge.utils import sample_question_utils as sq


def test_parse_sample_questions_content_strips_json_fence():
    questions = sq.parse_sample_questions_content('```json\n{"questions": ["What is a test?"]}\n```')

    assert questions == ["What is a test?"]


def test_parse_sample_questions_content_rejects_invalid_payload():
    with pytest.raises(ValueError, match="Định dạng câu hỏi"):
        sq.parse_sample_questions_content('{"items": []}')


@pytest.mark.asyncio
async def test_generate_database_sample_questions_rejects_empty_files(monkeypatch):
    class FakeKnowledgeBase:
        async def get_database_info(self, kb_id: str, include_files: bool = False) -> dict:
            return {"name": "empty knowledge base", "kb_type": "milvus", "files": {}}

    monkeypatch.setattr(sq, "knowledge_base", FakeKnowledgeBase())
    monkeypatch.setattr(
        sq.KnowledgeBaseFactory,
        "get_kb_class",
        lambda _kb_type: SimpleNamespace(supports_documents=True),
    )

    with pytest.raises(HTTPException) as exc_info:
        await sq.generate_database_sample_questions("kb_1")

    assert exc_info.value.status_code == 400
    assert "Không có file" in exc_info.value.detail


@pytest.mark.asyncio
async def test_generate_database_sample_questions_saves_and_returns_questions(monkeypatch):
    saved: dict = {}

    class FakeKnowledgeBase:
        async def get_database_info(self, kb_id: str, include_files: bool = False) -> dict:
            return {
                "name": "Test knowledge base",
                "kb_type": "milvus",
                "files": {"file_1": {"filename": "demo.md", "file_type": "md"}},
            }

    class FakeModel:
        async def call(self, messages, stream: bool = False):
            assert messages[0]["role"] == "system"
            assert "demo.md" in messages[1]["content"]
            return SimpleNamespace(content='{"questions": ["How to use demo?"]}')

    class FakeRepository:
        async def update(self, kb_id: str, data: dict) -> None:
            saved[kb_id] = data["sample_questions"]

        async def get_by_kb_id(self, kb_id: str):
            return SimpleNamespace(name="Test knowledge base", sample_questions=saved.get(kb_id))

    monkeypatch.setattr(sq, "knowledge_base", FakeKnowledgeBase())
    monkeypatch.setattr(
        sq.KnowledgeBaseFactory,
        "get_kb_class",
        lambda _kb_type: SimpleNamespace(supports_documents=True),
    )
    monkeypatch.setattr(sq, "select_model", lambda model_spec: FakeModel())
    monkeypatch.setattr(sq, "KnowledgeBaseRepository", lambda: FakeRepository())

    generated = await sq.generate_database_sample_questions("kb_1", count=1)
    stored = await sq.get_database_sample_questions("kb_1")

    assert generated["questions"] == ["How to use demo?"]
    assert generated["count"] == 1
    assert stored["questions"] == ["How to use demo?"]


@pytest.mark.asyncio
async def test_generate_database_sample_questions_maps_invalid_json(monkeypatch):
    class FakeKnowledgeBase:
        async def get_database_info(self, kb_id: str, include_files: bool = False) -> dict:
            return {
                "name": "Test knowledge base",
                "kb_type": "milvus",
                "files": {"file_1": {"filename": "demo.md", "file_type": "md"}},
            }

    class FakeModel:
        async def call(self, messages, stream: bool = False):
            return SimpleNamespace(content="not json")

    monkeypatch.setattr(sq, "knowledge_base", FakeKnowledgeBase())
    monkeypatch.setattr(
        sq.KnowledgeBaseFactory,
        "get_kb_class",
        lambda _kb_type: SimpleNamespace(supports_documents=True),
    )
    monkeypatch.setattr(sq, "select_model", lambda model_spec: FakeModel())

    with pytest.raises(HTTPException) as exc_info:
        await sq.generate_database_sample_questions("kb_1")

    assert exc_info.value.status_code == 500
    assert "Lỗi định dạng trả về từ AI" in exc_info.value.detail
