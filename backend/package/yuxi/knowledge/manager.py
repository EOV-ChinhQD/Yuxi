import asyncio
import os

from yuxi.knowledge.base import KBNotFoundError, KnowledgeBase
from yuxi.knowledge.chunking.ragflow_like.presets import deep_merge
from yuxi.knowledge.factory import KnowledgeBaseFactory
from yuxi.storage.postgres.models_business import User
from yuxi.utils import logger
from yuxi.utils.datetime_utils import utc_isoformat
from yuxi.utils.share_config import SHARE_ACCESS_LEVELS, normalize_share_config

DEFAULT_SHARE_CONFIG = {"access_level": "global", "department_ids": [], "user_uids": []}
ACCESS_LEVELS = SHARE_ACCESS_LEVELS


class KnowledgeBaseManager:
    """
    knowledge base manager

    Manage multiple types of Knowledge Base Example in one unified way, access askdatabase directly through Repository, and do not maintain redundant caches.
    """

    def __init__(self, work_dir: str):
        """
        Initialize the knowledge base manager

        Args:
            work_dir: working directory
        """
        self.work_dir = work_dir
        os.makedirs(work_dir, exist_ok=True)

        # Knowledge base instance cache {kb_type: kb_instance}
        self.kb_instances: dict[str, KnowledgeBase] = {}

        # metadata lock
        self._metadata_lock = asyncio.Lock()

    async def initialize(self):
        """Asynchronous initialization"""
        # Initialize an existing knowledge base instance
        self._initialize_existing_kbs()
        logger.info("KnowledgeBaseManager initialized")

    def _initialize_existing_kbs(self):
        """Initialize an existing knowledge base instance"""
        from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository

        async def _async_init():
            kb_repo = KnowledgeBaseRepository()
            rows = await kb_repo.get_all()

            kb_types_in_use = set()
            for row in rows:
                kb_type = row.kb_type or "milvus"
                if KnowledgeBaseFactory.is_type_supported(kb_type):
                    kb_types_in_use.add(kb_type)
                else:
                    logger.warning(f"Skip unsupported knowledge base type during initialization: {kb_type}")

            logger.info(f"[InitializeKB] Discover {len(kb_types_in_use)} knowledge base type: {kb_types_in_use}")

            # Create instances and load metadata for each knowledge base type in use
            for kb_type in kb_types_in_use:
                if not KnowledgeBaseFactory.is_type_supported(kb_type):
                    logger.warning(f"[InitializeKB] Skip initialization for unsupported knowledge base type: {kb_type}")
                    continue
                try:
                    kb_instance = self._get_or_create_kb_instance(kb_type)
                    # Let the KB instance load metadata on its own
                    await kb_instance._load_metadata()
                    logger.info(f"[InitializeKB] {kb_type} Instance is initialized")
                except Exception as e:
                    logger.error(f"Failed to initialize {kb_type} knowledge base: {e}")
                    import traceback

                    logger.error(traceback.format_exc())

        # Run asynchronous initialization in event loop
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_async_init())
        except RuntimeError:
            asyncio.run(_async_init())

    def _get_or_create_kb_instance(self, kb_type: str) -> KnowledgeBase:
        """
        Get orCreate a knowledge base instance

        Args:
            kb_type: Knowledge base type

        Returns:
            Knowledge Base Example
        """
        if kb_type in self.kb_instances:
            return self.kb_instances[kb_type]

        # Create a new knowledge base instance
        kb_work_dir = os.path.join(self.work_dir, f"{kb_type}_data")
        kb_instance = KnowledgeBaseFactory.create(kb_type, kb_work_dir)

        self.kb_instances[kb_type] = kb_instance
        logger.info(f"Created {kb_type} knowledge base instance")
        return kb_instance

    async def move_file(self, kb_id: str, file_id: str, new_parent_id: str | None) -> dict:
        """
        Move files/folder
        """
        kb_instance = await self._get_kb_for_database(kb_id)
        return await kb_instance.move_file(kb_id, file_id, new_parent_id)

    async def _get_kb_for_database(self, kb_id: str) -> KnowledgeBase:
        """
        Get the corresponding ofKnowledge Base Example according to the Database ID

        Args:
            kb_id: Database ID

        Returns:
            Knowledge Base Example

        Raises:
            KBNotFoundError: The database does not exist or the knowledge base type is not supported
        """
        from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository

        kb_repo = KnowledgeBaseRepository()
        kb = await kb_repo.get_by_kb_id(kb_id)

        if kb is None:
            raise KBNotFoundError(f"Database {kb_id} not found")

        kb_type = kb.kb_type or "milvus"

        if not KnowledgeBaseFactory.is_type_supported(kb_type):
            raise KBNotFoundError(f"Unsupported knowledge base type: {kb_type}")

        return self._get_or_create_kb_instance(kb_type)

    # =============================================================================
    # unified external interface
    # =============================================================================

    async def aget_kb(self, kb_id: str) -> KnowledgeBase:
        """Asynchronous Get knowledge base instance

        Args:
            kb_id: Database ID

        Returns:
            Knowledge Base Example
        """
        return await self._get_kb_for_database(kb_id)

    def _normalize_share_config(
        self,
        share_config: dict | None,
        *,
        user_uid: str | None = None,
        department_id: int | str | None = None,
    ) -> dict:
        return normalize_share_config(
            share_config,
            default_config=DEFAULT_SHARE_CONFIG,
            default_access_level="global",
            invalid_access_level_message="Cấp quyền kho kiến thức không hợp lệ",
            user_uid=user_uid,
            department_id=department_id,
        )

    async def get_databases(self) -> dict:
        """Get all database information"""
        from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository

        kb_repo = KnowledgeBaseRepository()
        rows = await kb_repo.get_all()
        all_databases = []
        metadata_reloaded_types: set[str] = set()
        for row in rows:
            kb_type = row.kb_type or "milvus"
            if not KnowledgeBaseFactory.is_type_supported(kb_type):
                logger.warning(f"Skip unsupported database: kb_id={row.kb_id}, kb_type={kb_type}")
                continue
            kb_instance = self._get_or_create_kb_instance(kb_type)
            db_info = kb_instance.get_database_info(row.kb_id, include_files=False)
            if not db_info and kb_type not in metadata_reloaded_types:
                try:
                    await kb_instance._load_metadata()
                    metadata_reloaded_types.add(kb_type)
                except Exception as e:
                    logger.warning(f"Failed to reload metadata for kb_type={kb_type}: {e}")
                db_info = kb_instance.get_database_info(row.kb_id, include_files=False)

            if not db_info:
                logger.warning(f"Skip database due to missing metadata: kb_id={row.kb_id}, kb_type={kb_type}")
                continue

            # Supplementary share_config and additional_params
            db_info["share_config"] = row.share_config or DEFAULT_SHARE_CONFIG.copy()
            db_info["additional_params"] = kb_instance.normalize_additional_params(row.additional_params)
            db_info["created_by"] = row.created_by
            all_databases.append(db_info)
        return {"databases": all_databases}

    @staticmethod
    def _database_info_accessible(user: dict, db_info: dict) -> bool:
        if user.get("role") == "superadmin":
            return True

        user_uid = str(user.get("uid") or "")
        if user_uid and db_info.get("created_by") == user_uid:
            return True

        share_config = db_info.get("share_config") or DEFAULT_SHARE_CONFIG.copy()
        access_level = share_config.get("access_level")
        if access_level == "global":
            return True

        if access_level == "department":
            user_department_id = user.get("department_id")
            if user_department_id is None:
                return False
            try:
                department_ids = [int(dept_id) for dept_id in share_config.get("department_ids") or []]
                return int(user_department_id) in department_ids
            except (ValueError, TypeError):
                return False

        if access_level == "user":
            return bool(user_uid and user_uid in (share_config.get("user_uids") or []))

        return False

    async def check_accessible(self, user: dict, kb_id: str) -> bool:
        """examineuserDo you have permission?Access askdatabase

        Args:
            user: user information dictionary
            kb_id: Database ID

        Returns:
            bool: Do you have permission?
        """
        # Super administrator has access to all
        if user.get("role") == "superadmin":
            return True

        from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository

        kb_repo = KnowledgeBaseRepository()
        kb = await kb_repo.get_by_kb_id(kb_id)
        if kb is None:
            return False

        return self._database_info_accessible(
            user,
            {
                "created_by": kb.created_by,
                "share_config": kb.share_config,
            },
        )

    async def get_databases_by_uid(self, uid: str) -> dict:
        """Get the knowledge base list based on uid"""
        from yuxi.repositories.user_repository import UserRepository

        # Get user information from database
        user_repo = UserRepository()
        user: User | None = await user_repo.get_by_uid(uid)
        if not user:
            logger.warning(f"User not found: {uid}")
            return {"databases": []}
        return await self.get_databases_by_user(user)

    async def get_databases_by_user(self, user: User | dict) -> dict:
        """Get the knowledge base list based on user permissions"""

        # Build user information dictionary (supports User object or dict)
        if isinstance(user, dict):
            user_info = user
        else:
            user_info = {
                "uid": user.uid,
                "role": user.role,
                "department_id": user.department_id,
            }

        user_role = user_info.get("role")
        user_dept = user_info.get("department_id")
        logger.info(f"Getting databases for user with role {user_role} and department {user_dept}")

        all_databases = (await self.get_databases()).get("databases", [])

        # Super administrators can see all knowledge bases
        if user_info.get("role") == "superadmin":
            return {"databases": all_databases}

        filtered_databases = [
            database for database in all_databases if self._database_info_accessible(user_info, database)
        ]

        return {"databases": filtered_databases}

    async def database_name_exists(self, database_name: str) -> bool:
        """Check if the knowledge base name already exists"""
        from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository
        from yuxi.storage.postgres.manager import pg_manager

        # Make sure pg_manager is initialized
        if not pg_manager._initialized:
            pg_manager.initialize()

        kb_repo = KnowledgeBaseRepository()
        rows = await kb_repo.get_all()
        for row in rows:
            if (row.name or "").lower() == database_name.lower():
                return True
        return False

    async def create_folder(self, kb_id: str, folder_name: str, parent_id: str = None) -> dict:
        """Create a folder in the database."""
        kb_instance = await self._get_kb_for_database(kb_id)
        return await kb_instance.create_folder(kb_id, folder_name, parent_id)

    async def create_database(
        self,
        database_name: str,
        description: str,
        kb_type: str = "milvus",
        embedding_model_spec: str | None = None,
        llm_model_spec: str | None = None,
        share_config: dict | None = None,
        created_by: str | None = None,
        created_by_department_id: int | str | None = None,
        **kwargs,
    ) -> dict:
        """
        create database

        Args:
            database_name: database name
            description: databasedescribe
            kb_type: Knowledge base type, default is milvus
            embedding_model_spec: Embedding Model spec
            llm_model_spec: LLM Model spec
            share_config: Sharing Configuration
            created_by: creator uid
            created_by_department_id: Creator department ID
            **kwargs: Other configuration parameters

        Returns:
            Database information dictionary
        """
        if not KnowledgeBaseFactory.is_type_supported(kb_type):
            available_types = list(KnowledgeBaseFactory.get_available_types().keys())
            raise ValueError(f"Unsupported knowledge base type: {kb_type}. Available types: {available_types}")

        # Check if name already exists
        if await self.database_name_exists(database_name):
            raise ValueError(f"Tên cơ sở kiến thức '{database_name}' đã tồn tại, vui lòng sử dụng tên khác")

        share_config = self._normalize_share_config(
            share_config,
            user_uid=created_by,
            department_id=created_by_department_id,
        )

        kb_instance = self._get_or_create_kb_instance(kb_type)
        kwargs = kb_instance.normalize_additional_params(kwargs)
        record_fields = {"share_config": share_config, "created_by": created_by}
        db_info = await kb_instance.create_database(
            database_name,
            description,
            embedding_model_spec=embedding_model_spec,
            llm_model_spec=llm_model_spec,
            record_fields=record_fields,
            **kwargs,
        )
        kb_id = db_info["kb_id"]

        from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository

        kb_repo = KnowledgeBaseRepository()
        if await kb_repo.get_by_kb_id(kb_id) is None:
            await kb_repo.create(
                {
                    "kb_id": kb_id,
                    "name": database_name,
                    "description": description,
                    "kb_type": kb_type,
                    "embedding_model_spec": embedding_model_spec,
                    "llm_model_spec": db_info.get("llm_model_spec"),
                    "additional_params": kwargs.copy(),
                    **record_fields,
                }
            )

        logger.info(f"Created {kb_type} database: {database_name} ({kb_id}) with {kwargs}")
        db_info["share_config"] = share_config
        return db_info

    async def delete_database(self, kb_id: str) -> dict:
        """Delete database"""
        from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository

        try:
            kb_instance = await self._get_kb_for_database(kb_id)
            result = await kb_instance.delete_database(kb_id)

            # Delete database record
            kb_repo = KnowledgeBaseRepository()
            await kb_repo.delete(kb_id)

            return result
        except KBNotFoundError as e:
            logger.warning(f"Database {kb_id} not found during deletion: {e}")
            return {"message": "Delete successfully"}

    async def add_file_record(
        self, kb_id: str, item: str, params: dict | None = None, operator_id: str | None = None
    ) -> dict:
        """Add file record to metadata"""
        kb_instance = await self._get_kb_for_database(kb_id)
        return await kb_instance.add_file_record(kb_id, item, params, operator_id)

    async def parse_file(self, kb_id: str, file_id: str, operator_id: str | None = None) -> dict:
        """Parse file to Markdown"""
        kb_instance = await self._get_kb_for_database(kb_id)
        return await kb_instance.parse_file(kb_id, file_id, operator_id)

    async def index_file(
        self, kb_id: str, file_id: str, operator_id: str | None = None, params: dict | None = None
    ) -> dict:
        """Index parsed file"""
        kb_instance = await self._get_kb_for_database(kb_id)
        return await kb_instance.index_file(kb_id, file_id, operator_id, params=params)

    async def update_file_params(self, kb_id: str, file_id: str, params: dict, operator_id: str | None = None) -> None:
        """Update file processing params"""
        kb_instance = await self._get_kb_for_database(kb_id)
        await kb_instance.update_file_params(kb_id, file_id, params, operator_id)

    async def aquery(self, query_text: str, kb_id: str, **kwargs) -> str:
        """Asynchronous query knowledge base"""
        kb_instance = await self._get_kb_for_database(kb_id)
        return await kb_instance.aquery(query_text, kb_id, **kwargs)

    async def export_data(self, kb_id: str, format: str = "zip", **kwargs) -> str:
        """Export knowledge base data"""
        kb_instance = await self._get_kb_for_database(kb_id)
        return await kb_instance.export_data(kb_id, format=format, **kwargs)

    @staticmethod
    def _file_record_list_item(record, child_counts: dict[str, int] | None = None) -> dict:
        child_counts = child_counts or {}
        file_id = getattr(record, "file_id")
        child_count = int(getattr(record, "virtual_children_count", 0) or child_counts.get(file_id, 0))
        created_at_value = getattr(record, "created_at", None)
        updated_at_value = getattr(record, "updated_at", None)
        created_at = utc_isoformat(created_at_value) if created_at_value else None
        updated_at = utc_isoformat(updated_at_value) if updated_at_value else None
        return {
            "file_id": file_id,
            "filename": getattr(record, "filename"),
            "file_type": getattr(record, "file_type", None),
            "status": getattr(record, "status", None) or "uploaded",
            "created_at": created_at,
            "updated_at": updated_at,
            "file_size": int(getattr(record, "file_size", None) or 0),
            "is_folder": bool(getattr(record, "is_folder", False)),
            "parent_id": getattr(record, "parent_id", None),
            "has_children": child_count > 0,
            "children_count": child_count,
            "has_original_file": bool(getattr(record, "minio_url", None) or getattr(record, "path", None)),
            "has_parsed_markdown": bool(getattr(record, "markdown_file", None)),
            "is_virtual_folder": bool(getattr(record, "is_virtual_folder", False)),
            "path_prefix": getattr(record, "path_prefix", None),
        }

    async def _get_database_file_stats(self, kb_id: str) -> dict[str, int]:
        from yuxi.repositories.knowledge_file_repository import KnowledgeFileRepository

        return await KnowledgeFileRepository().get_kb_file_stats(kb_id)

    async def get_database_info(self, kb_id: str, include_files: bool = False) -> dict | None:
        """Get database details"""
        from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository

        kb_repo = KnowledgeBaseRepository()
        kb = await kb_repo.get_by_kb_id(kb_id)
        if kb is None:
            return None

        kb_instance: KnowledgeBase | None = None
        kb_type = kb.kb_type or "milvus"
        kb_class = (
            KnowledgeBaseFactory.get_kb_class(kb_type) if KnowledgeBaseFactory.is_type_supported(kb_type) else None
        )
        normalized_additional_params = (
            kb_class.normalize_additional_params(kb.additional_params) if kb_class else (kb.additional_params or {})
        )
        db_info = {
            "kb_id": kb_id,
            "name": kb.name,
            "description": kb.description,
            "kb_type": kb.kb_type,
            "embedding_model_spec": kb.embedding_model_spec,
            "llm_model_spec": kb.llm_model_spec,
            "query_params": kb.query_params,
            "metadata": normalized_additional_params,
            "created_at": utc_isoformat(kb.created_at) if kb.created_at else None,
            "status": "Connected",
        }

        if include_files:
            from yuxi.repositories.knowledge_file_repository import KnowledgeFileRepository

            repo = KnowledgeFileRepository()
            records, total = await repo.list_documents(kb_id=kb_id, page=1, page_size=500)
            db_info["files"] = {
                record.file_id: {
                    "file_id": record.file_id,
                    "filename": record.filename,
                    "path": getattr(record, "path", "") or "",
                    "markdown_file": getattr(record, "markdown_file", "") or "",
                    "type": getattr(record, "file_type", "") or "",
                    "status": getattr(record, "status", None) or "uploaded",
                    "created_at": utc_isoformat(record.created_at) if getattr(record, "created_at", None) else None,
                    "is_folder": bool(getattr(record, "is_folder", False)),
                    "parent_id": getattr(record, "parent_id", None),
                    "chunk_count": int(getattr(record, "chunk_count", 0) or 0),
                    "token_count": int(getattr(record, "token_count", 0) or 0),
                }
                for record in records
            }
            db_info["files_truncated"] = total > len(records)
            db_info["files_page_size"] = 500

        # Add additional fields in database
        if kb_instance:
            db_info["additional_params"] = kb_instance.normalize_additional_params(kb.additional_params)
        else:
            db_info["additional_params"] = normalized_additional_params
        db_info["share_config"] = kb.share_config or DEFAULT_SHARE_CONFIG.copy()
        db_info["mindmap"] = kb.mindmap
        db_info["sample_questions"] = kb.sample_questions or []
        db_info["query_params"] = kb.query_params
        file_stats = await self._get_database_file_stats(kb_id)
        db_info["stats"] = file_stats
        db_info["row_count"] = file_stats["row_count"]

        return db_info

    async def list_document_files(
        self,
        kb_id: str,
        *,
        parent_id: str | None = None,
        path_prefix: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 100,
        recursive: bool = False,
        files_only: bool = False,
        include_stats: bool = True,
    ) -> dict:
        """Get a lightweight file list paginated by directory and filter criteria."""
        from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository
        from yuxi.repositories.knowledge_file_repository import KnowledgeFileRepository

        kb = await KnowledgeBaseRepository().get_by_kb_id(kb_id)
        if kb is None:
            raise KBNotFoundError(f"Database {kb_id} not found")

        repo = KnowledgeFileRepository()
        if parent_id:
            parent_record = await repo.get_by_file_id(parent_id)
            if not parent_record or parent_record.kb_id != kb_id:
                raise ValueError("Parent folder not found")
            if not parent_record.is_folder:
                raise ValueError("Parent is not a folder")

        normalized_page = max(int(page or 1), 1)
        normalized_page_size = min(max(int(page_size or 100), 1), 500)
        effective_recursive = recursive and bool(status and status != "all")
        records, total = await repo.list_documents(
            kb_id=kb_id,
            parent_id=parent_id,
            path_prefix=path_prefix,
            status=status,
            page=normalized_page,
            page_size=normalized_page_size,
            recursive=effective_recursive,
            files_only=files_only,
        )
        folder_ids = [record.file_id for record in records if record.is_folder]
        child_counts = await repo.count_children_by_parent_ids(kb_id=kb_id, parent_ids=folder_ids)
        stats = await repo.get_kb_file_stats(kb_id) if include_stats else None
        items = [self._file_record_list_item(record, child_counts) for record in records]
        normalize_path_prefix = getattr(repo, "_normalize_path_prefix", lambda value: value or "")

        result = {
            "items": items,
            "total": total,
            "page": normalized_page,
            "page_size": normalized_page_size,
            "has_more": normalized_page * normalized_page_size < total,
            "parent_id": parent_id,
            "path_prefix": normalize_path_prefix(path_prefix),
            "recursive": effective_recursive,
        }
        if stats is not None:
            result["stats"] = stats
        return result

    async def document_file_exists(self, kb_id: str, filename: str) -> bool:
        """Checks whether a file with the given presentation filename or relative path exists in the specified knowledge base."""
        from yuxi.repositories.knowledge_file_repository import KnowledgeFileRepository

        normalized_filename = filename.strip()
        if not normalized_filename:
            raise ValueError("filename is required")
        return await KnowledgeFileRepository().exists_by_filename(kb_id=kb_id, filename=normalized_filename)

    async def list_document_file_ids_by_statuses(
        self,
        kb_id: str,
        *,
        statuses: list[str],
        after_file_id: str | None = None,
        limit: int = 500,
    ) -> list[str]:
        """Get the file ID by paging with the file status cursor for background batch processing tasks."""
        from yuxi.repositories.knowledge_file_repository import KnowledgeFileRepository

        return await KnowledgeFileRepository().list_file_ids_by_exact_statuses(
            kb_id=kb_id,
            statuses=statuses,
            after_file_id=after_file_id,
            limit=limit,
        )

    async def delete_folder(self, kb_id: str, folder_id: str) -> None:
        """Delete folders recursively"""
        kb_instance = await self._get_kb_for_database(kb_id)
        await kb_instance.delete_folder(kb_id, folder_id)

    async def delete_file(self, kb_id: str, file_id: str) -> None:
        """Delete files"""
        kb_instance = await self._get_kb_for_database(kb_id)
        await kb_instance.delete_file(kb_id, file_id)

    async def update_content(self, kb_id: str, file_ids: list[str], params: dict | None = None) -> list[dict]:
        """Update content (re-chunking)"""
        kb_instance = await self._get_kb_for_database(kb_id)
        return await kb_instance.update_content(kb_id, file_ids, params or {})

    async def repair_missing_file_stats(self, kb_id: str) -> dict:
        """Fix chunks with missing history files/Token Statistics, and refresh the knowledge base aggregation statistics."""
        kb_instance = await self._get_kb_for_database(kb_id)
        return await kb_instance.repair_missing_file_stats(kb_id)

    async def get_file_basic_info(self, kb_id: str, file_id: str) -> dict:
        """Get basic file information (metadata only)"""
        kb_instance = await self._get_kb_for_database(kb_id)
        return await kb_instance.get_file_basic_info(kb_id, file_id)

    async def get_file_content(self, kb_id: str, file_id: str) -> dict:
        """Get file content information (chunks and lines)"""
        kb_instance = await self._get_kb_for_database(kb_id)
        return await kb_instance.get_file_content(kb_id, file_id)

    async def open_file_content(self, kb_id: str, file_id: str, offset: int = 0, limit: int = 800) -> dict:
        """Open the parsed Markdown content of the file in a line-by-line window"""
        kb_instance = await self._get_kb_for_database(kb_id)
        return await kb_instance.open_file_content(kb_id, file_id, offset, limit)

    async def find_file_content(
        self,
        kb_id: str,
        file_id: str,
        patterns: list[str],
        *,
        use_regex: bool = False,
        case_sensitive: bool = False,
        max_windows: int = 5,
        window_size: int = 80,
    ) -> dict:
        kb_instance = await self._get_kb_for_database(kb_id)
        return await kb_instance.find_file_content(
            kb_id,
            file_id,
            patterns,
            use_regex=use_regex,
            case_sensitive=case_sensitive,
            max_windows=max_windows,
            window_size=window_size,
        )

    async def get_file_info(self, kb_id: str, file_id: str) -> dict:
        """Get complete information about the file (basic information+content information)"""
        kb_instance = await self._get_kb_for_database(kb_id)
        return await kb_instance.get_file_info(kb_id, file_id)

    async def list_file_tree(
        self,
        kb_id: str,
        parent_id: str | None = None,
        recursive: bool = False,
        files_only: bool = False,
    ) -> dict:
        kb_instance = await self._get_kb_for_database(kb_id)
        return await kb_instance.list_file_tree(kb_id, parent_id, recursive, files_only)

    async def read_file_preview(self, kb_id: str, file_id: str) -> dict:
        kb_instance = await self._get_kb_for_database(kb_id)
        return await kb_instance.read_file_preview(kb_id, file_id)

    async def get_file_download(self, kb_id: str, file_id: str, variant: str = "original") -> dict:
        kb_instance = await self._get_kb_for_database(kb_id)
        return await kb_instance.get_file_download(kb_id, file_id, variant)

    async def file_name_existed_in_db(self, kb_id: str | None, file_name: str | None) -> bool:
        """Check whether a file with the same name exists in the specified database"""
        if not kb_id or not file_name:
            return False
        return await self.document_file_exists(kb_id, file_name)

    async def get_same_name_files(self, kb_id: str, filename: str) -> list[dict]:
        """Get List of files with the same name in the same knowledge base
        Direct comparison based on original file name
        Return basic information: file name, size, Upload time

        Args:
            kb_id: Database ID
            filename: To detect offile name (original file name)

        Returns:
            List of files with the same name, each item contains:
            - filename: file name
            - size: file size
            - created_at: Upload time
            - file_id: File ID (for download)
        """
        if not kb_id or not filename:
            return []

        from yuxi.repositories.knowledge_file_repository import KnowledgeFileRepository

        records = await KnowledgeFileRepository().list_same_name_files(kb_id=kb_id, filename=filename)
        return [
            {
                "file_id": record.file_id,
                "filename": record.filename,
                "size": int(record.file_size or 0),
                "created_at": utc_isoformat(record.created_at) if record.created_at else "",
                "content_hash": record.content_hash or "",
            }
            for record in records
        ]

    async def file_existed_in_db(self, kb_id: str | None, content_hash: str | None) -> bool:
        """Checks whether a file with the same content hash exists in the specified database"""
        if not kb_id or not content_hash:
            return False

        from yuxi.repositories.knowledge_file_repository import KnowledgeFileRepository

        return await KnowledgeFileRepository().exists_by_content_hash(kb_id=kb_id, content_hash=content_hash)

    async def update_database(
        self,
        kb_id: str,
        name: str,
        description: str,
        llm_model_spec: str | None = None,
        update_llm_model_spec: bool = False,
        additional_params: dict | None = None,
        share_config: dict | None = None,
        operator_uid: str | None = None,
        operator_department_id: int | str | None = None,
    ) -> dict:
        """Update database"""
        from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository

        kb_repo = KnowledgeBaseRepository()
        kb = await kb_repo.get_by_kb_id(kb_id)
        if kb is None:
            raise ValueError(f"Cơ sở dữ liệu {kb_id} không tồn tại")

        kb_instance = await self._get_kb_for_database(kb_id)
        kb_instance.update_database(kb_id, name, description, llm_model_spec, update_llm_model_spec)

        update_data: dict = {
            "name": name,
            "description": description,
        }
        if update_llm_model_spec:
            update_data["llm_model_spec"] = llm_model_spec

        if additional_params is not None:
            current_additional_params = kb.additional_params or {}
            current_graph_config = current_additional_params.get("graph_build_config") or {}
            if current_graph_config.get("locked") and "graph_build_config" in additional_params:
                raise ValueError("Cấu hình trích xuất đồ thị đã bị khóa, vui lòng sử dụng API reset đồ thị để cấu hình lại")

            merged_additional_params = kb_instance.normalize_additional_params(
                deep_merge(current_additional_params, additional_params)
            )
            update_data["additional_params"] = merged_additional_params
            if kb_id in kb_instance.databases_meta:
                kb_instance.databases_meta[kb_id]["metadata"] = merged_additional_params

        if share_config is not None:
            update_data["share_config"] = self._normalize_share_config(
                share_config,
                user_uid=operator_uid,
                department_id=operator_department_id,
            )

        # Save to database
        await kb_repo.update(kb_id, update_data)

        return await self.get_database_info(kb_id)

    def get_retrievers(self) -> dict[str, dict]:
        """Get all retrievers"""
        all_retrievers = {}

        # Collect crawlers for all knowledge bases
        for kb_instance in self.kb_instances.values():
            retrievers = kb_instance.get_retrievers()
            all_retrievers.update(retrievers)

        return all_retrievers

    # =============================================================================
    # Manager-specific methods
    # =============================================================================

    def get_supported_kb_types(self) -> dict[str, dict]:
        """Get supported knowledge base types"""
        return KnowledgeBaseFactory.get_available_types()

    def get_kb_instance_info(self) -> dict[str, dict]:
        """Get knowledge base instance information"""
        info = {}
        for kb_type, kb_instance in self.kb_instances.items():
            info[kb_type] = {
                "work_dir": kb_instance.work_dir,
                "database_count": len(kb_instance.databases_meta),
                "file_metadata_source": "database",
            }
        return info

    async def get_statistics(self) -> dict:
        """Get statistics"""
        from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository
        from yuxi.repositories.knowledge_file_repository import KnowledgeFileRepository

        kb_repo = KnowledgeBaseRepository()
        rows = await kb_repo.get_all()

        stats = {"total_databases": len(rows), "kb_types": {}, "total_files": 0}

        # Statistics by knowledge base type
        for row in rows:
            kb_type = row.kb_type or "milvus"
            if kb_type not in stats["kb_types"]:
                stats["kb_types"][kb_type] = 0
            stats["kb_types"][kb_type] += 1

        stats["total_files"] = await KnowledgeFileRepository().count_all()

        return stats

    # =============================================================================
    # Data consistency detection method
    # =============================================================================

    async def detect_data_inconsistencies(self) -> dict:
        """
        Detection vector exists in the database but is missing in metadata of data

        Returns:
            Dictionary containing inconsistent information, grouped by knowledge base type
        """
        inconsistencies = {
            "milvus": {"missing_collections": [], "missing_files": []},
            "total_missing_collections": 0,
            "total_missing_files": 0,
        }

        logger.info("Start checking the consistency of vector database and metadata...")

        # Detecting Milvus data inconsistencies
        if "milvus" in self.kb_instances:
            try:
                milvus_inconsistencies = await self._detect_milvus_inconsistencies()
                inconsistencies["milvus"] = milvus_inconsistencies
                inconsistencies["total_missing_collections"] += len(milvus_inconsistencies["missing_collections"])
                inconsistencies["total_missing_files"] += len(milvus_inconsistencies["missing_files"])
            except Exception as e:
                logger.error(f"Error detecting Milvus data inconsistency: {e}")

        # Output detection results to log
        self._log_inconsistencies(inconsistencies)

        return inconsistencies

    async def _detect_milvus_inconsistencies(self) -> dict:
        """Detecting data inconsistencies in Milvus"""
        from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository

        inconsistencies = {"missing_collections": [], "missing_files": []}

        milvus_kb = self.kb_instances["milvus"]

        try:
            from pymilvus import utility

            # Get all actual collections in Milvus
            actual_collection_names = set(utility.list_collections(using=milvus_kb.connection_alias))

            # Get all known database IDs from the database
            kb_repo = KnowledgeBaseRepository()
            rows = await kb_repo.get_all()
            all_known_kb_ids = {row.kb_id for row in rows}

            # Find collections that exist in Milvus but are not in metadata
            # missing_collections = actual_collection_names - metadata_collection_names
            for collection_name in actual_collection_names:
                # Skip some system collections
                if not collection_name.startswith("kb_"):
                    continue

                # Check if a collection belongs to a known database
                is_known = False

                if collection_name in all_known_kb_ids:
                    is_known = True

                # If it is a known set, skip
                if is_known:
                    continue

                # If it is an unknown collection, record it
                collection_info = {"collection_name": collection_name, "detected_at": utc_isoformat()}

                # Try to get basic information about the collection
                try:
                    from pymilvus import Collection

                    collection = Collection(name=collection_name, using=milvus_kb.connection_alias)
                    collection_info["count"] = collection.num_entities
                    collection_info["description"] = collection.description
                except Exception as e:
                    logger.warning(f"Unable to get collection {collection_name} Details of: {e}")
                    collection_info["count"] = "unknown"

                inconsistencies["missing_collections"].append(collection_info)
                logger.warning(
                    f"Discover collections that exist in Milvus but are missing from metadata: {collection_name} "
                    f"(Number of entities: {collection_info['count']})"
                )

            # Get the database ID recorded in metadata (Milvus type only, used to check file consistency)
            metadata_collection_names = set(milvus_kb.databases_meta.keys())

            # Check for file-level inconsistencies (against known databases)
            for kb_id in metadata_collection_names:
                try:
                    if utility.has_collection(kb_id, using=milvus_kb.connection_alias):
                        from pymilvus import Collection

                        collection = Collection(name=kb_id, using=milvus_kb.connection_alias)
                        actual_count = collection.num_entities

                        # Get the number of files recorded in metadata
                        from yuxi.repositories.knowledge_file_repository import KnowledgeFileRepository

                        metadata_files_count = (await KnowledgeFileRepository().get_kb_file_stats(kb_id))["file_count"]

                        # If there is data in the vector database but no file records in metadata, there may be missing files.
                        if actual_count > 0 and metadata_files_count == 0:
                            inconsistencies["missing_files"].append(
                                {
                                    "kb_id": kb_id,
                                    "vector_count": actual_count,
                                    "metadata_files_count": metadata_files_count,
                                    "detected_at": utc_isoformat(),
                                }
                            )
                            logger.warning(
                                f"discovery database {kb_id} In Milvus there is {actual_count} strip vector data,"
                                "But there is no file record in metadata"
                            )

                except Exception as e:
                    logger.debug(f"Check database {kb_id} Error in file consistency: {e}")

        except Exception as e:
            logger.error(f"Error detecting Milvus data inconsistency: {e}")

        return inconsistencies

    def _log_inconsistencies(self, inconsistencies: dict) -> None:
        """Output the inconsistency detection results to the log"""
        total_missing_collections = inconsistencies["total_missing_collections"]
        total_missing_files = inconsistencies["total_missing_files"]

        if total_missing_collections == 0 and total_missing_files == 0:
            logger.info("The data consistency check is completed and no inconsistencies are found.")
            return

        logger.warning("=" * 80)
        logger.warning("The data consistency check was completed and the following inconsistencies were found:")
        logger.warning("=" * 80)

        # Milvus inconsistencies
        milvus_missing = inconsistencies["milvus"]["missing_collections"]
        milvus_files_missing = inconsistencies["milvus"]["missing_files"]
        if milvus_missing or milvus_files_missing:
            logger.warning("Milvus inconsistencies：")
            logger.warning(f"  Number of missing sets: {len(milvus_missing)}")
            for collection_info in milvus_missing:
                logger.warning(f"    - gather: {collection_info['collection_name']}, Number of entities: {collection_info['count']}")
            logger.warning(f"  Number of missing file records: {len(milvus_files_missing)}")
            for file_info in milvus_files_missing:
                logger.warning(
                    f"    - database: {file_info['kb_id']}, vector number: {file_info['vector_count']}, "
                    f"Number of metadata files: {file_info['metadata_files_count']}"
                )

        logger.warning("=" * 80)
        logger.warning(f"Total: missing collection {total_missing_collections} , missing file records {total_missing_files} indivual")
        logger.warning("Recommendation: Check these inconsistent data and perform data cleaning or metadata repair if necessary")
        logger.warning("=" * 80)

    async def manual_consistency_check(self) -> dict:
        """
        Manually trigger data consistency detection

        Returns:
            Test result dictionary
        """
        logger.info("Manually trigger data consistency detection...")
        return await self.detect_data_inconsistencies()
