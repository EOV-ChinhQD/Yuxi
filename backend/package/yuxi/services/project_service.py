"""Project creation, selection, and historical-directory reuse use cases."""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from yuxi.repositories.project_repository import ProjectRepository
from yuxi.storage.postgres.models_business import Project
from yuxi.workspace.paths import normalize_linked_workdir_path
from yuxi.workspace.workdir import Workdir

MAX_PROJECT_NAME_LENGTH = 255


async def _lock_project_workdir_changes(*, db, uid: str) -> None:
    """Serialize linked-Project binding and test-directory removal for one user."""
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
        {"lock_key": f"project-workdir:{uid}"},
    )


def _normalize_project_name(name: str | None, *, required: bool) -> str | None:
    normalized_name = (name or "").strip()
    if required and not normalized_name:
        raise HTTPException(status_code=422, detail="Tên dự án không được để trống")
    if len(normalized_name) > MAX_PROJECT_NAME_LENGTH:
        raise HTTPException(status_code=422, detail="Tên dự án quá dài")
    return normalized_name or None


def _matches_creation_intent(project: Project, *, name: str, workdir_path: str) -> bool:
    return project.name == name and project.directory_mode == "linked" and project.workdir_path == workdir_path


async def create_project_record(
    *,
    uid: str,
    name: str | None,
    directory_mode: str,
    selection_status: str,
    db,
    workdir_path: str | None = None,
    idempotency_key: str | None = None,
) -> Project:
    """Create a Project inside the current transaction without committing or materializing it."""
    normalized_name = _normalize_project_name(name, required=selection_status == "selectable")
    if directory_mode not in {"managed", "linked"}:
        raise HTTPException(status_code=422, detail="directory_mode phải là managed hoặc linked")
    if selection_status not in {"implicit", "selectable"}:
        raise HTTPException(status_code=422, detail="selection_status không hợp lệ")

    project_id = str(uuid.uuid4())
    if directory_mode == "managed":
        if workdir_path is not None:
            raise HTTPException(status_code=422, detail="managed Project không chấp nhận workdir_path")
        normalized_path = f"projects/{project_id}"
    else:
        if workdir_path is None:
            raise HTTPException(status_code=422, detail="linked Project phải chỉ định workdir_path")
        try:
            normalized_path = normalize_linked_workdir_path(workdir_path)
            await _lock_project_workdir_changes(db=db, uid=str(uid))
            Workdir.open_existing(str(uid), normalized_path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Thư mục không tồn tại") from exc
        except (NotADirectoryError, PermissionError, OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    project = Project(
        id=project_id,
        uid=str(uid),
        name=normalized_name,
        selection_status=selection_status,
        workdir_path=normalized_path,
        directory_mode=directory_mode,
        idempotency_key=idempotency_key.strip() if idempotency_key else None,
    )
    return await ProjectRepository(db).add(project)


async def create_implicit_project(*, uid: str, db, idempotency_key: str | None = None) -> Project:
    """Create an implicit managed Project for a new Conversation."""
    return await create_project_record(
        uid=uid,
        name=None,
        directory_mode="managed",
        selection_status="implicit",
        db=db,
        idempotency_key=idempotency_key,
    )


async def create_project_view(
    *, uid: str, request_id: str, name: str, directory_mode: str, workdir_path: str | None, db
) -> dict:
    """Create a selectable Project idempotently."""
    normalized_request_id = (request_id or "").strip()
    if not normalized_request_id:
        raise HTTPException(status_code=422, detail="request_id không được để trống")
    if directory_mode != "linked" or not (workdir_path or "").strip():
        raise HTTPException(status_code=422, detail="Tạo dự án thủ công phải chọn thư mục")
    existing = await ProjectRepository(db).get_by_idempotency_key(normalized_request_id, str(uid))
    normalized_name = _normalize_project_name(name, required=True)
    try:
        normalized_path = normalize_linked_workdir_path(workdir_path or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if existing is not None:
        if not _matches_creation_intent(existing, name=normalized_name, workdir_path=normalized_path):
            raise HTTPException(status_code=409, detail="request_id đã dùng cho mục đích tạo Project khác")
        return existing.to_dict()

    try:
        project = await create_project_record(
            uid=uid,
            name=name,
            directory_mode=directory_mode,
            selection_status="selectable",
            workdir_path=workdir_path,
            db=db,
            idempotency_key=normalized_request_id,
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        replay = await ProjectRepository(db).get_by_idempotency_key(normalized_request_id, str(uid))
        if replay is None:
            raise HTTPException(status_code=409, detail="Xung đột khi tạo Project")
        if not _matches_creation_intent(replay, name=normalized_name, workdir_path=normalized_path):
            raise HTTPException(status_code=409, detail="request_id đã dùng cho mục đích tạo Project khác")
        project = replay
    return project.to_dict()


async def list_projects_view(*, uid: str, db) -> list[dict]:
    """List the Projects the current user can select."""
    projects = await ProjectRepository(db).list_selectable_for_user(str(uid))
    return [project.to_dict() for project in projects]


async def list_history_candidates_view(*, uid: str, db, query: str = "", limit: int = 20, offset: int = 0) -> dict:
    """List historical Conversations usable as directory shortcuts for a new Project."""
    conversations = await ProjectRepository(db).list_history_candidates(str(uid))
    normalized_query = (query or "").strip().lower()
    items = []
    seen_workdirs = set()
    for item, workdir_path in conversations:
        if workdir_path in seen_workdirs:
            continue
        if (
            normalized_query
            and normalized_query not in (item.title or "").lower()
            and normalized_query not in (item.agent_id or "").lower()
        ):
            continue
        seen_workdirs.add(workdir_path)
        items.append(
            {
                "thread_id": item.thread_id,
                "title": item.title,
                "agent_id": item.agent_id,
                "workdir_path": workdir_path,
                "updated_at": item.updated_at.isoformat(),
            }
        )
    return {"items": items[offset : offset + limit], "has_more": len(items) > offset + limit}
