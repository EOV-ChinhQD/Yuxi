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

DOUBAO_SEARCH_DESCRIPTION = """Perform web page search to retrieve real-time, high-quality internet content, news, and site information.

Use cases:
1. Get the latest news, real-time information, or recent technology trends
2. Search content from specific websites (via the sites parameter)
3. Find news or articles published within a specific time range (via the time_range parameter)

Parameter usage guide:
- query: Enter short, clear search keywords or a brief question
- count: Default 10 results; increase for in-depth research (max 50)
- time_range: Use 'OneDay', 'OneWeek', or 'OneMonth' when you need the latest or time-sensitive information
- sites: Specify site domains when only specific sites are needed (e.g., official media, platforms)
"""


class DoubaoSearchInput(BaseModel):
    query: str = Field(description="Search query, 1-100 characters, must precisely describe the search intent")
    count: int = Field(
        default=10, ge=1, le=50, description="Number of search results to return, supports 1-50, default 10"
    )
    time_range: str | None = Field(
        default=None,
        description=(
            "Filter results by publication time. Available values:\n"
            "- 'OneDay': Within the last 24 hours\n"
            "- 'OneWeek': Within the last week\n"
            "- 'OneMonth': Within the last month\n"
            "- 'OneYear': Within the last year\n"
            "- 'YYYY-MM-DD..YYYY-MM-DD': Custom date range (e.g., '2025-01-01..2025-12-31')"
        ),
    )
    sites: list[str] | None = Field(
        default=None,
        description="List of domain names to restrict search to (e.g., ['sohu.com', '163.com']), max 20 sites",
    )
    block_hosts: list[str] | None = Field(
        default=None, description="List of domain names to exclude from search (e.g., ['example.com']), max 5 sites"
    )
    content_format: str = Field(
        default="text",
        description="Content return format, supports 'text' (plain text) or 'markdown' (Markdown format), default 'text'",
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
        return {"query": query, "results": [], "error": "DOUBAO_SEARCH_API_KEY not configured"}

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
    "doubao": ("DOUBAO_SEARCH_API_KEY", _create_doubao_search, "Doubao Web Search"),
    "tavily": ("TAVILY_API_KEY", _create_tavily_search, "Tavily Web Search"),
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
    _extra_registry["web_search"] = ToolExtraMetadata(category="buildin", tags=["search"], display_name=display_name)
    _all_tool_instances.append(create_tool())


# Register web search tool at module load time
try:
    _register_web_search_tool()
except Exception as e:
    logger.warning(f"Failed to register web search tool: {e}")


class PresentArtifactsInput(BaseModel):
    """Expose artifact files to the frontend after the agent finishes."""

    filepaths: list[str] = Field(
        description=f"Absolute paths of files to present to the user, must be under {VIRTUAL_PATH_OUTPUTS} and must not be internal runtime files"
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
        raise ValueError("Missing thread_id in current runtime")
    uid = getattr(runtime_context, "uid", None)
    if not uid:
        raise ValueError("Missing uid in current runtime")

    ensure_thread_dirs(thread_id, str(uid))
    outputs_dir = sandbox_outputs_dir(thread_id).resolve()
    normalized_input = str(filepath or "").strip()
    if not normalized_input:
        raise ValueError("File path must not be empty")

    stripped = normalized_input.lstrip("/")
    virtual_prefix = VIRTUAL_PATH_PREFIX.lstrip("/")
    if stripped == virtual_prefix or stripped.startswith(f"{virtual_prefix}/"):
        actual_path = resolve_virtual_path(thread_id, normalized_input, uid=str(uid))
    else:
        actual_path = Path(normalized_input).expanduser().resolve()

    if not actual_path.exists() or not actual_path.is_file():
        raise ValueError(f"File does not exist or is not a regular file: {normalized_input}")

    try:
        relative_path = actual_path.relative_to(outputs_dir)
    except ValueError as exc:
        raise ValueError(f"Only files under {outputs_virtual_prefix}/ can be presented: {normalized_input}") from exc

    if relative_path.parts and relative_path.parts[0] in _PRESENT_ARTIFACTS_INTERNAL_DIR_NAMES:
        raise ValueError(
            f"Tool-stage intermediate files cannot be presented: {outputs_virtual_prefix}/{relative_path.as_posix()}"
        )

    return f"{outputs_virtual_prefix}/{relative_path.as_posix()}"


PRESENT_ARTIFACTS_DESCRIPTION = f"""
Present generated result files to the user.

Use cases:
1. You have written the final result files under `{VIRTUAL_PATH_OUTPUTS}`
2. You want the frontend to display these result file cards after the conversation ends
3. These files need download or preview support

Notes:
1. Only files under `{VIRTUAL_PATH_OUTPUTS}` can be passed
2. Do not pass intermediate files, only call for final result files the user actually needs to see
3. Do not pass tool-stage intermediate files, for example:
   - `{VIRTUAL_PATH_OUTPUTS}/{LARGE_TOOL_RESULTS_DIR_NAME}`
   - `{VIRTUAL_PATH_OUTPUTS}/{CONVERSATION_HISTORY_DIR_NAME}`
4. Multiple files can be passed at once
"""


@tool(
    category="buildin",
    tags=["file", "deliverable"],
    display_name="Present deliverables",
    description=PRESENT_ARTIFACTS_DESCRIPTION,
    args_schema=PresentArtifactsInput,
)
def present_artifacts(
    filepaths: list[str],
    runtime: ToolRuntime,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Register deliverable files in the current thread outputs directory for display when the conversation ends."""
    try:
        normalized_paths = [_normalize_presented_artifact_path(filepath, runtime) for filepath in filepaths]
    except ValueError as exc:
        return Command(update={"messages": [ToolMessage(content=f"Error: {exc}", tool_call_id=tool_call_id)]})

    return Command(
        update={
            "artifacts": normalized_paths,
            "messages": [ToolMessage(content="Deliverables presented to the user", tool_call_id=tool_call_id)],
        }
    )


class OcrParseFileInput(BaseModel):
    """Parse a sandbox file with OCR and save the Markdown result."""

    file_path: str = Field(description="Sandbox virtual path to parse with OCR, must be under /home/gem/user-data")
    ocr_engine: str | None = Field(
        default=None, description="Optional OCR engine; uses the system default when omitted"
    )


OCR_PARSE_FILE_DESCRIPTION = f"""
Parse a PDF, Office document, or image in the sandbox into Markdown text and save the result as a file.

Use cases:
1. The user uploaded a PDF, Office document, or image attachment and needs text content extracted
2. A file already exists in workspace, uploads, or outputs and needs conversion into readable Markdown
3. The parsed result is long, afterwards use read_file to read the saved Markdown file


Notes:
1. file_path must be a virtual path under /home/gem/user-data
2. Only regular files in workspace, uploads, outputs are allowed
3. The parsed result is written to {VIRTUAL_PATH_OUTPUTS}/{_OCR_OUTPUT_DIR_NAME}/
4. The tool only returns the result file path and a short preview, not the full OCR text directly
5. To display the result file in the user interface, call present_artifacts next
"""


@tool(
    category="buildin",
    tags=["file", "ocr"],
    display_name="Parse file with OCR",
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
        raise ValueError("File path must not be empty")

    virtual_prefix = get_virtual_path_prefix().rstrip("/")
    clean_virtual_path = "/" + normalized_input.lstrip("/")
    if clean_virtual_path != virtual_prefix and not clean_virtual_path.startswith(f"{virtual_prefix}/"):
        raise ValueError(f"Only sandbox virtual paths under {virtual_prefix} can be parsed")

    relative_path = clean_virtual_path[len(virtual_prefix) :].lstrip("/")
    namespace = Path(relative_path).parts[0] if relative_path else ""
    if namespace not in _OCR_PARSE_ALLOWED_DIRS:
        allowed = ", ".join(f"{virtual_prefix}/{item}" for item in sorted(_OCR_PARSE_ALLOWED_DIRS))
        raise ValueError(f"Only files in {allowed} can be parsed")

    try:
        actual_path = resolve_virtual_path(file_thread_id, clean_virtual_path, uid=uid)
    except ValueError as exc:
        raise ValueError(f"Only sandbox virtual paths under {virtual_prefix} can be parsed") from exc
    if not actual_path.exists():
        raise ValueError(f"File does not exist: {clean_virtual_path}")
    if not actual_path.is_file():
        raise ValueError(f"Path is not a regular file: {clean_virtual_path}")

    return file_thread_id, uid, actual_path


def _resolve_runtime_file_scope(runtime: ToolRuntime) -> tuple[str, str]:
    """Read the thread and user scope needed for sandbox path mapping from ToolRuntime."""
    thread_id = _runtime_scope_value(runtime, "file_thread_id") or _runtime_scope_value(runtime, "thread_id")
    uid = _runtime_scope_value(runtime, "uid")
    if not thread_id:
        raise ValueError("Current runtime is missing thread_id")
    if not uid:
        raise ValueError("Current runtime is missing uid")
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
        raise ValueError(f"Unsupported OCR engine: {engine}")
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
During execution, when you need the user to make a decision or provide additional requirements, use this tool to ask the user.

Applicable scenarios:
1. Collect user preferences or requirements (e.g., style, scope, priority)
2. Clarify ambiguous instructions (when multiple reasonable interpretations exist)
3. Let the user choose a solution direction during implementation
4. Let the user make trade-offs when there are explicit considerations

Usage rules:
1. questions provides 1-5 questions, each item includes: question, options, multi_select, allow_other
2. options for each question provides 2-5 distinct choices, each item includes label and value
3. If there is a recommended option: put the recommended option first and append "(Recommended)" to the label
4. If multiple selection is needed: set multi_select of that question to true
5. allow_other is usually true, the user can enter a custom answer via Other

Notes:
1. Do not use this tool for flow-control questions like "should execution continue" or "is the plan ready"
2. Do not overuse this tool when the information is already complete and the user needs no decision
3. Decide based on the current context first, only ask when there is significant uncertainty

Return value:
answer is an object with format {question_id: answer}.
Where answer can be a string (single choice), list (multiple choices), or object (text entered via Other).
"""


@tool(
    category="buildin",
    tags=["interaction"],
    display_name="Ask user",
    description=ASK_USER_QUESTION_DESCRIPTION,
)
def ask_user_question(
    questions: Annotated[
        list[dict] | str | None,
        "Question list, each item format {question, options, multi_select, allow_other, question_id(optional)}",
    ] = None,
) -> dict:
    """Send questions to the user and wait for answers."""
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
        raise ValueError("questions must contain at least one valid question")

    interrupt_payload = {
        "questions": normalized_questions,
        "source": "ask_user_question",
    }
    answer = interrupt(interrupt_payload)

    return {
        "questions": normalized_questions,
        "answer": answer,
    }
