"""Tasker behavior unit test: payload exposure, progress festival flow, final state retention and restart recovery.

Use memory fake repo, do not rely on real database and Docker.
"""

import asyncio

import pytest

from yuxi.services import task_service
from yuxi.services.task_service import Tasker


class FakeRecord:
    def __init__(self, data: dict):
        self._data = data

    def to_dict(self) -> dict:
        return self._data


class FakeRepo:
    """record upsert/delete The memory warehouse double to call."""

    def __init__(self, preset: list[FakeRecord] | None = None):
        self.preset = preset or []
        self.upsert_calls = 0
        self.progress_writes: list[float] = []
        self.deleted: list[str] = []

    async def upsert(self, task_id: str, data: dict) -> None:
        self.upsert_calls += 1
        self.progress_writes.append(data.get("progress"))

    async def delete(self, task_id: str) -> bool:
        self.deleted.append(task_id)
        return True

    async def list_all(self) -> list[FakeRecord]:
        return self.preset


async def _make_tasker(repo: FakeRepo, worker_count: int = 1) -> Tasker:
    tasker = Tasker(worker_count=worker_count)
    tasker._repo = repo
    await tasker.start()
    return tasker


async def _wait_status(tasker: Tasker, task_id: str, statuses: set[str], timeout: float = 2.0) -> dict:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        task = await tasker.get_task(task_id)
        if task and task["status"] in statuses:
            return task
        if loop.time() > deadline:
            raise AssertionError(f"Nhiệm vụ {task_id} không vào được {statuses} trong thời gian chờ")
        await asyncio.sleep(0.01)


async def test_task_context_exposes_payload():
    repo = FakeRepo()
    tasker = await _make_tasker(repo)
    seen: dict = {}

    async def coro(ctx):
        seen["payload"] = ctx.payload
        return "ok"

    task = await tasker.enqueue(name="x", task_type="demo", payload={"a": 1}, coroutine=coro)
    await _wait_status(tasker, task.id, {"success"})

    assert seen["payload"] == {"a": 1}
    await tasker.shutdown()


async def test_progress_updates_are_throttled():
    repo = FakeRepo()
    tasker = await _make_tasker(repo)

    async def coro(ctx):
        for percent in range(101):
            await ctx.set_progress(percent)
        return "done"

    task = await tasker.enqueue(name="x", task_type="demo", coroutine=coro)
    final = await _wait_status(tasker, task.id, {"success"})

    # After 101 progress advances, the number of dropouts after throttling should be much less than 101 (including enqueue/running/success, only single-digit additional writes)
    assert repo.upsert_calls < 60
    # The progress in memory is still full 100
    assert final["progress"] == 100
    await tasker.shutdown()


async def test_explicit_none_result_is_persisted():
    repo = FakeRepo()
    tasker = await _make_tasker(repo)

    async def coro(ctx):
        await ctx.set_result("partial")
        return None

    task = await tasker.enqueue(name="x", task_type="demo", coroutine=coro)
    final = await _wait_status(tasker, task.id, {"success"})

    # The coroutine eventually returns None and should overwrite the intermediate results (sentinel distinguishes between "untransmitted" and "explicit None")
    assert final["result"] is None
    await tasker.shutdown()


async def test_completed_tasks_are_pruned_to_limit(monkeypatch):
    monkeypatch.setattr(task_service, "MAX_TERMINAL_TASKS", 3)
    repo = FakeRepo()
    tasker = await _make_tasker(repo)

    async def coro(ctx):
        return "ok"

    for index in range(6):
        task = await tasker.enqueue(name=f"t{index}", task_type="demo", coroutine=coro)
        await _wait_status(tasker, task.id, {"success"})

    listing = await tasker.list_tasks(limit=100)
    assert listing["summary"]["total"] <= 3
    assert len(repo.deleted) >= 3
    await tasker.shutdown()


async def test_load_state_marks_interrupted_and_prunes(monkeypatch):
    monkeypatch.setattr(task_service, "MAX_TERMINAL_TASKS", 2)
    repo = FakeRepo(
        preset=[
            FakeRecord({"id": "a", "name": "a", "type": "demo", "status": "running",
                        "created_at": "2026-01-01T00:00:05"}),
            FakeRecord({"id": "b", "name": "b", "type": "demo", "status": "success",
                        "created_at": "2026-01-01T00:00:04"}),
            FakeRecord({"id": "c", "name": "c", "type": "demo", "status": "success",
                        "created_at": "2026-01-01T00:00:03"}),
            FakeRecord({"id": "d", "name": "d", "type": "demo", "status": "success",
                        "created_at": "2026-01-01T00:00:02"}),
        ]
    )
    tasker = await _make_tasker(repo)

    # Interrupted running tasks are marked as failed
    interrupted = await tasker.get_task("a")
    assert interrupted["status"] == "failed"
    # Only the most recent MAX_TERMINAL_TASKS final tasks are retained, and the oldest ones are cleared.
    listing = await tasker.list_tasks(limit=100)
    assert listing["summary"]["total"] == 2
    assert "c" in repo.deleted and "d" in repo.deleted
    await tasker.shutdown()
