import pytest
import asyncio
import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select, update, text

# Mock Milvus connection before importing memory tasks to avoid live connections
from yuxi.agents.memory.milvus_store import MilvusMemoryStore
MilvusMemoryStore._init_connection = MagicMock()
MilvusMemoryStore.get_or_create_collection = MagicMock()

from yuxi.storage.postgres.models_business import (
    UserEpisodicMemory,
    UserProceduralMemory,
    RejectedMemoryLog,
)
from yuxi.agents.memory.extractor import MemoryExtractorTask
from yuxi.agents.memory.injector import MemoryInjector
from yuxi.agents.memory.decay_job import run_episodic_decay_job

# --- Mock LLM Responses ---
class MockLLMResponse:
    def __init__(self, content: str):
        self.content = content

# --- Heuristic Filter Tests ---
def test_heuristic_filter():
    task = MemoryExtractorTask()
    # Should ignore greetings and common technical queries
    assert task._should_ignore_content("hello ad") is True
    assert task._should_ignore_content("cảm ơn bạn nhé") is True
    assert task._should_ignore_content("hướng dẫn cài đặt docker trên ubuntu") is True
    assert task._should_ignore_content("làm sao để debug lỗi python") is True
    assert task._should_ignore_content("   ") is True

    # Should not ignore actual facts about the user
    assert task._should_ignore_content("Tôi làm việc ở bộ phận Kế toán") is False
    assert task._should_ignore_content("Hôm nay tôi đã ký được hợp đồng lớn") is False
    assert task._should_ignore_content("Tôi thích học lập trình Go và Python") is False

# --- Memory Extractor Task Tests ---
@pytest.mark.asyncio
async def test_memory_extractor_confidence_gate_and_log(monkeypatch):
    # Mock Milvus Memory Store
    mock_milvus = MagicMock()
    mock_milvus.search_facts = AsyncMock(return_value=[])
    mock_milvus.insert_fact = AsyncMock()
    
    # Mock LLM to return low confidence semantic fact
    llm_output = {
        "semantic": [{"fact_text": "Thích ăn kem", "confidence_score": 0.5}],
        "episodic": [{"event_summary": "Ký hợp đồng", "sentiment_score": 0.8, "confidence_score": 0.9}],
        "procedural": []
    }
    
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MockLLMResponse(content=json_dumps(llm_output)))

    # Mock DB Session
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars = MagicMock(return_value=MagicMock(all=lambda: []))
    mock_db.execute.return_value = mock_result
    
    # Instantiate extractor and apply mocks
    task = MemoryExtractorTask()
    task.milvus_store = mock_milvus
    monkeypatch.setattr(task, "_get_high_reasoning_model", lambda: mock_llm)

    # We mock get_async_session_context to yield our mock_db session
    @asynccontextmanager
    async def fake_session_context():
        yield mock_db

    from yuxi.storage.postgres.manager import pg_manager
    monkeypatch.setattr(pg_manager, "get_async_session_context", fake_session_context)

    messages = [{"role": "user", "content": "Hôm nay tôi vừa ký hợp đồng và tôi thích ăn kem"}]
    
    await task.extract_memory_from_dialogue("user-123", "thread-abc", messages)

    # 1. Verification of advisory lock
    lock_call_found = False
    for call in mock_db.execute.call_args_list:
        args, kwargs = call
        if args and hasattr(args[0], "text") and "pg_advisory_xact_lock" in args[0].text:
            if len(args) > 1 and args[1] == {"lock_id": hash("user-123") % (2**31 - 1)}:
                lock_call_found = True
                break
    assert lock_call_found is True

    # 2. Verification of confidence gate for Semantic fact (low confidence -> RejectedMemoryLog)
    # Check if a RejectedMemoryLog was added to Postgres session
    added_objects = [args[0] for args, _ in mock_db.add.call_args_list]
    rejected_logs = [obj for obj in added_objects if isinstance(obj, RejectedMemoryLog)]
    assert len(rejected_logs) == 1
    assert rejected_logs[0].raw_fact == "Thích ăn kem"
    assert rejected_logs[0].confidence_score == 0.5
    assert rejected_logs[0].memory_type == "semantic"

    # 3. Verification of confidence gate for Episodic fact (high confidence -> UserEpisodicMemory)
    episodic_mems = [obj for obj in added_objects if isinstance(obj, UserEpisodicMemory)]
    assert len(episodic_mems) == 1
    assert episodic_mems[0].event_summary == "Ký hợp đồng"
    assert episodic_mems[0].sentiment_score == 0.8
    assert episodic_mems[0].confidence_score == 0.9

    # 4. Verify Milvus insert wasn't called for low confidence
    mock_milvus.insert_fact.assert_not_called()

