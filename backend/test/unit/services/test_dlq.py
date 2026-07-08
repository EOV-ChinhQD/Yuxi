from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from yuxi.services.run_worker import _record_failed_job

@pytest.mark.asyncio
async def test_record_failed_job():
    mock_failed_job_instance = MagicMock()
    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_context)
    mock_context.__aexit__ = AsyncMock()

    # Mock database session commit and add
    mock_context.add = MagicMock()
    mock_context.commit = AsyncMock()

    with patch("yuxi.storage.postgres.manager.pg_manager.get_async_session_context", return_value=mock_context), \
         patch("yuxi.storage.postgres.models_business.FailedJob", return_value=mock_failed_job_instance) as mock_model_cls:
        await _record_failed_job(
            ctx={},
            job_type="process_agent_run",
            job_id="job_123",
            payload={"run_id": "run_123"},
            error_type="ValueError",
            error_message="Test error",
            retry_count=2
        )
    
    mock_model_cls.assert_called_once_with(
        job_type="process_agent_run",
        job_id="job_123",
        payload={"run_id": "run_123"},
        error_type="ValueError",
        error_message="Test error",
        retry_count=2,
        status="failed"
    )
    mock_context.add.assert_called_once_with(mock_failed_job_instance)
    mock_context.commit.assert_called_once()
