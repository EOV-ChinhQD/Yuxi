"""Module công cụ kho kiến thức"""

import inspect
from typing import Any

from langgraph.prebuilt.tool_node import ToolRuntime
from pydantic import BaseModel, Field

from yuxi.agents.toolkits.registry import tool
from yuxi.knowledge.base import KnowledgeBase
from yuxi.knowledge.schemas import (
    FindInputSchema,
    FindOutputSchema,
    OpenInputSchema,
    OpenOutputSchema,
    SearchInputSchema,
    SearchOutputSchema,
)
from yuxi.utils import logger

# ========== Các hàm công cụ kho kiến thức chung ==========


def _get_knowledge_base():
    from yuxi import knowledge_base

    return knowledge_base


class ListKBsInput(BaseModel):
    """Model input danh sách kho kiến thức người dùng có thể truy cập"""

    # Cơ chế inject runtime của Langchain yêu cầu phải có tham số
    dummy: str = Field(default="", description="Dummy parameter - ignore")  # Add this


@tool(category="knowledge", tags=["kho-kien-thuc"], args_schema=ListKBsInput)
async def list_kbs(dummy: str = "", runtime: ToolRuntime = None) -> str:  # Now has 2 params with defaults
    """Liệt kê danh sách các kho kiến thức mà người dùng hiện tại có thể truy cập.

    Trả về danh sách tên các kho kiến thức mà người dùng có quyền truy cập dựa trên vai trò và phòng ban,
    nhưng không bao gồm các kho kiến thức chưa được bật trong cuộc trò chuyện hiện tại.

    Returns:
        Danh sách tên các kho kiến thức có thể truy cập (dạng chuỗi)
    """
    # Lấy thông tin người dùng từ runtime.context
    runtime_context = runtime.context
    uid = getattr(runtime_context, "uid", None)
    if not uid:
        return "Không thể lấy thông tin người dùng"

    # In toàn bộ thông tin trong runtime.context để debug
    logger.debug(f"Runtime context: {runtime_context.__dict__}")

    enabled_kb_names = getattr(runtime_context, "knowledges", None)

    try:
        from yuxi.agents.backends.knowledge_base_backend import resolve_visible_knowledge_bases_for_context

        available_kbs = await resolve_visible_knowledge_bases_for_context(runtime_context)
    except Exception as e:
        logger.error(f"Lấy danh sách kho kiến thức người dùng thất bại: {e}")
        return f"Lấy danh sách kho kiến thức thất bại: {str(e)}"

    all_kb_names = [kb["name"] for kb in available_kbs]

    logger.debug(f"Danh sách kho kiến thức người dùng {uid} có thể truy cập: {all_kb_names}")
    logger.debug(f"Danh sách kho kiến thức người dùng {uid} đã bật trong cuộc trò chuyện hiện tại: {enabled_kb_names}")

    if not available_kbs:
        return "Hiện tại không có kho kiến thức nào có thể truy cập"

    # Định dạng đầu ra (bao gồm tên và mô tả)
    kb_list = []
    for kb in available_kbs:
        name = kb.get("name", "")
        desc = kb.get("description") or "Không có mô tả"
        kb_list.append({"kb_id": kb.get("kb_id"), "name": name, "description": desc})

    return kb_list


class GetMindmapInput(BaseModel):
    """Model input lấy mindmap"""

    kb_name: str = Field(description="Tên kho kiến thức dùng để lấy sơ đồ tư duy")


