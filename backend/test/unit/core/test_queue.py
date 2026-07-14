import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from yuxi.core.queue import QueueClient, RAGWorker

@pytest.mark.asyncio
async def test_queue_publish():
    mock_redis = AsyncMock()
    mock_redis.xadd.return_value = "12345-0"

    async def mock_get_redis():
        return mock_redis

    with patch("yuxi.core.queue.get_async_redis_client", mock_get_redis):
        msg_id = await QueueClient.publish("TEST_EVENT", {"data": "test_value"})
        assert msg_id == "12345-0"
        mock_redis.xadd.assert_called_once()
        assert mock_redis.xadd.call_args[0][0] == "yuxi:rag:stream"
        assert mock_redis.xadd.call_args[0][1]["event_type"] == "TEST_EVENT"

@pytest.mark.asyncio
async def test_worker_consume_and_handler():
    mock_redis = AsyncMock()
    
    # Mock xgroup_create to pass
    mock_redis.xgroup_create.return_value = True
    
    # Mock xreadgroup to return one message first time, and None after
    call_count = 0
    async def mock_xreadgroup(*args, **kwargs):
        nonlocal call_count
        if call_count == 0:
            call_count += 1
            # Return format: [ (stream_name, [ (msg_id, fields) ]) ]
            return [("yuxi:rag:stream", [("12345-0", {"event_type": b"MY_EVENT", "payload": b'{"hello": "world"}'})])]
        else:
            # Sleep a bit then cancel/return empty to avoid infinite loop
            await asyncio.sleep(0.1)
            return []

    mock_redis.xreadgroup = mock_xreadgroup
    mock_redis.xack.return_value = 1

    async def mock_get_redis():
        return mock_redis

    worker = RAGWorker(stream_name="test_stream")
    
    handler_called = asyncio.Event()
    received_payload = {}
    
    async def my_handler(payload):
        nonlocal received_payload
        received_payload.update(payload)
        handler_called.set()

    worker.register_handler("MY_EVENT", my_handler)

    with patch("yuxi.core.queue.get_async_redis_client", mock_get_redis):
        # Start worker as background task
        task = asyncio.create_task(worker.start())
        
        # Wait for handler to be executed
        await asyncio.wait_for(handler_called.wait(), timeout=2.0)
        
        # Stop worker
        worker.stop()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    assert received_payload == {"hello": "world"}
    mock_redis.xack.assert_called_once()
