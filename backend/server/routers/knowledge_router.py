import asyncio
import os
import textwrap
import time
import traceback
from urllib.parse import quote, unquote

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.responses import StreamingResponse
from yuxi import config, knowledge_base
from yuxi.knowledge.factory import KnowledgeBaseFactory
from yuxi.knowledge.graphs.milvus_graph_service import GRAPH_TASK_TYPE, MilvusGraphService
from yuxi.knowledge.parser import SUPPORTED_FILE_EXTENSIONS, Parser, is_supported_file_extension
from yuxi.knowledge.utils import calculate_content_hash, is_minio_url, parse_minio_url
from yuxi.knowledge.utils.mindmap_utils import (
    generate_database_mindmap,
    get_database_mindmap_data,
    get_mindmap_database_files,
    get_mindmap_databases_overview,
    get_mindmap_diff,
)
from yuxi.knowledge.utils.sample_question_utils import (
    generate_database_sample_questions,
    get_database_sample_questions,
)
from yuxi.knowledge.utils.url_fetcher import fetch_url_content
from yuxi.models.providers.cache import model_cache
from yuxi.services.task_service import TaskContext, tasker
from yuxi.services.workspace_service import MAX_WORKSPACE_UPLOAD_SIZE_BYTES, resolve_workspace_file_path
from yuxi.storage.minio.client import MinIOClient, StorageError, aupload_file_to_minio, get_minio_client
from yuxi.storage.postgres.models_business import User
from yuxi.utils import logger
from yuxi.utils.upload_utils import MAX_UPLOAD_SIZE_BYTES, read_upload_with_limit, write_upload_to_path

from server.utils.auth_middleware import get_admin_user, get_required_user

knowledge = APIRouter(prefix="/knowledge", tags=["knowledge"])

ACTIVE_GRAPH_BUILD_STATUSES = {"pending", "running"}
ACTIVE_DOCUMENT_ACTION_TASK_STATUSES = {"pending", "running"}
DOCUMENT_ACTION_BATCH_SIZE = 500
DOCUMENT_ACTION_RESULT_ITEM_LIMIT = 200
MAX_DIRECT_DOCUMENT_ACTION_FILE_IDS = 1000
PENDING_PARSE_STATUSES = ["uploaded"]
PENDING_INDEX_STATUSES = ["parsed", "error_indexing"]


class UpdateDatabaseRequest(BaseModel):
    name: str
    description: str
    llm_model_spec: str | None = None
    additional_params: dict | None = None
    share_config: dict | None = None


class WorkspaceImportRequest(BaseModel):
    kb_id: str
    paths: list[str]


class AddUploadedDocumentsRequest(BaseModel):
    items: list[str]
    params: dict | None = None


class PendingIndexDocumentsRequest(BaseModel):
    params: dict | None = None


media_types = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".json": "application/json",
    ".csv": "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".ppt": "application/vnd.ms-powerpoint",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
    ".zip": "application/zip",
    ".rar": "application/x-rar-compressed",
    ".7z": "application/x-7z-compressed",
    ".tar": "application/x-tar",
    ".gz": "application/gzip",
    ".html": "text/html",
    ".htm": "text/html",
    ".xml": "text/xml",
    ".css": "text/css",
    ".js": "application/javascript",
    ".py": "text/x-python",
    ".java": "text/x-java-source",
    ".cpp": "text/x-c++src",
    ".c": "text/x-csrc",
    ".h": "text/x-chdr",
    ".hpp": "text/x-c++hdr",
}


async def _delete_document_storage_objects(kb_id: str, doc_id: str, file_path: str) -> None:
    minio_client = get_minio_client()

    if is_minio_url(file_path):
        try:
            bucket_name, object_name = parse_minio_url(file_path)
            await minio_client.adelete_file(bucket_name, object_name)
        except Exception as minio_error:
            logger.warning(f"Deletion of original files from MinIO failed: {minio_error}")

    try:
        await minio_client.adelete_file(minio_client.KB_BUCKETS["parsed"], f"{kb_id}/parsed/{doc_id}.md")
    except Exception as minio_error:
        logger.warning(f"Deleting parse results from MinIO failed: {minio_error}")

    try:
        await minio_client.adelete_file(minio_client.KB_BUCKETS["parsed"], f"{kb_id}/preview/{doc_id}.pdf")
    except Exception as minio_error:
        logger.warning(f"Deleting preview PDF from MinIO failed: {minio_error}")


async def _ensure_database_supports_documents(kb_id: str, operation: str) -> None:
    db_info = await knowledge_base.get_database_info(kb_id)
    if not db_info:
        raise HTTPException(status_code=404, detail=f"Kho kiến thức {kb_id} không tồn tại")
    kb_type = (db_info.get("kb_type") or "").lower()
    kb_class = KnowledgeBaseFactory.get_kb_class(kb_type)
    if not kb_class.supports_documents:
        raise HTTPException(status_code=400, detail=f"{db_info.get('name') or kb_type} chỉ hỗ trợ tìm kiếm, không hỗ trợ {operation}")


def _ensure_document_params(params: dict | None) -> dict:
    if params is None:
        return {}
    if not isinstance(params, dict):
        raise HTTPException(status_code=400, detail="params must be an object")
    return params


def _validate_uploaded_document_items(items: list[str], params: dict) -> None:
    if not items:
        raise HTTPException(status_code=400, detail="items must not be empty")

    content_hashes = params.get("content_hashes")
    if content_hashes is not None and not isinstance(content_hashes, dict):
        raise HTTPException(status_code=400, detail="params.content_hashes must be an object")

    file_sizes = params.get("file_sizes")
    if file_sizes is not None and not isinstance(file_sizes, dict):
        raise HTTPException(status_code=400, detail="params.file_sizes must be an object")

    preprocessed_map = params.get("_preprocessed_map")
    if preprocessed_map is not None and not isinstance(preprocessed_map, dict):
        raise HTTPException(status_code=400, detail="params._preprocessed_map must be an object")

    for item in items:
        if not isinstance(item, str) or not item.strip():
            raise HTTPException(status_code=400, detail="items must only contain non-empty strings")
        if not is_minio_url(item):
            raise HTTPException(status_code=400, detail="File source must be a MinIO URL")

        has_content_hash = isinstance(content_hashes, dict) and bool(content_hashes.get(item))
        preprocessed = preprocessed_map.get(item) if isinstance(preprocessed_map, dict) else None
        has_preprocessed_hash = isinstance(preprocessed, dict) and bool(preprocessed.get("content_hash"))
        if not has_content_hash and not has_preprocessed_hash:
            raise HTTPException(status_code=400, detail=f"Missing content_hash for file: {item}")


def _params_for_uploaded_document_item(item: str, params: dict) -> dict:
    source_paths = params.get("source_paths")
    item_params = dict(params)
    item_params.pop("source_paths", None)
    if isinstance(source_paths, dict) and source_paths.get(item):
        item_params["source_path"] = source_paths[item]
    return item_params


async def _has_running_graph_build_task(kb_id: str) -> bool:
    return (
        await tasker.find_task_by_payload(
            task_type=GRAPH_TASK_TYPE,
            payload_match={"kb_id": kb_id},
            statuses=ACTIVE_GRAPH_BUILD_STATUSES,
        )
        is not None
    )


# =============================================================================
# === Knowledge Base Management Group ===
# =============================================================================


@knowledge.get("/databases")
async def get_databases(current_user: User = Depends(get_admin_user)):
    """Get all knowledge bases (filtered based on user permissions)"""
    try:
        return await knowledge_base.get_databases_by_uid(current_user.uid)
    except Exception as e:
        logger.error(f"Failed to get database list {e}, {traceback.format_exc()}")
        return {"message": f"Failed to get database list {e}", "databases": []}


@knowledge.post("/databases")
async def create_database(
    database_name: str = Body(...),
    description: str = Body(...),
    embedding_model_spec: str | None = Body(None),
    kb_type: str = Body("milvus"),
    additional_params: dict | None = Body(None),
    llm_model_spec: str | None = Body(None),
    share_config: dict | None = Body(None),
    current_user: User = Depends(get_admin_user),
):
    """Create a knowledge base"""
    logger.debug(
        f"Create database {database_name} with kb_type {kb_type}, "
        f"additional_params {additional_params}, llm_model_spec {llm_model_spec}, "
        f"embedding_model_spec {embedding_model_spec}, share_config {share_config}"
    )
    try:
        # First check if the name already exists
        if await knowledge_base.database_name_exists(database_name):
            raise HTTPException(
                status_code=409,
                detail=f"Tên kho kiến thức '{database_name}' đã tồn tại, vui lòng sử dụng tên khác",
            )

        if not KnowledgeBaseFactory.is_type_supported(kb_type):
            raise HTTPException(status_code=400, detail=f"Unsupported knowledge base type: {kb_type}")

        kb_class = KnowledgeBaseFactory.get_kb_class(kb_type)

        additional_params = {**(additional_params or {})}
        additional_params["auto_generate_questions"] = False  # Does not generate problems by default

        if "reranker_config" in additional_params:
            raise HTTPException(
                status_code=400,
                detail="reranker_config đã bị gỡ bỏ, vui lòng sử dụng reranker_model spec trong tham số truy vấn",
            )
        additional_params = kb_class.normalize_additional_params(additional_params)

        if kb_class.requires_embedding_model:
            if not embedding_model_spec:
                raise HTTPException(status_code=400, detail="embedding_model_spec không được để trống")

            info = model_cache.get_model_info(embedding_model_spec)
            if not info or info.model_type != "embedding":
                raise HTTPException(status_code=400, detail=f"Mô hình embedding không hỗ trợ: {embedding_model_spec}")
        else:
            embedding_model_spec = None

        database_info = await knowledge_base.create_database(
            database_name,
            description,
            kb_type=kb_type,
            embedding_model_spec=embedding_model_spec,
            llm_model_spec=llm_model_spec,
            share_config=share_config,
            created_by=current_user.uid,
            created_by_department_id=current_user.department_id,
            **additional_params,
        )

        # All agents need to be reloaded because the tool refreshed
        from yuxi.agents.buildin import agent_manager

        await agent_manager.reload_all()

        return database_info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create database {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=f"Tạo cơ sở dữ liệu thất bại: {e}")


