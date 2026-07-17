"""Define the configurable parameters for the agent."""

import asyncio
import uuid
from dataclasses import MISSING, dataclass, field, fields
from typing import Any, get_origin

from yuxi.agents.backends.sandbox.paths import sandbox_workspace_agents_prompt_file
from yuxi.utils.logging_config import logger

WORKSPACE_AGENTS_PROMPT_MAX_BYTES = 64 * 1024
DEFAULT_SUMMARY_THRESHOLD_K = 100  # 100K tokens
DEFAULT_SUMMARY_KEEP_MESSAGES = 10
DEFAULT_SUMMARY_TOOL_RESULT_TOKEN_LIMIT = 300
DEFAULT_SUMMARY_L2_TRIGGER_RATIO = 0.4
DEFAULT_MAX_EXECUTION_STEPS = 300
DEFAULT_TOOL_RESULT_EVICTION_K_TOKENS = 3
DEFAULT_YUXI_SUMMARY_PROMPT = """Bạn là trợ lý nén ngữ cảnh hội thoại.
Nhiệm vụ của bạn là nén lịch sử trò chuyện dưới đây thành ngữ cảnh có giá trị cao cần thiết để agent tiếp theo tiếp tục làm việc.

Vui lòng đặc biệt giữ lại và ghi nhận rõ ràng:

## Ý ĐỊNH PHIÊN TRÒ CHUYỆN
Mục tiêu chính, phạm vi nhiệm vụ và sản phẩm bàn giao cuối cùng hiện tại của người dùng.

## YÊU CẦU VÀ SỞ THÍCH CỦA NGƯỜI DÙNG
Các yêu cầu, sở thích, điều tối kỵ, định dạng đầu ra, phong cách ngôn ngữ, ràng buộc kỹ thuật, tiêu chí chấp nhận được người dùng nêu rõ, cũng như ý kiến lựa chọn phương án thực hiện. Chỉ ghi lại những nội dung vẫn có thể ảnh hưởng đến các câu trả lời hoặc việc thực thi tiếp theo.

## TIẾN ĐỘ VÀ QUYẾT ĐỊNH
Các bước đã hoàn thành, kết luận chính, phương án đã xác nhận, phương án bị từ chối và lý do.

## TÀI LIỆU VÀ THAM KHẢO
Các tệp, đường dẫn, kết quả đầu ra của công cụ, thread hoặc định danh đã được tạo, sửa đổi, đọc hoặc cần tiếp tục theo dõi. Giữ lại đường dẫn cụ thể và các định danh chính.

## BƯỚC TIẾP THEO
Để hoàn thành nhiệm vụ, cần tiếp tục thực hiện các bước cụ thể nhất. Viết Không có (None) nếu không có việc cần làm.

Yêu cầu:
- Không lặp lại nguyên văn kết quả dài của công cụ; chỉ giữ lại kết luận, đường dẫn và bằng chứng cần thiết.
- Không bịa đặt những sự kiện không xuất hiện trong cuộc hội thoại.
- Nếu có vấn đề hoặc rủi ro chưa được giải quyết, hãy ghi nhận lại rõ ràng.
- Sử dụng ngôn ngữ nhất quán với cuộc trò chuyện chính của người dùng (Tiếng Việt).

<messages>
{messages}
</messages>

Chỉ xuất ra ngữ cảnh đã nén mà không thêm các mô tả bổ sung khác."""


def _role_can_access(auth: str | None, role: str | None) -> bool:
    if not auth:
        return True
    if auth == "admin":
        return role in {"admin", "superadmin"}
    if auth == "superadmin":
        return role == "superadmin"
    return False


def _load_workspace_agents_prompt(thread_id: str, uid: str) -> str:
    prompt_file = sandbox_workspace_agents_prompt_file(thread_id, uid)
    try:
        with prompt_file.open("rb") as buffer:
            content = buffer.read(WORKSPACE_AGENTS_PROMPT_MAX_BYTES + 1)
    except FileNotFoundError:
        return ""
    except IsADirectoryError:
        logger.warning("Read workspace AGENTS.md fail: path is directory")
        return ""
    except OSError as exc:
        logger.warning(f"Read workspace AGENTS.md fail: {exc}")
        return ""

    prompt = content[:WORKSPACE_AGENTS_PROMPT_MAX_BYTES].decode("utf-8", errors="replace").strip()
    if not prompt:
        return ""
    if len(content) > WORKSPACE_AGENTS_PROMPT_MAX_BYTES:
        return f"{prompt}\n\n[AGENTS.md Content has been truncated]"
    return prompt


