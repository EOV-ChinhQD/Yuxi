import os
from pathlib import Path
from typing import Annotated

from langchain.tools import InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolRuntime
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

from yuxi.agents.toolkits.registry import ToolExtraMetadata, _all_tool_instances, _extra_registry, tool
from yuxi.utils import logger
from yuxi.utils.paths import CONVERSATION_HISTORY_DIR_NAME, LARGE_TOOL_RESULTS_DIR_NAME, VIRTUAL_PATH_OUTPUTS
from yuxi.utils.question_utils import normalize_questions

# Lazy initialization for TavilySearch (only when API key is available)
_tavily_search_instance = None

_PRESENT_ARTIFACTS_INTERNAL_DIR_NAMES = frozenset(
    {CONVERSATION_HISTORY_DIR_NAME, LARGE_TOOL_RESULTS_DIR_NAME, "large_tool_history"}
)


def _create_tavily_search():
    """Create and register TavilySearch tool with metadata."""
    global _tavily_search_instance
    if _tavily_search_instance is None:
        from langchain_tavily import TavilySearch

        _tavily_search_instance = TavilySearch()

    return _tavily_search_instance


# Đăng ký công cụ TavilySearch (khởi tạo trễ)
def _register_tavily_tool():
    """Register TavilySearch tool with extra metadata."""
    tavily_instance = _create_tavily_search()
    # Đăng ký thủ công vào registry toàn cục
    _extra_registry["tavily_search"] = ToolExtraMetadata(
        category="buildin",
        tags=["search"],
        display_name="Tavily Web Search",
    )
    # Add to tool instance list
    _all_tool_instances.append(tavily_instance)


# Register when module is loaded
if os.getenv("TAVILY_API_KEY"):
    try:
        _register_tavily_tool()
    except Exception as e:
        logger.warning(f"Failed to register TavilySearch tool: {e}")


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
        raise ValueError(f"Không cho phép hiển thị tệp giai đoạn gọi công cụ: {outputs_virtual_prefix}/{relative_path.as_posix()}")

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
            "messages": [ToolMessage(content="Đã hiển thị sản phẩm giao nộp cho người dùng", tool_call_id=tool_call_id)],
        }
    )


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
