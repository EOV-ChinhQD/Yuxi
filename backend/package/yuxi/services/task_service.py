import asyncio
import math
import os
import uuid
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from yuxi.repositories.task_repository import TaskRepository
from yuxi.utils.datetime_utils import coerce_any_to_utc_datetime, utc_isoformat
from yuxi.utils.logging_config import logger

TaskCoroutine = Callable[["TaskContext"], Awaitable[Any]]
TERMINAL_STATUSES = {"success", "failed", "cancelled"}
# When pure progress is advanced, if the progress increment is less than this threshold, only the memory is updated and the library is not dropped (the front-end reads the memory and is not affected)
PROGRESS_PERSIST_DELTA = 2.0
# The memory and database each retain the most recent final tasks, and any excess tasks will be automatically cleared.
MAX_TERMINAL_TASKS = 200
# Nhiệm vụ nền mặc định tối đa thực thi 6 giờ, có thể ghi đè theo môi trường triển khai hoặc từng nhiệm vụ.
TASKER_DEFAULT_TIMEOUT_SECONDS = float(os.getenv("TASKER_DEFAULT_TIMEOUT_SECONDS", 6 * 60 * 60))
# Sentinel: phân biệt「không truyền tham số」và「truyền None tường minh」để result/error có thể bị xóa

_UNSET: Any = object()


class _TaskExecutionTimeout(TimeoutError):
    pass


def _iso_to_utc_naive(value: str | None) -> datetime | None:
    if not value:
        return None
    return coerce_any_to_utc_datetime(value).replace(tzinfo=None)


