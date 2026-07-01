from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BuiltinSkillSpec:
    slug: str
    source_dir: Path
    description: str = ""
    version: str = "1.0.0"
    tool_dependencies: tuple[str, ...] = ()
    mcp_dependencies: tuple[str, ...] = ()
    skill_dependencies: tuple[str, ...] = ()


_SKILLS_ROOT = Path(__file__).resolve().parent

BUILTIN_SKILLS: list[BuiltinSkillSpec] = [
    BuiltinSkillSpec(
        slug="image-gen",
        source_dir=_SKILLS_ROOT / "image-gen",
        description="Tạo hình ảnh trong sandbox Agent và lưu vào thư mục outputs, mặc định hỗ trợ Qwen-Image, cũng có thể kết nối với các giao diện tạo hình ảnh khác.",
        version="2026.06.02",
        tool_dependencies=("present_artifacts",),
    ),
    BuiltinSkillSpec(
        slug="deep-research",
        source_dir=_SKILLS_ROOT / "deep-research",
        description="Phương pháp luận điều phối nghiên cứu chuyên sâu: làm rõ phạm vi, phân rã kế hoạch, lập lịch song song khảo sát của các sub-agent, đối kháng kiểm chứng, tổng hợp thành báo cáo có cấu trúc kèm trích dẫn.",
        version="2026.06.05",
        tool_dependencies=("tavily_search",),
    ),
    BuiltinSkillSpec(
        slug="knowledge-base",
        source_dir=_SKILLS_ROOT / "knowledge-base",
        description="Sử dụng kho kiến thức Yuxi để tìm kiếm, mở tài liệu, định vị trong tài liệu và xem sơ đồ tư duy.",
        version="2026.06.24",
        tool_dependencies=(
            "list_kbs",
            "query_kb",
            "find_kb_document",
            "open_kb_document",
            "get_mindmap",
            "search_file",
        ),
    ),
    BuiltinSkillSpec(
        slug="mysql-reporter",
        source_dir=_SKILLS_ROOT / "mysql-reporter",
        description="Tạo báo cáo truy vấn MySQL và tạo biểu đồ trực quan hóa.",
        version="2026.06.05",
        mcp_dependencies=("mcp-server-chart",),
    ),
]
