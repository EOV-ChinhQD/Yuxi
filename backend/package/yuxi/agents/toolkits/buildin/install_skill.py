import asyncio
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from typing import Annotated

from langchain.tools import InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolRuntime
from langgraph.types import Command
from pydantic import BaseModel, Field

from yuxi.agents.backends.sandbox.download import download_sandbox_directory
from yuxi.agents.toolkits.registry import tool
from yuxi.repositories.agent_repository import AgentRepository
from yuxi.repositories.conversation_repository import ConversationRepository
from yuxi.storage.postgres.manager import pg_manager
from yuxi.utils.logging_config import logger
from yuxi.utils.paths import VIRTUAL_PATH_WORKSPACE_SKILLS

SANDBOX_PATH_HINT = "Vui lòng sử dụng /home/gem/user-data/workspace/..., /home/gem/user-data/uploads/... hoặc /home/gem/user-data/outputs/..."


class InstallSkillInput(BaseModel):
    source: str = Field(
        description="Nguồn Skill, hỗ trợ hai định dạng:\n"
        "1. Đường dẫn Sandbox: /home/gem/user-data/workspace/..., "
        "/home/gem/user-data/uploads/... hoặc /home/gem/user-data/outputs/... (bắt đầu bằng /)\n"
        "2. Kho Git: owner/repo hoặc URL GitHub đầy đủ"
    )
    skill_names: list[str] | None = Field(
        default=None,
        description="Danh sách skill slug cần cài đặt khi cài đặt qua Git (ít nhất một). Bỏ qua tham số này khi cài đặt bằng đường dẫn Sandbox.",
    )


def _prepare_skill_from_sandbox(sandbox_path: str, thread_id: str, uid: str, staging_root: Path) -> Path:
    """Chuẩn bị thư mục skill từ đường dẫn Sandbox, trả về thư mục tạm cục bộ."""
    from yuxi.agents.backends.sandbox import ProvisionerSandboxBackend
    from yuxi.agents.skills.service import is_valid_skill_slug

    slug = PurePosixPath(sandbox_path.rstrip("/")).name
    if not is_valid_skill_slug(slug):
        raise ValueError(f"slug '{slug}' không hợp lệ (chỉ cho phép chữ thường, chữ số và dấu gạch ngang)")

    if not sandbox_path.startswith("/home/gem/user-data/"):
        raise ValueError(f"Đường dẫn sandbox không được hỗ trợ: {sandbox_path}. {SANDBOX_PATH_HINT}")

    staging = staging_root / slug
    backend = ProvisionerSandboxBackend(thread_id=thread_id, uid=uid)
    download_sandbox_directory(
        backend,
        sandbox_path,
        staging,
        empty_message=f"Không tìm thấy tệp có thể tải xuống trong đường dẫn sandbox {sandbox_path}",
    )
    if not (staging / "SKILL.md").exists():
        shutil.rmtree(staging, ignore_errors=True)
        raise ValueError(f"Không tìm thấy SKILL.md trong đường dẫn sandbox {sandbox_path}")

    return staging


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
            update={
                "messages": [
                    ToolMessage(
                        content="Lỗi: Không thể lấy thông tin phiên hội thoại hiện tại", tool_call_id=tool_call_id
                    )
                ]
            }
        )
    if not source:
        return Command(
            update={
                "messages": [ToolMessage(content="Lỗi: Nguồn Skill không được để trống", tool_call_id=tool_call_id)]
            }
        )

    try:
        from yuxi.agents.middlewares.skills import build_dependency_map, build_prompt_metadata
        from yuxi.agents.skills.service import (
            install_personal_skill_dir,
            list_personal_skills,
            normalize_string_list,
            sync_thread_readable_skills_async,
        )

        installed_items = []
        installed_slugs: list[str] = []
        failed_items: list[dict] = []
        config_success = True

        if source.startswith("/"):
            with tempfile.TemporaryDirectory(prefix=".skill-install-") as tmp:
                source_dir = await asyncio.to_thread(
                    _prepare_skill_from_sandbox,
                    source,
                    thread_id,
                    uid,
                    Path(tmp),
                )
                item = await install_personal_skill_dir(uid, source_dir)
                installed_items = [item]
                installed_slugs = [item.slug]
                async with pg_manager.get_async_session_context() as db:
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
                for result in preparation.results:
                    if not result.get("success"):
                        failed_items.append(result)
                        continue
                    try:
                        item = await install_personal_skill_dir(
                            uid,
                            result["source_dir"],
                            refresh_cache=False,
                        )
                        installed_items.append(item)
                        installed_slugs.append(item.slug)
                    except Exception as e:
                        failed_items.append({"slug": result["slug"], "success": False, "error": str(e)})

                if installed_slugs:
                    await list_personal_skills(uid, refresh=True)
                    async with pg_manager.get_async_session_context() as db:
                        config_success = await _enable_skills_in_current_config(db, thread_id, uid, installed_slugs)
            finally:
                await preparation.cleanup()

        for attr_name in ("skills", "_prompt_skills", "_readable_skills"):
            current = normalize_string_list(getattr(runtime_context, attr_name, None))
            setattr(runtime_context, attr_name, normalize_string_list(current + installed_slugs))

        prompt_metadata = dict(getattr(runtime_context, "_runtime_skill_metadata", {}) or {})
        dependency_map = dict(getattr(runtime_context, "_runtime_skill_dependency_map", {}) or {})
        prompt_metadata.update(build_prompt_metadata(installed_items))
        dependency_map.update(build_dependency_map(installed_items))
        setattr(runtime_context, "_runtime_skill_metadata", prompt_metadata)
        setattr(runtime_context, "_runtime_skill_dependency_map", dependency_map)

        skill_sources = dict(getattr(runtime_context, "_runtime_skill_sources", {}) or {})
        for slug in installed_slugs:
            skill_sources.pop(slug, None)
        setattr(runtime_context, "_runtime_skill_sources", skill_sources)
        projected_skills = [slug for slug in runtime_context._readable_skills if slug in skill_sources]
        await sync_thread_readable_skills_async(thread_id, projected_skills, skill_sources)

        lines = []
        if installed_slugs:
            lines.append(f"✅ Cài đặt và kích hoạt thành công kỹ năng: {', '.join(installed_slugs)}")
            for slug in installed_slugs:
                lines.append(f"📁 Vị trí cài đặt: {VIRTUAL_PATH_WORKSPACE_SKILLS}/{slug}")
        if failed_items:
            for item in failed_items:
                lines.append(f"❌ Cài đặt thất bại ({item['slug']}): {item.get('error', 'Lỗi không xác định')}")
        if not config_success:
            lines.append(
                "⚠️ Skill đã được cài đặt vào không gian cá nhân và kích hoạt trong phiên hiện tại; cấu hình Agent hiện tại chưa được cập nhật"
            )
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