# --- Semantic Fact Conflict Resolution (Soft Update) ---
@pytest.mark.asyncio
async def test_semantic_fact_conflict_resolution(monkeypatch):
    # Mock Milvus memory store returning a conflicting fact (distance > 0.85)
    mock_milvus = MagicMock()
    mock_milvus.search_facts = AsyncMock(return_value=[{
        "id": "old-fact-id",
        "fact_text": "Thích Python",
        "distance": 0.91  # High similarity (conflict)
    }])
    mock_milvus.deactivate_fact = AsyncMock()
    mock_milvus.insert_fact = AsyncMock()

    llm_output = {
        "semantic": [{"fact_text": "Thích học lập trình Python", "confidence_score": 0.9}],
        "episodic": [],
        "procedural": []
    }
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MockLLMResponse(content=json_dumps(llm_output)))

    mock_db = AsyncMock()
    # Mock select query for active rules to return empty list
    mock_db.execute.return_value = MagicMock(scalars=lambda: MagicMock(all=lambda: []))

    task = MemoryExtractorTask()
    task.milvus_store = mock_milvus
    monkeypatch.setattr(task, "_get_high_reasoning_model", lambda: mock_llm)

    @asynccontextmanager
    async def fake_session_context():
        yield mock_db

    from yuxi.storage.postgres.manager import pg_manager
    monkeypatch.setattr(pg_manager, "get_async_session_context", fake_session_context)

    messages = [{"role": "user", "content": "Tôi thích học lập trình Python"}]
    await task.extract_memory_from_dialogue("user-123", "thread-abc", messages)

    # Check Milvus deactivation and insert was triggered
    mock_milvus.deactivate_fact.assert_called_once()
    args, kwargs = mock_milvus.deactivate_fact.call_args
    assert args[0] == "user-123"
    assert args[1] == "old-fact-id"
    
    mock_milvus.insert_fact.assert_called_once()

# --- Procedural Memory Rule Override ---
@pytest.mark.asyncio
async def test_procedural_memory_rule_override(monkeypatch):
    mock_milvus = MagicMock()
    mock_milvus.search_facts = AsyncMock(return_value=[])

    # LLM outputs procedural rule that overrides rule with id 15
    llm_output = {
        "semantic": [],
        "episodic": [],
        "procedural": [{"rule_text": "Không dùng emoji", "confidence_score": 0.95, "supersedes_id": 15}]
    }
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MockLLMResponse(content=json_dumps(llm_output)))

    mock_db = AsyncMock()
    
    # Mocking select query for active rules
    fake_old_rule = UserProceduralMemory(id=15, uid="user-123", rule_text="Dùng emoji thân thiện", is_active=True)
    
    # Setup database mock executions
    mock_result = MagicMock()
    mock_result.scalars = MagicMock(return_value=MagicMock(all=lambda: [fake_old_rule]))
    mock_result.scalar_one_or_none = MagicMock(return_value=fake_old_rule)
    mock_db.execute.return_value = mock_result

    task = MemoryExtractorTask()
    task.milvus_store = mock_milvus
    monkeypatch.setattr(task, "_get_high_reasoning_model", lambda: mock_llm)

    @asynccontextmanager
    async def fake_session_context():
        yield mock_db

    from yuxi.storage.postgres.manager import pg_manager
    monkeypatch.setattr(pg_manager, "get_async_session_context", fake_session_context)

    messages = [{"role": "user", "content": "Không dùng emoji nữa nhé"}]
    await task.extract_memory_from_dialogue("user-123", "thread-abc", messages)

    # Verify that the old rule was marked inactive (is_active = False)
    assert fake_old_rule.is_active is False

    # Verify new rule was added
    added_objects = [args[0] for args, _ in mock_db.add.call_args_list]
    new_rules = [obj for obj in added_objects if isinstance(obj, UserProceduralMemory)]
    assert len(new_rules) == 1
    assert new_rules[0].rule_text == "Không dùng emoji"
    assert new_rules[0].is_active is True

