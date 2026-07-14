from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from server.utils.auth_middleware import get_db, get_current_user
from yuxi.storage.postgres.models_business import AuditLog, User
from yuxi.storage.postgres.audit_repository import AuditLogRepository
from yuxi.utils import logger

router = APIRouter(
    prefix="/audit",
    tags=["Audit Log"],
)

def verify_audit_access(user: User = Depends(get_current_user)) -> User:
    """RBAC check for audit access."""
    if user.role not in ["superadmin", "compliance_officer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Requires superadmin or compliance_officer role",
        )
    return user

@router.get("/logs")
async def get_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(verify_audit_access),
) -> Any:
    """Fetch audit logs (Admin/Compliance only)."""
    try:
        stmt = select(AuditLog).order_by(AuditLog.id.desc()).offset(skip).limit(limit)
        if user_id:
            stmt = stmt.where(AuditLog.uid == user_id)
            
        result = await db.execute(stmt)
        logs = result.scalars().all()
        
        return {
            "status": "success",
            "data": [log.to_dict() for log in logs]
        }
    except Exception as e:
        logger.error(f"Error fetching audit logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch audit logs",
        )

@router.get("/verify-chain")
async def verify_audit_chain(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(verify_audit_access),
) -> Any:
    """Verify the integrity of the audit log hash chain."""
    try:
        audit_repo = AuditLogRepository(db)
        is_valid = await audit_repo.verify_chain()
        
        return {
            "status": "success",
            "is_valid": is_valid
        }
    except Exception as e:
        logger.error(f"Error verifying audit chain: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify audit chain",
        )
