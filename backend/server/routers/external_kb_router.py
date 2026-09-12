from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from yuxi.knowledge.runtime import knowledge_base
from yuxi.knowledge.base import KBNotFoundError
from yuxi.knowledge.read_models import KnowledgeBaseSummary
from yuxi.storage.postgres.models_business import User
from yuxi.utils import logger

from server.utils.auth_middleware import get_required_user

external_kb = APIRouter(prefix="/knowledge", tags=["knowledge"])


class ExternalRetrieveRequest(BaseModel):
    query: str
    file_name: str | None = None
    options: dict | None = None


class ExternalFindRequest(BaseModel):
    patterns: list[str]
    use_regex: bool = False
    case_sensitive: bool = False
    max_windows: int = 5
    window_size: int = 80


@external_kb.get("/databases/external")
async def list_external_databases(current_user: User = Depends(get_required_user)):
    """List knowledge bases visible to current user for CLI selection."""
    databases = await knowledge_base.get_databases_by_uid(current_user.uid)
    items = []
    for db in databases:
        kb_type = db.kb_type.lower()
        items.append(
            {
                "kb_id": db.kb_id,
                "name": db.name,
                "description": db.description or "",
                "kb_type": kb_type,
                "supports_documents": knowledge_base.database_type_supports_documents(kb_type),
            }
        )
    return {"databases": items}


@external_kb.get("/databases/external/{kb_id}/files")
async def list_external_files(
    kb_id: str,
    query: str | None = Query(None, description="Search by filename keyword"),
    offset: int = Query(0, ge=0, description="Offset, starting from 0"),
    limit: int = Query(100, ge=1, le=500, description="Number of items per page"),
    status: str = Query("all", description="File status filter"),
    current_user: User = Depends(get_required_user),
):
    """List or search knowledge base files for CLI browsing and location."""
    database = await knowledge_base.get_accessible_database_info_by_uid(current_user.uid, kb_id)
    if not database:
        raise HTTPException(status_code=404, detail=f"Knowledge base {kb_id} does not exist or access denied")
    if not knowledge_base.database_type_supports_documents(database.kb_type):
        raise HTTPException(
            status_code=400,
            detail=f"{database.name or database.kb_type} only supports retrieval, not document viewing",
        )
    return await knowledge_base.search_document_files(
        [{"kb_id": database.kb_id, "name": database.name}],
        query=query,
        offset=offset,
        limit=limit,
        status=status,
        include_is_folder=True,
        include_parent_id=True,
    )


@external_kb.post("/databases/external/{kb_id}/retrieve")
async def retrieve_external(
    kb_id: str,
    payload: ExternalRetrieveRequest,
    current_user: User = Depends(get_required_user),
):
    """Execute retrieval query on knowledge base and return structured results."""
    if not payload.query:
        raise HTTPException(status_code=400, detail="query is required")
    await _require_accessible_kb(kb_id, current_user.uid)
    options = dict(payload.options or {})
    if payload.file_name:
        options["file_name"] = payload.file_name
    try:
        return await knowledge_base.retrieve(kb_id, payload.query, **options)
    except KBNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.exception(f"external knowledge base query failed: {e}")
        raise HTTPException(status_code=400, detail=f"Knowledge base query failed: {e}") from e


@external_kb.get("/databases/external/{kb_id}/files/{file_id}/open")
async def open_external_file(
    kb_id: str,
    file_id: str,
    offset: int = Query(0, ge=0, description="Starting line offset"),
    limit: int = Query(200, ge=1, le=1800, description="Number of lines to return"),
    current_user: User = Depends(get_required_user),
):
    """Open parsed Markdown content of file with line window."""
    await _require_accessible_kb(kb_id, current_user.uid, require_documents=True, operation="document viewing")
    try:
        return await knowledge_base.open_document(kb_id, file_id, offset=offset, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception(f"external failed to open knowledge base file: {e}")
        raise HTTPException(status_code=400, detail="Failed to open knowledge base file") from e


@external_kb.post("/databases/external/{kb_id}/files/{file_id}/find")
async def find_external_file(
    kb_id: str,
    file_id: str,
    payload: ExternalFindRequest,
    current_user: User = Depends(get_required_user),
):
    """Locate keywords or regex patterns in specified file, returning matched windows."""
    await _require_accessible_kb(kb_id, current_user.uid, require_documents=True, operation="document search")
    if not payload.patterns:
        raise HTTPException(status_code=400, detail="patterns cannot be empty")
    try:
        return await knowledge_base.find_in_document(
            kb_id,
            file_id,
            payload.patterns,
            use_regex=payload.use_regex,
            case_sensitive=payload.case_sensitive,
            max_windows=payload.max_windows,
            window_size=payload.window_size,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception(f"external in-file search failed: {e}")
        raise HTTPException(status_code=400, detail="Knowledge base in-file search failed") from e


async def _require_accessible_kb(
    kb_id: str,
    uid: str,
    *,
    require_documents: bool = False,
    operation: str = "document viewing",
) -> KnowledgeBaseSummary:
    """Validate that knowledge base is visible to uid, checking document capability if required."""
    database = await knowledge_base.get_accessible_database_info_by_uid(uid, str(kb_id or "").strip())
    if not database:
        raise HTTPException(status_code=404, detail=f"Knowledge base {kb_id} does not exist or access denied")
    if require_documents and not knowledge_base.database_type_supports_documents(database.kb_type):
        kb_type = database.kb_type.lower()
        raise HTTPException(status_code=400, detail=f"{database.name or kb_type} only supports retrieval, not {operation}")
    return database