@tool(category="knowledge", tags=["kho-kien-thuc"], args_schema=GetMindmapInput)
async def get_mindmap(kb_name: str, runtime: ToolRuntime) -> str:
    """Lấy cấu trúc sơ đồ tư duy của kho kiến thức được chỉ định.

    Sử dụng công cụ này khi người dùng muốn hiểu cấu trúc tổng thể, phân loại tệp, hoặc kiến trúc tri thức của kho kiến thức.
    Trả về cấu trúc sơ đồ tư duy phân cấp của kho kiến thức.

    Args:
        kb_name: Tên kho kiến thức

    Returns:
        Cấu trúc sơ đồ tư duy của kho kiến thức (dạng văn bản)
    """
    if not kb_name:
        return "Vui lòng cung cấp tên kho kiến thức"

    # Lấy tất cả các retriever
    knowledge_base = _get_knowledge_base()
    retrievers = knowledge_base.get_retrievers()

    # Tìm kho kiến thức tương ứng
    target_kb_id = None
    target_info = None
    for kb_id, info in retrievers.items():
        if info["name"] == kb_name:
            target_kb_id = kb_id
            target_info = info
            break

    if not target_kb_id:
        return f"Kho kiến thức '{kb_name}' không tồn tại"

    try:
        from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository

        kb_repo = KnowledgeBaseRepository()
        kb = await kb_repo.get_by_kb_id(target_kb_id)

        if kb is None:
            return f"Kho kiến thức {target_info['name']} không tồn tại"

        mindmap_data = kb.mindmap

        if not mindmap_data:
            return f"Kho kiến thức {target_info['name']} chưa tạo sơ đồ tư duy."

        def mindmap_to_text(node, level=0):
            """Đệ quy chuyển đổi JSON sơ đồ tư duy thành văn bản phân cấp"""
            indent = "  " * level
            text = f"{indent}- {node.get('content', '')}\n"
            for child in node.get("children", []):
                text += mindmap_to_text(child, level + 1)
            return text

        mindmap_text = f"Cấu trúc sơ đồ tư duy của kho kiến thức {target_info['name']}:\n\n"
        mindmap_text += mindmap_to_text(mindmap_data)

        return mindmap_text

    except Exception as e:
        logger.error(f"Lấy sơ đồ tư duy thất bại: {e}")
        return f"Lấy sơ đồ tư duy thất bại: {str(e)}"


QueryKBInput = SearchInputSchema
OpenKBDocumentInput = OpenInputSchema
FindKBDocumentInput = FindInputSchema


async def _resolve_visible_knowledge_bases_for_query(runtime: ToolRuntime | None) -> list[dict[str, Any]]:
    if runtime is None:
        return []

    context = getattr(runtime, "context", None)
    if context is None:
        return []

    visible_kbs = getattr(context, "_visible_knowledge_bases", None)
    if isinstance(visible_kbs, list):
        return visible_kbs

    try:
        from yuxi.agents.backends.knowledge_base_backend import resolve_visible_knowledge_bases_for_context

        return await resolve_visible_knowledge_bases_for_context(context)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Phân tích kho kiến thức hiển thị cho phiên thất bại: {exc}")
        return []


