import traceback
import uuid
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.storage.postgres.models_business import User
from server.utils.auth_middleware import get_db, get_required_user
from yuxi import config as conf
from yuxi.models import select_model
from yuxi.services.chat_service import get_agent_state_view, stream_agent_resume
from yuxi.repositories.conversation_repository import ConversationRepository
from yuxi.services.conversation_service import (
    confirm_tmp_thread_attachments_view,
    create_thread_view,
    delete_thread_attachment_view,
    delete_thread_view,
    get_thread_history_view,
    list_thread_attachments_view,
    list_threads_view,
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


# TODO: The functions of the current file are too complex and the routing labels are confusing.


# Image upload response model
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
    """Call the model for simple Q&A (login required)"""
    meta = meta or {}

    # Make sure request_id exists
    if "request_id" not in meta or not meta.get("request_id"):
        meta["request_id"] = str(uuid.uuid4())

    model = select_model(model_spec=meta.get("model_spec") or meta.get("model") or conf.default_model)

    response = await model.call(query)
    logger.debug({"query": query, "response": response.content})

    return {"response": response.content, "request_id": meta["request_id"]}


@chat.post("/thread/{thread_id}/resume")
async def resume_thread_chat(
    thread_id: str,
    approved: bool | None = Body(None),
    answer: dict | None = Body(None),
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """Resume a conversation interrupted by manual approval (login required)"""

    # Verify that thread exists and belongs to the current user
    conv_repo = ConversationRepository(db)
    conversation = await conv_repo.get_conversation_by_thread_id(thread_id)
    if not conversation or conversation.uid != str(current_user.uid) or conversation.status == "deleted":
        raise HTTPException(status_code=404, detail="Luồng hội thoại không tồn tại")
    agent_id = conversation.agent_id

    def normalize_resume_input(raw_answer: Any, raw_approved: bool | None) -> Any:
        def normalize_single_answer(value: Any) -> Any:
            if isinstance(value, str):
                normalized = value.strip()
                if not normalized:
                    raise HTTPException(status_code=422, detail="answer không được để trống")
                return normalized

            if isinstance(value, list):
                if len(value) == 0:
                    raise HTTPException(status_code=422, detail="answer không được để trống")

                normalized_list: list[str] = []
                for item in value:
                    if not isinstance(item, str) or not item.strip():
                        raise HTTPException(status_code=422, detail="Danh sách answer phải là chuỗi không trống")
                    normalized_list.append(item.strip())
                return normalized_list

            if isinstance(value, dict):
                if value.get("type") == "other":
                    text = value.get("text")
                    if not isinstance(text, str) or not text.strip():
                        raise HTTPException(status_code=422, detail="Văn bản other không được để trống")
                return value

            raise HTTPException(status_code=422, detail="Loại giá trị của answer không được hỗ trợ")

        if raw_answer is not None:
            if isinstance(raw_answer, dict):
                if len(raw_answer) == 0:
                    raise HTTPException(status_code=422, detail="answer không được để trống")

                normalized_answers: dict[str, Any] = {}
                for question_id, value in raw_answer.items():
                    normalized_question_id = str(question_id).strip()
                    if not normalized_question_id:
                        raise HTTPException(status_code=422, detail="question_id không được để trống")
                    normalized_answers[normalized_question_id] = normalize_single_answer(value)
                return normalized_answers

            raise HTTPException(status_code=422, detail="answer phải là ánh xạ đối tượng {question_id: answer}")

        if raw_approved is not None:
            return "approve" if raw_approved else "reject"

        raise HTTPException(status_code=422, detail="approved hoặc answer phải cung cấp ít nhất một trường")

    resume_input = normalize_resume_input(answer, approved)

    logger.info(
        "Resuming agent_id: %s, thread_id: %s, approved: %s, answer_type: %s",
        agent_id,
        thread_id,
        approved,
        type(answer).__name__ if answer is not None else "None",
    )

    meta = {
        "agent_id": agent_id,
        "thread_id": thread_id,
        "uid": current_user.uid,
        "approved": approved,
        "answer": answer,
        "resume_input": resume_input,
    }
    if "request_id" not in meta or not meta.get("request_id"):
        meta["request_id"] = str(uuid.uuid4())
    return StreamingResponse(
        stream_agent_resume(
            thread_id=thread_id,
            resume_input=resume_input,
            meta=meta,
            current_user=current_user,
            db=db,
        ),
        media_type="application/json",
    )


@chat.get("/thread/{thread_id}/history")
async def get_thread_history(
    thread_id: str, current_user: User = Depends(get_required_user), db: AsyncSession = Depends(get_db)
):
    """Get conversation history messages (login required)- Contains user feedback status"""
    try:
        return await get_thread_history_view(
            thread_id=thread_id,
            current_uid=str(current_user.uid),
            db=db,
        )

    except Exception as e:
        logger.error(f"Error getting conversation history message: {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy tin nhắn lịch sử hội thoại: {str(e)}")


@chat.get("/thread/{thread_id}/state")
async def get_thread_state(
    thread_id: str,
    include_messages: bool = Query(False),
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current status of the conversation (login required)"""
    try:
        return await get_agent_state_view(
            thread_id=thread_id,
            current_uid=str(current_user.uid),
            db=db,
            include_messages=include_messages,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation status: {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy trạng thái hội thoại: {str(e)}")


# ==================== Thread Management API ====================


class ThreadCreate(BaseModel):
    title: str | None = None
    agent_id: str
    metadata: dict | None = None


class ThreadResponse(BaseModel):
    id: str
    uid: str
    agent_id: str
    title: str | None = None
    is_pinned: bool = False
    created_at: str
    updated_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


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
# > === Session Management Group ===
# =============================================================================


@chat.post("/thread", response_model=ThreadResponse)
async def create_thread(
    thread: ThreadCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_required_user)
):
    """Create new conversation thread (Use new storage system)"""
    return await create_thread_view(
        agent_id=thread.agent_id,
        title=thread.title,
        metadata=thread.metadata,
        db=db,
        current_uid=str(current_user.uid),
    )


@chat.get("/threads", response_model=list[ThreadResponse])
async def list_threads(
    agent_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """Get all conversation threads of a user (Use new storage system)"""
    return await list_threads_view(
        agent_id=agent_id, db=db, current_uid=str(current_user.uid), limit=limit, offset=offset
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
    """搜索当前用户的历史对话。"""
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
    """Delete conversation thread (Use new storage system)"""
    return await delete_thread_view(thread_id=thread_id, db=db, current_uid=str(current_user.uid))


class ThreadUpdate(BaseModel):
    title: str | None = None
    is_pinned: bool | None = None


@chat.put("/thread/{thread_id}", response_model=ThreadResponse)
async def update_thread(
    thread_id: str,
    thread_update: ThreadUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """Update conversation thread information (Use new storage system)"""
    return await update_thread_view(
        thread_id=thread_id,
        title=thread_update.title,
        is_pinned=thread_update.is_pinned,
        db=db,
        current_uid=str(current_user.uid),
    )


# ================================
# > === Attachment management group ===
# ================================


@chat.post("/attachments/tmp", response_model=TmpAttachmentResponse)
async def upload_tmp_attachment(file: UploadFile = File(...), current_user: User = Depends(get_required_user)):
    """Upload attachments to MinIO tmp, not associated with threads yet."""
    return await upload_tmp_attachment_view(file=file, current_uid=str(current_user.uid))


@chat.post("/attachments/tmp/parse", response_model=TmpAttachmentParseResponse)
async def parse_tmp_attachment(
    request: TmpAttachmentParseRequest,
    current_user: User = Depends(get_required_user),
):
    """Parses a tmp attachment and returns the parsed tmp URL."""
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
    """Officially add the tmp attachment to the thread attachment list."""
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
    """Upload the original attachment and associate it to the specified conversation thread."""
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
    """Lists all attachment metainformation for the current conversation thread."""
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
    """Remove the specified attachment."""
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
    """List thread file directories."""
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
    """Read a threaded text file (paged by line)."""
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
    """Download or preview the thread file."""
    file_path = await resolve_thread_artifact_view(
        thread_id=thread_id,
        current_uid=str(current_user.uid),
        db=db,
        path=path,
    )

    media_type = detect_media_type(file_path.name, file_path.read_bytes())
    headers = {"Content-Disposition": f'attachment; filename="{file_path.name}"'} if download else None
    return FileResponse(path=file_path, media_type=media_type, headers=headers)


@chat.post("/thread/{thread_id}/artifacts/save", response_model=SaveThreadArtifactResponse)
async def save_thread_artifact_to_workspace(
    thread_id: str,
    request: SaveThreadArtifactRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """Save deliverables to shared workspace/saved_artifacts Table of contents."""
    return await save_thread_artifact_to_workspace_view(
        thread_id=thread_id,
        current_uid=str(current_user.uid),
        db=db,
        path=request.path,
    )


# =============================================================================
# > === Message feedback grouping ===
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
    """Submit message feedback (login required)"""
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
    """Get user feedback for a specified message (login required)"""
    return await get_message_feedback_view(
        message_id=message_id,
        db=db,
        current_uid=str(current_user.uid),
    )


# =============================================================================
# > === Multi-modal images support grouping ===
# =============================================================================


@chat.post("/image/upload", response_model=ImageUploadResponse)
async def upload_image(file: UploadFile = File(...), current_user: User = Depends(get_required_user)):
    """
    Upload and process images and return base64-encoded image data
    """
    try:
        # Verify file type
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Chỉ hỗ trợ tải lên tệp hình ảnh")

        # Read file contents
        image_data = await file.read()

        # Check file size (10MB limit, will be compressed to 5MB after exceeding)
        if len(image_data) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Tệp hình ảnh quá lớn, vui lòng tải lên hình ảnh nhỏ hơn 10MB")

        # Process pictures
        result = process_uploaded_image(image_data, file.filename)

        if not result["success"]:
            raise HTTPException(status_code=400, detail=f"Xử lý hình ảnh thất bại: {result['error']}")

        logger.info(
            f"user {current_user.id} Image uploaded successfully: {file.filename}, "
            f"size: {result['width']}x{result['height']}, "
            f"Format: {result['format']}, "
            f"size: {result['size_bytes']} bytes"
        )

        return ImageUploadResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image upload processing failed: {str(e)}, {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Xử lý hình ảnh thất bại: {str(e)}")
