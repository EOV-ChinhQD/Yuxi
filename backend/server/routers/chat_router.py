import traceback
import uuid
from typing import Any

import aiofiles
from fastapi import APIRouter, Body, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.storage.postgres.models_business import User
from server.utils.auth_middleware import get_db, get_required_user
from yuxi import config as conf
from yuxi.agents.tool_approval import ToolApprovalMode
from yuxi.models import select_model
from yuxi.services.chat_service import get_agent_state_view
from yuxi.services.conversation_service import (
    confirm_tmp_thread_attachments_view,
    create_thread_view,
    delete_thread_attachment_view,
    delete_thread_view,
    get_thread_history_view,
    list_thread_attachments_view,
    list_threads_view,
    mark_thread_viewed_view,
    parse_tmp_attachment_view,
    search_threads_view,
    update_thread_view,
    upload_thread_attachment_view,
    upload_tmp_attachment_view,
)
from yuxi.services.file_preview import detect_media_type
from yuxi.services.thread_files_service import (
    list_thread_files_view,
    read_thread_file_content_view,
    resolve_thread_artifact_view,
    save_thread_artifact_to_workspace_view,
)
from yuxi.services.feedback_service import get_message_feedback_view, submit_message_feedback_view
from yuxi.utils.logging_config import logger
from yuxi.utils.image_processor import process_uploaded_image
from yuxi.utils.paths import VIRTUAL_PATH_PREFIX


# TODO: Chức năng của file hiện tại quá phức tạp, tag định tuyến bị lộn xộn


# Model phản hồi khi tải lên hình ảnh
class ImageUploadResponse(BaseModel):
    success: bool
    image_content: str | None = None
    thumbnail_content: str | None = None
    width: int | None = None
    height: int | None = None
    format: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    error: str | None = None


chat = APIRouter(prefix="/chat", tags=["chat"])


@chat.post("/call")
async def call(query: str = Body(...), meta: dict = Body(None), current_user: User = Depends(get_required_user)):
    """Gọi mô hình để hỏi đáp đơn giản (yêu cầu đăng nhập)"""
    meta = meta or {}

    # Đảm bảo request_id tồn tại
    if "request_id" not in meta or not meta.get("request_id"):
        meta["request_id"] = str(uuid.uuid4())

    model = select_model(model_spec=meta.get("model_spec") or meta.get("model") or conf.default_model)

    response = await model.call(query)
    logger.debug({"query": query, "response": response.content})

    return {"response": response.content, "request_id": meta["request_id"]}


@chat.get("/thread/{thread_id}/history")
async def get_thread_history(
    thread_id: str, current_user: User = Depends(get_required_user), db: AsyncSession = Depends(get_db)
):
    """Lấy lịch sử tin nhắn cuộc hội thoại (yêu cầu đăng nhập) - bao gồm trạng thái phản hồi của người dùng"""
    try:
        return await get_thread_history_view(
            thread_id=thread_id,
            current_uid=str(current_user.uid),
            db=db,
        )

    except Exception as e:
        logger.error(f"Lỗi khi lấy lịch sử cuộc hội thoại: {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy lịch sử tin nhắn: {str(e)}")