async def build_agent_input_context(
    agent_config: dict | None,
    *,
    thread_id: str,
    uid: str,
    run_id: str | None = None,
    request_id: str | None = None,
) -> dict:
    input_context = dict(agent_config or {})
    agents_prompt = await asyncio.to_thread(_load_workspace_agents_prompt, thread_id, uid)

    if agents_prompt:
        agents_section = f"User workspace agents/AGENTS.md content:\n{agents_prompt}"
        base_prompt = str(input_context.get("system_prompt") or "").rstrip()
        input_context["system_prompt"] = f"{base_prompt}\n\n{agents_section}" if base_prompt else agents_section

    input_context.update({"uid": uid, "thread_id": thread_id, "run_id": run_id, "request_id": request_id})
    return input_context


def filter_config_by_role(
    config_json: dict,
    role: str | None,
    context_schema: type["BaseContext"] | None = None,
) -> dict:
    """By Context field metadata.auth filter config_json.context。"""
    if not isinstance(config_json, dict):
        return {}

    schema = context_schema or BaseContext
    restricted_fields = {
        f.name
        for f in fields(schema)
        if f.metadata.get("auth") and not _role_can_access(str(f.metadata.get("auth")), role)
    }
    if not restricted_fields:
        return dict(config_json)

    filtered = dict(config_json)
    context = filtered.get("context")
    if isinstance(context, dict):
        filtered["context"] = {key: value for key, value in context.items() if key not in restricted_fields}
    return filtered


