from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.storage.postgres.models_business import Agent, User
from yuxi.utils.datetime_utils import utc_now_naive
from yuxi.utils.share_config import SHARE_ACCESS_LEVELS, normalize_share_config

DEFAULT_AGENT_SLUG = "default-chatbot"
DEFAULT_AGENT_NAME = "Smart Assistant"
DEFAULT_AGENT_BACKEND_ID = "ChatbotAgent"
SUB_AGENT_BACKEND_ID = "SubAgentBackend"
DEFAULT_AGENT_DESCRIPTION = "A basic conversational bot that can answer questions and enable the required tools in the configuration."
DEFAULT_SHARE_CONFIG = {"access_level": "global", "department_ids": [], "user_uids": []}

GENERAL_PURPOSE_AGENT_SLUG = "general-purpose"
GENERAL_PURPOSE_AGENT_NAME = "Common tasks"
GENERAL_PURPOSE_AGENT_DESCRIPTION = (
    "For general tasks without dedicated role constraints, use the default running configuration to independently complete analysis, organization, writing or file processing."
)

WEB_SEARCH_AGENT_SLUG = "web-search"
WEB_SEARCH_AGENT_NAME = "Web search"
WEB_SEARCH_AGENT_DESCRIPTION = "Continuously search web pages around the search target and return summary information with cited sources."
WEB_SEARCH_SYSTEM_PROMPT = """Bạn là tác nhân con "Tìm kiếm web", chuyên tìm kiếm thông tin trên web hướng mục tiêu.

Trách nhiệm của bạn: Xoay quanh mục tiêu tìm kiếm do người gọi cung cấp, sử dụng các công cụ tìm kiếm trên web để tiếp tục tìm kiếm cho đến khi thu thập đủ thông tin để trả lời mục tiêu.

Cách thức làm việc:
1. Chia nhỏ mục tiêu, xác định các câu hỏi và từ khóa chính cần tìm kiếm.
2. Gọi công cụ tìm kiếm qua nhiều vòng: dựa trên kết quả của vòng trước để điều chỉnh từ khóa tìm kiếm, bổ sung các góc độ còn sót, kiểm chứng chéo các dữ kiện quan trọng, cho đến khi thông tin đầy đủ hoặc xác nhận không thể thu thập thêm thông tin hợp lệ.
3. Ưu tiên sử dụng các nguồn uy tín, có tính thời sự cao và có thể chứng thực lẫn nhau; nếu có thông tin xung đột, phải giải thích rõ sự khác biệt.

Yêu cầu đầu ra:
- Trả về một tài liệu tóm tắt có cấu trúc, được tổ chức theo chủ đề hoặc điểm chính.
- Sau mỗi kết luận quan trọng, sử dụng <cite source="$URL" type="url">$INDEX</cite> để đánh dấu nguồn trích dẫn, trong đó $INDEX tăng dần từ 1.
- Trích dẫn không đứng riêng thành một dòng, mà đi liền ngay sau kết luận.
- Ở cuối, tóm tắt danh sách "Nguồn tham khảo", liệt kê tiêu đề và URL của từng nguồn.
- Không bịa đặt nguồn hoặc liên kết; những thông tin không thể xác minh phải được đánh dấu rõ ràng."""