@chat.get("/thread/{thread_id}/state")
async def get_thread_state(
    thread_id: str,
    include_messages: bool = Query(False),
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """Lấy trạng thái hiện tại của cuộc hội thoại (yêu cầu đăng nhập)"""
    try:
        return await get_agent_state_view(
            thread_id=thread_id,
            current_user=current_user,
            db=db,
            include_messages=include_messages,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Lỗi khi lấy trạng thái cuộc hội thoại: {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy trạng thái cuộc hội thoại: {str(e)}")


# ==================== API Quản lý Luồng ====================


class ThreadCreate(BaseModel):
    title: str | None = None
    agent_id: str
    metadata: dict | None = None
    request_id: str | None = None
    project_id: str | None = None


class ThreadResponse(BaseModel):
    id: str
    uid: str
    agent_id: str
    title: str | None = None
    is_pinned: bool = False
    project_id: str | None = None
    creation_request_id: str | None = None
    created_at: str
    updated_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    thread_status: str = "done"


class ThreadSearchSnippet(BaseModel):
    message_id: int | None = None
    content: str
    created_at: str | None = None


class ThreadSearchItem(ThreadResponse):
    thread_id: str
    matched_count: int
    message_id: int | None = None
    latest_match_at: str | None = None
    snippets: list[ThreadSearchSnippet] = Field(default_factory=list)


class ThreadSearchResponse(BaseModel):
    items: list[ThreadSearchItem]
    has_more: bool
    limit: int
    offset: int


class AttachmentResponse(BaseModel):
    file_id: str
    file_name: str
    file_type: str | None = None
    file_size: int
    status: str
    uploaded_at: str
    path: str
    artifact_url: str | None = None
    original_path: str | None = None
    original_artifact_url: str | None = None
    minio_url: str | None = None
    request_id: str | None = None


class AttachmentLimits(BaseModel):
    allowed_extensions: list[str]
    max_size_bytes: int


class AttachmentListResponse(BaseModel):
    attachments: list[AttachmentResponse]
    limits: AttachmentLimits


class TmpAttachmentResponse(BaseModel):
    tmp_file_id: str
    file_name: str
    file_type: str | None = None
    file_size: int
    bucket_name: str
    object_name: str
    minio_url: str
    uploaded_at: str
    parse_supported: bool = False
    parse_methods: list[str] = Field(default_factory=list)


class TmpAttachmentParseRequest(BaseModel):
    object_name: str
    file_name: str
    parse_method: str | None = None
    bucket_name: str | None = None


class TmpAttachmentParseResponse(BaseModel):
    tmp_file_id: str
    file_name: str
    bucket_name: str
    object_name: str
    parsed_object_name: str
    parsed_minio_url: str
    parse_method: str
    status: str
    truncated: bool = False


class TmpAttachmentConfirmItem(BaseModel):
    file_name: str
    file_type: str | None = None
    bucket_name: str
    object_name: str
    parsed_object_name: str | None = None
    truncated: bool = False


class TmpAttachmentConfirmRequest(BaseModel):
    attachments: list[TmpAttachmentConfirmItem]


class TmpAttachmentConfirmResponse(BaseModel):
    attachments: list[AttachmentResponse]


class ThreadFileEntry(BaseModel):
    path: str
    name: str
    is_dir: bool
    size: int
    modified_at: str | None = None
    artifact_url: str | None = None


class ThreadFileListResponse(BaseModel):
    path: str
    files: list[ThreadFileEntry]


class ThreadFileContentResponse(BaseModel):
    path: str
    content: list[str]
    offset: int
    limit: int
    total_lines: int
    artifact_url: str


class SaveThreadArtifactRequest(BaseModel):
    path: str


class SaveThreadArtifactResponse(BaseModel):
    name: str
    source_path: str
    saved_path: str
    saved_artifact_url: str


# =============================================================================
# > === Nhóm quản lý phiên hội thoại ===
# =============================================================================


@chat.post("/thread", response_model=ThreadResponse)
async def create_thread(
    thread: ThreadCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_required_user)
):
    """Tạo luồng hội thoại mới (sử dụng hệ thống lưu trữ mới)"""
    return await create_thread_view(
        agent_slug=thread.agent_id,
        title=thread.title,
        metadata=thread.metadata,
        db=db,
        current_uid=str(current_user.uid),
        request_id=thread.request_id,
        project_id=thread.project_id,
    )


@chat.get("/threads", response_model=list[ThreadResponse])
async def list_threads(
    agent_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """Lấy tất cả các luồng hội thoại của người dùng (sử dụng hệ thống lưu trữ mới)"""
    return await list_threads_view(
        agent_slug=agent_id, db=db, current_uid=str(current_user.uid), limit=limit, offset=offset
    )


@chat.get("/threads/search", response_model=ThreadSearchResponse)
async def search_threads(
    q: str = Query(..., min_length=1, max_length=200),
    agent_id: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """Tìm kiếm lịch sử cuộc hội thoại của người dùng hiện tại."""
    return await search_threads_view(
        query=q,
        agent_id=agent_id,
        db=db,
        current_uid=str(current_user.uid),
        limit=limit,
        offset=offset,
    )


@chat.delete("/thread/{thread_id}")
async def delete_thread(
    thread_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_required_user)
):
    """Xóa luồng hội thoại (sử dụng hệ thống lưu trữ mới)"""
    return await delete_thread_view(thread_id=thread_id, db=db, current_uid=str(current_user.uid))


class ThreadUpdate(BaseModel):
    title: str | None = None
    is_pinned: bool | None = None
    tool_approval_mode: ToolApprovalMode | None = None


@chat.put("/thread/{thread_id}", response_model=ThreadResponse)
async def update_thread(
    thread_id: str,
    thread_update: ThreadUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """Cập nhật thông tin luồng hội thoại (sử dụng hệ thống lưu trữ mới)"""
    return await update_thread_view(
        thread_id=thread_id,
        title=thread_update.title,
        is_pinned=thread_update.is_pinned,
        tool_approval_mode=thread_update.tool_approval_mode,
        db=db,
        current_uid=str(current_user.uid),
    )


@chat.post("/thread/{thread_id}/viewed", response_model=ThreadResponse)
async def mark_thread_viewed(
    thread_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """记录用户已查看该线程的最新顶层 run，清除侧边栏未读状态。"""
    return await mark_thread_viewed_view(
        thread_id=thread_id,
        db=db,
        current_uid=str(current_user.uid),
    )


# ================================
# > === Nhóm quản lý tệp đính kèm ===
# ================================


@chat.post("/attachments/tmp", response_model=TmpAttachmentResponse)
async def upload_tmp_attachment(file: UploadFile = File(...), current_user: User = Depends(get_required_user)):
    """Tải tệp đính kèm lên thư mục tmp của MinIO, tạm thời chưa liên kết với luồng."""
    return await upload_tmp_attachment_view(file=file, current_uid=str(current_user.uid))


@chat.post("/attachments/tmp/parse", response_model=TmpAttachmentParseResponse)
async def parse_tmp_attachment(
    request: TmpAttachmentParseRequest,
    current_user: User = Depends(get_required_user),
):
    """Phân tích tệp đính kèm tmp và trả về URL tmp sau khi phân tích."""
    return await parse_tmp_attachment_view(
        object_name=request.object_name,
        file_name=request.file_name,
        parse_method=request.parse_method,
        bucket_name=request.bucket_name,
        current_uid=str(current_user.uid),
    )


@chat.post("/thread/{thread_id}/attachments/confirm", response_model=TmpAttachmentConfirmResponse)
async def confirm_tmp_thread_attachments(
    thread_id: str,
    request: TmpAttachmentConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """Thêm chính thức tệp đính kèm tmp vào danh sách đính kèm của luồng."""
    return await confirm_tmp_thread_attachments_view(
        thread_id=thread_id,
        attachments=[item.model_dump() for item in request.attachments],
        db=db,
        current_uid=str(current_user.uid),
    )


@chat.post("/thread/{thread_id}/attachments", response_model=AttachmentResponse)
async def upload_thread_attachment(
    thread_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """Tải tệp đính kèm gốc lên và liên kết với luồng hội thoại chỉ định."""
    return await upload_thread_attachment_view(
        thread_id=thread_id,
        file=file,
        db=db,
        current_uid=str(current_user.uid),
    )


@chat.get("/thread/{thread_id}/attachments", response_model=AttachmentListResponse)
async def list_thread_attachments(
    thread_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """Liệt kê toàn bộ metadata tệp đính kèm của luồng hội thoại hiện tại."""
    return await list_thread_attachments_view(
        thread_id=thread_id,
        db=db,
        current_uid=str(current_user.uid),
    )


@chat.delete("/thread/{thread_id}/attachments/{file_id}")
async def delete_thread_attachment(
    thread_id: str,
    file_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """Xóa tệp đính kèm chỉ định."""
    return await delete_thread_attachment_view(
        thread_id=thread_id,
        file_id=file_id,
        db=db,
        current_uid=str(current_user.uid),
    )


@chat.get("/thread/{thread_id}/files", response_model=ThreadFileListResponse)
async def list_thread_files(
    thread_id: str,
    path: str = Query(f"{VIRTUAL_PATH_PREFIX}"),
    recursive: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """Liệt kê thư mục tệp tin của luồng."""
    return await list_thread_files_view(
        thread_id=thread_id,
        current_uid=str(current_user.uid),
        db=db,
        path=path,
        recursive=recursive,
    )


@chat.get("/thread/{thread_id}/files/content", response_model=ThreadFileContentResponse)
async def read_thread_file_content(
    thread_id: str,
    path: str = Query(...),
    offset: int = Query(0, ge=0),
    limit: int = Query(2000, ge=1, le=5000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """Đọc tệp văn bản của luồng (phân trang theo dòng)."""
    return await read_thread_file_content_view(
        thread_id=thread_id,
        current_uid=str(current_user.uid),
        db=db,
        path=path,
        offset=offset,
        limit=limit,
    )


@chat.get("/thread/{thread_id}/artifacts/{path:path}")
async def get_thread_artifact(
    thread_id: str,
    path: str,
    download: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """Tải xuống hoặc xem trước tệp của luồng."""
    file_path = await resolve_thread_artifact_view(
        thread_id=thread_id,
        current_uid=str(current_user.uid),
        db=db,
        path=path,
    )

    async with aiofiles.open(file_path, "rb") as artifact_file:
        file_head = await artifact_file.read(512)
    media_type = detect_media_type(file_path.name, file_head)
    headers = {"Content-Disposition": f'attachment; filename="{file_path.name}"'} if download else None
    return FileResponse(path=file_path, media_type=media_type, headers=headers)


@chat.post("/thread/{thread_id}/artifacts/save", response_model=SaveThreadArtifactResponse)
async def save_thread_artifact_to_workspace(
    thread_id: str,
    request: SaveThreadArtifactRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """Lưu sản phẩm bàn giao vào thư mục dùng chung workspace/saved_artifacts."""
    return await save_thread_artifact_to_workspace_view(
        thread_id=thread_id,
        current_uid=str(current_user.uid),
        db=db,
        path=request.path,
    )


# =============================================================================
# > === Nhóm phản hồi tin nhắn ===
# =============================================================================


class MessageFeedbackRequest(BaseModel):
    rating: str  # 'like' or 'dislike'
    reason: str | None = None  # Optional reason for dislike


class MessageFeedbackResponse(BaseModel):
    id: int
    message_id: int
    rating: str
    reason: str | None
    created_at: str


@chat.post("/message/{message_id}/feedback", response_model=MessageFeedbackResponse)
async def submit_message_feedback(
    message_id: int,
    feedback_data: MessageFeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """Gửi phản hồi cho tin nhắn (yêu cầu đăng nhập)"""
    result = await submit_message_feedback_view(
        message_id=message_id,
        rating=feedback_data.rating,
        reason=feedback_data.reason,
        db=db,
        current_uid=str(current_user.uid),
    )
    return MessageFeedbackResponse(**result)


@chat.get("/message/{message_id}/feedback")
async def get_message_feedback(
    message_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """Lấy phản hồi của người dùng cho tin nhắn chỉ định (yêu cầu đăng nhập)"""
    return await get_message_feedback_view(
        message_id=message_id,
        db=db,
        current_uid=str(current_user.uid),
    )


# =============================================================================
# > === Nhóm hỗ trợ hình ảnh đa phương thức ===
# =============================================================================


@chat.post("/image/upload", response_model=ImageUploadResponse)
async def upload_image(file: UploadFile = File(...), current_user: User = Depends(get_required_user)):
    """
    Tải lên và xử lý hình ảnh, trả về dữ liệu hình ảnh mã hóa base64
    """
    try:
        # Xác thực loại tệp
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Chỉ hỗ trợ tải lên tệp hình ảnh")

        # Đọc nội dung tệp
        image_data = await file.read()

        # Kiểm tra kích thước tệp (giới hạn 10MB, vượt quá sẽ nén xuống 5MB)
        if len(image_data) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Tệp hình ảnh quá lớn, vui lòng tải lên hình ảnh dưới 10MB")

        # Xử lý hình ảnh
        result = process_uploaded_image(image_data, file.filename)

        if not result["success"]:
            raise HTTPException(status_code=400, detail=f"Xử lý hình ảnh thất bại: {result['error']}")

        logger.info(
            f"Người dùng {current_user.id} tải lên hình ảnh thành công: {file.filename}, "
            f"kích thước: {result['width']}x{result['height']}, "
            f"định dạng: {result['format']}, "
            f"dung lượng: {result['size_bytes']} bytes"
        )

        return ImageUploadResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Xử lý tải lên hình ảnh thất bại: {str(e)}, {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Xử lý hình ảnh thất bại: {str(e)}")