@dataclass(kw_only=True)
class BaseContext:
    """
    Define oneindivual basic Context for inheritance by various graphs

    Configuration priority:
    1. Runtime configuration(RunnableConfig): Highest priority, passed directly from function arguments
    2. Class default configuration: lowest priority, default value defined in the class
    """

    def update(self, data: dict):
        """Update configuration fields"""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)

    thread_id: str = field(
        default_factory=lambda: str(uuid.uuid4()),
        metadata={
            "name": "Thread ID",
            "configurable": False,
            "description": "Used to uniquely identify a conversation thread",
        },
    )

    uid: str = field(
        default_factory=lambda: str(uuid.uuid4()),
        metadata={"name": "UID", "configurable": False, "description": "Used to uniquely identify a user"},
    )

    run_id: str | None = field(
        default=None,
        metadata={"name": "Run ID", "configurable": False, "hide": True},
    )

    request_id: str | None = field(
        default=None,
        metadata={"name": "Request ID", "configurable": False, "hide": True},
    )

    system_prompt: str = field(
        default="You are a helpful assistant.",
        metadata={"name": "System Prompt", "description": "Mô tả vai trò và hành vi của Agent", "kind": "prompt"},
    )

    model: str = field(
        default="",
        metadata={
            "name": "Model của Agent",
            "options": [],
            "description": "Model thúc đẩy Agent, để trống sẽ sử dụng model mặc định của hệ thống.",
            "kind": "llm",
        },
    )

    tools: list[str] | None = field(
        default=None,
        metadata={
            "name": "Công cụ",
            "description": "Các công cụ tích hợp. Mặc định chọn tất cả công cụ khả dụng cho người dùng hiện tại.",
            "type": "list",
            "kind": "tools",
        },
    )

    knowledges: list[str] | None = field(
        default=None,
        metadata={
            "name": "Kho kiến thức",
            "description": "Danh sách kho kiến thức, có thể tạo ở trang Kho kiến thức bên trái. Mặc định chọn tất cả kho kiến thức người dùng hiện tại có thể truy cập.",
            "type": "list",
            "kind": "knowledges",
        },
    )

    mcps: list[str] | None = field(
        default=None,
        metadata={
            "name": "MCP Server",
            "options": [],
            "description": (
                "Danh sách MCP server, mặc định chọn tất cả MCP server khả dụng cho người dùng hiện tại. Khuyên dùng MCP server hỗ trợ SSE. "
                "Nếu cần dùng server chạy qua uvx hoặc npx, vui lòng khởi động MCP server bên ngoài dự án và cấu hình MCP server trong dự án."
            ),
            "type": "list",
            "kind": "mcps",
        },
    )

    skills: list[str] | None = field(
        default=None,
        metadata={
            "name": "Skills",
            "options": [],
            "description": "Danh sách tiện ích mở rộng Skill tùy chọn, mặc định chọn tất cả Skill khả dụng cho người dùng hiện tại. "
            "Các công cụ và MCP server mà tiện ích Skill phụ thuộc vào cũng sẽ được tự động gắn kèm.",
            "type": "list",
            "kind": "skills",
        },
    )

    summary_threshold: int = field(
        default=DEFAULT_SUMMARY_THRESHOLD_K,
        metadata={
            "name": "Ngưỡng kích hoạt tóm tắt ngữ cảnh (K)",
            "description": (
                f"Khi kích thước ngữ cảnh vượt quá giá trị này, tính năng tóm tắt sẽ được bật để tối ưu hóa việc sử dụng ngữ cảnh. Đơn vị là K, giá trị mặc định là "
                f"{DEFAULT_SUMMARY_THRESHOLD_K}K."
            ),
            "type": "number",
            "auth": "admin",
        },
    )

    summary_keep_messages: int = field(
        default=DEFAULT_SUMMARY_KEEP_MESSAGES,
        metadata={
            "name": "Số tin nhắn giữ lại sau tóm tắt",
            "description": (
                f"Sau khi kích hoạt tóm tắt ngữ cảnh, số lượng tin nhắn gần đây nhất được giữ lại (ngoài tin nhắn tóm tắt), mặc định là {DEFAULT_SUMMARY_KEEP_MESSAGES} tin nhắn."
            ),
            "type": "number",
            "auth": "admin",
        },
    )

    summary_prompt: str = field(
        default=DEFAULT_YUXI_SUMMARY_PROMPT,
        metadata={
            "name": "Prompt tóm tắt ngữ cảnh",
            "description": "Prompt được sử dụng khi kích hoạt tóm tắt ngữ cảnh, phải nhận được {messages} làm vị trí giữ chỗ cho các tin nhắn cần tóm tắt.",
            "type": "string",
            "kind": "prompt",
            "auth": "admin",
        },
    )

    summary_tool_result_token_limit: int = field(
        default=DEFAULT_SUMMARY_TOOL_RESULT_TOKEN_LIMIT,
        metadata={
            "name": "Giới hạn xem trước kết quả công cụ tóm tắt",
            "description": (
                "Khi tóm tắt ngữ cảnh L1 làm sạch lịch sử kết quả công cụ, ToolMessage vượt quá số token này sẽ được ghi vào outputs, "
                f"và ngữ cảnh sẽ giữ lại phần xem trước không vượt quá số token đó; nếu không vượt quá thì giữ nguyên. Mặc định là {DEFAULT_SUMMARY_TOOL_RESULT_TOKEN_LIMIT}."
            ),
            "type": "number",
            "auth": "admin",
        },
    )

    summary_l2_trigger_ratio: float = field(
        default=DEFAULT_SUMMARY_L2_TRIGGER_RATIO,
        metadata={
            "name": "Tỷ lệ kích hoạt tóm tắt L2",
            "description": (
                "Sau khi L1 tinh giản cấu trúc, ngữ cảnh còn lại chỉ vào L2 summary khi vượt quá ngưỡng kích hoạt * tỷ lệ này. "
                "Khuyến nghị dùng giá trị từ 0.1 đến 1.0, giá trị càng nhỏ càng dễ kích hoạt L2. Mặc định là "
                f"{DEFAULT_SUMMARY_L2_TRIGGER_RATIO}."
            ),
            "type": "number",
            "auth": "admin",
        },
    )

    max_execution_steps: int = field(
        default=DEFAULT_MAX_EXECUTION_STEPS,
        metadata={
            "name": "Số bước thực thi tối đa",
            "description": (
                "Số bước thực thi LangGraph tối đa cho phép trong một lần chạy Agent, tương ứng với recursion_limit, mặc định là "
                f"{DEFAULT_MAX_EXECUTION_STEPS}."
            ),
            "type": "number",
            "auth": "admin",
        },
    )

    model_retry_times: int = field(
        default=2,
        metadata={
            "name": "Số lần thử lại model",
            "description": "Số lần thử lại tối đa khi gọi model thất bại, mặc định là 2.",
            "type": "number",
            "auth": "admin",
        },
    )

    @classmethod
    def get_configurable_items(cls, user_role: str | None = None):
        """Triển khai danh sách tham số có thể cấu hình, được sử dụng khi cấu hình trên giao diện người dùng (UI)"""
        configurable_items = {}
        for f in fields(cls):
            if f.init and not f.metadata.get("hide", False):
                if user_role is not None and not _role_can_access(f.metadata.get("auth"), user_role):
                    continue
                if f.metadata.get("configurable", True):
                    type_name = cls._get_type_name(f.type)

                    options = f.metadata.get("options", [])
                    if callable(options):
                        options = options()

                    configurable_items[f.name] = {
                        "type": f.metadata.get("type", type_name),
                        "name": f.metadata.get("name", f.name),
                        "options": options,
                        "default": f.default
                        if f.default is not MISSING
                        else f.default_factory()
                        if f.default_factory is not MISSING
                        else None,
                        "description": f.metadata.get("description", ""),
                        "kind": f.metadata.get("kind", ""),
                    }

        return configurable_items

    @classmethod
    def _get_type_name(cls, field_type) -> str:
        """Get type name"""
        origin = get_origin(field_type)
        if origin is not None:
            if hasattr(origin, "__name__"):
                return origin.__name__
            return str(origin)
        elif hasattr(field_type, "__name__"):
            return field_type.__name__
        else:
            return str(field_type)

    def update_from_dict(self, data: dict):
        """Update configuration fields from dictionary"""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)


