import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from yuxi.storage.postgres.models_business import AuditLog
from yuxi.storage.postgres.audit_repository import AuditLogRepository

@pytest.fixture
def mock_db_session():
    return AsyncMock()

@pytest.mark.asyncio
async def test_audit_log_hash_chain_creation(mock_db_session):
    repo = AuditLogRepository(mock_db_session)
    
    # Mock _get_last_hash to return a genesis hash
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = "GENESIS_HASH"
    mock_db_session.execute.return_value = mock_result
    
    audit_log = await repo.create_audit_log(
        uid="user123",
        raw_query="What is the policy?",
        conversation_id="conv_1",
        request_id="req_1",
        response_content="The policy is ABC.",
        source_refs=[{"chunk_id": "c1", "file_id": "f1"}],
        grounding_scores={"score": 0.95}
    )
    
    assert audit_log.prev_hash == "GENESIS_HASH"
    assert audit_log.log_hash is not None
    assert audit_log.uid == "user123"
    
    # Verify flush was called
    mock_db_session.add.assert_called_once_with(audit_log)
    mock_db_session.flush.assert_called_once()

@pytest.mark.asyncio
async def test_verify_chain_success(mock_db_session):
    repo = AuditLogRepository(mock_db_session)
    
    # Create two valid linked logs
    from yuxi.utils.datetime_utils import utc_now_naive
    now = utc_now_naive()
    
    log1 = AuditLog(
        id=1,
        uid="u1",
        raw_query="q1",
        response_content="r1",
        source_refs=None,
        grounding_scores=None,
        created_at=now,
        prev_hash=None,
    )
    log1.log_hash = repo._compute_hash(log1.uid, log1.raw_query, log1.response_content, None, None, log1.created_at.isoformat(), log1.prev_hash)
    
    log2 = AuditLog(
        id=2,
        uid="u2",
        raw_query="q2",
        response_content="r2",
        source_refs=None,
        grounding_scores=None,
        created_at=now,
        prev_hash=log1.log_hash,
    )
    log2.log_hash = repo._compute_hash(log2.uid, log2.raw_query, log2.response_content, None, None, log2.created_at.isoformat(), log2.prev_hash)
    
    # Mock the execute return for verify_chain
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [log1, log2]
    mock_db_session.execute.return_value = mock_result
    
    is_valid = await repo.verify_chain()
    assert is_valid is True

@pytest.mark.asyncio
async def test_verify_chain_broken_by_tampering(mock_db_session):
    repo = AuditLogRepository(mock_db_session)
    
    from yuxi.utils.datetime_utils import utc_now_naive
    now = utc_now_naive()
    
    log1 = AuditLog(
        id=1,
        uid="u1",
        raw_query="q1",
        response_content="r1",
        created_at=now,
        prev_hash=None,
    )
    log1.log_hash = repo._compute_hash(log1.uid, log1.raw_query, log1.response_content, None, None, log1.created_at.isoformat(), log1.prev_hash)
    
    log2 = AuditLog(
        id=2,
        uid="u2",
        raw_query="q2",
        response_content="r2",
        created_at=now,
        prev_hash=log1.log_hash,
    )
    log2.log_hash = repo._compute_hash(log2.uid, log2.raw_query, log2.response_content, None, None, log2.created_at.isoformat(), log2.prev_hash)
    
    # Simulate an attacker changing log1's content but not updating log2's prev_hash (which they can't without breaking the rest of the chain)
    log1.response_content = "TAMPERED_CONTENT"
    
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [log1, log2]
    mock_db_session.execute.return_value = mock_result
    
    is_valid = await repo.verify_chain()
    
    # Because log1's content changed, its log_hash re-computed during verification will NOT match its stored log_hash.
    # Therefore, the chain is invalid.
    assert is_valid is False