@dataclass
class Task:
    id: str
    name: str
    type: str
    status: str = "pending"
    progress: float = 0.0
    message: str = ""
    created_at: str = field(default_factory=utc_isoformat)
    updated_at: str = field(default_factory=utc_isoformat)
    started_at: str | None = None
    completed_at: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    result: Any | None = None
    error: str | None = None
    cancel_requested: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_summary_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("payload", None)
        data.pop("result", None)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        return cls(
            id=data["id"],
            name=data.get("name", "Unnamed Task"),
            type=data.get("type", "general"),
            status=data.get("status", "pending"),
            progress=data.get("progress", 0.0),
            message=data.get("message", ""),
            created_at=data.get("created_at", utc_isoformat()),
            updated_at=data.get("updated_at", utc_isoformat()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            payload=data.get("payload", {}),
            result=data.get("result"),
            error=data.get("error"),
            cancel_requested=data.get("cancel_requested", False),
        )


class TaskContext:
    def __init__(self, tasker: "Tasker", task_id: str, payload: dict[str, Any] | None = None):
        self._tasker = tasker
        self.task_id = task_id
        self.payload = payload or {}
        self.cancellation_reason: str | None = None

    async def set_progress(self, progress: float, message: str | None = None) -> None:
        await self._tasker._update_task(
            self.task_id,
            progress=max(0.0, min(progress, 100.0)),
            message=message,
        )

    async def set_message(self, message: str) -> None:
        await self._tasker._update_task(self.task_id, message=message)

    async def set_result(self, result: Any) -> None:
        await self._tasker._update_task(self.task_id, result=result)

    def is_cancel_requested(self) -> bool:
        return self._tasker._is_cancel_requested(self.task_id)

    async def raise_if_cancelled(self) -> None:
        if self.is_cancel_requested():
            self.cancellation_reason = "cancelled"
            raise asyncio.CancelledError("Task was cancelled")


class Tasker:
    def __init__(
        self,
        worker_count: int = 2,
        default_timeout_seconds: float = TASKER_DEFAULT_TIMEOUT_SECONDS,
    ):
        self.worker_count = max(1, worker_count)
        self.default_timeout_seconds = self._validate_timeout_seconds(default_timeout_seconds)
        self._queue: asyncio.Queue[tuple[str, TaskCoroutine, float]] = asyncio.Queue()
        self._tasks: dict[str, Task] = {}
        self._lock = asyncio.Lock()
        self._lifecycle_lock = asyncio.Lock()
        self._workers: list[asyncio.Task[Any]] = []
        self._started = False
        self._repo = TaskRepository()
        # Record the progress of each task when it was last dropped into the library for progress throttling
        self._last_persisted_progress: dict[str, float] = {}

    async def start(self) -> None:
        async with self._lifecycle_lock:
            async with self._lock:
                if self._started:
                    return
                await self._load_state()
                for _ in range(self.worker_count):
                    worker = asyncio.create_task(self._worker_loop(), name="tasker-worker")
                    self._workers.append(worker)
                self._started = True
                logger.info("Tasker started with {} workers", self.worker_count)

    async def shutdown(self) -> None:
        async with self._lifecycle_lock:
            async with self._lock:
                if not self._started:
                    return
                workers = self._workers.copy()
                self._workers.clear()
                self._started = False
                for worker in workers:
                    worker.cancel()

            await asyncio.gather(*workers, return_exceptions=True)
            logger.info("Tasker shutdown complete")

    async def enqueue(
        self,
        *,
        name: str,
        task_type: str,
        payload: dict[str, Any] | None = None,
        coroutine: TaskCoroutine,
        timeout_seconds: float | None = None,
    ) -> Task:
        effective_timeout = self._resolve_timeout_seconds(timeout_seconds)
        task_id = uuid.uuid4().hex
        task = Task(id=task_id, name=name, type=task_type, payload=payload or {})
        async with self._lock:
            self._tasks[task_id] = task
            await self._persist_task(task)
            await self._queue.put((task_id, coroutine, effective_timeout))
        logger.info("Enqueued task {} ({})", task_id, name)
        return task

    async def find_task_by_payload(
        self,
        *,
        task_type: str,
        payload_match: dict[str, Any],
        statuses: set[str] | None = None,
    ) -> Task | None:
        async with self._lock:
            matching_tasks = [
                task
                for task in self._tasks.values()
                if task.type == task_type
                and (statuses is None or task.status in statuses)
                and all(task.payload.get(key) == value for key, value in payload_match.items())
            ]
            if not matching_tasks:
                return None
            return max(matching_tasks, key=lambda task: (task.created_at or "", task.id))

    async def enqueue_unique_by_payload(
        self,
        *,
        name: str,
        task_type: str,
        payload: dict[str, Any] | None = None,
        coroutine: TaskCoroutine,
        payload_match: dict[str, Any],
        statuses: set[str] | None = None,
        timeout_seconds: float | None = None,
    ) -> tuple[Task, bool]:
        effective_timeout = self._resolve_timeout_seconds(timeout_seconds)
        task_payload = payload or {}
        async with self._lock:
            existing = self._find_task_by_payload_locked(task_type, payload_match, statuses)
            if existing:
                return existing, False
            task_id = uuid.uuid4().hex
            task = Task(id=task_id, name=name, type=task_type, payload=task_payload)
            self._tasks[task_id] = task
            await self._persist_task(task)
            await self._queue.put((task_id, coroutine, effective_timeout))
        logger.info("Enqueued task {} ({})", task.id, name)
        return task, True

    def _find_task_by_payload_locked(
        self,
        task_type: str,
        payload_match: dict[str, Any],
        statuses: set[str] | None,
    ) -> Task | None:
        for task in self._tasks.values():
            if task.type != task_type:
                continue
            if statuses is not None and task.status not in statuses:
                continue
            if all(task.payload.get(key) == value for key, value in payload_match.items()):
                return task
        return None

    async def list_tasks(self, status: str | None = None, limit: int = 100) -> dict[str, Any]:
        async with self._lock:
            all_tasks = list(self._tasks.values())

        status_counter = Counter(task.status for task in all_tasks)
        type_counter = Counter(task.type for task in all_tasks)
        all_tasks.sort(key=lambda item: item.created_at or utc_isoformat(), reverse=True)

        tasks = all_tasks
        if status:
            tasks = [task for task in tasks if task.status == status]

        limited_tasks = tasks[: max(limit, 0)]

        summary: dict[str, Any] = {
            "total": len(all_tasks),
            "filtered_total": len(tasks),
            "status_counts": dict(status_counter),
            "type_counts": dict(type_counter),
        }

        return {
            "tasks": [task.to_summary_dict() for task in limited_tasks],
            "summary": summary,
        }

    async def get_task(self, task_id: str) -> dict[str, Any] | None:
        async with self._lock:
            task = self._tasks.get(task_id)
        return task.to_dict() if task else None

    async def cancel_task(self, task_id: str) -> bool:
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            if task.status in TERMINAL_STATUSES:
                return False
            task.cancel_requested = True
            task.updated_at = utc_isoformat()
            await self._persist_task(task)
        logger.info("Cancellation requested for task {}", task_id)
        return True

    async def delete_task(self, task_id: str) -> bool:
        """Delete a task by id. Returns True if deleted, False if not found."""
        async with self._lock:
            if task_id not in self._tasks:
                return False
            del self._tasks[task_id]
            self._last_persisted_progress.pop(task_id, None)
        await self._repo.delete(task_id)
        logger.info("Deleted task {}", task_id)
        return True

    async def _worker_loop(self) -> None:
        while True:
            try:
                task_id, coroutine, timeout_seconds = await self._queue.get()
                try:
                    task = await self._get_task_instance(task_id)
                    if not task:
                        continue
                    if task.cancel_requested:
                        await self._mark_cancelled(task_id, "Task was cancelled before execution")
                        continue
                    await self._update_task(
                        task_id, status="running", progress=0.0, message="Nhiệm vụ bắt đầu", started_at=utc_isoformat()
                    )
                    context = TaskContext(self, task_id, task.payload)
                    try:
                        result = await self._run_task_coroutine(coroutine, context, timeout_seconds)
                        if task.cancel_requested:
                            await self._mark_cancelled(task_id, "Task cancelled during execution")
                            continue
                        await self._update_task(
                            task_id,
                            status="success",
                            progress=100.0,
                            message="Nhiệm vụ đã hoàn thành",
                            result=result,
                            completed_at=utc_isoformat(),
                        )
                    except _TaskExecutionTimeout as exc:
                        logger.warning("Task {} timed out after {} seconds", task_id, timeout_seconds)
                        await self._update_task(
                            task_id,
                            status="failed",
                            progress=100.0,
                            message="Nhiệm vụ thực thi vượt thời gian cho phép",
                            error=str(exc),
                            completed_at=utc_isoformat(),
                        )
                    except asyncio.CancelledError:
                        worker = asyncio.current_task()
                        should_stop_worker = worker is not None and worker.cancelling() > 0
                        await self._mark_cancelled(task_id, "Nhiệm vụ đã bị hủy")
                        if should_stop_worker:
                            raise
                    except Exception as exc:  # noqa: BLE001
                        logger.exception("Task {} failed: {}", task_id, exc)
                        await self._update_task(
                            task_id,
                            status="failed",
                            progress=100.0,
                            message="Nhiệm vụ thực thi thất bại",
                            error=str(exc),
                            completed_at=utc_isoformat(),
                        )
                finally:
                    self._queue.task_done()
                    await self._prune_terminal_tasks()
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                logger.exception("Tasker worker error: {}", exc)
                worker = asyncio.current_task()
                if worker is not None and worker.cancelling() > 0:
                    break

    async def _run_task_coroutine(
        self,
        coroutine: TaskCoroutine,
        context: TaskContext,
        timeout_seconds: float,
    ) -> Any:
        execution = asyncio.ensure_future(coroutine(context))
        try:
            done, _ = await asyncio.wait({execution}, timeout=timeout_seconds)
            if execution not in done:
                context.cancellation_reason = "timeout"
                execution.cancel()
                await asyncio.gather(execution, return_exceptions=True)
                raise _TaskExecutionTimeout(f"Task exceeded the {timeout_seconds:g}-second execution timeout")
            return await execution
        except asyncio.CancelledError:
            current_task = asyncio.current_task()
            if current_task is not None and current_task.cancelling():
                context.cancellation_reason = "shutdown"
                execution.cancel()
                current_task.uncancel()
                try:
                    await asyncio.gather(execution, return_exceptions=True)
                finally:
                    current_task.cancel()
            raise

    def _resolve_timeout_seconds(self, timeout_seconds: float | None) -> float:
        if timeout_seconds is None:
            return self.default_timeout_seconds
        return self._validate_timeout_seconds(timeout_seconds)

    @staticmethod
    def _validate_timeout_seconds(timeout_seconds: float) -> float:
        timeout_seconds = float(timeout_seconds)
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("Task timeout must be a positive finite number")
        return timeout_seconds

    async def _get_task_instance(self, task_id: str) -> Task | None:
        async with self._lock:
            return self._tasks.get(task_id)

    async def _mark_cancelled(self, task_id: str, message: str) -> None:
        await self._update_task(
            task_id,
            status="cancelled",
            progress=100.0,
            message=message,
            completed_at=utc_isoformat(),
        )

    async def _update_task(
        self,
        task_id: str,
        *,
        status: str | None = None,
        progress: float | None = None,
        message: str | None = None,
        result: Any = _UNSET,
        error: Any = _UNSET,
        started_at: str | None = None,
        completed_at: str | None = None,
    ) -> None:
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            if status:
                task.status = status
            if progress is not None:
                task.progress = max(0.0, min(progress, 100.0))
            if message is not None:
                task.message = message
            if result is not _UNSET:
                task.result = result
            if error is not _UNSET:
                task.error = error
            if started_at is not None:
                task.started_at = started_at
            if completed_at is not None:
                task.completed_at = completed_at
            task.updated_at = utc_isoformat()

            # Only high-frequency updates of progress are throttled; status switching, results, errors, and start and end times are all immediately dropped into the library.
            only_progress = (
                status is None and result is _UNSET and error is _UNSET and started_at is None and completed_at is None
            )
            if only_progress:
                last = self._last_persisted_progress.get(task_id)
                if last is not None and abs(task.progress - last) < PROGRESS_PERSIST_DELTA:
                    return
            self._last_persisted_progress[task_id] = task.progress
            await self._persist_task(task)

    def _is_cancel_requested(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        return bool(task and task.cancel_requested)

    def _collect_stale_terminal_ids(self) -> list[str]:
        """Remove old final tasks that exceed the retention limit from memory and return the ID that needs to be deleted from the database (the caller must hold the lock)."""
        terminal = [task for task in self._tasks.values() if task.status in TERMINAL_STATUSES]
        if len(terminal) <= MAX_TERMINAL_TASKS:
            return []
        terminal.sort(key=lambda item: item.created_at or "", reverse=True)
        stale = terminal[MAX_TERMINAL_TASKS:]
        for task in stale:
            self._tasks.pop(task.id, None)
            self._last_persisted_progress.pop(task.id, None)
        return [task.id for task in stale]

    async def _prune_terminal_tasks(self) -> None:
        async with self._lock:
            stale_ids = self._collect_stale_terminal_ids()
        for task_id in stale_ids:
            await self._repo.delete(task_id)
        if stale_ids:
            logger.info("Pruned {} old terminal tasks", len(stale_ids))

    async def _load_state(self) -> None:
        records = await self._repo.list_all()
        interrupted = 0
        for record in records:
            task = Task.from_dict(record.to_dict())
            if task.status not in TERMINAL_STATUSES:
                # After the process is restarted, the memory queue has been lost and cannot be continued, and is marked as failed.
                task.message = (
                    "Task interrupted when service restarts"
                    if task.status == "running"
                    else "The task did not continue execution when the service was restarted"
                )
                task.status = "failed"
                task.updated_at = utc_isoformat()
                await self._persist_task(task)
                interrupted += 1
            self._tasks[task.id] = task
        if interrupted:
            logger.info("Marked {} interrupted tasks as failed", interrupted)
        stale_ids = self._collect_stale_terminal_ids()
        for task_id in stale_ids:
            await self._repo.delete(task_id)
        if stale_ids:
            logger.info("Pruned {} old terminal tasks on startup", len(stale_ids))

    async def _persist_task(self, task: Task) -> None:
        data: dict[str, Any] = {
            "name": task.name,
            "type": task.type,
            "status": task.status,
            "progress": task.progress,
            "message": task.message,
            "payload": task.payload,
            "result": task.result,
            "error": task.error,
            "cancel_requested": 1 if task.cancel_requested else 0,
            "created_at": _iso_to_utc_naive(task.created_at),
            "updated_at": _iso_to_utc_naive(task.updated_at),
            "started_at": _iso_to_utc_naive(task.started_at),
            "completed_at": _iso_to_utc_naive(task.completed_at),
        }
        await self._repo.upsert(task.id, data)


tasker = Tasker()


__all__ = ["tasker", "TaskContext", "Tasker"]
