import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from yuxi.knowledge.manager import KnowledgeBaseManager

@pytest.mark.asyncio
async def test_kb_access_control_allowed(tmp_path):
    # Mock UserRepository and User
    mock_user = MagicMock()
    mock_user.uid = "user-123"
    mock_user.role = "user"
    mock_user.department_id = 1
    
    mock_user_repo = MagicMock()
    mock_user_repo.get_by_uid = AsyncMock(return_value=mock_user)
    
    # Mock check_accessible
    kb_manager = KnowledgeBaseManager(str(tmp_path))
    kb_manager.check_accessible = AsyncMock(return_value=True)
    
    # Mock _get_kb_for_database to return a mock KB instance
    mock_kb_instance = AsyncMock()
    mock_kb_instance.aquery = AsyncMock(return_value="mocked query result")
    kb_manager._get_kb_for_database = AsyncMock(return_value=mock_kb_instance)
    
    with patch("yuxi.repositories.user_repository.UserRepository", return_value=mock_user_repo):
        result = await kb_manager.aquery("test query", "kb-1", caller_uid="user-123")
        assert result == "mocked query result"
        kb_manager.check_accessible.assert_called_once_with(
            {"uid": "user-123", "role": "user", "department_id": 1},
            "kb-1"
        )
        mock_kb_instance.aquery.assert_called_once_with("test query", "kb-1")

@pytest.mark.asyncio
async def test_kb_access_control_denied(tmp_path):
    mock_user = MagicMock()
    mock_user.uid = "user-123"
    mock_user.role = "user"
    mock_user.department_id = 1
    
    mock_user_repo = MagicMock()
    mock_user_repo.get_by_uid = AsyncMock(return_value=mock_user)
    
    kb_manager = KnowledgeBaseManager(str(tmp_path))
    kb_manager.check_accessible = AsyncMock(return_value=False)
    
    mock_kb_instance = AsyncMock()
    kb_manager._get_kb_for_database = AsyncMock(return_value=mock_kb_instance)
    
    with patch("yuxi.repositories.user_repository.UserRepository", return_value=mock_user_repo):
        with pytest.raises(PermissionError) as exc_info:
            await kb_manager.aquery("test query", "kb-1", caller_uid="user-123")
        assert "does not have permission" in str(exc_info.value)
        kb_manager.check_accessible.assert_called_once()
        mock_kb_instance.aquery.assert_not_called()
