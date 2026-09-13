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
        slug="html-preview",
        source_dir=_SKILLS_ROOT / "html-preview",
        description=(
            "Render lightweight static HTML/CSS visualizations with Markdown `html:preview` fences, "
            "suitable for numeric comparisons, flows, timelines, hierarchies, and key metrics."
        ),
        version="2026.07.23",
    ),
    BuiltinSkillSpec(
        slug="deep-research",
        source_dir=_SKILLS_ROOT / "deep-research",
        description="Phương pháp luận điều phối nghiên cứu chuyên sâu: làm rõ phạm vi, phân rã kế hoạch, lập lịch song song khảo sát của các sub-agent, đối kháng kiểm chứng, tổng hợp thành báo cáo có cấu trúc kèm trích dẫn.",
        version="2026.07.29",
        tool_dependencies=("web_search",),
        skill_dependencies=("html-preview",),
    ),
    BuiltinSkillSpec(
        slug="knowledge-base",
        source_dir=_SKILLS_ROOT / "knowledge-base",
        description="Sử dụng kho kiến thức Yuxi để tìm kiếm, mở tài liệu, định vị trong tài liệu và xem sơ đồ tư duy.",
        version="2026.06.24",
        tool_dependencies=(
            "list_kbs",
            "query_kb",
            "query_keywords",
            "find_kb_document",
            "open_kb_document",
            "get_mindmap",
            "search_file",
            "download_kb_file",
        ),
    ),
    BuiltinSkillSpec(
        slug="mysql-reporter",
        source_dir=_SKILLS_ROOT / "mysql-reporter",
        description="Tạo báo cáo truy vấn và biểu đồ trực quan hóa dựa trên cơ sở dữ liệu MySQL, thích hợp cho việc phân tích các chỉ số kinh doanh, xu hướng thống kê và hiển thị kết quả bằng Charts MCP.",
        version="2026.06.05",
        mcp_dependencies=("mcp-server-chart",),
    ),
]
