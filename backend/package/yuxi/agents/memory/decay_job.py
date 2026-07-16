import datetime
from sqlalchemy import update
from yuxi.storage.postgres.manager import pg_manager
from yuxi.storage.postgres.models_business import UserEpisodicMemory
from yuxi.utils.logging_config import logger


async def run_episodic_decay_job() -> int:
    """
    Quét và tự động lưu trữ (is_archived=True) các Episodic Memory cũ hơn 90 ngày.
    Trả về số lượng bản ghi đã được lưu trữ.
    """
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=90)
    async with pg_manager.get_async_session_context() as session:
        try:
            stmt = (
                update(UserEpisodicMemory)
                .where(UserEpisodicMemory.timestamp < cutoff_date, UserEpisodicMemory.is_archived == False)
                .values(is_archived=True)
            )
            result = await session.execute(stmt)
            await session.commit()
            count = result.rowcount
            logger.info(f"Episodic decay job completed. Archived {count} old memories.")
            return count
        except Exception as e:
            logger.error(f"Error during episodic decay job: {e}", exc_info=True)
            await session.rollback()
            return 0