@knowledge.get("/databases/accessible")
async def get_accessible_databases(current_user: User = Depends(get_required_user)):
    """Get the list of knowledge bases that the current user has access to (for agent configuration)"""
    try:
        databases = await knowledge_base.get_databases_by_uid(current_user.uid)

        accessible = [
            {
                "name": db.get("name", ""),
                "kb_id": db.get("kb_id"),
                "description": db.get("description", ""),
                "created_by": db.get("created_by"),
                "kb_type": db.get("kb_type"),
                "supports_documents": KnowledgeBaseFactory.get_kb_class(
                    (db.get("kb_type") or "milvus").lower()
                ).supports_documents,
            }
            for db in databases.get("databases", [])
        ]

        return {"databases": accessible}
    except Exception as e:
        logger.error(f"Failed to obtain list of accessible knowledge bases: {e}, {traceback.format_exc()}")
        return {"message": f"Lấy danh sách kho kiến thức có quyền truy cập thất bại: {str(e)}", "databases": []}


@knowledge.get("/mindmap/databases")
async def get_mindmap_databases(current_user: User = Depends(get_admin_user)):
    """Get an overview of all knowledge bases for mind mapping interface selection."""
    try:
        return await get_mindmap_databases_overview(current_user.uid)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to obtain knowledge base list: {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Lấy danh sách kho kiến thức thất bại: {str(e)}")


@knowledge.get("/databases/{kb_id}/mindmap/files")
async def get_database_mindmap_files(kb_id: str, current_user: User = Depends(get_admin_user)):
    """Get a list of all files in the specified knowledge base."""
    try:
        return await get_mindmap_database_files(kb_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get file list: {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Lấy danh sách tệp thất bại: {str(e)}")


@knowledge.post("/databases/{kb_id}/mindmap/generate")
async def generate_mindmap(
    kb_id: str,
    file_ids: list[str] | None = Body(default=None, description="Danh sách ID tệp được chọn"),
    user_prompt: str = Body(default="", description="Prompt tùy chỉnh của người dùng"),
    incremental: bool = Body(default=False, description="Có cập nhật tăng dần hay không"),
    current_user: User = Depends(get_admin_user),
):
    """Use AI to analyze knowledge base files and generate mind map structures. Supports incremental update mode."""
    try:
        return await generate_database_mindmap(kb_id, file_ids, user_prompt, incremental)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate mind map: {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Tạo sơ đồ tư duy thất bại: {str(e)}")


@knowledge.get("/databases/{kb_id}/mindmap")
async def get_database_mindmap(kb_id: str, current_user: User = Depends(get_admin_user)):
    """Get a mind map associated with the knowledge base."""
    try:
        return await get_database_mindmap_data(kb_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to obtain knowledge base mind map: {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Lấy sơ đồ tư duy kho kiến thức thất bại: {str(e)}")


@knowledge.get("/databases/{kb_id}/mindmap/diff")
async def get_mindmap_diff_route(kb_id: str, current_user: User = Depends(get_admin_user)):
    """Detect changes in mind maps and knowledge base files."""
    try:
        return await get_mindmap_diff(kb_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to detect mind map changes: {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Phát hiện thay đổi sơ đồ tư duy thất bại: {str(e)}")


@knowledge.get("/databases/{kb_id}")
async def get_database_info(
    kb_id: str,
    include_files: bool = Query(False, description="Có bao gồm danh sách tệp đầy đủ hay không, mặc định tắt để tránh phản hồi quá lớn cho kho kiến thức lớn"),
    current_user: User = Depends(get_admin_user),
):
    """Get knowledge base details"""
    database = await knowledge_base.get_database_info(kb_id, include_files=include_files)
    if database is None:
        raise HTTPException(status_code=404, detail="Database not found")
    return database


@knowledge.post("/databases/{kb_id}/stats/repair")
async def repair_database_stats(kb_id: str, current_user: User = Depends(get_admin_user)):
    """Fix missing chunks in knowledge base history files/Token statistics."""
    await _ensure_database_supports_documents(kb_id, "Stats fix")
    try:
        return await knowledge_base.repair_missing_file_stats(kb_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Fix knowledge base statistics failure {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Sửa lỗi thống kê kho kiến thức thất bại: {e}")


@knowledge.put("/databases/{kb_id}")
async def update_database_info(
    kb_id: str,
    data: UpdateDatabaseRequest,
    current_user: User = Depends(get_admin_user),
):
    """Update knowledge base information"""
    logger.debug(
        f"[update_database_info] parameters received: name={data.name}, llm_model_spec={data.llm_model_spec}, "
        f"additional_params={data.additional_params}, share_config={data.share_config}"
    )
    try:
        update_llm_model_spec = "llm_model_spec" in data.model_fields_set

        additional_params = data.additional_params
        if additional_params is not None:
            db_info = await knowledge_base.get_database_info(kb_id)
            if not db_info:
                raise HTTPException(status_code=404, detail=f"Kho kiến thức {kb_id} không tồn tại")

            kb_type = (db_info.get("kb_type") or "").lower()
            kb_class = KnowledgeBaseFactory.get_kb_class(kb_type)
            merged_params = dict(db_info.get("additional_params") or {})
            merged_params.update(additional_params)
            kb_class.normalize_additional_params(merged_params)
            additional_params = (
                kb_class.normalize_additional_params(additional_params)
                if kb_class.apply_chunk_defaults
                else kb_class.normalize_additional_params(merged_params)
            )

        database = await knowledge_base.update_database(
            kb_id,
            data.name,
            data.description,
            data.llm_model_spec,
            update_llm_model_spec=update_llm_model_spec,
            additional_params=additional_params,
            share_config=data.share_config,
            operator_uid=current_user.uid,
            operator_department_id=current_user.department_id,
        )
        return {"message": "Cập nhật thành công", "database": database}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cập nhật cơ sở dữ liệu thất bại {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=f"Cập nhật cơ sở dữ liệu thất bại: {e}")


@knowledge.delete("/databases/{kb_id}")
async def delete_database(kb_id: str, current_user: User = Depends(get_admin_user)):
    """Delete knowledge base"""
    logger.debug(f"Delete database {kb_id}")
    try:
        await knowledge_base.delete_database(kb_id)

        # All agents need to be reloaded because the tool refreshed
        from yuxi.agents.buildin import agent_manager

        await agent_manager.reload_all()

        return {"message": "Xóa thành công"}
    except Exception as e:
        logger.error(f"Failed to delete database {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=f"Xóa cơ sở dữ liệu thất bại: {e}")


@knowledge.get("/databases/{kb_id}/graph-build/status")
async def get_graph_build_status(kb_id: str, current_user: User = Depends(get_admin_user)):
    try:
        return await MilvusGraphService().get_status(kb_id, tasker=tasker)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to obtain graph build status {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Lấy trạng thái xây dựng đồ thị thất bại: {e}")


@knowledge.post("/databases/{kb_id}/graph-build/config")
async def configure_graph_build(
    kb_id: str,
    data: dict = Body(...),
    current_user: User = Depends(get_admin_user),
):
    try:
        config = await MilvusGraphService().configure(
            kb_id,
            extractor_type=data.get("extractor_type"),
            extractor_options=data.get("extractor_options") or {},
            created_by=current_user.uid,
        )
        return {"message": "Cấu hình trích xuất đồ thị đã được khóa", "status": "success", "config": config}
    except ValueError as e:
        status_code = 409 if "locked" in str(e) else 400
        raise HTTPException(status_code=status_code, detail=str(e))
    except Exception as e:
        logger.error(f"Configuration map build failed {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Cấu hình xây dựng đồ thị thất bại: {e}")


@knowledge.post("/databases/{kb_id}/graph-build/index")
async def index_graph_build(
    kb_id: str,
    data: dict | None = Body(default=None),
    current_user: User = Depends(get_admin_user),
):
    data = data or {}
    try:
        if await _has_running_graph_build_task(kb_id):
            raise HTTPException(status_code=409, detail="Kho kiến thức này đã có nhiệm vụ xây dựng đồ thị đang chạy")

        database = await knowledge_base.get_database_info(kb_id)
        if not database:
            raise HTTPException(status_code=404, detail=f"Kho kiến thức {kb_id} không tồn tại")

        batch_size = max(1, min(int(data.get("batch_size") or 20), 200))
        service = MilvusGraphService()
        graph_status = await service.get_status(kb_id)
        if not graph_status.get("locked"):
            raise HTTPException(status_code=400, detail="Vui lòng xác nhận và khóa cấu hình trích xuất đồ thị trước")

        async def run_graph_index(context: TaskContext):
            await context.set_message("Task initialization")
            await context.set_progress(5.0, "Prepare to build the map")
            result = await service.build_pending_chunks(kb_id, batch_size=batch_size, context=context)
            await context.set_result(result)
            await context.set_progress(100.0, f"Map construction completed, successful {result['success']} one, failed {result['failed']} indivual")
            return result

        task, created = await tasker.enqueue_unique_by_payload(
            name=f"Map construction ({database['name']})",
            task_type=GRAPH_TASK_TYPE,
            payload={"kb_id": kb_id, "batch_size": batch_size},
            coroutine=run_graph_index,
            payload_match={"kb_id": kb_id},
            statuses=ACTIVE_GRAPH_BUILD_STATUSES,
        )
        if not created:
            raise HTTPException(status_code=409, detail="Kho kiến thức này đã có nhiệm vụ xây dựng đồ thị đang chạy")
        return {"message": "Nhiệm vụ xây dựng đồ thị đã được gửi", "status": "queued", "task_id": task.id}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to submit graph construction task {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Gửi nhiệm vụ xây dựng đồ thị thất bại: {e}")


@knowledge.post("/databases/{kb_id}/graph-build/reset")
async def reset_graph_build(
    kb_id: str,
    data: dict | None = Body(default=None),
    current_user: User = Depends(get_admin_user),
):
    data = data or {}
    try:
        if await _has_running_graph_build_task(kb_id):
            raise HTTPException(status_code=409, detail="Kho kiến thức này có nhiệm vụ xây dựng đồ thị đang chạy, không thể đặt lại")

        return await MilvusGraphService().reset(
            kb_id,
            clear_extraction_result=bool(data.get("clear_extraction_result", True)),
            clear_config=bool(data.get("clear_config", False)),
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to reset map build status {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Đặt lại trạng thái xây dựng đồ thị thất bại: {e}")


@knowledge.get("/databases/{kb_id}/export")
async def export_database(
    kb_id: str,
    format: str = Query("csv", enum=["csv", "xlsx", "md", "txt"]),
    include_vectors: bool = Query(False, description="Có bao gồm dữ liệu vector trong xuất bản hay không"),
    current_user: User = Depends(get_admin_user),
):
    """Export knowledge base data"""
    logger.debug(f"Exporting database {kb_id} with format {format}")
    try:
        file_path = await knowledge_base.export_data(kb_id, format=format, include_vectors=include_vectors)

        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Exported file not found.")

        media_type = media_types.get(f".{format}", "application/octet-stream")

        return FileResponse(path=file_path, filename=os.path.basename(file_path), media_type=media_type)
    except HTTPException:
        raise
    except NotImplementedError as e:
        logger.warning(f"A disabled feature was accessed: {e}")
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        logger.error(f"Export database failed {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Xuất cơ sở dữ liệu thất bại: {e}")


# =============================================================================
# === Knowledge base document management group ===
# =============================================================================


@knowledge.get("/databases/{kb_id}/documents")
async def list_documents(
    kb_id: str,
    parent_id: str | None = Query(None, description="ID thư mục cha, giá trị trống nghĩa là thư mục gốc"),
    path_prefix: str | None = Query(None, description="Tiền tố thư mục dạng đường dẫn, dùng để tải lười thư mục ảo được tạo từ source_path"),
    status: str = Query("all", description="Bộ lọc trạng thái tệp"),
    page: int = Query(1, ge=1, description="Số trang"),
    page_size: int = Query(100, ge=1, le=500, description="Số lượng mỗi trang"),
    recursive: bool = Query(False, description="Có lọc chéo thư mục hay không"),
    current_user: User = Depends(get_admin_user),
):
    """Get the list of knowledge base files in pages."""
    await _ensure_database_supports_documents(kb_id, "Document view")
    try:
        return await knowledge_base.list_document_files(
            kb_id,
            parent_id=parent_id,
            path_prefix=path_prefix,
            status=status,
            page=page,
            page_size=page_size,
            recursive=recursive,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@knowledge.get("/databases/{kb_id}/documents/exists")
async def document_file_exists(
    kb_id: str,
    filename: str = Query(..., min_length=1, description="Tên hiển thị hoặc đường dẫn tương đối của tệp kho kiến thức"),
    current_user: User = Depends(get_admin_user),
):
    """Checks whether a file with the specified file name or relative path already exists in the knowledge base."""
    await _ensure_database_supports_documents(kb_id, "Document existence check")
    normalized_filename = filename.strip()
    if not normalized_filename:
        raise HTTPException(status_code=400, detail="filename is required")
    try:
        exists = await knowledge_base.document_file_exists(kb_id, normalized_filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"kb_id": kb_id, "filename": normalized_filename, "exists": exists}


@knowledge.post("/databases/{kb_id}/documents")
async def add_documents(
    kb_id: str, items: list[str] = Body(...), params: dict = Body(...), current_user: User = Depends(get_admin_user)
):
    """Add documents to the knowledge base (upload -> parse -> Optional storage)"""
    logger.debug(f"Add documents for kb_id {kb_id}: {items} {params=}")
    await _ensure_database_supports_documents(kb_id, "Documentation added/parse/Warehouse")

    params = _ensure_document_params(params)
    content_type = params.get("content_type", "file")
    # Automatic storage parameters
    auto_index = params.get("auto_index", False)
    indexing_params = {}
    chunk_preset_id = params.get("chunk_preset_id")
    if chunk_preset_id:
        indexing_params["chunk_preset_id"] = chunk_preset_id

    chunk_parser_config = params.get("chunk_parser_config")
    if isinstance(chunk_parser_config, dict):
        indexing_params["chunk_parser_config"] = chunk_parser_config

    if content_type == "url":
        raise HTTPException(status_code=400, detail="Cách xử lý URL đã thay đổi, vui lòng sử dụng API fetch-url để lấy nội dung trước")
    if content_type != "file":
        raise HTTPException(status_code=400, detail=f"Unsupported content_type: {content_type}")

    _validate_uploaded_document_items(items, params)

    async def run_ingest(context: TaskContext):
        await context.set_message("Task initialization")
        await context.set_progress(5.0, "Prepare to process documents")

        total = len(items)
        processed_items: list[dict | None] = [None] * total
        added_files: list[dict] = []

        try:
            await context.set_message("Phase One: Add Document Records")
            for idx, item in enumerate(items, 1):
                await context.raise_if_cancelled()

                progress = 5.0 + (idx / total) * 25.0
                await context.set_progress(progress, f"[1/3] Add record {idx}/{total}")

                try:
                    file_meta = await knowledge_base.add_file_record(
                        kb_id, item, params=params, operator_id=current_user.uid
                    )
                    added_files.append(
                        {
                            "index": idx - 1,
                            "item": item,
                            "file_id": file_meta["file_id"],
                            "file_meta": file_meta,
                        }
                    )
                except Exception as add_error:
                    logger.error(f"Failed to add file record {item}: {add_error}")
                    error_type = "timeout" if isinstance(add_error, TimeoutError) else "add_failed"
                    error_msg = "add timeout" if isinstance(add_error, TimeoutError) else "Failed to add record"
                    processed_items[idx - 1] = {
                        "item": item,
                        "status": "failed",
                        "error": f"{error_msg}: {str(add_error)}",
                        "error_type": error_type,
                    }

            await context.set_message("Phase 2: Parse the file")
            parse_end = 60.0 if auto_index else 95.0
            parse_total = len(added_files)
            for idx, record in enumerate(added_files, 1):
                await context.raise_if_cancelled()

                progress = 30.0 + (idx / parse_total) * (parse_end - 30.0)
                await context.set_progress(progress, f"[2/3] parse file {idx}/{parse_total}")

                item = record["item"]
                file_id = record["file_id"]
                try:
                    file_meta = await knowledge_base.parse_file(kb_id, file_id, operator_id=current_user.uid)
                    record["file_meta"] = file_meta
                    if not auto_index or file_meta.get("status") != "parsed":
                        processed_items[record["index"]] = file_meta
                except Exception as parse_error:
                    logger.error(f"Failed to parse file {item} (file_id={file_id}): {parse_error}")
                    error_type = "timeout" if isinstance(parse_error, TimeoutError) else "parse_failed"
                    error_msg = "Parse timeout" if isinstance(parse_error, TimeoutError) else "Parsing failed"
                    processed_items[record["index"]] = {
                        "item": item,
                        "status": "failed",
                        "error": f"{error_msg}: {str(parse_error)}",
                        "error_type": error_type,
                    }

            if auto_index:
                await context.set_message("The third stage: automatic storage")
                parsed_files = [record for record in added_files if record["file_meta"].get("status") == "parsed"]
                total_parsed = len(parsed_files)

                for idx, record in enumerate(parsed_files, 1):
                    await context.raise_if_cancelled()

                    progress = 60.0 + (idx / total_parsed) * 35.0
                    await context.set_progress(progress, f"[3/3] Inbound files {idx}/{total_parsed}")

                    item = record["item"]
                    file_id = record["file_id"]
                    try:
                        await knowledge_base.update_file_params(
                            kb_id, file_id, indexing_params, operator_id=current_user.uid
                        )
                        result = await knowledge_base.index_file(
                            kb_id, file_id, operator_id=current_user.uid, params=indexing_params
                        )
                        processed_items[record["index"]] = result
                    except Exception as index_error:
                        logger.error(f"Automatic storage failed {item} (file_id={file_id}): {index_error}")
                        processed_items[record["index"]] = {
                            "item": item,
                            "status": "failed",
                            "error": f"Storage failed: {str(index_error)}",
                            "error_type": "index_failed",
                        }

        except asyncio.CancelledError:
            await context.set_progress(100.0, "Task canceled")
            raise
        except Exception as task_error:
            logger.exception(f"Task processing failed: {task_error}")
            await context.set_progress(100.0, f"Task processing failed: {str(task_error)}")
            raise

        final_items = [
            item
            if item is not None
            else {
                "item": items[index],
                "status": "failed",
                "error": "File not processed",
                "error_type": "not_processed",
            }
            for index, item in enumerate(processed_items)
        ]
        failed_count = len([item for item in final_items if _is_failed_item(item)])

        summary = {
            "kb_id": kb_id,
            "item_type": "Tệp",
            "submitted": total,
            "failed": failed_count,
        }
        message = f"Xử lý tệp hoàn tất, thất bại {failed_count} tệp" if failed_count else "Xử lý tệp hoàn tất"
        await context.set_result(summary | {"items": final_items})
        await context.set_progress(100.0, message)

        if failed_count:
            raise RuntimeError(message)

        return summary | {"items": final_items}

    try:
        database = await knowledge_base.get_database_info(kb_id)
        task = await tasker.enqueue(
            name=f"Knowledge base document processing ({database['name']})",
            task_type="knowledge_ingest",
            payload={
                "kb_id": kb_id,
                "items": items,
                "params": params,
                "content_type": content_type,
            },
            coroutine=run_ingest,
        )
        return {
            "message": "Nhiệm vụ đã được gửi, vui lòng kiểm tra tiến độ trong trung tâm nhiệm vụ",
            "status": "queued",
            "task_id": task.id,
        }
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to enqueue {content_type}s: {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to enqueue task: {e}")


@knowledge.post("/databases/{kb_id}/documents/add")
async def add_uploaded_documents(
    kb_id: str,
    payload: AddUploadedDocumentsRequest,
    current_user: User = Depends(get_admin_user),
):
    """The uploaded MinIO files are synchronously added as knowledge base document records, and are not parsed or stored in the database."""
    logger.debug(f"Add uploaded documents for kb_id {kb_id}: {payload.items} params={payload.params}")
    await _ensure_database_supports_documents(kb_id, "Documentation added")

    params = _ensure_document_params(payload.params)
    content_type = params.get("content_type", "file")
    if content_type == "url":
        raise HTTPException(status_code=400, detail="Cách xử lý URL đã thay đổi, vui lòng sử dụng API fetch-url để lấy nội dung trước")
    if content_type != "file":
        raise HTTPException(status_code=400, detail=f"Unsupported content_type: {content_type}")

    _validate_uploaded_document_items(payload.items, params)

    added_items: list[dict] = []
    failed_items: list[dict] = []
    for index, item in enumerate(payload.items):
        try:
            file_meta = await knowledge_base.add_file_record(
                kb_id,
                item,
                params=_params_for_uploaded_document_item(item, params),
                operator_id=current_user.uid,
            )
            added_items.append(
                {
                    "index": index,
                    "item": item,
                    "file_id": file_meta["file_id"],
                    "status": file_meta.get("status"),
                    "file_meta": file_meta,
                }
            )
        except Exception as add_error:  # noqa: BLE001
            logger.error(f"Failed to add file record {item}: {add_error}")
            failed_items.append(
                {
                     "index": index,
                     "item": item,
                     "status": "failed",
                     "error": f"Thêm bản ghi thất bại: {str(add_error)}",
                     "error_type": "add_failed",
                }
            )

    failed_count = len(failed_items)
    added_count = len(added_items)
    if failed_count == 0:
        status = "success"
        message = f"Đã thêm {added_count} tệp"
    elif added_count == 0:
        status = "failed"
        message = f"Thêm tệp thất bại, thất bại {failed_count} tệp"
    else:
        status = "partial_failed"
        message = f"Đã thêm {added_count} tệp, thất bại {failed_count} tệp"

    return {
        "message": message,
        "status": status,
        "items": added_items,
        "failed_items": failed_items,
        "added": added_count,
        "failed": failed_count,
    }


def _validate_direct_document_action_file_ids(file_ids: list[str]) -> list[str]:
    normalized_file_ids = [file_id for file_id in file_ids if file_id]
    if not normalized_file_ids:
        raise HTTPException(status_code=400, detail="Vui lòng chọn ít nhất một tệp")
    if len(normalized_file_ids) > MAX_DIRECT_DOCUMENT_ACTION_FILE_IDS:
        raise HTTPException(
            status_code=400,
            detail=(f"Hỗ trợ tối đa {MAX_DIRECT_DOCUMENT_ACTION_FILE_IDS} tệp cho mỗi lần chạy, vui lòng sử dụng cổng trạng thái chờ xử lý để gửi toàn bộ nhiệm vụ chạy ngầm"),
        )
    return normalized_file_ids


def _append_document_action_result_sample(items: list[dict], item: dict) -> None:
    if len(items) < DOCUMENT_ACTION_RESULT_ITEM_LIMIT:
        items.append(item)


def _is_failed_item(item: dict) -> bool:
    """Determine if individualProcessing results are nofail: explicit fail status, or carry non-empty mistake information.

    documentMetadatasuccess will also bring `error: None`, so we cannot rely solely on `error` key Determine failure if it exists.
    """
    return item.get("status") == "failed" or bool(item.get("error"))


async def _run_parse_file_ids(
    *,
    context: TaskContext,
    kb_id: str,
    file_ids: list[str],
    operator_id: str,
) -> dict:
    await context.set_message("Task initialization")
    await context.set_progress(5.0, "Prepare to parse document")

    total = len(file_ids)
    processed_items = []

    for idx, file_id in enumerate(file_ids, 1):
        await context.raise_if_cancelled()
        progress = 5.0 + (idx / total) * 90.0
        await context.set_progress(progress, f"Đang phân tích tài liệu thứ {idx}/{total}")

        try:
            result = await knowledge_base.parse_file(kb_id, file_id, operator_id=operator_id)
            processed_items.append(result)
        except Exception as e:
            logger.error(f"Parse failed for {file_id}: {e}")
            processed_items.append({"file_id": file_id, "status": "failed", "error": str(e)})

    failed_count = len([p for p in processed_items if _is_failed_item(p)])
    message = f"Phân tích hoàn tất, thất bại {failed_count} tệp"
    result_payload = {"items": processed_items, "processed": len(processed_items), "failed": failed_count}
    await context.set_result(result_payload)
    await context.set_progress(100.0, message)
    return result_payload


async def _run_index_file_ids(
    *,
    context: TaskContext,
    kb_id: str,
    file_ids: list[str],
    operator_id: str,
    params: dict,
) -> dict:
    await context.set_message("Task initialization")
    await context.set_progress(5.0, "Prepare documents for storage")

    total = len(file_ids)
    processed_items = []
    param_update_failed = set()

    if params:
        for file_id in file_ids:
            try:
                await knowledge_base.update_file_params(kb_id, file_id, params, operator_id=operator_id)
            except Exception as e:
                logger.error(f"Failed to update params for {file_id}: {e}")
                param_update_failed.add(file_id)
                processed_items.append({"file_id": file_id, "status": "failed", "error": f"Cập nhật tham số thất bại: {str(e)}"})

    for idx, file_id in enumerate(file_ids, 1):
        await context.raise_if_cancelled()

        if file_id in param_update_failed:
            logger.debug(f"Skipping {file_id} due to param update failure")
            continue

        progress = 5.0 + (idx / total) * 90.0
        await context.set_progress(progress, f"Đang nhập kho tài liệu thứ {idx}/{total}")

        try:
            result = await knowledge_base.index_file(kb_id, file_id, operator_id=operator_id, params=params)
            processed_items.append(result)
        except Exception as e:
            logger.error(f"Index failed for {file_id}: {e}")
            processed_items.append({"file_id": file_id, "status": "failed", "error": str(e)})

    failed_count = len([p for p in processed_items if _is_failed_item(p)])
    message = f"Nhập kho hoàn tất, thất bại {failed_count} tệp"
    result_payload = {"items": processed_items, "processed": len(processed_items), "failed": failed_count}
    await context.set_result(result_payload)
    await context.set_progress(100.0, message)
    return result_payload


async def _run_parse_pending_statuses(
    *,
    context: TaskContext,
    kb_id: str,
    statuses: list[str],
    initial_total: int,
    operator_id: str,
) -> dict:
    await context.set_message("Task initialization")
    await context.set_progress(5.0, "Prepare to parse pending documents")

    processed_count = 0
    failed_count = 0
    result_items = []
    after_file_id = None

    while True:
        file_ids = await knowledge_base.list_document_file_ids_by_statuses(
            kb_id,
            statuses=statuses,
            after_file_id=after_file_id,
            limit=DOCUMENT_ACTION_BATCH_SIZE,
        )
        if not file_ids:
            break

        for file_id in file_ids:
            await context.raise_if_cancelled()
            after_file_id = file_id
            processed_count += 1
            progress_total = max(initial_total, processed_count)
            progress = 5.0 + (processed_count / progress_total) * 90.0
            await context.set_progress(progress, f"Đang phân tích tài liệu thứ {processed_count}/{progress_total}")

            try:
                result = await knowledge_base.parse_file(kb_id, file_id, operator_id=operator_id)
                _append_document_action_result_sample(result_items, result)
            except Exception as e:
                failed_count += 1
                logger.error(f"Parse failed for {file_id}: {e}")
                _append_document_action_result_sample(
                    result_items,
                    {"file_id": file_id, "status": "failed", "error": str(e)},
                )

    message = f"Phân tích hoàn tất, thất bại {failed_count} tệp" if processed_count else "Không có tài liệu nào chờ phân tích"
    result_payload = {
        "items": result_items,
        "processed": processed_count,
        "failed": failed_count,
        "result_truncated": processed_count > len(result_items),
    }
    await context.set_result(result_payload)
    await context.set_progress(100.0, message)
    return result_payload


async def _run_index_pending_statuses(
    *,
    context: TaskContext,
    kb_id: str,
    statuses: list[str],
    initial_total: int,
    operator_id: str,
    params: dict,
) -> dict:
    await context.set_message("Task initialization")
    await context.set_progress(5.0, "Prepare documents for storage and pending processing")

    processed_count = 0
    failed_count = 0
    result_items = []
    after_file_id = None

    while True:
        file_ids = await knowledge_base.list_document_file_ids_by_statuses(
            kb_id,
            statuses=statuses,
            after_file_id=after_file_id,
            limit=DOCUMENT_ACTION_BATCH_SIZE,
        )
        if not file_ids:
            break

        for file_id in file_ids:
            await context.raise_if_cancelled()
            after_file_id = file_id
            processed_count += 1
            progress_total = max(initial_total, processed_count)
            progress = 5.0 + (processed_count / progress_total) * 90.0
            await context.set_progress(progress, f"Đang nhập kho tài liệu thứ {processed_count}/{progress_total}")

            try:
                if params:
                    await knowledge_base.update_file_params(kb_id, file_id, params, operator_id=operator_id)
                result = await knowledge_base.index_file(kb_id, file_id, operator_id=operator_id, params=params)
                _append_document_action_result_sample(result_items, result)
            except Exception as e:
                failed_count += 1
                logger.error(f"Index failed for {file_id}: {e}")
                _append_document_action_result_sample(
                    result_items,
                    {"file_id": file_id, "status": "failed", "error": str(e)},
                )

    message = f"Nhập kho hoàn tất, thất bại {failed_count} tệp" if processed_count else "Không có tài liệu nào chờ nhập kho"
    result_payload = {
        "items": result_items,
        "processed": processed_count,
        "failed": failed_count,
        "result_truncated": processed_count > len(result_items),
    }
    await context.set_result(result_payload)
    await context.set_progress(100.0, message)
    return result_payload


@knowledge.post("/databases/{kb_id}/documents/parse")
async def parse_documents(kb_id: str, file_ids: list[str] = Body(...), current_user: User = Depends(get_admin_user)):
    """Manually trigger document parsing"""
    file_ids = _validate_direct_document_action_file_ids(file_ids)
    logger.debug(f"Parse documents for kb_id {kb_id}: {file_ids}")
    await _ensure_database_supports_documents(kb_id, "Document parsing")

    async def run_parse(context: TaskContext):
        try:
            return await _run_parse_file_ids(
                context=context,
                kb_id=kb_id,
                file_ids=file_ids,
                operator_id=current_user.uid,
            )
        except Exception as e:
            logger.exception(f"Parse task failed: {e}")
            raise

    try:
        database = await knowledge_base.get_database_info(kb_id)
        task = await tasker.enqueue(
            name=f"Document parsing ({database['name']})",
            task_type="knowledge_parse",
            payload={"kb_id": kb_id, "file_ids": file_ids},
            coroutine=run_parse,
        )
        return {"message": "Nhiệm vụ phân tích đã được gửi", "status": "queued", "task_id": task.id}
    except Exception as e:
        return {"message": f"Gửi thất bại: {e}", "status": "failed"}


@knowledge.post("/databases/{kb_id}/documents/parse-pending")
async def parse_pending_documents(kb_id: str, current_user: User = Depends(get_admin_user)):
    """Manually trigger parsing of all documents to be parsed by status."""
    logger.debug(f"Parse pending documents for kb_id {kb_id}")
    await _ensure_database_supports_documents(kb_id, "Document parsing")

    try:
        database = await knowledge_base.get_database_info(kb_id)
        pending_count = int((database.get("stats") or {}).get("pending_parse_count") or 0)
        if pending_count <= 0:
            return {"message": "Không có tài liệu nào chờ phân tích", "status": "success", "queued_count": 0}

        async def run_parse(context: TaskContext):
            try:
                return await _run_parse_pending_statuses(
                    context=context,
                    kb_id=kb_id,
                    statuses=PENDING_PARSE_STATUSES,
                    initial_total=pending_count,
                    operator_id=current_user.uid,
                )
            except Exception as e:
                logger.exception(f"Pending parse task failed: {e}")
                raise

        task, created = await tasker.enqueue_unique_by_payload(
            name=f"Document parsing to be parsed ({database['name']})",
            task_type="knowledge_parse",
            payload={
                "kb_id": kb_id,
                "scope": "pending",
                "action": "parse",
                "statuses": PENDING_PARSE_STATUSES,
                "count": pending_count,
            },
            payload_match={"kb_id": kb_id, "scope": "pending", "action": "parse"},
            statuses=ACTIVE_DOCUMENT_ACTION_TASK_STATUSES,
            coroutine=run_parse,
        )
        return {
            "message": "Nhiệm vụ phân tích đã được gửi" if created else "Đã có nhiệm vụ phân tích đang thực thi",
            "status": "queued",
            "task_id": task.id,
            "queued_count": pending_count,
        }
    except Exception as e:
        return {"message": f"Gửi thất bại: {e}", "status": "failed"}


@knowledge.post("/databases/{kb_id}/documents/index")
async def index_documents(
    kb_id: str,
    file_ids: list[str] = Body(...),
    params: dict | None = Body(None),
    current_user: User = Depends(get_admin_user),
):
    """Manually trigger document warehousing (Indexing) and support updating parameters"""
    file_ids = _validate_direct_document_action_file_ids(file_ids)
    params = params or {}
    logger.debug(f"Index documents for kb_id {kb_id}: {file_ids} {params=}")
    await _ensure_database_supports_documents(kb_id, "Document storage")

    operator_id = current_user.uid

    async def run_index(context: TaskContext):
        try:
            return await _run_index_file_ids(
                context=context,
                kb_id=kb_id,
                file_ids=file_ids,
                operator_id=operator_id,
                params=params,
            )
        except Exception as e:
            logger.exception(f"Index task failed: {e}")
            raise

    try:
        database = await knowledge_base.get_database_info(kb_id)
        task = await tasker.enqueue(
            name=f"Document storage ({database['name']})",
            task_type="knowledge_index",
            payload={"kb_id": kb_id, "file_ids": file_ids, "params": params},
            coroutine=run_index,
        )
        return {"message": "Nhiệm vụ nhập kho đã được gửi", "status": "queued", "task_id": task.id}
    except Exception as e:
        return {"message": f"Gửi thất bại: {e}", "status": "failed"}


@knowledge.post("/databases/{kb_id}/documents/index-pending")
async def index_pending_documents(
    kb_id: str,
    payload: PendingIndexDocumentsRequest | None = None,
    current_user: User = Depends(get_admin_user),
):
    """Manually trigger the storage of all documents to be stored according to status."""
    params = payload.params if payload else None
    params = params or {}
    logger.debug(f"Index pending documents for kb_id {kb_id}: {params=}")
    await _ensure_database_supports_documents(kb_id, "Document storage")

    try:
        database = await knowledge_base.get_database_info(kb_id)
        pending_count = int((database.get("stats") or {}).get("pending_index_count") or 0)
        if pending_count <= 0:
            return {"message": "Không có tài liệu nào chờ nhập kho", "status": "success", "queued_count": 0}

        operator_id = current_user.uid

        async def run_index(context: TaskContext):
            try:
                return await _run_index_pending_statuses(
                    context=context,
                    kb_id=kb_id,
                    statuses=PENDING_INDEX_STATUSES,
                    initial_total=pending_count,
                    operator_id=operator_id,
                    params=params,
                )
            except Exception as e:
                logger.exception(f"Pending index task failed: {e}")
                raise

        task, created = await tasker.enqueue_unique_by_payload(
            name=f"Documents to be stored in the database ({database['name']})",
            task_type="knowledge_index",
            payload={
                "kb_id": kb_id,
                "scope": "pending",
                "action": "index",
                "statuses": PENDING_INDEX_STATUSES,
                "count": pending_count,
                "params": params,
            },
            payload_match={"kb_id": kb_id, "scope": "pending", "action": "index"},
            statuses=ACTIVE_DOCUMENT_ACTION_TASK_STATUSES,
            coroutine=run_index,
        )
        return {
            "message": "Nhiệm vụ nhập kho đã được gửi" if created else "Đã có nhiệm vụ nhập kho đang thực thi",
            "status": "queued",
            "task_id": task.id,
            "queued_count": pending_count,
        }
    except Exception as e:
        return {"message": f"Gửi thất bại: {e}", "status": "failed"}


@knowledge.get("/databases/{kb_id}/documents/{doc_id}")
async def get_document_info(kb_id: str, doc_id: str, current_user: User = Depends(get_admin_user)):
    """Get document details (including basic information and content information)"""
    logger.debug(f"GET document {doc_id} info in {kb_id}")
    await _ensure_database_supports_documents(kb_id, "Document view")

    try:
        info = await knowledge_base.get_file_info(kb_id, doc_id)
        return info
    except Exception as e:
        logger.error(f"Failed to get file info, {e}, {kb_id=}, {doc_id=}, {traceback.format_exc()}")
        return {"message": "Failed to get file info", "status": "failed"}


@knowledge.get("/databases/{kb_id}/documents/{doc_id}/basic")
async def get_document_basic_info(kb_id: str, doc_id: str, current_user: User = Depends(get_admin_user)):
    """Get basic document information (metadata only)"""
    logger.debug(f"GET document {doc_id} basic info in {kb_id}")
    await _ensure_database_supports_documents(kb_id, "Document view")

    try:
        info = await knowledge_base.get_file_basic_info(kb_id, doc_id)
        return info
    except Exception as e:
        logger.error(f"Failed to get file basic info, {e}, {kb_id=}, {doc_id=}, {traceback.format_exc()}")
        return {"message": "Failed to get file basic info", "status": "failed"}


@knowledge.get("/databases/{kb_id}/documents/{doc_id}/content")
async def get_document_content(kb_id: str, doc_id: str, current_user: User = Depends(get_admin_user)):
    """Get document content information (chunks and lines)"""
    logger.debug(f"GET document {doc_id} content in {kb_id}")
    await _ensure_database_supports_documents(kb_id, "Document view")

    try:
        info = await knowledge_base.get_file_content(kb_id, doc_id)
        return info
    except Exception as e:
        logger.error(f"Failed to get file content, {e}, {kb_id=}, {doc_id=}, {traceback.format_exc()}")
        return {"message": "Failed to get file content", "status": "failed"}


@knowledge.delete("/databases/{kb_id}/documents/batch")
async def batch_delete_documents(
    kb_id: str, file_ids: list[str] = Body(...), current_user: User = Depends(get_admin_user)
):
    """Delete documents or folders in batches"""
    logger.debug(f"BATCH DELETE documents {file_ids} in {kb_id}")
    await _ensure_database_supports_documents(kb_id, "Batch document deletion")

    deleted_count = 0
    failed_items = []
    mindmap_removals: list[tuple[str, str]] = []

    for doc_id in file_ids:
        try:
            file_meta_info = await knowledge_base.get_file_basic_info(kb_id, doc_id)

            # Check if it is a folder
            is_folder = file_meta_info.get("meta", {}).get("is_folder", False)
            if is_folder:
                await knowledge_base.delete_folder(kb_id, doc_id)
                deleted_count += 1
                continue

            file_path = file_meta_info.get("meta", {}).get("path", "")

            await _delete_document_storage_objects(kb_id, doc_id, file_path)

            # Collect file names to be cleaned (maps will be cleaned up after the cycle ends)
            removed_filename = file_meta_info.get("meta", {}).get("filename", "")
            if removed_filename:
                mindmap_removals.append((doc_id, removed_filename))

            # Regardless of whether the MinIO deletion is successful or not, it will continue to be deleted from the knowledge base.
            await knowledge_base.delete_file(kb_id, doc_id)
            deleted_count += 1
        except Exception as e:
            logger.error(f"Create department {doc_id} fail: {e}, {traceback.format_exc()}")
            failed_items.append({"doc_id": doc_id, "error": str(e)})

    if failed_items:
        if deleted_count == 0:
            raise HTTPException(status_code=400, detail=f"Xóa hàng loạt thất bại: Tất cả {len(failed_items)} tệp đều chưa được xóa.")
        return {
            "message": f"Xóa thành công một phần: Đã xóa {deleted_count} tệp, thất bại {len(failed_items)} tệp",
            "deleted_count": deleted_count,
            "failed_items": failed_items,
        }

    return {"message": f"Xóa hàng loạt thành công: Đã xóa {deleted_count} tệp", "deleted_count": deleted_count}


@knowledge.delete("/databases/{kb_id}/documents/{doc_id}")
async def delete_document(kb_id: str, doc_id: str, current_user: User = Depends(get_admin_user)):
    """Delete a document or folder"""
    logger.debug(f"DELETE document {doc_id} info in {kb_id}")
    await _ensure_database_supports_documents(kb_id, "Document deletion")
    try:
        file_meta_info = await knowledge_base.get_file_basic_info(kb_id, doc_id)

        # Check if it is a folder
        is_folder = file_meta_info.get("meta", {}).get("is_folder", False)
        if is_folder:
            await knowledge_base.delete_folder(kb_id, doc_id)
            return {"message": "Xóa thư mục thành công"}

        file_path = file_meta_info.get("meta", {}).get("path", "")

        await _delete_document_storage_objects(kb_id, doc_id, file_path)

        # Regardless of whether the MinIO deletion is successful or not, it will continue to be deleted from the knowledge base.
        await knowledge_base.delete_file(kb_id, doc_id)
        return {"message": "Xóa thành công"}
    except Exception as e:
        logger.error(f"Failed to delete document {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=f"Xóa tài liệu thất bại: {e}")


@knowledge.get("/databases/{kb_id}/documents/{doc_id}/download")
async def download_document(kb_id: str, doc_id: str, current_user: User = Depends(get_admin_user)):
    """Download original file"""
    logger.debug(f"Download document {doc_id} from {kb_id}")
    await _ensure_database_supports_documents(kb_id, "Document download")
    try:
        file_info = await knowledge_base.get_file_basic_info(kb_id, doc_id)
        file_meta = file_info.get("meta", {})

        # Get file type, path and file name
        file_type = file_meta.get("file_type", "file")
        file_path = file_meta.get("path", "")
        filename = file_meta.get("filename", "file")

        # There is no original file for URL type file to download
        if file_type == "url":
            raise HTTPException(status_code=400, detail="Tệp loại URL không hỗ trợ tải xuống tệp gốc")
        logger.debug(f"File path from database: {file_path}")
        logger.debug(f"Original filename from database: {filename}")

        # Decode URL-encoded filenames (if any)
        try:
            decoded_filename = unquote(filename, encoding="utf-8")
            logger.debug(f"Decoded filename: {decoded_filename}")
        except Exception as e:
            logger.debug(f"Failed to decode filename {filename}: {e}")
            decoded_filename = filename  # If decoding fails, use the original file name

        _, ext = os.path.splitext(decoded_filename)
        media_type = media_types.get(ext.lower(), "application/octet-stream")

        if not is_minio_url(file_path):
            raise HTTPException(status_code=400, detail="Đường dẫn tệp phải là URL MinIO")

        logger.debug(f"Downloading from MinIO: {file_path}")

        try:
            bucket_name, object_name = parse_minio_url(file_path)
            logger.debug(f"Parsed bucket_name: {bucket_name}, object_name: {object_name}")

            minio_client = get_minio_client()

            # Download directly using the resolved full object name
            minio_response = await minio_client.adownload_response(
                bucket_name=bucket_name,
                object_name=object_name,
            )
            logger.debug(f"Successfully downloaded object: {object_name}")

        except Exception as e:
            logger.error(f"Failed to download MinIO file: {e}")
            raise StorageError(f"Tải xuống tệp thất bại: {e}")

        # Create a streaming generator
        async def minio_stream():
            try:
                while True:
                    chunk = await asyncio.to_thread(minio_response.read, 8192)
                    if not chunk:
                        break
                    yield chunk
            finally:
                minio_response.close()
                minio_response.release_conn()

        response = StreamingResponse(
            minio_stream(),
            media_type=media_type,
        )
        try:
            decoded_filename.encode("ascii")
            response.headers["Content-Disposition"] = f'attachment; filename="{decoded_filename}"'
        except UnicodeEncodeError:
            encoded_filename = quote(decoded_filename.encode("utf-8"))
            response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{encoded_filename}"

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download file failed: {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Tải xuống thất bại: {e}")


# =============================================================================
# === Knowledge base query grouping ===
# =============================================================================


@knowledge.post("/databases/{kb_id}/query")
async def query_knowledge_base(
    kb_id: str, query: str = Body(...), meta: dict = Body(...), current_user: User = Depends(get_admin_user)
):
    """Query knowledge base"""
    logger.debug(f"Query knowledge base {kb_id}: {query}")
    try:
        result = await knowledge_base.aquery(query, kb_id=kb_id, **meta)
        return {"result": result, "status": "success"}
    except Exception as e:
        logger.error(f"Knowledge base query failed {e}, {traceback.format_exc()}")
        return {"message": f"Truy vấn kho kiến thức thất bại: {e}", "status": "failed"}


@knowledge.post("/databases/{kb_id}/query-test")
async def query_test(
    kb_id: str, query: str = Body(...), meta: dict = Body(...), current_user: User = Depends(get_admin_user)
):
    """Test query knowledge base"""
    logger.debug(f"Query test in {kb_id}: {query}")
    try:
        result = await knowledge_base.aquery(query, kb_id=kb_id, **meta)
        return result
    except Exception as e:
        logger.error(f"Test query failed {e}, {traceback.format_exc()}")
        return {"message": f"Truy vấn thử nghiệm thất bại: {e}", "status": "failed"}


@knowledge.put("/databases/{kb_id}/query-params")
async def update_knowledge_base_query_params(
    kb_id: str, params: dict = Body(...), current_user: User = Depends(get_admin_user)
):
    """Update knowledge base query parameter configuration"""
    try:
        # Get knowledge base instance
        kb_instance = await knowledge_base._get_kb_for_database(kb_id)
        if not kb_instance:
            raise HTTPException(status_code=404, detail="Knowledge base not found")

        # Update query parameters in instance metadata
        async with knowledge_base._metadata_lock:
            # Make sure the kb_id is in the instance's databases_meta
            if kb_id not in kb_instance.databases_meta:
                raise HTTPException(status_code=404, detail="Database not found in instance metadata")

            # Make sure query_params is not None
            if kb_instance.databases_meta[kb_id].get("query_params") is None:
                kb_instance.databases_meta[kb_id]["query_params"] = {}

            options = kb_instance.databases_meta[kb_id]["query_params"].setdefault("options", {})
            options.update(params)
            updated_query_params = kb_instance.databases_meta[kb_id]["query_params"]

        # Update a single record directly through the Repository, avoiding calling _save_metadata() to traverse all databases and files
        from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository

        kb_repo = KnowledgeBaseRepository()
        await kb_repo.update(kb_id, {"query_params": updated_query_params})

        logger.info(f"Update knowledge base {kb_id} query parameters: {params}")

        return {"message": "success", "data": params}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update knowledge base query parameters: {e}")
        raise HTTPException(status_code=500, detail=f"Cập nhật tham số truy vấn thất bại: {str(e)}")


@knowledge.get("/databases/{kb_id}/query-params")
async def get_knowledge_base_query_params(kb_id: str, current_user: User = Depends(get_admin_user)):
    """Get knowledge base type specific query parameters"""
    try:
        # Get knowledge base instance
        kb_instance = await knowledge_base._get_kb_for_database(kb_id)

        # Call the method of the knowledge base instance to obtain the configuration
        params = kb_instance.get_query_params_config(kb_id=kb_id)

        # Get user-saved configurations and merge (read from instance metadata)
        saved_options = kb_instance._get_query_params(kb_id)
        if saved_options:
            params = _merge_saved_options(params, saved_options)

        return {"params": params, "message": "success"}

    except Exception as e:
        logger.error(f"Failed to obtain knowledge base query parameters {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


def _merge_saved_options(params: dict, saved_options: dict) -> dict:
    """Merge user saved configuration into default configuration"""
    for option in params.get("options", []):
        key = option.get("key")
        if key in saved_options:
            option["default"] = saved_options[key]
    return params


# =============================================================================
# === AI generated sample questions ===
# =============================================================================


@knowledge.post("/databases/{kb_id}/sample-questions")
async def generate_sample_questions(
    kb_id: str,
    request_body: dict = Body(...),
    current_user: User = Depends(get_admin_user),
):
    """AI generates test questions against the knowledge base."""
    try:
        count = request_body.get("count", 10)
        return await generate_database_sample_questions(kb_id, count=count)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate knowledge base questions: {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Tạo câu hỏi thất bại: {str(e)}")


@knowledge.get("/databases/{kb_id}/sample-questions")
async def get_sample_questions(kb_id: str, current_user: User = Depends(get_admin_user)):
    """Get test questions from the knowledge base."""
    try:
        return await get_database_sample_questions(kb_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get knowledge base questions: {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Lấy câu hỏi thất bại: {str(e)}")


# =============================================================================
# === File management group ===
# =============================================================================


@knowledge.post("/databases/{kb_id}/folders")
async def create_folder(
    kb_id: str,
    folder_name: str = Body(..., embed=True),
    parent_id: str | None = Body(None, embed=True),
    current_user: User = Depends(get_admin_user),
):
    """Create folder"""
    try:
        await _ensure_database_supports_documents(kb_id, "Folder creation")
        return await knowledge_base.create_folder(kb_id, folder_name, parent_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create folder {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@knowledge.put("/databases/{kb_id}/documents/{doc_id}/move")
async def move_document(
    kb_id: str,
    doc_id: str,
    new_parent_id: str | None = Body(..., embed=True),
    current_user: User = Depends(get_admin_user),
):
    """Move a file or folder"""
    logger.debug(f"Move document {doc_id} to {new_parent_id} in {kb_id}")
    try:
        await _ensure_database_supports_documents(kb_id, "File movement")
        return await knowledge_base.move_file(kb_id, doc_id, new_parent_id)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to move file {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@knowledge.post("/files/fetch-url")
async def fetch_url(
    url: str = Body(..., embed=True),
    kb_id: str | None = Body(None, embed=True),
    current_user: User = Depends(get_admin_user),
):
    """
    Crawl URL content and upload to MinIO
    """
    logger.debug(f"Fetching URL: {url} for kb_id: {kb_id}")
    try:
        # 1. Download content (including whitelist verification, size limit, type check)
        content_bytes, final_url = await fetch_url_content(url)

        # 2. Calculate Hash
        content_hash = await calculate_content_hash(content_bytes)

        # Check if a file with the same content already exists
        if kb_id:
            file_exists = await knowledge_base.file_existed_in_db(kb_id, content_hash)
            if file_exists:
                raise HTTPException(
                    status_code=409,
                    detail="Cơ sở dữ liệu đã tồn tại tệp có cùng nội dung",
                )

        # 3. Upload to MinIO
        minio_client = get_minio_client()
        bucket_name = MinIOClient.KB_BUCKETS["documents"]
        await asyncio.to_thread(minio_client.ensure_bucket_exists, bucket_name)

        folder = kb_id if kb_id else "unknown"
        object_name = f"{folder}/upload/{content_hash}.html"

        upload_result = await minio_client.aupload_file(
            bucket_name=bucket_name,
            object_name=object_name,
            data=content_bytes,
            content_type="text/html",
        )

        # Detect files with the same name (URL is the file name)
        same_name_files = []
        has_same_name = False
        if kb_id:
            same_name_files = await knowledge_base.get_same_name_files(kb_id, url)
            has_same_name = len(same_name_files) > 0

        return {
            "status": "success",
            "file_path": upload_result.url,
            "minio_url": upload_result.url,
            "content_hash": content_hash,
            "filename": url,  # Original URL as file name
            "final_url": final_url,
            "size": len(content_bytes),
            "has_same_name": has_same_name,
            "same_name_files": same_name_files,
        }

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"URL fetch validation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to fetch URL {url}: {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch URL: {str(e)}")


@knowledge.post("/files/import-workspace")
async def import_workspace_files(
    payload: WorkspaceImportRequest,
    current_user: User = Depends(get_admin_user),
):
    """Import the current user workspace file into MinIO and return preprocessing results consistent with ordinary file upload."""
    kb_id = payload.kb_id.strip()
    paths = [path for path in payload.paths if str(path or "").strip()]
    if not kb_id:
        raise HTTPException(status_code=400, detail="kb_id is required")
    if not paths:
        raise HTTPException(status_code=400, detail="Vui lòng chọn ít nhất một tệp làm việc")

    await _ensure_database_supports_documents(kb_id, "Documentation added/parse/Warehouse")

    bucket_name = MinIOClient.KB_BUCKETS["documents"]
    results = []
    for workspace_path in paths:
        target = resolve_workspace_file_path(path=workspace_path, current_user=current_user)

        filename = target.name
        ext = os.path.splitext(filename)[1].lower()
        if not is_supported_file_extension(filename):
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

        size = target.stat().st_size
        if size > MAX_WORKSPACE_UPLOAD_SIZE_BYTES:
            raise HTTPException(status_code=400, detail="Tệp quá lớn, hiện tại chỉ hỗ trợ tệp làm việc dưới 100 MB")

        file_bytes = await asyncio.to_thread(target.read_bytes)
        content_hash = await calculate_content_hash(file_bytes)

        file_exists = await knowledge_base.file_existed_in_db(kb_id, content_hash)
        if file_exists:
            raise HTTPException(status_code=409, detail=f"Cơ sở dữ liệu đã tồn tại tệp có cùng nội dung: {filename}")

        basename, ext = os.path.splitext(filename)
        timestamp = int(time.time() * 1000)
        minio_filename = f"{basename}_{timestamp}{ext}"
        object_name = f"{kb_id}/upload/{minio_filename}"
        minio_url = await aupload_file_to_minio(bucket_name, object_name, file_bytes)

        normalized_filename = filename.lower()
        same_name_files = await knowledge_base.get_same_name_files(kb_id, normalized_filename)
        results.append(
            {
                "message": "Workspace file successfully imported",
                "file_path": minio_url,
                "minio_path": minio_url,
                "kb_id": kb_id,
                "content_hash": content_hash,
                "filename": normalized_filename,
                "original_filename": basename,
                "size": len(file_bytes),
                "minio_filename": minio_filename,
                "object_name": object_name,
                "bucket_name": bucket_name,
                "workspace_path": workspace_path,
                "same_name_files": same_name_files,
                "has_same_name": len(same_name_files) > 0,
            }
        )

    return {"status": "success", "items": results}


@knowledge.post("/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    kb_id: str | None = Query(None),
    current_user: User = Depends(get_admin_user),
):
    """Upload files"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No selected file")

    if kb_id:
        await _ensure_database_supports_documents(kb_id, "Document upload")

    logger.debug(f"Received upload file with filename: {file.filename}")

    ext = os.path.splitext(file.filename)[1].lower()

    if not is_supported_file_extension(file.filename):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    basename, ext = os.path.splitext(file.filename)
    # Use the original filename directly (lowercase)
    filename = f"{basename}{ext}".lower()

    try:
        file_bytes = await read_upload_with_limit(
            file,
            max_size_bytes=MAX_UPLOAD_SIZE_BYTES,
            too_large_message="Tệp quá lớn, hiện tại chỉ hỗ trợ tệp dưới 100 MB",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    content_hash = await calculate_content_hash(file_bytes)

    file_exists = await knowledge_base.file_existed_in_db(kb_id, content_hash)
    if file_exists:
        raise HTTPException(
            status_code=409,
            detail="Cơ sở dữ liệu đã tồn tại tệp có cùng nội dung",
        )

    # Upload directly to MinIO, add timestamp to distinguish versions
    timestamp = int(time.time() * 1000)
    minio_filename = f"{basename}_{timestamp}{ext}"

    bucket_name = MinIOClient.KB_BUCKETS["documents"]
    folder = kb_id if kb_id else "unknown"
    object_name = f"{folder}/upload/{minio_filename}"

    # Upload to MinIO
    minio_url = await aupload_file_to_minio(bucket_name, object_name, file_bytes)

    # Detect files with the same name (based on original file name)
    same_name_files = await knowledge_base.get_same_name_files(kb_id, filename)
    has_same_name = len(same_name_files) > 0

    return {
        "message": "File successfully uploaded",
        "file_path": minio_url,  # MinIO path as primary path
        "minio_path": minio_url,  # MiniIO path
        "kb_id": kb_id,
        "content_hash": content_hash,
        "filename": filename,  # Original file name (lowercase)
        "original_filename": basename,  # Original file name (remove suffix)
        "size": len(file_bytes),
        "minio_filename": minio_filename,  # Filename in MinIO (with timestamp)
        "object_name": object_name,
        "bucket_name": bucket_name,  # MinIO bucket name
        "same_name_files": same_name_files,  # List of files with the same name
        "has_same_name": has_same_name,  # Whether to include the file flag with the same name
    }


@knowledge.get("/files/supported-types")
async def get_supported_file_types(current_user: User = Depends(get_admin_user)):
    """Get currently supported file types"""
    return {"message": "success", "file_types": sorted(SUPPORTED_FILE_EXTENSIONS)}


@knowledge.post("/files/markdown")
async def mark_it_down(file: UploadFile = File(...), current_user: User = Depends(get_admin_user)):
    """Call unified Parser to parse the file into markdown, which requires administrator rights."""
    import tempfile

    if not file.filename:
        return {"message": "Phân tích tệp thất bại: Không thể nhận dạng tên tệp", "markdown_content": ""}

    suffix = os.path.splitext(file.filename)[1].lower()
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = temp_file.name

        await write_upload_to_path(
            file,
            temp_path,
            max_size_bytes=MAX_UPLOAD_SIZE_BYTES,
            too_large_message="Tệp quá lớn, hiện tại chỉ hỗ trợ tệp dưới 100 MB",
        )

        markdown_content = await Parser.aparse(temp_path)
        return {"markdown_content": markdown_content, "message": "success"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"File parsing failed {e}, {traceback.format_exc()}")
        return {"message": f"Phân tích tệp thất bại {e}", "markdown_content": ""}
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception as cleanup_error:
                logger.warning(f"Temporary file cleanup failed {temp_path}: {cleanup_error}")


# =============================================================================
# === Knowledge base type grouping ===
# =============================================================================


@knowledge.get("/types")
async def get_knowledge_base_types(current_user: User = Depends(get_admin_user)):
    """Get supported knowledge base types"""
    try:
        kb_types = knowledge_base.get_supported_kb_types()
        return {"kb_types": kb_types, "message": "success"}
    except Exception as e:
        logger.error(f"Failed to obtain knowledge base type {e}, {traceback.format_exc()}")
        return {"message": f"Lấy loại kho kiến thức thất bại {e}", "kb_types": {}}


@knowledge.get("/stats")
async def get_knowledge_base_statistics(current_user: User = Depends(get_admin_user)):
    """Get knowledge base statistics"""
    try:
        stats = await knowledge_base.get_statistics()
        return {"stats": stats, "message": "success"}
    except Exception as e:
        logger.error(f"Failed to obtain knowledge base statistics {e}, {traceback.format_exc()}")
        return {"message": f"Lấy thống kê kho kiến thức thất bại {e}", "stats": {}}


# =============================================================================
# === Knowledge Base AI Accessibility Grouping ===
# =============================================================================


@knowledge.post("/generate-description")
async def generate_description(
    name: str = Body(..., description="Tên kho kiến thức"),
    current_description: str = Body("", description="Mô tả hiện tại (tùy chọn, dùng để tối ưu hóa)"),
    file_list: list[str] | None = Body(None, description="Danh sách tệp"),
    current_user: User = Depends(get_admin_user),
):
    """Use LLM generator to optimize knowledge basedescribe

    According to the Knowledge base name and existing describe, Use LLM generate is suitable as the agent tooldescribeofcontent.
    """
    from yuxi.models import select_model

    file_list = file_list or []
    logger.debug(f"Generating description for knowledge base: {name}, files: {len(file_list)}")

    # Build file list text
    if file_list:
        # Limit the number of files to avoid too long prompts
        display_files = file_list[:50]
        files_str = "\n".join([f"- {f}" for f in display_files])
        more_text = f"\n... (besides {len(file_list) - 50} files)" if len(file_list) > 50 else ""
        current_description += f"\n\nFiles included in the knowledge base:\n{files_str}{more_text}"

    current_description = current_description or "No description yet"

    # Build prompt words
    prompt = textwrap.dedent(f"""
        Giúp tôi tối ưu hóa mô tả cho kho kiến thức sau.

        Tên kho kiến thức: {name}
        Mô tả hiện tại: {current_description}

        Yêu cầu:
        1. Mô tả này sẽ được sử dụng làm mô tả công cụ cho agent
        2. Agent sẽ chọn công cụ phù hợp dựa trên tiêu đề và mô tả của kho kiến thức
        3. Do đó, mô tả cần rõ ràng, cụ thể, giải thích những nội dung gì có trong kho kiến thức và loại câu hỏi nào nó phù hợp để trả lời
        4. Mô tả nên ngắn gọn và súc tích, thông thường chỉ cần 2-4 câu
        5. Không sử dụng định dạng Markdown
        {"6. Vui lòng tham khảo danh sách tệp được cung cấp để tóm tắt chính xác nội dung kho kiến thức" if file_list else ""}

        Vui lòng xuất trực tiếp mô tả đã tối ưu hóa, không kèm theo bất kỳ văn bản giải thích nào khác.
    """).strip()

    try:
        model = select_model(model_spec=config.default_model)
        response = await model.call(prompt)
        description = response.content.strip()
        logger.debug(f"Generated description: {description}")
        return {"description": description, "status": "success"}
    except Exception as e:
        logger.error(f"Tạo mô tả thất bại: {e}, {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Tạo mô tả thất bại: {e}")
