import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from yuxi.knowledge.grounding.nli_verifier import NLIVerifier, get_nli_pipeline


def test_split_into_claims():
    text = "Hệ thống RAG hoạt động tốt. Tuy nhiên, nó vẫn có thể bị ảo giác! Bạn có muốn biết thêm không? Chào bạn."
    claims = NLIVerifier.split_into_claims(text)
    
    assert "Hệ thống RAG hoạt động tốt." in claims
    assert "Tuy nhiên, nó vẫn có thể bị ảo giác!" in claims
    # Sentences too short or containing greeting should be ignored
    assert "Chào bạn." not in claims
    assert "Bạn có muốn biết thêm không?" in claims


@pytest.mark.asyncio
async def test_verify_claims_mocked_pipeline(monkeypatch):
    # Mock the pipeline return output
    mock_pipeline = MagicMock()
    mock_pipeline.return_value = {
        "labels": ["Hệ thống RAG hoạt động tốt.", "Nó bị ảo giác."],
        "scores": [0.95, 0.15]
    }
    
    monkeypatch.setattr("yuxi.knowledge.grounding.nli_verifier.get_nli_pipeline", lambda: mock_pipeline)
    
    claims = ["Hệ thống RAG hoạt động tốt.", "Nó bị ảo giác."]
    chunks = ["Hệ thống RAG hoạt động rất tốt trên cơ sở dữ liệu thực tế."]
    
    results = await NLIVerifier.verify_claims(claims, chunks)
    
    assert len(results) == 2
    # First claim (score 0.95) should be entailment
    assert results[0]["claim"] == "Hệ thống RAG hoạt động tốt."
    assert results[0]["score"] == 0.95
    assert results[0]["label"] == "entailment"
    
    # Second claim (score 0.15) should be contradiction
    assert results[1]["claim"] == "Nó bị ảo giác."
    assert results[1]["score"] == 0.15
    assert results[1]["label"] == "contradiction"


@pytest.mark.asyncio
async def test_verify_claims_graceful_timeout(monkeypatch):
    # Mock NLI processing to sleep longer than timeout
    async def mock_run_batch_nli_slow(*args, **kwargs):
        await asyncio.sleep(2.0)
        return []
        
    import time
    monkeypatch.setattr(NLIVerifier, "_run_batch_nli", lambda cls, context: time.sleep(2.0))
    
    claims = ["Hệ thống RAG hoạt động tốt."]
    chunks = ["Context"]
    
    # Run with a very small timeout to force timeout exception
    results = await NLIVerifier.verify_claims(claims, chunks, timeout=0.1)
    
    # Check that we degrade gracefully on timeout instead of raising exception
    assert len(results) == 1
    assert results[0]["claim"] == "Hệ thống RAG hoạt động tốt."
    assert results[0]["score"] == 0.5
    assert results[0]["label"] == "neutral"
    assert results[0]["error"] == "timeout"