def _find_query_target(
    *,
    kb_id: str,
    retrievers: dict[str, Any],
    visible_kbs: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    if not visible_kbs:
        return None, None, "Không thể lấy danh sách kho kiến thức có thể truy cập của phiên hội thoại hiện tại"

    normalized_kb_id = str(kb_id or "").strip()
    visible_kb_ids = {str(kb.get("kb_id") or "").strip() for kb in visible_kbs}
    if normalized_kb_id not in visible_kb_ids:
        return None, None, f"Tài nguyên kho kiến thức '{normalized_kb_id}' không tồn tại hoặc chưa được bật trong phiên hội thoại hiện tại"

    target_info = retrievers.get(normalized_kb_id)
    if target_info is None:
        return None, None, f"Tài nguyên kho kiến thức '{normalized_kb_id}' không tồn tại"
    return target_info, normalized_kb_id, None


async def _build_query_output(target_kb_id: str, result: Any) -> Any:
    if isinstance(result, dict) and result.get("kb_id") == target_kb_id and isinstance(result.get("results"), list):
        return SearchOutputSchema(**result).model_dump()
    return KnowledgeBase.build_search_output(target_kb_id, result)


@tool(category="knowledge", tags=["kho-kien-thuc"], args_schema=QueryKBInput)
async def query_kb(kb_id: str, query_text: str, file_name: str | None = None, runtime: ToolRuntime = None) -> Any:
    """Tìm kiếm nội dung trong kho kiến thức được chỉ định.

    Sử dụng công cụ này khi người dùng cần truy vấn nội dung cụ thể. kb_id là ID tài nguyên kho kiến thức; 
    file_id trong kết quả trả về có thể tiếp tục được sử dụng cho find_kb_document hoặc open_kb_document.
    """
    if not kb_id:
        return "Vui lòng cung cấp kb_id"
    if not query_text:
        return "Vui lòng cung cấp nội dung truy vấn"

    knowledge_base = _get_knowledge_base()
    retrievers = knowledge_base.get_retrievers()
    visible_kbs = await _resolve_visible_knowledge_bases_for_query(runtime)
    target_info, target_kb_id, target_error = _find_query_target(
        kb_id=kb_id,
        retrievers=retrievers,
        visible_kbs=visible_kbs,
    )
    if target_error:
        return target_error

    try:
        retriever = target_info["retriever"]
        kwargs = {}
        if file_name:
            kwargs["file_name"] = file_name

        from yuxi.knowledge.retrieval.multi_hop_retriever import detect_and_decompose, multi_hop_retrieve_labeled

        # Lấy cấu hình LLM để thực hiện phân tách câu hỏi
        llm_model_spec = target_info.get("metadata", {}).get("llm_model_spec") or "gpt-4o"

        is_multi_hop = False
        sub_queries = []
        if inspect.iscoroutinefunction(retriever):
            is_multi_hop, sub_queries = await detect_and_decompose(query_text, llm_model_spec)

        if is_multi_hop:
            result = await multi_hop_retrieve_labeled(sub_queries, retriever, **kwargs)
            result["kb_id"] = target_kb_id
        else:
            if inspect.iscoroutinefunction(retriever):
                result = await retriever(query_text, **kwargs)
            else:
                result = retriever(query_text, **kwargs)

        return await _build_query_output(target_kb_id, result)

    except Exception as e:
        logger.error(f"Truy xuất thất bại: {e}")
        return f"Truy xuất thất bại: {str(e)}"


@tool(category="knowledge", tags=["kho-kien-thuc"], args_schema=OpenKBDocumentInput)
async def open_kb_document(
    kb_id: str,
    file_id: str,
    line: int | None = None,
    offset: int | None = None,
    window_size: int = 1800,
    runtime: ToolRuntime = None,
) -> dict[str, Any] | str:
    """Mở văn bản gốc của tài liệu kho kiến thức theo cửa sổ dòng.

    Sử dụng khi các đoạn trích trả về từ query_kb không đủ để trả lời câu hỏi, hoặc cần xem ngữ cảnh của một tài liệu nào đó.
    kb_id là ID tài nguyên kho kiến thức; file_id là ID tệp kho kiến thức.
    """
    normalized_kb_id = str(kb_id or "").strip()
    normalized_file_id = str(file_id or "").strip()
    if not normalized_kb_id:
        return "Vui lòng cung cấp kb_id"
    if not normalized_file_id:
        return "Vui lòng cung cấp file_id"

    visible_kbs = await _resolve_visible_knowledge_bases_for_query(runtime)
    if not visible_kbs:
        return "Không thể lấy danh sách kho kiến thức có thể truy cập của phiên hội thoại hiện tại"

    visible_kb_ids = {str(kb.get("kb_id") or "").strip() for kb in visible_kbs}
    if normalized_kb_id not in visible_kb_ids:
        return f"Tài nguyên kho kiến thức '{normalized_kb_id}' không tồn tại hoặc chưa được bật trong phiên hội thoại hiện tại"

    knowledge_base = _get_knowledge_base()
    retrievers = knowledge_base.get_retrievers()
    target_info = retrievers.get(normalized_kb_id)
    if target_info is None:
        return f"Tài nguyên kho kiến thức '{normalized_kb_id}' không tồn tại"

    metadata = target_info.get("metadata") if isinstance(target_info, dict) else None
    kb_type = str((metadata or {}).get("kb_type") or "").strip().lower()
    if kb_type == "dify":
        return "Kho kiến thức Dify là nguồn truy xuất ngoài chỉ đọc, hiện tại không hỗ trợ mở toàn văn qua Open"

    try:
        start_offset = int(line) - 1 if line is not None else int(offset or 0)
        window = await knowledge_base.open_file_content(
            normalized_kb_id,
            normalized_file_id,
            offset=start_offset,
            limit=window_size,
        )
        return OpenOutputSchema(kb_id=normalized_kb_id, file_id=normalized_file_id, **window).model_dump()

    except Exception as e:
        logger.error(f"Mở tài liệu kho kiến thức thất bại: {e}")
        return f"Mở tài liệu kho kiến thức thất bại: {str(e)}"


@tool(category="knowledge", tags=["kho-kien-thuc"], args_schema=FindKBDocumentInput)
async def find_kb_document(
    kb_id: str,
    file_id: str,
    patterns: list[str],
    use_regex: bool = False,
    case_sensitive: bool = False,
    max_windows: int = 5,
    window_size: int = 80,
    runtime: ToolRuntime = None,
) -> dict[str, Any] | str:
    """Định vị từ khóa hoặc regex trong tệp kho kiến thức đã biết.

    Sử dụng khi query_kb đã tìm thấy tệp ứng viên, nhưng cần định vị thuật ngữ, chỉ số, chương mục hoặc thực thể trong tệp đó.
    """
    normalized_kb_id = str(kb_id or "").strip()
    normalized_file_id = str(file_id or "").strip()
    if not normalized_kb_id:
        return "Vui lòng cung cấp kb_id"
    if not normalized_file_id:
        return "Vui lòng cung cấp file_id"
    if not patterns:
        return "Vui lòng cung cấp patterns"

    visible_kbs = await _resolve_visible_knowledge_bases_for_query(runtime)
    if not visible_kbs:
        return "Không thể lấy danh sách kho kiến thức có thể truy cập của phiên hội thoại hiện tại"

    visible_kb_ids = {str(kb.get("kb_id") or "").strip() for kb in visible_kbs}
    if normalized_kb_id not in visible_kb_ids:
        return f"Tài nguyên kho kiến thức '{normalized_kb_id}' không tồn tại hoặc chưa được bật trong phiên hội thoại hiện tại"

    knowledge_base = _get_knowledge_base()
    retrievers = knowledge_base.get_retrievers()
    target_info = retrievers.get(normalized_kb_id)
    if target_info is None:
        return f"Tài nguyên kho kiến thức '{normalized_kb_id}' không tồn tại"

    metadata = target_info.get("metadata") if isinstance(target_info, dict) else None
    kb_type = str((metadata or {}).get("kb_type") or "").strip().lower()
    if kb_type == "dify":
        return "Kho kiến thức Dify là nguồn truy xuất ngoài chỉ đọc, hiện tại không hỗ trợ tìm kiếm toàn văn qua Find"

    try:
        result = await knowledge_base.find_file_content(
            normalized_kb_id,
            normalized_file_id,
            patterns,
            use_regex=use_regex,
            case_sensitive=case_sensitive,
            max_windows=max_windows,
            window_size=window_size,
        )
        return FindOutputSchema(kb_id=normalized_kb_id, file_id=normalized_file_id, **result).model_dump()
    except Exception as e:
        logger.error(f"Tìm kiếm trong tài liệu kho kiến thức thất bại: {e}")
        return f"Tìm kiếm trong tài liệu kho kiến thức thất bại: {str(e)}"


# Số lượng tệp tối đa quét một lần cho mỗi kho kiến thức (giữ nguyên giới hạn cứng với list_by_kb_id_after ở tầng lưu trữ),
# Dùng để lọc tên tệp và đếm chính xác trong bộ nhớ, tránh cắt ngắn theo limit+offset làm sai lệch total/has_more.
_KB_FILE_SCAN_LIMIT = 5000


class SearchFileInput(BaseModel):
    """Model input tìm kiếm tệp"""

    kb_name: str | None = Field(default=None, description="Tên kho kiến thức, để trống để tìm kiếm tất cả kho kiến thức")
    query: str | None = Field(default=None, description="Từ khóa tìm kiếm, để trống để trả về tất cả các tệp")
    offset: int = Field(default=0, ge=0, description="Độ lệch offset, bắt đầu từ 0")
    limit: int = Field(default=300, ge=1, le=5000, description="Giới hạn số lượng trả về, mặc định 300")


@tool(category="knowledge", tags=["kho-kien-thuc"], args_schema=SearchFileInput)
async def search_file(
    kb_name: str | None = None,
    query: str | None = None,
    offset: int = 0,
    limit: int = 300,
    runtime: ToolRuntime = None,
) -> dict[str, Any] | str:
    """Tìm kiếm tệp trong kho kiến thức.

    Sử dụng công cụ này khi người dùng cần tìm kiếm tệp cụ thể. Có thể chỉ định tên kho kiến thức và từ khóa tìm kiếm.
    Nếu không chỉ định kho kiến thức, hệ thống sẽ tìm kiếm trong tất cả kho kiến thức có quyền truy cập.
    Nếu không chỉ định từ khóa tìm kiếm, hệ thống sẽ trả về tất cả các tệp.

    Args:
        kb_name: Tên kho kiến thức, để trống để tìm kiếm trong tất cả các kho kiến thức
        query: Từ khóa tìm kiếm, để trống để trả về tất cả các tệp
        offset: Độ lệch offset, bắt đầu từ 0
        limit: Giới hạn số lượng trả về, mặc định 300

    Returns:
        Danh sách các tệp khớp và thông tin phân trang
    """
    if not kb_name and not query:
        return "Vui lòng cung cấp tên kho kiến thức hoặc từ khóa tìm kiếm, không được để trống cả hai"

    visible_kbs = await _resolve_visible_knowledge_bases_for_query(runtime)
    if not visible_kbs:
        return "Không thể lấy danh sách kho kiến thức có thể truy cập của phiên hội thoại hiện tại"

    if kb_name:
        target_kbs = [kb for kb in visible_kbs if kb.get("name") == kb_name]
        if not target_kbs:
            return f"Kho kiến thức '{kb_name}' không tồn tại hoặc chưa được bật trong phiên hội thoại hiện tại"
    else:
        target_kbs = visible_kbs

    from yuxi.repositories.knowledge_file_repository import KnowledgeFileRepository

    repo = KnowledgeFileRepository()

    all_files = []
    for kb in target_kbs:
        kb_id = kb.get("kb_id")
        if not kb_id:
            continue

        files = await repo.list_by_kb_id_after(
            kb_id=kb_id,
            limit=_KB_FILE_SCAN_LIMIT,
            files_only=True,
        )

        if query:
            query_lower = query.lower()
            files = [f for f in files if query_lower in f.filename.lower()]

        for f in files:
            all_files.append(
                {
                    "kb_id": kb_id,
                    "kb_name": kb.get("name"),
                    "file_id": f.file_id,
                    "filename": f.filename,
                    "file_type": f.file_type,
                    "status": f.status,
                    "created_at": str(f.created_at) if f.created_at else None,
                    "updated_at": str(f.updated_at) if f.updated_at else None,
                    "file_size": f.file_size,
                }
            )

    all_files.sort(key=lambda x: x.get("updated_at") or "", reverse=True)

    total = len(all_files)
    paginated_files = all_files[offset : offset + limit]

    return {
        "files": paginated_files,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
    }


def get_common_kb_tools() -> list:
    """Lấy danh sách các công cụ kho kiến thức chung.

    Trả về 6 công cụ chung:
    - list_kbs: Liệt kê danh sách kho kiến thức người dùng có thể truy cập
    - get_mindmap: Lấy sơ đồ tư duy của kho kiến thức được chỉ định
    - query_kb: Truy xuất thông tin trong kho kiến thức được chỉ định
    - find_kb_document: Định vị từ khóa hoặc regex trong tệp được chỉ định
    - open_kb_document: Mở một phần tài liệu kho kiến thức theo file_id
    - search_file: Tìm kiếm tệp trong kho kiến thức
    """
    return [list_kbs, get_mindmap, query_kb, find_kb_document, open_kb_document, search_file]