_DEFAULT_ALL_CONTEXT_FIELDS = frozenset({"tools", "knowledges", "mcps", "skills"})
_EMPTY_ALL_CONTEXT_FIELDS = frozenset({"subagents"})
_AGENT_RESOURCE_FIELDS = _DEFAULT_ALL_CONTEXT_FIELDS | _EMPTY_ALL_CONTEXT_FIELDS


def _normalize_selected_resource_keys(value: Any, available: list[str]) -> list[str]:
    if not isinstance(value, list):
        return []

    allowed = set(available)
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        key = item.strip()
        if not key or key in seen or key not in allowed:
            continue
        seen.add(key)
        normalized.append(key)
    return normalized


def _resource_fields_requiring_available_keys(normalized: dict, resource_fields: set[str]) -> set[str]:
    fields_to_load: set[str] = set()
    for field_name in resource_fields:
        current = normalized.get(field_name)
        if current is None:
            if field_name in _DEFAULT_ALL_CONTEXT_FIELDS | _EMPTY_ALL_CONTEXT_FIELDS:
                fields_to_load.add(field_name)
            else:
                normalized[field_name] = []
        elif field_name in _EMPTY_ALL_CONTEXT_FIELDS and current == []:
            normalized[field_name] = None
            fields_to_load.add(field_name)
        elif isinstance(current, list) and current:
            fields_to_load.add(field_name)
        else:
            normalized[field_name] = []
    return fields_to_load


def _resource_option(key: Any, name: Any = None, description: Any = None) -> dict[str, str]:
    key_value = str(key)
    return {
        "key": key_value,
        "name": str(name or key_value),
        "description": str(description or ""),
    }


async def resolve_agent_resource_options(
    resource_fields: set[str] | None = None,
    *,
    db,
    user,
) -> dict[str, list[dict[str, str]]]:
    fields_to_load = _AGENT_RESOURCE_FIELDS if resource_fields is None else resource_fields
    if not fields_to_load:
        return {}

    options: dict[str, list[dict[str, str]]] = {}

    if "tools" in fields_to_load:
        from yuxi.agents.toolkits.service import get_tool_metadata

        options["tools"] = [
            _resource_option(tool["slug"], tool.get("name"), tool.get("description"))
            for tool in get_tool_metadata(category="buildin")
            if tool.get("slug")
        ]
    if "knowledges" in fields_to_load:
        from yuxi.knowledge import knowledge_base

        databases = (await knowledge_base.get_databases_by_user(user)).get("databases", [])
        import os

        # Filter out SiliconFlow databases if SILICONFLOW_API_KEY is not set
        databases = [
            db
            for db in databases
            if not (
                str(db.get("embedding_model_spec") or "").startswith("siliconflow")
                and not os.environ.get("SILICONFLOW_API_KEY")
            )
        ]
        # Filter TEST_RAG_PIPELINE databases to keep only the latest one
        test_dbs = [db for db in databases if str(db.get("name") or "").startswith("TEST_RAG_PIPELINE_")]
        if test_dbs:

            def get_suffix(db):
                try:
                    return int(db.get("name").split("_")[-1])
                except Exception:
                    return -1

            latest_test_db = max(test_dbs, key=get_suffix)
            databases = [db for db in databases if not str(db.get("name") or "").startswith("TEST_RAG_PIPELINE_")] + [latest_test_db]

        options["knowledges"] = [
            _resource_option(item.get("kb_id"), item.get("name"), item.get("description"))
            for item in databases
            if isinstance(item, dict) and item.get("kb_id")
        ]
    if "mcps" in fields_to_load:
        from yuxi.agents.mcp.service import get_all_mcp_servers

        servers = await get_all_mcp_servers(db)
        options["mcps"] = [
            _resource_option(server.slug, server.name, server.description)
            for server in servers
            if server.enabled and server.slug
        ]
    if "skills" in fields_to_load:
        from yuxi.agents.skills.service import list_accessible_skills

        skills = await list_accessible_skills(db, user)
        options["skills"] = [
            _resource_option(skill.slug, skill.name, skill.description) for skill in skills if skill.slug
        ]
    if "subagents" in fields_to_load:
        from yuxi.repositories.agent_repository import AgentRepository

        subagents = await AgentRepository(db).list_visible_subagents(user=user)
        options["subagents"] = [
            _resource_option(agent.slug, agent.name, agent.description) for agent in subagents if agent.slug
        ]

    return options


