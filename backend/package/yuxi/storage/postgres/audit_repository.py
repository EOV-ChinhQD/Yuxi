import hashlib
import json
import logging

from sqlalchemy import desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from yuxi.storage.postgres.models_business import AuditLog

logger = logging.getLogger(__name__)


class AuditLogRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _compute_hash(
        self,
        uid: str,
        raw_query: str,
        response_content: str | None,
        source_refs: list[dict] | None,
        grounding_scores: dict | None,
        created_at_iso: str,
        prev_hash: str | None,
    ) -> str:
        """Compute SHA-256 hash of the audit log record."""
        # Convert JSON fields to stable strings
        source_refs_str = json.dumps(source_refs, sort_keys=True) if source_refs else ""
        grounding_scores_str = json.dumps(grounding_scores, sort_keys=True) if grounding_scores else ""

        # Combine all fields
        data_to_hash = (
            f"{uid}|{raw_query}|{response_content or ''}|"
            f"{source_refs_str}|{grounding_scores_str}|"
            f"{created_at_iso}|{prev_hash or 'GENESIS'}"
        )

        return hashlib.sha256(data_to_hash.encode("utf-8")).hexdigest()

    async def _get_last_hash(self) -> str | None:
        """Get the hash of the most recent audit log entry."""
        stmt = select(AuditLog.log_hash).order_by(desc(AuditLog.id)).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_audit_log(
        self,
        uid: str,
        raw_query: str,
        conversation_id: str | None = None,
        request_id: str | None = None,
        response_content: str | None = None,
        source_refs: list[dict] | None = None,
        grounding_scores: dict | None = None,
    ) -> AuditLog:
        """
        Create a tamper-proof audit log entry.
        Note: In a true outbox pattern, this might be broken into two steps.
        For simplicity and consistency with the DB constraints (no UPDATE allowed),
        we create it once with all available data.
        """
        prev_hash = await self._get_last_hash()

        # Create a new AuditLog instance to get the default created_at
        audit_log = AuditLog(
            uid=uid,
            conversation_id=conversation_id,
            request_id=request_id,
            raw_query=raw_query,
            response_content=response_content,
            source_refs=source_refs,
            grounding_scores=grounding_scores,
        )

        # In SQLAlchemy, default values are not available until flushed or explicitly set.
        # So we use utc_now_naive directly if not set by DB yet.
        from yuxi.utils.datetime_utils import utc_now_naive

        if not audit_log.created_at:
            audit_log.created_at = utc_now_naive()

        created_at_iso = audit_log.created_at.isoformat()

        audit_log.prev_hash = prev_hash
        audit_log.log_hash = self._compute_hash(
            uid=uid,
            raw_query=raw_query,
            response_content=response_content,
            source_refs=source_refs,
            grounding_scores=grounding_scores,
            created_at_iso=created_at_iso,
            prev_hash=prev_hash,
        )

        self.db.add(audit_log)
        try:
            await self.db.flush()
        except Exception as e:
            logger.error(f"[Audit] Failed to insert audit log: {e}")
            raise

        return audit_log

    async def verify_chain(self) -> bool:
        """
        Verify the integrity of the entire audit log hash chain.
        Returns True if intact, False if tampering detected.
        """
        stmt = select(AuditLog).order_by(AuditLog.id)
        result = await self.db.execute(stmt)
        logs = result.scalars().all()

        expected_prev_hash = None
        for log in logs:
            if expected_prev_hash is not None and log.prev_hash != expected_prev_hash:
                logger.error(f"[Audit] Chain broken at ID {log.id}: prev_hash mismatch.")
                return False

            computed_hash = self._compute_hash(
                uid=log.uid,
                raw_query=log.raw_query,
                response_content=log.response_content,
                source_refs=log.source_refs,
                grounding_scores=log.grounding_scores,
                created_at_iso=log.created_at.isoformat(),
                prev_hash=log.prev_hash,
            )

            if computed_hash != log.log_hash:
                logger.error(f"[Audit] Chain broken at ID {log.id}: log_hash mismatch.")
                return False

            expected_prev_hash = log.log_hash

        return True
