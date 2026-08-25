import os
import re
from pathlib import Path
from typing import Annotated

import httpx
from langchain.tools import InjectedToolCallId
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool as langchain_tool
from langgraph.prebuilt.tool_node import ToolRuntime
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

from yuxi.agents.toolkits.registry import ToolExtraMetadata, _all_tool_instances, _extra_registry, tool
from yuxi.utils import logger
from yuxi.utils.paths import (
    CONVERSATION_HISTORY_DIR_NAME,
    LARGE_TOOL_RESULTS_DIR_NAME,
    OUTPUTS_DIR_NAME,
    UPLOADS_DIR_NAME,
    VIRTUAL_PATH_OUTPUTS,
    WORKSPACE_DIR_NAME,
)
from yuxi.utils.question_utils import normalize_questions

_PRESENT_ARTIFACTS_INTERNAL_DIR_NAMES = frozenset(
    {CONVERSATION_HISTORY_DIR_NAME, LARGE_TOOL_RESULTS_DIR_NAME, "large_tool_history"}
)
_OCR_PARSE_ALLOWED_DIRS = frozenset({WORKSPACE_DIR_NAME, UPLOADS_DIR_NAME, OUTPUTS_DIR_NAME})
_OCR_OUTPUT_DIR_NAME = "ocr"
_OCR_PREVIEW_LIMIT = 1200
_SAFE_OUTPUT_STEM_RE = re.compile(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+")


_DOUBAO_SEARCH_URL = "https://open.feedcoopapi.com/search_api/web_search"

DOUBAO_SEARCH_DESCRIPTION = """执行网络网页搜索，通过豆包联网搜索获取实时高质量互联网网页内容、新闻和站点资料。

适用场景：
1. 获取最新的时事新闻、即时信息或最新科技动态
2. 检索特定网站的内容（通过 sites 参数指定）
3. 查找指定时间范围内发布的新闻或文章（通过 time_range 参数过滤）

参数使用建议：
- query: 输入简短清晰的搜索关键词或简短提问
- count: 默认 10 条，深度调研可适当调大（最多 50 条）
- time_range: 需要最新消息或时效性强的资讯时建议传入 'OneDay'、'OneWeek' 或 'OneMonth'
- sites: 仅需特定站点（如官媒、平台）时传入站点域名
"""


class DoubaoSearchInput(BaseModel):
    query: str = Field(description="搜索查询词，1-100字符，必须精准描述检索需求")
    count: int = Field(default=10, ge=1, le=50, description="返回搜索结果数量，支持 1-50 条，默认 10 条")
    time_range: str | None = Field(
        default=None,
        description=(
            "按发文时间筛选结果。可选枚举值:\n"
            "- 'OneDay': 近24小时内\n"
            "- 'OneWeek': 近1周内\n"
            "- 'OneMonth': 近1个月内\n"
            "- 'OneYear': 近1年内\n"
            "- 'YYYY-MM-DD..YYYY-MM-DD': 自定义日期范围区间 (如 '2025-01-01..2025-12-31')"
        ),
    )
    sites: list[str] | None = Field(
        default=None, description="指定限定搜索的完整域名列表 (如 ['sohu.com', '163.com'])，最多支持 20 个站点"
    )
    block_hosts: list[str] | None = Field(
        default=None, description="指定屏蔽的搜索域名列表 (如 ['example.com'])，最多支持 5 个站点"
    )
    content_format: str = Field(
        default="text", description="正文返回格式，支持 'text' (纯文本) 或 'markdown' (Markdown 格式)，默认 'text'"
    )


def _build_doubao_search_payload(
    query: str,
    count: int,
    time_range: str | None,
    sites: list[str] | None,
    block_hosts: list[str] | None,
    content_format: str,
) -> dict:
    filter_obj: dict[str, str | bool] = {"NeedUrl": True}
    if sites:
        filter_obj["Sites"] = "|".join(sites[:20])
    if block_hosts:
        filter_obj["BlockHosts"] = "|".join(block_hosts[:5])

    payload = {
        "Query": query[:100],
        "SearchType": "web",
        "Count": min(max(1, count), 50),
        "Filter": filter_obj,
        "ContentFormats": "markdown" if content_format.lower() == "markdown" else "text",
    }
    if time_range:
        payload["TimeRange"] = time_range
    return payload


def _parse_doubao_search_response(query: str, data: dict) -> dict:
    error_info = data.get("ResponseMetadata", {}).get("Error")
    if error_info:
        logger.error(f"Doubao search API returned error: {error_info}")
        return {"query": query, "results": [], "error": error_info.get("Message", "Unknown error")}

    result_data = data.get("Result") or {}
    results = []
    for item in result_data.get("WebResults") or []:
        res_item = {
            "title": item.get("Title") or "",
            "url": item.get("Url") or "",
            "content": item.get("Summary") or item.get("Snippet") or item.get("Content") or "",
            "score": item.get("RankScore"),
        }
        if item.get("SiteName"):
            res_item["site_name"] = item["SiteName"]
        if item.get("PublishTime"):
            res_item["publish_time"] = item["PublishTime"]
        results.append(res_item)

    return {
        "query": query,
        "results": results,
        "response_time": result_data.get("TimeCost", 0) / 1000.0,
    }


@langchain_tool("web_search", args_schema=DoubaoSearchInput, description=DOUBAO_SEARCH_DESCRIPTION)
def _doubao_search(
    query: str,
    count: int = 10,
    time_range: str | None = None,
    sites: list[str] | None = None,
    block_hosts: list[str] | None = None,
    content_format: str = "text",
) -> dict:
    api_key = os.getenv("DOUBAO_SEARCH_API_KEY")
    if not api_key:
        return {"query": query, "results": [], "error": "DOUBAO_SEARCH_API_KEY 未配置"}

    payload = _build_doubao_search_payload(query, count, time_range, sites, block_hosts, content_format)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(_DOUBAO_SEARCH_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.error(f"Doubao search failed: {exc}")
        return {"query": query, "results": [], "error": str(exc)}

    return _parse_doubao_search_response(query, data)


def _create_doubao_search():
    """Create the Doubao web search tool instance."""
    return _doubao_search


def _create_tavily_search():
    """Create the Tavily web search tool instance with tool name web_search."""
    from langchain_tavily import TavilySearch

    return TavilySearch(name="web_search")


# provider -> (required env var, factory, display name)
_WEB_SEARCH_PROVIDERS = {
    "doubao": ("DOUBAO_SEARCH_API_KEY", _create_doubao_search, "豆包 网页搜索"),
    "tavily": ("TAVILY_API_KEY", _create_tavily_search, "Tavily 网页搜索"),
}


def _resolve_web_search_provider() -> str | None:
    """Resolve the web search provider to use from WEB_SEARCH_PROVIDER, or auto-detect by API key."""
    configured = os.getenv("WEB_SEARCH_PROVIDER", "").strip().lower()
    if configured:
        if configured not in _WEB_SEARCH_PROVIDERS:
            logger.warning(f"Unknown WEB_SEARCH_PROVIDER '{configured}', ignoring.")
            return None
        env_key, _, _ = _WEB_SEARCH_PROVIDERS[configured]
        if not os.getenv(env_key):
            logger.warning(f"WEB_SEARCH_PROVIDER is set to '{configured}', but {env_key} is not configured.")
            return None
        return configured

    return next(
        (provider for provider, (env_key, _, _) in _WEB_SEARCH_PROVIDERS.items() if os.getenv(env_key)),
        None,
    )


def _register_web_search_tool() -> None:
    """Register the web search tool selected via WEB_SEARCH_PROVIDER (or auto-detection)."""
    provider = _resolve_web_search_provider()
    if provider is None:
        return

    _, create_tool, display_name = _WEB_SEARCH_PROVIDERS[provider]
    _extra_registry["web_search"] = ToolExtraMetadata(category="buildin", tags=["搜索"], display_name=display_name)
    _all_tool_instances.append(create_tool())


# 模块加载时注册网络搜索工具
try:
    _register_web_search_tool()
except Exception as e:
    logger.warning(f"Failed to register web search tool: {e}")


class PresentArtifactsInput(BaseModel):
    """Expose artifact files to the frontend after the agent finishes."""

    filepaths: list[str] = Field(
        description=f"Danh sách đường dẫn tuyệt đối của các tệp cần hiển thị cho người dùng, chỉ được nằm dưới {VIRTUAL_PATH_OUTPUTS} và không được là tệp chạy nội bộ"
    )


def _normalize_presented_artifact_path(filepath: str, runtime: ToolRuntime) -> str:
    from yuxi.agents.backends.sandbox.paths import (
        VIRTUAL_PATH_PREFIX,
        ensure_thread_dirs,
        resolve_virtual_path,
        sandbox_outputs_dir,
    )

    outputs_virtual_prefix = f"{VIRTUAL_PATH_PREFIX}/outputs"
    runtime_context = runtime.context
    thread_id = getattr(runtime_context, "file_thread_id", None) or getattr(runtime_context, "thread_id", None)
    if not thread_id:
        raise ValueError("Thiếu thread_id trong runtime hiện tại")
    uid = getattr(runtime_context, "uid", None)
    if not uid:
        raise ValueError("Thiếu uid trong runtime hiện tại")

    ensure_thread_dirs(thread_id, str(uid))
    outputs_dir = sandbox_outputs_dir(thread_id).resolve()
    normalized_input = str(filepath or "").strip()
    if not normalized_input:
        raise ValueError("Đường dẫn tệp không được để trống")

    stripped = normalized_input.lstrip("/")
    virtual_prefix = VIRTUAL_PATH_PREFIX.lstrip("/")
    if stripped == virtual_prefix or stripped.startswith(f"{virtual_prefix}/"):
        actual_path = resolve_virtual_path(thread_id, normalized_input, uid=str(uid))
    else:
        actual_path = Path(normalized_input).expanduser().resolve()

    if not actual_path.exists() or not actual_path.is_file():
        raise ValueError(f"Tệp không tồn tại hoặc không phải là tệp thông thường: {normalized_input}")

    try:
        relative_path = actual_path.relative_to(outputs_dir)
    except ValueError as exc:
        raise ValueError(f"Chỉ cho phép hiển thị các tệp dưới {outputs_virtual_prefix}/: {normalized_input}") from exc

    if relative_path.parts and relative_path.parts[0] in _PRESENT_ARTIFACTS_INTERNAL_DIR_NAMES:
        raise ValueError(
            f"Không cho phép hiển thị tệp giai đoạn gọi công cụ: {outputs_virtual_prefix}/{relative_path.as_posix()}"
        )

    return f"{outputs_virtual_prefix}/{relative_path.as_posix()}"


PRESENT_ARTIFACTS_DESCRIPTION = f"""
Hiển thị tệp kết quả đã được tạo cho người dùng.

Trường hợp sử dụng:
1. Bạn đã ghi tệp kết quả cuối cùng dưới `{VIRTUAL_PATH_OUTPUTS}`
2. Bạn muốn frontend hiển thị thẻ tệp kết quả này sau khi kết thúc cuộc trò chuyện
3. Các tệp này cần hỗ trợ tải xuống hoặc xem trước

Lưu ý:
1. Chỉ có thể truyền vào các tệp dưới `{VIRTUAL_PATH_OUTPUTS}`
2. Không truyền vào các tệp quá trình trung gian, chỉ gọi cho các tệp kết quả thực sự cần cho người dùng xem
3. Không truyền các tệp giai đoạn gọi công cụ, ví dụ:
   - `{VIRTUAL_PATH_OUTPUTS}/{LARGE_TOOL_RESULTS_DIR_NAME}`
   - `{VIRTUAL_PATH_OUTPUTS}/{CONVERSATION_HISTORY_DIR_NAME}`
4. Có thể truyền nhiều tệp cùng lúc
"""


@tool(
    category="buildin",
    tags=["file", "deliverable"],
    display_name="Hiển thị sản phẩm giao nộp",
    description=PRESENT_ARTIFACTS_DESCRIPTION,
    args_schema=PresentArtifactsInput,
)
def present_artifacts(
    filepaths: list[str],
    runtime: ToolRuntime,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Đăng ký tệp sản phẩm giao nộp trong thư mục outputs của luồng hiện tại để hiển thị cho người dùng khi kết thúc hội thoại."""
    try:
        normalized_paths = [_normalize_presented_artifact_path(filepath, runtime) for filepath in filepaths]
    except ValueError as exc:
        return Command(update={"messages": [ToolMessage(content=f"Error: {exc}", tool_call_id=tool_call_id)]})

    return Command(
        update={
            "artifacts": normalized_paths,
            "messages": [
                ToolMessage(content="Đã hiển thị sản phẩm giao nộp cho người dùng", tool_call_id=tool_call_id)
            ],
        }
    )


class OcrParseFileInput(BaseModel):
    """Parse a sandbox file with OCR and save the Markdown result."""

    file_path: str = Field(description="Đường dẫn ảo sandbox cần OCR phân tích, phải nằm trong /home/gem/user-data")
    ocr_engine: str | None = Field(default=None, description="Engine OCR tùy chọn; nếu bỏ qua sẽ dùng OCR mặc định của hệ thống")


OCR_PARSE_FILE_DESCRIPTION = f"""
Phân tích tệp PDF, tài liệu Office hoặc hình ảnh trong sandbox thành văn bản Markdown và lưu kết quả thành tệp.

Trường hợp sử dụng:
1. Người dùng tải lên tệp đính kèm PDF, tài liệu Office hoặc hình ảnh và cần trích xuất nội dung văn bản
2. Đã có tệp trong thư mục workspace, uploads hoặc outputs và cần chuyển thành Markdown có thể đọc được
3. Kết quả phân tích dài, sau đó nên dùng read_file để đọc tệp Markdown đã lưu


Lưu ý:
1. file_path phải là đường dẫn ảo trong /home/gem/user-data
2. Chỉ cho phép đọc các tệp thông thường trong workspace, uploads, outputs
3. Kết quả phân tích sẽ được ghi vào {VIRTUAL_PATH_OUTPUTS}/{_OCR_OUTPUT_DIR_NAME}/
4. Công cụ chỉ trả về đường dẫn tệp kết quả và bản xem trước ngắn, không trả về toàn bộ văn bản OCR trực tiếp
5. Nếu cần hiển thị tệp kết quả trên giao diện người dùng, vui lòng gọi tiếp present_artifacts
"""


@tool(
    category="buildin",
    tags=["Tệp tin", "OCR"],
    display_name="Trích xuất OCR tệp tin",
    description=OCR_PARSE_FILE_DESCRIPTION,
    args_schema=OcrParseFileInput,
)
async def ocr_parse_file(file_path: str, runtime: ToolRuntime, ocr_engine: str | None = None) -> dict:
    """Parse a sandbox file with OCR, persist Markdown output, and return only a short result summary."""
    from yuxi.agents.backends.sandbox.paths import virtual_path_for_thread_file
    from yuxi.services.ocr_service import parse_document

    file_thread_id, uid, actual_path = _resolve_ocr_source_path(file_path, runtime)
    engine = _resolve_ocr_engine(ocr_engine)
    markdown = await parse_document(str(actual_path), params={"ocr_engine": engine})

    output_path = _next_ocr_output_path(file_thread_id, actual_path)
    output_path.write_text(markdown, encoding="utf-8")
    parsed_path = virtual_path_for_thread_file(file_thread_id, output_path, uid=uid)
    source_virtual_path = virtual_path_for_thread_file(file_thread_id, actual_path, uid=uid)
    preview, truncated = _ocr_preview(markdown)

    return {
        "source_path": source_virtual_path,
        "parsed_path": parsed_path,
        "ocr_engine": engine,
        "char_count": len(markdown),
        "preview": preview,
        "truncated": truncated,
    }


def _resolve_ocr_source_path(file_path: str, runtime: ToolRuntime) -> tuple[str, str, Path]:
    """Resolve a sandbox virtual path to a host file inside the Agent-visible user-data roots."""
    from yuxi.agents.backends.sandbox.paths import get_virtual_path_prefix, resolve_virtual_path

    file_thread_id, uid = _resolve_runtime_file_scope(runtime)

    normalized_input = str(file_path or "").strip()
    if not normalized_input:
        raise ValueError("Đường dẫn tệp không được để trống")

    virtual_prefix = get_virtual_path_prefix().rstrip("/")
    clean_virtual_path = "/" + normalized_input.lstrip("/")
    if clean_virtual_path != virtual_prefix and not clean_virtual_path.startswith(f"{virtual_prefix}/"):
        raise ValueError(f"Chỉ cho phép phân tích đường dẫn ảo sandbox trong {virtual_prefix}")

    relative_path = clean_virtual_path[len(virtual_prefix) :].lstrip("/")
    namespace = Path(relative_path).parts[0] if relative_path else ""
    if namespace not in _OCR_PARSE_ALLOWED_DIRS:
        allowed = ", ".join(f"{virtual_prefix}/{item}" for item in sorted(_OCR_PARSE_ALLOWED_DIRS))
        raise ValueError(f"Chỉ cho phép phân tích tệp trong {allowed}")

    try:
        actual_path = resolve_virtual_path(file_thread_id, clean_virtual_path, uid=uid)
    except ValueError as exc:
        raise ValueError(f"Chỉ cho phép phân tích đường dẫn ảo sandbox trong {virtual_prefix}") from exc
    if not actual_path.exists():
        raise ValueError(f"Tệp không tồn tại: {clean_virtual_path}")
    if not actual_path.is_file():
        raise ValueError(f"Đường dẫn không phải là tệp thông thường: {clean_virtual_path}")

    return file_thread_id, uid, actual_path


def _resolve_runtime_file_scope(runtime: ToolRuntime) -> tuple[str, str]:
    """Read the thread and user scope needed for sandbox path mapping from ToolRuntime."""
    thread_id = _runtime_scope_value(runtime, "file_thread_id") or _runtime_scope_value(runtime, "thread_id")
    uid = _runtime_scope_value(runtime, "uid")
    if not thread_id:
        raise ValueError("Runtime hiện tại thiếu thread_id")
    if not uid:
        raise ValueError("Runtime hiện tại thiếu uid")
    return thread_id, uid


def _runtime_scope_value(runtime: ToolRuntime, key: str) -> str | None:
    """Look up a runtime scope value from LangGraph config, context, or state."""
    config = getattr(runtime, "config", None)
    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    sources = (
        configurable if isinstance(configurable, dict) else {},
        getattr(runtime, "context", None),
        getattr(runtime, "state", None) if isinstance(getattr(runtime, "state", None), dict) else {},
    )
    for source in sources:
        value = source.get(key) if isinstance(source, dict) else getattr(source, key, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _resolve_ocr_engine(ocr_engine: str | None) -> str:
    """Validate the requested OCR engine, falling back to the system default when omitted."""
    from yuxi.knowledge.parser.factory import DocumentProcessorFactory
    from yuxi.services.ocr_service import resolve_ocr_engine_id

    engine = resolve_ocr_engine_id(ocr_engine)
    allowed = {"disable", *DocumentProcessorFactory.get_available_processors()}
    if engine not in allowed:
        raise ValueError(f"Engine OCR không được hỗ trợ: {engine}")
    return engine


def _next_ocr_output_path(thread_id: str, source_path: Path) -> Path:
    """Choose a non-conflicting Markdown output path under the thread outputs/ocr directory."""
    from yuxi.agents.backends.sandbox.paths import sandbox_outputs_dir

    output_dir = sandbox_outputs_dir(thread_id) / _OCR_OUTPUT_DIR_NAME
    output_dir.mkdir(parents=True, exist_ok=True)

    base_name = _safe_ocr_output_stem(source_path)
    candidate = output_dir / f"{base_name}.md"
    index = 1
    while candidate.exists():
        candidate = output_dir / f"{base_name}-{index}.md"
        index += 1
    return candidate


def _safe_ocr_output_stem(source_path: Path) -> str:
    """Build a filesystem-friendly output filename stem from the source file name."""
    stem = source_path.stem.strip() or "ocr_result"
    safe_stem = _SAFE_OUTPUT_STEM_RE.sub("_", stem).strip("._-")
    return safe_stem or "ocr_result"


def _ocr_preview(markdown: str) -> tuple[str, bool]:
    """Return the short preview included in the tool result and whether it was truncated."""
    if len(markdown) <= _OCR_PREVIEW_LIMIT:
        return markdown, False
    return markdown[:_OCR_PREVIEW_LIMIT].rstrip(), True


ASK_USER_QUESTION_DESCRIPTION = """
Trong quá trình thực thi, khi bạn cần người dùng đưa ra quyết định hoặc bổ sung yêu cầu, hãy sử dụng công cụ này để hỏi người dùng.

Kịch bản áp dụng:
1. Thu thập sở thích hoặc yêu cầu của người dùng (ví dụ: phong cách, phạm vi, mức độ ưu tiên)
2. Làm rõ các chỉ thị mơ hồ (khi có nhiều cách hiểu hợp lý)
3. Cho phép người dùng chọn hướng giải pháp trong quá trình triển khai
4. Cho phép người dùng thực hiện đánh đổi khi có sự cân nhắc rõ ràng

Quy chuẩn sử dụng:
1. questions cung cấp từ 1-5 câu hỏi, mỗi mục bao gồm: question, options, multi_select, allow_other
2. options của mỗi câu hỏi cung cấp từ 2-5 tùy chọn có tính phân biệt, mỗi mục bao gồm label và value
3. Nếu có tùy chọn được đề xuất: đặt tùy chọn đề xuất ở vị trí đầu tiên và thêm "(Recommended)" vào cuối label
4. Nếu cần chọn nhiều: đặt multi_select của câu hỏi đó thành true
5. allow_other thường giữ là true, người dùng có thể nhập câu trả lời tùy chỉnh qua Other

Lưu ý:
1. Không sử dụng công cụ này để hỏi các câu hỏi kiểm soát luồng như "có tiếp tục thực thi không" hoặc "kế hoạch đã sẵn sàng chưa"
2. Không lạm dụng công cụ này khi thông tin đã đầy đủ và người dùng không cần đưa ra quyết định
3. Tự đưa ra quyết định dựa trên ngữ cảnh hiện tại trước, chỉ hỏi khi có sự không chắc chắn quan trọng

Kết quả trả về:
answer là object, có định dạng {question_id: answer}.
Trong đó answer có thể là string (chọn một), list (chọn nhiều) hoặc object (văn bản nhập ở Other).
"""


@tool(
    category="buildin",
    tags=["interaction"],
    display_name="Hỏi người dùng",
    description=ASK_USER_QUESTION_DESCRIPTION,
)
def ask_user_question(
    questions: Annotated[
        list[dict] | str | None,
        "Danh sách câu hỏi, định dạng mỗi mục {question, options, multi_select, allow_other, question_id(optional)}",
    ] = None,
) -> dict:
    """Gửi câu hỏi tới người dùng và đợi câu trả lời."""
    # Parse the questions parameter: if it is a string, try to parse it as JSON
    if isinstance(questions, str):
        try:
            import json

            questions = json.loads(questions)
            logger.debug(f"Parsed string questions to list: {questions}")
        except Exception as e:
            logger.error(f"Failed to parse questions string: {e}, using None")
            questions = None

    normalized_questions = normalize_questions(questions or [])

    if not normalized_questions:
        raise ValueError("questions phải chứa ít nhất một câu hỏi hợp lệ")

    interrupt_payload = {
        "questions": normalized_questions,
        "source": "ask_user_question",
    }
    answer = interrupt(interrupt_payload)

    return {
        "questions": normalized_questions,
        "answer": answer,
    }