async def normalize_agent_context_config(
    context: dict | None,
    *,
    db,
    user,
    context_schema: type[BaseContext] | None = None,
) -> dict:
    schema = context_schema or BaseContext
    raw_context = dict(context) if isinstance(context, dict) else {}
    filtered = filter_config_by_role({"context": raw_context}, getattr(user, "role", None), schema)
    normalized = dict(filtered.get("context") or {})
    field_names = {item.name for item in fields(schema)}
    resource_fields = _AGENT_RESOURCE_FIELDS & field_names
    if not resource_fields:
        return normalized

    fields_to_load = _resource_fields_requiring_available_keys(normalized, resource_fields)
    if not fields_to_load:
        return normalized

    resource_options = await resolve_agent_resource_options(fields_to_load, db=db, user=user)
    available = {
        field_name: [option["key"] for option in field_options]
        for field_name, field_options in resource_options.items()
    }

    for field_name, available_keys in available.items():
        current = normalized.get(field_name)
        if current is None:
            normalized[field_name] = available_keys
        else:
            normalized[field_name] = _normalize_selected_resource_keys(current, available_keys)

    return normalized


async def prepare_agent_runtime_context(
    context: BaseContext,
    *,
    context_schema: type[BaseContext] | None = None,
) -> BaseContext:
    """Preparing the Agent runtime context mainly involves loading the user-accessible resource list based on the uid in the context and normalizing it."""
    schema = context_schema or type(context)
    uid = str(getattr(context, "uid", "") or "").strip()
    if not uid:
        return context

    from yuxi.agents.backends.knowledge_base_backend import resolve_visible_knowledge_bases_for_context
    from yuxi.agents.middlewares.skills import resolve_runtime_skills_for_context
    from yuxi.repositories.user_repository import UserRepository
    from yuxi.storage.postgres.manager import pg_manager

    resource_fields = _AGENT_RESOURCE_FIELDS
    async with pg_manager.get_async_session_context() as db:
        user = await UserRepository().get_by_uid_with_db(db, uid)
        if user is None:
            for field_name in resource_fields:
                if hasattr(context, field_name):
                    setattr(context, field_name, [])
            setattr(context, "_visible_knowledge_bases", [])
            setattr(context, "_prompt_skills", [])
            setattr(context, "_readable_skills", [])
            setattr(context, "_runtime_skill_metadata", {})
            setattr(context, "_runtime_skill_dependency_map", {})
            return context

        raw_resources = {
            field_name: getattr(context, field_name, None)
            for field_name in resource_fields
            if hasattr(context, field_name)
        }
        normalized = await normalize_agent_context_config(
            raw_resources,
            db=db,
            user=user,
            context_schema=schema,
        )
        for field_name in resource_fields:
            if hasattr(context, field_name):
                setattr(context, field_name, normalized.get(field_name, []))

        await resolve_visible_knowledge_bases_for_context(context)
        skill_scope = await resolve_runtime_skills_for_context(context, db=db, user=user)
        context.skills = skill_scope["context_skills"]
        setattr(context, "_prompt_skills", skill_scope["prompt_skills"])
        setattr(context, "_readable_skills", skill_scope["readable_skills"])
        setattr(context, "_runtime_skill_metadata", skill_scope["runtime_skill_metadata"])
        setattr(context, "_runtime_skill_dependency_map", skill_scope["runtime_skill_dependency_map"])

    return context
