import shutil
import tempfile
from pathlib import Path, PurePosixPath
from typing import Annotated

from langchain.tools import InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolRuntime
from langgraph.types import Command
from pydantic import BaseModel, Field

from yuxi.agents.toolkits.registry import tool
from yuxi.repositories.agent_repository import AgentRepository
from yuxi.repositories.conversation_repository import ConversationRepository
from yuxi.storage.postgres.manager import pg_manager
from yuxi.utils.logging_config import logger

SANDBOX_PATH_HINT = (
    "Vui lòng sử dụng /home/gem/user-data/workspace/..., /home/gem/user-data/uploads/... hoặc /home/gem/user-data/outputs/..."
)
MAX_SANDBOX_SKILL_FILES = 1000


class InstallSkillInput(BaseModel):
    source: str = Field(
        description="Nguồn Skill, hỗ trợ hai định dạng:\n"
        "1. Đường dẫn Sandbox: /home/gem/user-data/workspace/..., "
        "/home/gem/user-data/uploads/... hoặc /home/gem/user-data/outputs/... (bắt đầu bằng /)\n"
        "2. Kho Git: owner/repo hoặc URL GitHub đầy đủ"
    )
    skill_names: list[str] | None = Field(
        default=None, description="Danh sách skill slug cần cài đặt khi cài đặt qua Git (ít nhất một). Bỏ qua tham số này khi cài đặt bằng đường dẫn Sandbox."
    )


def _personal_skill_share_config(uid: str) -> dict:
    return {"access_level": "user", "department_ids": [], "user_uids": [str(uid)]}


def _collect_sandbox_file_paths(backend, remote_dir: str, file_paths: list[str] | None = None) -> list[str]:
    file_paths = file_paths if file_paths is not None else []
    result = backend.ls(remote_dir)
    if result.error:
        raise ValueError(result.error)
    entries = result.entries or []
    for entry in entries:
        path = entry["path"]
        if entry.get("is_dir"):
            _collect_sandbox_file_paths(backend, path, file_paths)
        else:
            if len(file_paths) >= MAX_SANDBOX_SKILL_FILES:
                raise ValueError(f"Số lượng tệp trong thư mục Skill vượt quá giới hạn (tối đa {MAX_SANDBOX_SKILL_FILES} tệp)")
            file_paths.append(path)
    return file_paths


def _download_skill_dir(backend, remote_dir: str, local_dir: Path) -> None:
    """Recursively download the skill directory to the local through the sandbox API."""
    remote_root = PurePosixPath(remote_dir.rstrip("/"))
    file_paths = _collect_sandbox_file_paths(backend, remote_dir)
    if not file_paths:
        raise ValueError(f"Không tìm thấy tệp có thể tải xuống trong đường dẫn sandbox {remote_dir}")

    responses = backend.download_files(file_paths)
    if len(responses) != len(file_paths):
        raise ValueError("Số lượng kết quả tải xuống tệp sandbox không khớp")

    for expected_path, response in zip(file_paths, responses):
        error = getattr(response, "error", None)
        content = getattr(response, "content", None)
        if error or content is None:
            raise ValueError(f"Tải tệp sandbox thất bại: {expected_path} ({error or 'empty_content'})")

        pure_path = PurePosixPath(expected_path)
        try:
            relative_path = pure_path.relative_to(remote_root)
        except ValueError:
            relative_path = PurePosixPath(pure_path.name)

        target_path = local_dir / Path(relative_path.as_posix())
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(content)


def _prepare_skill_from_sandbox(sandbox_path: str, thread_id: str, uid: str, staging_root: Path) -> tuple[Path, str]:
    """Prepare the skill directory from the sandbox path. return (local directory, Original skill name)。"""
    from yuxi.agents.backends.sandbox import ProvisionerSandboxBackend, resolve_virtual_path
    from yuxi.agents.skills.service import (
        _parse_skill_markdown,
        is_valid_skill_slug,
    )

    slug = PurePosixPath(sandbox_path.rstrip("/")).name
    if not is_valid_skill_slug(slug):
        raise ValueError(f"slug '{slug}' không hợp lệ (chỉ cho phép chữ thường, chữ số và dấu gạch ngang)")

    if not sandbox_path.startswith("/home/gem/user-data/"):
        raise ValueError(f"Đường dẫn sandbox không được hỗ trợ: {sandbox_path}. {SANDBOX_PATH_HINT}")

    staging = staging_root / slug

    # Try shared volume paths first (better performance, no need to go through the sandbox API).
    try:
        local_path = resolve_virtual_path(thread_id, sandbox_path, uid=uid)
        if (local_path / "SKILL.md").exists():
            shutil.copytree(local_path, staging)
        else:
            raise FileNotFoundError(f"Không tìm thấy SKILL.md trong {local_path}")
    except FileNotFoundError:
        staging.mkdir(parents=True, exist_ok=True)
        backend = ProvisionerSandboxBackend(thread_id=thread_id, uid=uid)
        _download_skill_dir(backend, sandbox_path, staging)
        if not (staging / "SKILL.md").exists():
            raise ValueError(f"Không tìm thấy SKILL.md trong đường dẫn sandbox {sandbox_path}")

    content = (staging / "SKILL.md").read_text(encoding="utf-8")
    parsed_name, _, _ = _parse_skill_markdown(content)
    return staging, parsed_name