# --- Cross User Isolation & Memory Injector Tests ---
@pytest.mark.asyncio
async def test_memory_injector_procedural_retrieval(monkeypatch):
    # Mock Milvus memory store returning facts
    mock_milvus = MagicMock()
    mock_milvus.search_facts = AsyncMock(return_value=[
        {"fact_text": "Học Go", "distance": 0.9}
    ])

    mock_db = AsyncMock()
    
    # Mock Procedural Rules retrieval
    proc_rules = [
        UserProceduralMemory(rule_text="Luôn xưng là Mèo"),
        UserProceduralMemory(rule_text="Trả lời ngắn gọn")
    ]
    
    # Mock Episodic Events retrieval
    episodic_events = [
        UserEpisodicMemory(event_summary="Đã ký hợp đồng HD-123")
    ]

    # Setup database query results
    mock_result = MagicMock()
    # First execute: procedural rules. Second execute: episodic events
    mock_result.scalars = MagicMock(return_value=MagicMock(all=lambda: proc_rules))
    mock_db.execute.return_value = mock_result

    injector = MemoryInjector()
    injector.milvus_store = mock_milvus

    memories = await injector.get_memories_for_prompt(mock_db, "user-123", "Hỏi thăm hợp đồng")

    # Verify correct format of retrieved memories
    assert len(memories["procedural_rules"]) == 2
    assert memories["procedural_rules"][0] == "Luôn xưng là Mèo"
    assert memories["procedural_rules"][1] == "Trả lời ngắn gọn"
    
    assert len(memories["semantic_facts"]) == 1
    assert memories["semantic_facts"][0] == "Học Go"

# --- Cross User Isolation Test ---
@pytest.mark.asyncio
async def test_cross_user_isolation(monkeypatch):
    # Verify that when querying memories for a specific user, we strictly pass their uid to database and Milvus
    mock_milvus = MagicMock()
    mock_milvus.search_facts = AsyncMock(return_value=[])

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars = MagicMock(return_value=MagicMock(all=lambda: []))
    mock_db.execute.return_value = mock_result

    injector = MemoryInjector()
    injector.milvus_store = mock_milvus

    # Query memories for user-A
    await injector.get_memories_for_prompt(mock_db, "user-A", "truy vấn thử nghiệm")

    # 1. Verify Milvus search was called with "user-A"
    mock_milvus.search_facts.assert_called_once_with("user-A", "truy vấn thử nghiệm", limit=5)

    # 2. Verify Postgres queries filtered by uid == "user-A"
    execute_calls = mock_db.execute.call_args_list
    assert len(execute_calls) >= 1
    
    for call in execute_calls:
        args, kwargs = call
        stmt = args[0]
        # Compile statement to check bound parameters
        compiled = stmt.compile()
        assert "user-A" in compiled.params.values()

# --- Decay Job Test ---
@pytest.mark.asyncio
async def test_decay_job(monkeypatch):
    mock_db = AsyncMock()
    mock_result = MagicMock(rowcount=3)
    mock_db.execute.return_value = mock_result

    @asynccontextmanager
    async def fake_session_context():
        yield mock_db

    from yuxi.storage.postgres.manager import pg_manager
    monkeypatch.setattr(pg_manager, "get_async_session_context", fake_session_context)

    archived_count = await run_episodic_decay_job()
    assert archived_count == 3
    
    # Verify correct query statement execution (soft update is_archived = True)
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()

# --- Helper Utilities for mock formatting ---
def json_dumps(data: dict) -> str:
    import json
    return json.dumps(data)

def patch_text_expr(sql_str: str):
    # Returns helper to compare text objects
    return text(sql_str)

from contextlib import asynccontextmanager