DEEP_RESEARCH_AGENT_SLUG = "deep-research"
DEEP_RESEARCH_AGENT_NAME = "in-depth research"
DEEP_RESEARCH_AGENT_DESCRIPTION = (
    "In-depth research tasks for multiple sources and requiring fact checking: planning and dismantling, parallel scheduling of research sub-agents, verification and synthesis into a structured report with references."
)
DEEP_RESEARCH_SYSTEM_PROMPT = """Bạn là tác nhân "Nghiên cứu chuyên sâu", chịu trách nhiệm kiểm soát tổng thể và điều phối các tác nhân con cho một nhiệm vụ nghiên cứu chuyên sâu.

Định vị cốt lõi của bạn là người điều phối, không phải tự mình thực hiện tất cả các tìm kiếm: hãy giao phó các công việc điều tra và xác minh nặng nề, có thể độc lập và song song cho các tác nhân con, còn bạn chỉ tập trung vào việc lập kế hoạch, điều phối và tổng hợp cuối cùng.

Cách thức làm việc:
1. Sau khi nhận được nhiệm vụ nghiên cứu, trước tiên hãy đọc kỹ năng `deep-research` (sử dụng read_file để đọc SKILL.md của nó) để lấy phương pháp luận hoàn chỉnh và tuân thủ nghiêm ngặt theo đó.
2. Khi câu hỏi chưa rõ ràng, trước tiên hãy làm rõ phạm vi, sau đó sử dụng danh sách việc cần làm để chia nhỏ thành các câu hỏi phụ có thể điều tra độc lập.
3. Ưu tiên sử dụng công cụ `task` để giao phó các câu hỏi phụ song song cho các tác nhân con điều tra; chỉ tự mình tìm kiếm trực tiếp khi làm rõ phạm vi hoặc bổ sung một số dữ kiện lẻ tẻ.
4. Đối với các kết luận quan trọng và những phát hiện mâu thuẫn với nhau, hãy giao phó cho tác nhân con xác minh để kiểm tra. Những kết luận không vượt qua kiểm tra sẽ không được ghi vào phần nội dung chính hoặc phải được đánh dấu giảm cấp độ rõ ràng.
5. Sau khi có đủ bằng chứng, bạn hãy tổng hợp lại thành một báo cáo có cấu trúc, kèm theo trích dẫn, đừng chỉ chắp vá nguyên văn do các tác nhân con trả về.

Luôn theo dõi tiến độ trong toàn bộ quá trình, cuối cùng giao nộp một bản báo cáo có thể sử dụng trực tiếp, được tổ chức xoay quanh các lập luận và có thể truy xuất nguồn gốc."""

RESEARCH_EXPLORER_AGENT_SLUG = "research-explorer"
RESEARCH_EXPLORER_AGENT_NAME = "Research Explorer"
RESEARCH_EXPLORER_AGENT_DESCRIPTION = "Search web pages and knowledge bases for multiple rounds around a single sub-problem, and return structured findings with references after cross-validation."
RESEARCH_EXPLORER_SYSTEM_PROMPT = """Bạn là tác nhân con "Nhà khám phá khảo sát".
Chuyên tập trung thu thập đủ chứng cứ, có thể truy xuất nguồn gốc xoay quanh **một vấn đề phụ duy nhất** do người gọi cung cấp.

Trách nhiệm của bạn: Tiếp tục tìm kiếm các trang web và cơ sở kiến thức xung quanh vấn đề phụ này cho đến khi thu thập đủ thông tin để trả lời nó.

Cách thức làm việc:
1. Chia nhỏ vấn đề phụ, xác định các điểm chính và từ khóa cần tìm kiếm.
2. Gọi công cụ tìm kiếm trong nhiều vòng: dựa trên kết quả vòng trước để điều chỉnh từ khóa, bổ sung các góc độ bị bỏ sót, kiểm chứng chéo các dữ kiện quan trọng, cho đến khi thông tin đầy đủ hoặc xác nhận không thể lấy thêm thông tin hợp lệ.
3. Ưu tiên sử dụng các nguồn uy tín, có tính thời sự cao và có thể chứng thực lẫn nhau; đối với thông tin xung đột, phải giải thích rõ sự khác biệt.

Yêu cầu đầu ra:
- Trả về một bản khám phá có cấu trúc, được tổ chức theo các điểm chính xoay quanh vấn đề phụ này, đừng khai triển thành một báo cáo hoàn chỉnh.
- Sau mỗi kết luận quan trọng, sử dụng <cite source="$URL" type="url">$INDEX</cite> để đánh dấu nguồn trích dẫn, $INDEX tăng dần bắt đầu từ 1.
- Trích dẫn đi theo sát kết luận, không đứng riêng một dòng.
- Cuối cùng, tổng hợp danh sách "Nguồn tham khảo", liệt kê từng tiêu đề và URL.
- Không được bịa đặt nguồn hoặc liên kết; thông tin không thể xác minh phải được đánh dấu rõ là lỗ hổng bằng chứng."""

