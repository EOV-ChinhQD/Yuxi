from fastapi import APIRouter, Depends, HTTPException, Query

from yuxi.storage.postgres.models_business import User
from yuxi.services.task_service import tasker
from server.utils.auth_middleware import get_admin_user

tasks = APIRouter(prefix="/tasks", tags=["tasks"])


@tasks.get("")
async def list_tasks(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=100),
    current_user: User = Depends(get_admin_user),
):
    """List tasks, optionally filtered by status."""
    return await tasker.list_tasks(status=status, limit=limit)


@tasks.get("/{task_id}")
async def get_task(task_id: str, current_user: User = Depends(get_admin_user)):
    """Retrieve a single task by id."""
    task = await tasker.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task": task}


@tasks.post("/{task_id}/cancel")
async def cancel_task(task_id: str, current_user: User = Depends(get_admin_user)):
    """Request cancellation of a task."""
    success = await tasker.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="Task cannot be cancelled")
    return {"task_id": task_id, "status": "cancelled"}


@tasks.delete("/{task_id}")
async def delete_task(task_id: str, current_user: User = Depends(get_admin_user)):
    """Delete a task by id."""
    success = await tasker.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task_id": task_id, "status": "deleted"}


from sqlalchemy import select
from yuxi.storage.postgres.manager import pg_manager
from yuxi.storage.postgres.models_business import FailedJob, AgentRun
from yuxi.services.agent_run_service import enqueue_agent_run

@tasks.get("/failed-jobs")
async def list_failed_jobs(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=100),
    current_user: User = Depends(get_admin_user),
):
    """List failed jobs in the DLQ."""
    async with pg_manager.get_async_session_context() as db:
        query = select(FailedJob)
        if status:
            query = query.where(FailedJob.status == status)
        query = query.order_by(FailedJob.failed_at.desc()).limit(limit)
        result = await db.execute(query)
        failed_jobs = result.scalars().all()
        return [job.to_dict() for job in failed_jobs]


@tasks.post("/failed-jobs/{failed_job_id}/replay")
async def replay_failed_job(
    failed_job_id: int,
    current_user: User = Depends(get_admin_user),
):
    """Replay a failed job from DLQ."""
    async with pg_manager.get_async_session_context() as db:
        failed_job = await db.get(FailedJob, failed_job_id)
        if not failed_job:
            raise HTTPException(status_code=404, detail="Failed job not found")
        
        if failed_job.status != "failed":
            raise HTTPException(status_code=400, detail=f"Job cannot be replayed with status {failed_job.status}")
            
        payload = failed_job.payload or {}
        run_id = payload.get("run_id")
        
        if not run_id:
            raise HTTPException(status_code=400, detail="Missing run_id in job payload")
            
        run = await db.get(AgentRun, run_id)
        if not run:
            raise HTTPException(status_code=404, detail=f"AgentRun {run_id} not found")
            
        # Reset run status to pending
        run.status = "pending"
        run.error_type = None
        run.error_message = None
        
        # Mark job as replayed
        failed_job.status = "replayed"
        
        await db.commit()
        
        # Enqueue back to ARQ
        await enqueue_agent_run(run_id)
        
        return {"status": "replayed", "failed_job_id": failed_job_id, "run_id": run_id}


@tasks.post("/failed-jobs/{failed_job_id}/ignore")
async def ignore_failed_job(
    failed_job_id: int,
    current_user: User = Depends(get_admin_user),
):
    """Mark a failed job as ignored."""
    async with pg_manager.get_async_session_context() as db:
        failed_job = await db.get(FailedJob, failed_job_id)
        if not failed_job:
            raise HTTPException(status_code=404, detail="Failed job not found")
            
        failed_job.status = "ignored"
        await db.commit()
        
        return {"status": "ignored", "failed_job_id": failed_job_id}
