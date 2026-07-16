import asyncio
import json
from typing import Any
from collections.abc import Callable
from yuxi.storage.redis import get_async_redis_client
from yuxi.utils.logging_config import logger


class QueueClient:
    """MQ Client trừu tượng hóa việc giao tiếp với Redis Streams."""

    @classmethod
    async def publish(cls, event_type: str, payload: dict, stream_name: str = "yuxi:rag:stream") -> str:
        try:
            redis = await get_async_redis_client()
            data = {"event_type": event_type, "payload": json.dumps(payload)}
            # Thêm message vào Redis Stream
            msg_id = await redis.xadd(stream_name, data)
            logger.info(f"Published event '{event_type}' with message ID {msg_id} to {stream_name}")
            return msg_id
        except Exception as e:
            logger.error(f"Failed to publish event to Redis Stream: {e}")
            raise


class RAGWorker:
    """Worker đa nhiệm lắng nghe Redis Streams và xử lý background RAG tasks (với cơ chế Retry & DLQ)."""

    def __init__(
        self,
        group_name: str = "rag_group",
        consumer_name: str = "worker_1",
        stream_name: str = "yuxi:rag:stream",
        max_retries: int = 3,
    ):
        self.stream_name = stream_name
        self.group_name = group_name
        self.consumer_name = consumer_name
        self.max_retries = max_retries
        self.is_running = False
        self._handlers: dict[str, Callable[[dict], Any]] = {}

    def register_handler(self, event_type: str, handler: Callable[[dict], Any]) -> None:
        self._handlers[event_type] = handler

    async def start(self) -> None:
        self.is_running = True
        redis = await get_async_redis_client()

        # Khởi tạo consumer group nếu chưa có
        try:
            await redis.xgroup_create(self.stream_name, self.group_name, id="0", mkstream=True)
            logger.info(f"Created Redis Streams group '{self.group_name}' for stream '{self.stream_name}'")
        except Exception:
            # Group đã tồn tại
            pass

        logger.info(f"RAG background worker started (consumer: {self.consumer_name})")

        while self.is_running:
            try:
                # Đọc tin nhắn từ group (block 1 giây)
                streams = await redis.xreadgroup(
                    self.group_name, self.consumer_name, {self.stream_name: ">"}, count=1, block=1000
                )
                if not streams:
                    continue

                for stream_name, messages in streams:
                    for msg_id, fields in messages:
                        # Decode message fields
                        event_type_bytes = fields.get(b"event_type") or fields.get("event_type")
                        payload_bytes = fields.get(b"payload") or fields.get("payload")

                        if not event_type_bytes or not payload_bytes:
                            continue

                        event_type = (
                            event_type_bytes.decode("utf-8")
                            if isinstance(event_type_bytes, bytes)
                            else str(event_type_bytes)
                        )
                        payload_str = (
                            payload_bytes.decode("utf-8") if isinstance(payload_bytes, bytes) else str(payload_bytes)
                        )

                        payload = json.loads(payload_str)
                        logger.info(f"Processing event '{event_type}' (id: {msg_id})")

                        # Tra cứu số lần thử lại bằng Redis key
                        retry_key = f"yuxi:rag:retry:{msg_id}"
                        retry_count_val = await redis.get(retry_key)
                        retry_count = int(retry_count_val) if retry_count_val else 0

                        # Dispatch xử lý
                        handler = self._handlers.get(event_type)
                        if handler:
                            try:
                                if asyncio.iscoroutinefunction(handler):
                                    await handler(payload)
                                else:
                                    handler(payload)
                                # Acknowledge tin nhắn sau khi thành công
                                await redis.xack(self.stream_name, self.group_name, msg_id)
                                await redis.delete(retry_key)
                            except Exception as handler_err:
                                retry_count += 1
                                logger.error(
                                    f"Handler error for event {event_type} (attempt {retry_count}/{self.max_retries}): {handler_err}"
                                )

                                if retry_count >= self.max_retries:
                                    # Vượt quá giới hạn retry -> Đẩy vào Dead Letter Queue (DLQ) trong PostgreSQL
                                    logger.error(f"Max retries reached for message {msg_id}. Moving to DLQ.")
                                    await self._move_to_dlq(event_type, msg_id, payload, handler_err, retry_count)
                                    # Acknowledge để xóa khỏi hàng đợi chính
                                    await redis.xack(self.stream_name, self.group_name, msg_id)
                                    await redis.delete(retry_key)
                                else:
                                    # Cập nhật số lần thử lại và không XACK để thử lại sau
                                    await redis.set(retry_key, retry_count, ex=3600)
                        else:
                            logger.warning(
                                f"No handler registered for event {event_type}, acknowledging automatically."
                            )
                            await redis.xack(self.stream_name, self.group_name, msg_id)

            except asyncio.CancelledError:
                logger.info("Worker loop cancelled.")
                self.is_running = False
            except Exception as worker_err:
                logger.error(f"RAG Worker Loop Exception: {worker_err}")
                await asyncio.sleep(2)

    async def _move_to_dlq(
        self, event_type: str, msg_id: str, payload: dict, error: Exception, retry_count: int
    ) -> None:
        from yuxi.storage.postgres.models_business import FailedJob
        from yuxi.storage.postgres.manager import pg_manager

        try:
            async with pg_manager.get_async_session_context() as db:
                failed_job = FailedJob(
                    job_type=event_type,
                    job_id=msg_id,
                    payload=payload,
                    error_type=type(error).__name__,
                    error_message=str(error),
                    retry_count=retry_count,
                    status="failed",
                )
                db.add(failed_job)
                await db.commit()
                logger.info(f"Successfully recorded failed RAG job {msg_id} to DLQ table")
        except Exception as dlq_err:
            logger.critical(f"Failed to write job {msg_id} to DLQ: {dlq_err}")

    def stop(self) -> None:
        self.is_running = False
        logger.info("Worker stop requested.")