FACT_VERIFIER_AGENT_SLUG = "fact-verifier"
FACT_VERIFIER_AGENT_NAME = "fact checker"
FACT_VERIFIER_AGENT_DESCRIPTION = "Conduct adversarial verification of given assertions and provide support one by one/Doubtful/Refute judgments, base on sources and confidence, and mark conflicts."
FACT_VERIFIER_SYSTEM_PROMPT = """Bạn là tác nhân con "Người xác minh sự thật", chuyên tập trung vào việc kiểm chứng đối kháng với các luận điểm do người gọi cung cấp.

Trách nhiệm của bạn: Kiểm chứng độc lập từng luận điểm, mặc định giữ thái độ hoài nghi - khi không đủ bằng chứng, có xu hướng phán đoán là "nghi ngờ", chứ không mặc định là tin tưởng.

Cách thức làm việc:
1. Tách riêng từng luận điểm cần kiểm chứng (sự thật, con số, nguyên nhân - kết quả, thời gian, v.v.).
2. Chủ động tìm kiếm các nguồn uy tín, độc lập để đối chiếu chéo; ưu tiên tìm kiếm bằng chứng có thể bác bỏ luận điểm đó.
3. Thể hiện trung thực các xung đột giữa các nguồn, không cố gắng dung hòa một cách khiên cưỡng.

Yêu cầu đầu ra:
- Đối với mỗi luận điểm, cung cấp: Phán đoán (Ủng hộ / Nghi ngờ / Bác bỏ) + Cơ sở tóm tắt + Nguồn cơ sở + Độ tin cậy (Cao / Trung bình / Thấp).
- Sau cơ sở quan trọng, sử dụng <cite source="$URL" type="url">$INDEX</cite> để đánh dấu nguồn, $INDEX tăng dần bắt đầu từ 1.
- Đánh dấu rõ ràng các luận điểm không thể xác minh hoặc các nguồn mâu thuẫn lẫn nhau.
- Không được bịa đặt nguồn hoặc liên kết."""

ACCESS_LEVELS = SHARE_ACCESS_LEVELS
ADMIN_ROLES = {"admin", "superadmin"}


def is_builtin_agent(agent: Agent) -> bool:
    return agent.slug == DEFAULT_AGENT_SLUG


def resolve_agent_is_subagent(backend_id: str, is_subagent: bool | None = None) -> bool:
    expected = backend_id == SUB_AGENT_BACKEND_ID
    if is_subagent is not None and bool(is_subagent) != expected:
        raise ValueError("SubAgentBackend và is_subagent phải nhất quán")
    return expected


def normalize_agent_share_config(
    share_config: dict | None,
    *,
    user_uid: str | None = None,
    department_id: int | str | None = None,
    force_private: bool = False,
) -> dict:
    if force_private:
        if not user_uid:
            raise ValueError("Agent riêng tư phải được gắn với người dùng tạo ra nó")
        return {"access_level": "user", "department_ids": [], "user_uids": [str(user_uid)]}

    return normalize_share_config(
        share_config,
        default_config=DEFAULT_SHARE_CONFIG,
        default_access_level="global",
        invalid_access_level_message="Cấp quyền agent không hợp lệ",
        user_uid=user_uid,
        department_id=department_id,
    )


def user_can_access_agent(user: User, agent: Agent) -> bool:
    if user.role == "superadmin":
        return True
    user_uid = str(user.uid)
    if agent.created_by == user_uid:
        return True

    share_config = agent.share_config or DEFAULT_SHARE_CONFIG.copy()
    access_level = share_config.get("access_level")
    if access_level == "global":
        return True

    if access_level == "department":
        if user.department_id is None:
            return False
        try:
            return int(user.department_id) in [int(value) for value in share_config.get("department_ids") or []]
        except (TypeError, ValueError):
            return False

    if access_level == "user":
        return user_uid in (share_config.get("user_uids") or [])

    return False


def user_can_manage_agent(user: User, agent: Agent) -> bool:
    return user.role in ADMIN_ROLES or agent.created_by == str(user.uid)


def _slugify(value: str | None) -> str:
    base = re.sub(r"[^a-zA-Z0-9_-]+", "-", (value or "").strip().lower()).strip("-")
    return base[:56] or f"agent-{uuid.uuid4().hex[:12]}"