async def _enable_skills_in_current_config(db, thread_id: str, uid: str, skill_slugs: list[str]) -> bool:
    """Enables the newly installed skill in the Agent configuration bound to the current session and owned by the current user."""
    conv_repo = ConversationRepository(db)
    conv = await conv_repo.get_conversation_by_thread_id(thread_id)
    if not conv or str(conv.uid) != str(uid):
        return False

    agent_repo = AgentRepository(db)
    agent = await agent_repo.get_by_slug(conv.agent_id)
    if not agent or agent.created_by != str(uid):
        return False

    config_json = dict(agent.config_json or {})
    context = dict(config_json.get("context") or {})
    skills = [item for item in context.get("skills") or [] if isinstance(item, str) and item.strip()]
    seen = set(skills)
    for slug in skill_slugs:
        if slug not in seen:
            skills.append(slug)
            seen.add(slug)
    context["skills"] = skills
    config_json["context"] = context
    await agent_repo.update(agent, config_json=config_json, updated_by=str(uid))
    return True


async def _run_install_task(
    source: str,
    runtime: ToolRuntime,
    tool_call_id: str,
    skill_names: list[str] | None = None,
) -> Command:
    """The core logic for executing asynchronous installation tasks."""
    runtime_context = getattr(runtime, "context", None)
    if getattr(runtime_context, "is_subagent_runtime", False):
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content="Lỗi: install_skill chỉ có thể được sử dụng trong agent chính, sub-agent không thể cài đặt Skill",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )

    source = str(source or "").strip()
    uid = getattr(runtime_context, "uid", None)
    thread_id = getattr(runtime_context, "thread_id", None)

    logger.info(f"install_skill called with uid={uid}, thread_id={thread_id}, source={source}")

    if not uid or not thread_id:
        return Command(
            update={"messages": [ToolMessage(content="Lỗi: Không thể lấy thông tin phiên hội thoại hiện tại", tool_call_id=tool_call_id)]}
        )
    if not source:
        return Command(
            update={"messages": [ToolMessage(content="Lỗi: Nguồn Skill không được để trống", tool_call_id=tool_call_id)]}
        )

    personal_share_config = _personal_skill_share_config(uid)

    try:
        from yuxi.agents.skills.service import (
            import_skill_dir,
            normalize_string_list,
            sync_thread_readable_skills,
        )

        installed_slugs: list[str] = []
        failed_items: list[dict] = []
        slug_warnings: list[str] = []
        config_success = True

        if source.startswith("/"):
            with tempfile.TemporaryDirectory(prefix=".skill-install-") as tmp:
                source_dir, parsed_name = _prepare_skill_from_sandbox(source, thread_id, uid, Path(tmp))
                async with pg_manager.get_async_session_context() as db:
                    item = await import_skill_dir(
                        db,
                        source_dir=source_dir,
                        created_by=uid,
                        share_config=personal_share_config,
                    )
                    installed_slugs = [item.slug]
                    if item.slug != parsed_name:
                        slug_warnings.append(f"⚠️ Skill slug '{item.slug}' đã tồn tại, đã tự động đổi tên và cài đặt")
                    config_success = await _enable_skills_in_current_config(db, thread_id, uid, installed_slugs)
        else:
            _skill_names = skill_names or []
            if not _skill_names:
                return Command(
                    update={
                        "messages": [
                            ToolMessage(
                                content="❌ Lỗi: Khi cài đặt từ Git, phải chỉ định tên kỹ năng qua skill_names",
                                tool_call_id=tool_call_id,
                            )
                        ]
                    }
                )

            from yuxi.agents.skills.remote_install import prepare_remote_skills_batch

            preparation = await prepare_remote_skills_batch(source=source, skills=_skill_names)
            try:
                async with pg_manager.get_async_session_context() as db:
                    for result in preparation.results:
                        if not result.get("success"):
                            failed_items.append(result)
                            continue

                        try:
                            item = await import_skill_dir(
                                db,
                                source_dir=result["source_dir"],
                                created_by=uid,
                                share_config=personal_share_config,
                            )
                            installed_slugs.append(item.slug)
                        except Exception as e:
                            await db.rollback()
                            failed_items.append({"slug": result["slug"], "success": False, "error": str(e)})

                    config_success = True
                    if installed_slugs:
                        config_success = await _enable_skills_in_current_config(db, thread_id, uid, installed_slugs)
            finally:
                preparation.cleanup()

        current_skills = normalize_string_list(getattr(runtime_context, "skills", None))
        sync_thread_readable_skills(thread_id, normalize_string_list(current_skills + installed_slugs))

        lines = []
        if installed_slugs:
            lines.append(f"✅ Cài đặt và kích hoạt thành công kỹ năng: {', '.join(installed_slugs)}")
        for warning in slug_warnings:
            lines.append(warning)
        if failed_items:
            for item in failed_items:
                lines.append(f"❌ Cài đặt thất bại ({item['slug']}): {item.get('error', 'Lỗi không xác định')}")
        if not config_success:
            lines.append("⚠️ Đã thêm tiện ích mở rộng Skill này (chỉ có hiệu lực trong phiên hiện tại, chưa được ghi vào cấu hình Agent hiện tại)")
        if not installed_slugs and not failed_items:
            lines.append("ℹ️ Không tìm thấy kỹ năng cần cài đặt")

        return Command(
            update={
                "activated_skills": installed_slugs,
                "messages": [ToolMessage(content="\n".join(lines), tool_call_id=tool_call_id)],
            }
        )

    except Exception as e:
        logger.exception("install_skill abnormal")
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"❌ Lỗi cài đặt ngoại lệ: {str(e)}",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )


@tool(
    category="buildin",
    tags=["skill", "cai-dat"],
    display_name="Cài đặt kỹ năng",
    args_schema=InstallSkillInput,
)
async def install_skill(
    source: str,
    skill_names: list[str] | None = None,
    runtime: ToolRuntime = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> Command:
    """Cài đặt Skill mới vào không gian riêng tư của người dùng hiện tại và kích hoạt trong phiên agent chính hiện tại."""
    return await _run_install_task(source, runtime, tool_call_id, skill_names)
