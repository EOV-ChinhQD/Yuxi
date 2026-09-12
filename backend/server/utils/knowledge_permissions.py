"""FastAPI dependency adapter for knowledge base resource permissions."""

from fastapi import Depends, HTTPException

from server.utils.auth_middleware import get_admin_user
from yuxi.knowledge.read_models import KnowledgeBaseDetail
from yuxi.knowledge.runtime import knowledge_base
from yuxi.permissions import (
    ResourcePermission,
    ResourcePermissionDenied,
    require_knowledge_base_permission,
)
from yuxi.storage.postgres.models_business import User


async def ensure_knowledge_base_permission(
    kb_id: str,
    current_user: User,
    required: ResourcePermission,
) -> KnowledgeBaseDetail:
    """Load knowledge base and verify effective resource permission for current user."""

    db_info = await knowledge_base.get_database_info(kb_id)
    if not db_info:
        raise HTTPException(status_code=404, detail=f"Knowledge base {kb_id} does not exist")

    try:
        require_knowledge_base_permission(current_user, db_info, required)
    except ResourcePermissionDenied as error:
        raise HTTPException(status_code=403, detail="Permission denied for this knowledge base") from error
    return db_info


async def require_knowledge_base_read(
    kb_id: str,
    current_user: User = Depends(get_admin_user),
) -> User:
    """Verify administrator read permission for specified knowledge base."""

    await ensure_knowledge_base_permission(kb_id, current_user, ResourcePermission.READ)
    return current_user


async def require_knowledge_base_manage(
    kb_id: str,
    current_user: User = Depends(get_admin_user),
) -> User:
    """Verify administrator management permission for specified knowledge base."""

    await ensure_knowledge_base_permission(kb_id, current_user, ResourcePermission.MANAGE)
    return current_user