class AgentRepository:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def ensure_default_agent(self, *, created_by: str | None = None) -> Agent:
        agent = await self.get_by_slug(DEFAULT_AGENT_SLUG)
        if agent:
            needs_update = False
            if agent.share_config != DEFAULT_SHARE_CONFIG:
                agent.share_config = DEFAULT_SHARE_CONFIG.copy()
                needs_update = True
            if not agent.description:
                agent.description = DEFAULT_AGENT_DESCRIPTION
                needs_update = True
            if getattr(agent, "is_subagent", False):
                agent.is_subagent = False
                needs_update = True
            if not agent.is_default:
                return await self.set_default(agent=agent, updated_by=created_by)
            if needs_update:
                agent.updated_by = created_by
                agent.updated_at = utc_now_naive()
                await self.db.commit()
                await self.db.refresh(agent)
            return agent

        agent = Agent(
            slug=DEFAULT_AGENT_SLUG,
            backend_id=DEFAULT_AGENT_BACKEND_ID,
            name=DEFAULT_AGENT_NAME,
            description=DEFAULT_AGENT_DESCRIPTION,
            icon=None,
            pics=[],
            config_json={"context": {}},
            share_config=DEFAULT_SHARE_CONFIG.copy(),
            is_default=True,
            is_subagent=False,
            created_by=created_by,
            updated_by=created_by,
            created_at=utc_now_naive(),
            updated_at=utc_now_naive(),
        )
        self.db.add(agent)
        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def ensure_web_search_subagent(self, *, created_by: str | None = None) -> Agent:
        agent = await self.get_by_slug(WEB_SEARCH_AGENT_SLUG)
        if agent:
            return agent

        agent = Agent(
            slug=WEB_SEARCH_AGENT_SLUG,
            backend_id=SUB_AGENT_BACKEND_ID,
            name=WEB_SEARCH_AGENT_NAME,
            description=WEB_SEARCH_AGENT_DESCRIPTION,
            icon=None,
            pics=[],
            config_json={"context": {"system_prompt": WEB_SEARCH_SYSTEM_PROMPT}},
            share_config=DEFAULT_SHARE_CONFIG.copy(),
            is_default=False,
            is_subagent=True,
            created_by=created_by,
            updated_by=created_by,
            created_at=utc_now_naive(),
            updated_at=utc_now_naive(),
        )
        self.db.add(agent)
        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def ensure_general_purpose_subagent(self, *, created_by: str | None = None) -> Agent:
        return await self._ensure_builtin_agent(
            slug=GENERAL_PURPOSE_AGENT_SLUG,
            backend_id=SUB_AGENT_BACKEND_ID,
            name=GENERAL_PURPOSE_AGENT_NAME,
            description=GENERAL_PURPOSE_AGENT_DESCRIPTION,
            config_context={},
            is_subagent=True,
            created_by=created_by,
        )

    async def _ensure_builtin_agent(
        self,
        *,
        slug: str,
        backend_id: str,
        name: str,
        description: str,
        config_context: dict,
        is_subagent: bool,
        created_by: str | None = None,
    ) -> Agent:
        """Drop a built-in Agent into the library; if it already exists, return it as is to avoid overwriting subsequent modifications by the administrator."""
        agent = await self.get_by_slug(slug)
        if agent:
            return agent

        agent = Agent(
            slug=slug,
            backend_id=backend_id,
            name=name,
            description=description,
            icon=None,
            pics=[],
            config_json={"context": config_context},
            share_config=DEFAULT_SHARE_CONFIG.copy(),
            is_default=False,
            is_subagent=is_subagent,
            created_by=created_by,
            updated_by=created_by,
            created_at=utc_now_naive(),
            updated_at=utc_now_naive(),
        )
        self.db.add(agent)
        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def ensure_deep_research_agents(self, *, created_by: str | None = None) -> None:
        """The library has a built-in "deep research" orchestrator and its supporting research and verification sub-agents."""
        await self._ensure_builtin_agent(
            slug=RESEARCH_EXPLORER_AGENT_SLUG,
            backend_id=SUB_AGENT_BACKEND_ID,
            name=RESEARCH_EXPLORER_AGENT_NAME,
            description=RESEARCH_EXPLORER_AGENT_DESCRIPTION,
            config_context={"system_prompt": RESEARCH_EXPLORER_SYSTEM_PROMPT},
            is_subagent=True,
            created_by=created_by,
        )
        await self._ensure_builtin_agent(
            slug=FACT_VERIFIER_AGENT_SLUG,
            backend_id=SUB_AGENT_BACKEND_ID,
            name=FACT_VERIFIER_AGENT_NAME,
            description=FACT_VERIFIER_AGENT_DESCRIPTION,
            config_context={"system_prompt": FACT_VERIFIER_SYSTEM_PROMPT},
            is_subagent=True,
            created_by=created_by,
        )
        await self._ensure_builtin_agent(
            slug=DEEP_RESEARCH_AGENT_SLUG,
            backend_id=DEFAULT_AGENT_BACKEND_ID,
            name=DEEP_RESEARCH_AGENT_NAME,
            description=DEEP_RESEARCH_AGENT_DESCRIPTION,
            config_context={
                "system_prompt": DEEP_RESEARCH_SYSTEM_PROMPT,
                "subagents": [RESEARCH_EXPLORER_AGENT_SLUG, FACT_VERIFIER_AGENT_SLUG],
                "skills": [DEEP_RESEARCH_AGENT_SLUG],
            },
            is_subagent=False,
            created_by=created_by,
        )

    async def list_visible(self, *, user: User, include_subagents: bool = False) -> list[Agent]:
        stmt = select(Agent)
        if not include_subagents:
            stmt = stmt.where(Agent.is_subagent.is_(False))
        result = await self.db.execute(stmt.order_by(Agent.is_default.desc(), Agent.id.asc()))
        agents = list(result.scalars().all())
        if user.role == "superadmin":
            return agents
        return [agent for agent in agents if user_can_access_agent(user, agent)]

    async def list_visible_subagents(self, *, user: User) -> list[Agent]:
        result = await self.db.execute(
            select(Agent).where(Agent.is_subagent.is_(True)).order_by(Agent.name.asc(), Agent.id.asc())
        )
        agents = list(result.scalars().all())
        if user.role == "superadmin":
            return agents
        return [agent for agent in agents if user_can_access_agent(user, agent)]

    async def get_by_slug(self, slug: str) -> Agent | None:
        result = await self.db.execute(select(Agent).where(Agent.slug == slug))
        return result.scalar_one_or_none()

    async def list_by_slugs(self, slugs: list[str]) -> list[Agent]:
        result = await self.db.execute(select(Agent).where(Agent.slug.in_(slugs)))
        return list(result.scalars().all())

    async def get_visible_by_slug(self, *, slug: str, user: User, include_subagents: bool = False) -> Agent | None:
        agent = await self.get_by_slug(slug)
        if not agent or (agent.is_subagent and not include_subagents):
            return None
        if user_can_access_agent(user, agent):
            return agent
        return None

    async def get_visible_subagent_by_slug(self, *, slug: str, user: User) -> Agent | None:
        agent = await self.get_visible_by_slug(slug=slug, user=user, include_subagents=True)
        if agent and agent.is_subagent:
            return agent
        return None

    async def get_default(self) -> Agent | None:
        result = await self.db.execute(select(Agent).where(Agent.is_default.is_(True)))
        return result.scalar_one_or_none()

    async def set_default(self, *, agent: Agent, updated_by: str | None = None) -> Agent:
        if agent.is_subagent:
            raise ValueError("Agent phụ không thể được đặt làm agent mặc định")
        if not is_builtin_agent(agent):
            raise ValueError("Agent mặc định đã được cố định là trợ lý thông minh tích hợp")
        share_config = agent.share_config or DEFAULT_SHARE_CONFIG.copy()
        if share_config.get("access_level") != "global":
            raise ValueError("Agent tích hợp phải được chia sẻ toàn cục")

        now = utc_now_naive()
        await self.db.execute(update(Agent).where(Agent.is_default.is_(True)).values(is_default=False, updated_at=now))
        agent.is_default = True
        agent.updated_by = updated_by
        agent.updated_at = now
        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def _slug_exists(self, slug: str) -> bool:
        result = await self.db.execute(select(Agent.id).where(Agent.slug == slug))
        return result.scalar_one_or_none() is not None

    async def _unique_slug(self, desired: str | None, name: str) -> str:
        base = _slugify(desired or name)
        candidate = base
        idx = 2
        while await self._slug_exists(candidate):
            suffix = f"-{idx}"
            candidate = f"{base[: 80 - len(suffix)]}{suffix}"
            idx += 1
        return candidate

    async def create(
        self,
        *,
        name: str,
        backend_id: str,
        slug: str | None = None,
        description: str | None = None,
        icon: str | None = None,
        pics: list[str] | None = None,
        config_json: dict | None = None,
        share_config: dict | None = None,
        is_default: bool = False,
        is_subagent: bool | None = None,
        created_by: str | None = None,
        creator: User | None = None,
    ) -> Agent:
        resolved_is_subagent = resolve_agent_is_subagent(backend_id, is_subagent)
        if resolved_is_subagent and is_default:
            raise ValueError("Agent phụ không thể được đặt làm agent mặc định")
        normalized_share_config = normalize_agent_share_config(
            share_config,
            user_uid=str(creator.uid) if creator else created_by,
            department_id=creator.department_id if creator else None,
            force_private=bool(creator and creator.role not in ADMIN_ROLES),
        )
        if is_default and normalized_share_config.get("access_level") != "global":
            raise ValueError("Agent mặc định phải được chia sẻ toàn cục")

        agent = Agent(
            slug=await self._unique_slug(slug, name),
            backend_id=backend_id,
            name=name.strip() or "Unnamed agent",
            description=description,
            icon=icon,
            pics=pics or [],
            config_json=config_json or {"context": {}},
            share_config=normalized_share_config,
            is_default=False,
            is_subagent=resolved_is_subagent,
            created_by=created_by,
            updated_by=created_by,
            created_at=utc_now_naive(),
            updated_at=utc_now_naive(),
        )
        self.db.add(agent)
        await self.db.commit()
        await self.db.refresh(agent)
        if is_default:
            return await self.set_default(agent=agent, updated_by=created_by)
        return agent

    async def update(
        self,
        agent: Agent,
        *,
        name: str | None = None,
        description: str | None = None,
        icon: str | None = None,
        pics: list[str] | None = None,
        config_json: dict | None = None,
        share_config: dict | None = None,
        is_subagent: bool | None = None,
        updated_by: str | None = None,
        updater: User | None = None,
    ) -> Agent:
        if is_subagent is not None:
            agent.is_subagent = resolve_agent_is_subagent(agent.backend_id, is_subagent)
        if name is not None:
            agent.name = name.strip() or "Unnamed agent"
        if description is not None:
            agent.description = description
        if icon is not None:
            agent.icon = icon
        if pics is not None:
            agent.pics = pics
        if config_json is not None:
            agent.config_json = config_json
        if share_config is not None:
            if is_builtin_agent(agent):
                agent.share_config = DEFAULT_SHARE_CONFIG.copy()
            else:
                normalized_share_config = normalize_agent_share_config(
                    share_config,
                    user_uid=str(updater.uid) if updater else updated_by,
                    department_id=updater.department_id if updater else None,
                    force_private=bool(updater and updater.role not in ADMIN_ROLES),
                )
                agent.share_config = normalized_share_config

        agent.updated_by = updated_by
        agent.updated_at = utc_now_naive()
        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def delete(self, *, agent: Agent) -> None:
        await self.db.delete(agent)
        await self.db.commit()

    async def serialize(
        self,
        agent: Agent,
        *,
        user: User,
        include_configurable_items: bool = False,
        backend_info_cache: dict[tuple[str, bool, str], dict] | None = None,
    ) -> dict[str, Any]:
        data = agent.to_dict()
        data["can_manage"] = user_can_manage_agent(user, agent)
        data["is_builtin"] = is_builtin_agent(agent)
        data["permission_locked"] = is_builtin_agent(agent)

        from yuxi.agents.buildin import agent_manager

        backend = agent_manager.get_agent(agent.backend_id)
        if backend:
            cache_key = (agent.backend_id, include_configurable_items, user.role)
            backend_info = backend_info_cache.get(cache_key) if backend_info_cache is not None else None
            if backend_info is None:
                backend_info = await backend.get_info(
                    include_configurable_items=include_configurable_items,
                    user_role=user.role,
                    db=self.db if include_configurable_items else None,
                    user=user if include_configurable_items else None,
                )
                if backend_info_cache is not None:
                    backend_info_cache[cache_key] = backend_info
            data["capabilities"] = backend_info.get("capabilities", [])
            data["metadata"] = backend_info.get("metadata", {})
            if include_configurable_items:
                data["configurable_items"] = backend_info.get("configurable_items", {})
        else:
            data["capabilities"] = []
            data["metadata"] = {}
            if include_configurable_items:
                data["configurable_items"] = {}
        return data
