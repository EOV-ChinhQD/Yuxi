import asyncio
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from yuxi.models.embed import OtherEmbedding, EMBEDDING_RATE_LIMIT_MAX_RETRIES

@pytest.fixture
def other_embedding():
    # Setup test env
    os.environ["EMBED_MAX_CONCURRENCY"] = "5"
    return OtherEmbedding(
        model="test-model",
        base_url="http://mock-test",
        api_key="sk-test",
        dimension=1536
    )

@pytest.mark.asyncio
async def test_aencode_retry_429_then_success(other_embedding):
    messages = ["test msg"]
    mock_success_response = MagicMock(status_code=200)
    mock_success_response.json.return_value = {"data": [{"embedding": [0.1, 0.2]}]}

    mock_429_response = httpx.Response(status_code=429, request=httpx.Request("POST", "http://mock"))
    mock_429_error = httpx.HTTPStatusError("429 Too Many Requests", request=mock_429_response.request, response=mock_429_response)

    # First call returns 429, second call returns success
    side_effects = [mock_429_error, mock_success_response]

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = side_effects
        
        # We also need to patch asyncio.sleep to not actually wait in tests
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await other_embedding.aencode(messages)
            
            assert result == [[0.1, 0.2]]
            assert mock_post.call_count == 2
            assert mock_sleep.call_count == 1

@pytest.mark.asyncio
async def test_aencode_retry_500_then_success(other_embedding):
    messages = ["test msg"]
    mock_success_response = MagicMock(status_code=200)
    mock_success_response.json.return_value = {"data": [{"embedding": [0.1, 0.2]}]}

    mock_500_response = httpx.Response(status_code=500, request=httpx.Request("POST", "http://mock"))
    mock_500_error = httpx.HTTPStatusError("500 Server Error", request=mock_500_response.request, response=mock_500_response)

    side_effects = [mock_500_error, mock_success_response]

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = side_effects
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await other_embedding.aencode(messages)
            
            assert result == [[0.1, 0.2]]
            assert mock_post.call_count == 2
            assert mock_sleep.call_count == 1

@pytest.mark.asyncio
async def test_aencode_retry_exhausted_429(other_embedding):
    messages = ["test msg"]
    
    mock_429_response = httpx.Response(status_code=429, request=httpx.Request("POST", "http://mock"))
    mock_429_error = httpx.HTTPStatusError("429 Too Many Requests", request=mock_429_response.request, response=mock_429_response)

    # Always return 429
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = mock_429_error
        
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(ValueError, match="Embedding async request failed"):
                await other_embedding.aencode(messages)
            
            # Should have called it max_retries + 1 times (initial call + retries)
            assert mock_post.call_count == EMBEDDING_RATE_LIMIT_MAX_RETRIES + 1
            assert mock_sleep.call_count == EMBEDDING_RATE_LIMIT_MAX_RETRIES

@pytest.mark.asyncio
async def test_aencode_fast_fail_401(other_embedding):
    messages = ["test msg"]
    
    mock_401_response = httpx.Response(status_code=401, request=httpx.Request("POST", "http://mock"))
    mock_401_error = httpx.HTTPStatusError("401 Unauthorized", request=mock_401_response.request, response=mock_401_response)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = mock_401_error
        
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(ValueError, match="Embedding async request failed"):
                await other_embedding.aencode(messages)
            
            # Should fail immediately without retrying
            assert mock_post.call_count == 1
            assert mock_sleep.call_count == 0
