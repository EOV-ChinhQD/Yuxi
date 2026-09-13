import asyncio
import os
import secrets
import string
from collections.abc import Awaitable
from dataclasses import replace
from typing import Any

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from yuxi.knowledge.base import KBNameConflictError, KBNotFoundError, KnowledgeBase
from yuxi.knowledge.cache import (
    cache_kb_config,
    get_cached_kb_config,
    kb_config_cache_lock,
    serialize_kb_config,
)
from yuxi.knowledge.chunking.ragflow_like.presets import deep_merge
from yuxi.knowledge.factory import KnowledgeBaseFactory
from yuxi.knowledge.read_models import (
    KnowledgeBaseConfig,
    KnowledgeBaseDetail,
    KnowledgeBaseSummary,
)
from yuxi.knowledge.schemas import FindOutputSchema, OpenOutputSchema
from yuxi.knowledge.utils.security import redact_sensitive_params
from yuxi.permissions import ResourcePermission, normalize_permission_config, resolve_knowledge_base_permission
from yuxi.storage.postgres.models_business import User
from yuxi.utils import logger
from yuxi.utils.datetime_utils import utc_isoformat

KB_FILE_SEARCH_SCAN_LIMIT = 5000


class KnowledgeBaseManager:
    """
    Knowledge base manager.

    Manage all knowledge base executors; business facts come from PostgreSQL,
    Redis only caches the minimal runtime config.
    """

    def __init__(self, work_dir: str):
        """
        Initialize the knowledge base manager.

        Args:
            work_dir: Working directory
        """
        self.work_dir = work_dir
        os.makedirs(work_dir, exist_ok=True)

        # Knowledge base instance cache {kb_type: kb_instance}
        self.kb_instances: dict[str, KnowledgeBase] = {}

    async def initialize(self):
        """Async initialization"""
        # Initialize the knowledge base type executors in use; config is read on demand per operation.
        await self._initialize_existing_kbs()
        logger.info("KnowledgeBaseManager initialized")

    async def _initialize_existing_kbs(self):
        """Initialize existing knowledge base instances"""
        from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository

        kb_repo = KnowledgeBaseRepository()
        rows = await kb_repo.get_all()

        kb_types_in_use = set()
        for row in rows:
            kb_type = row.kb_type or "milvus"
            if KnowledgeBaseFactory.is_type_supported(kb_type):
                kb_types_in_use.add(kb_type)
            else:
                logger.warning(f"Skip unsupported knowledge base type during initialization: {kb_type}")

        logger.info(f"[InitializeKB] Found {len(kb_types_in_use)} knowledge base types: {kb_types_in_use}")

        # Create a shared executor for each knowledge base type in use.
        for kb_type in kb_types_in_use:
            if not KnowledgeBaseFactory.is_type_supported(kb_type):
                logger.warning(f"[InitializeKB] Skip initialization for unsupported knowledge base type: {kb_type}")
                continue
            try:
                self._get_or_create_kb_instance(kb_type)
                logger.info(f"[InitializeKB] {kb_type} instance initialized")
            except Exception as e:
                logger.error(f"Failed to initialize {kb_type} knowledge base: {e}")
                import traceback

                logger.error(traceback.format_exc())

    def _get_or_create_kb_instance(self, kb_type: str) -> KnowledgeBase:
        """
        Get or create a knowledge base instance.

        Args:
            kb_type: Knowledge base type

        Returns:
            Knowledge base instance
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
        Move a file/folder.
        """
        kb_instance = await self.get_kb_executor(kb_id)
        return await kb_instance.move_file(kb_id, file_id, new_parent_id)

    async def get_kb_config(self, kb_id: str) -> KnowledgeBaseConfig:
        """Read the knowledge base runtime config, falling back to PostgreSQL on a Redis miss.

        Args:
            kb_id: Database ID

        Returns:
            Normalized knowledge base runtime config

        Raises:
            KBNotFoundError: Database does not exist or the knowledge base type is unsupported
        """
        from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository

        snapshot = await get_cached_kb_config(kb_id)
        if snapshot is None:
            try:
                async with kb_config_cache_lock(kb_id):
                    # A write request may have refreshed the config while waiting for the lock; recheck cache first.
                    snapshot = await get_cached_kb_config(kb_id)
                    if snapshot is None:
                        kb = await KnowledgeBaseRepository().get_by_kb_id(kb_id)
                        if kb is None:
                            raise KBNotFoundError(f"Database {kb_id} not found")
                        await cache_kb_config(kb)
                        snapshot = serialize_kb_config(kb)
            except (RedisConnectionError, RedisTimeoutError) as exc:
                # Redis is only a cache; on connection failure fall back to read-only source without writing
                # possibly stale recovered cache.
                logger.warning(f"Bypass knowledge base cache: kb_id={kb_id}: {exc}")
                kb = await KnowledgeBaseRepository().get_by_kb_id(kb_id)
                if kb is None:
                    raise KBNotFoundError(f"Database {kb_id} not found") from exc
                snapshot = serialize_kb_config(kb)

        kb_type = snapshot.get("kb_type") or "milvus"

        if not KnowledgeBaseFactory.is_type_supported(kb_type):
            raise KBNotFoundError(f"Unsupported knowledge base type: {kb_type}")

        executor = self._get_or_create_kb_instance(kb_type)
        additional_params = executor.normalize_additional_params(snapshot.get("additional_params"))
        additional_params.pop("stats", None)
        return KnowledgeBaseConfig(
            kb_id=kb_id,
            kb_type=kb_type,
            embedding_model_spec=snapshot.get("embedding_model_spec"),
            query_params=snapshot.get("query_params") or executor.get_default_query_params(kb_id),
            additional_params=additional_params,
        )

    async def get_kb_executor(self, kb_id: str) -> KnowledgeBase:
        """Get the knowledge base type executor."""
        config = await self.get_kb_config(kb_id)
        return self._get_or_create_kb_instance(config.kb_type)

    async def _get_kb_for_database(self, kb_id: str) -> KnowledgeBase:
        """Bí danh tương thích của get_kb_executor cho các module nội bộ (reconciliation, RAG worker, evaluation)."""
        return await self.get_kb_executor(kb_id)

    # =============================================================================
    # Unified external interface
    # =============================================================================

    def _normalize_share_config(
        self,
        share_config: dict | None,
        *,
        user_uid: str | None = None,
        department_id: int | str | None = None,
    ) -> dict:
        if share_config is None:
            return {
                "version": 2,
                "read_scope": {"access_level": "global", "department_ids": [], "user_uids": []},
                "manage_scope": None,
            }

        if share_config and share_config.get("version") == 2:
            normalized = normalize_permission_config(
                share_config,
                strict=user_uid is not None or department_id is not None,
            )
            if normalized["read_scope"] is None and (user_uid is not None or department_id is not None):
                raise ValueError("Kho kiến thức phải thiết lập phạm vi đọc")
            read_scope = normalized["read_scope"]
            if read_scope and read_scope["access_level"] == "department" and department_id is not None:
                read_scope["department_ids"] = sorted({*read_scope["department_ids"], int(department_id)})
            elif read_scope and read_scope["access_level"] == "user" and user_uid:
                read_scope["user_uids"] = sorted({*read_scope["user_uids"], str(user_uid)})
            return normalized

        raise ValueError("Cấu hình chia sẻ kho kiến thức phải dùng version 2")

    @staticmethod
    def _normalize_database_stats(stats: dict | None) -> dict[str, int]:
        """Normalize the knowledge base aggregate stats fields."""
        normalized = {
            "file_count": 0,
            "folder_count": 0,
            "row_count": 0,
            "total_size": 0,
            "chunk_count": 0,
            "token_count": 0,
            "pending_parse_count": 0,
            "pending_index_count": 0,
            "processing_count": 0,
        }
        if not isinstance(stats, dict):
            return normalized

        for key in normalized:
            try:
                normalized[key] = max(int(stats.get(key) or 0), 0)
            except (TypeError, ValueError):
                normalized[key] = 0
        return normalized

    async def _refresh_database_stats(
        self,
        kb_id: str,
        stats: dict[str, int] | None = None,
    ) -> dict[str, int]:
        """Refresh and persist the knowledge base aggregate stats."""
        from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository

        if stats is None:
            stats = await self._get_database_file_stats(kb_id)
        normalized_stats = self._normalize_database_stats(stats)
        kb = await KnowledgeBaseRepository().update_stats(kb_id, normalized_stats)
        if kb is None:
            raise KBNotFoundError(f"Database {kb_id} not found")
        return normalized_stats

    async def _run_with_stats_refresh(self, kb_id: str, operation: Awaitable[Any]) -> Any:
        """Run a file operation and refresh stats, preserving the original operation exception."""
        try:
            result = await operation
        except (Exception, asyncio.CancelledError):
            try:
                await self._refresh_database_stats(kb_id)
            except (Exception, asyncio.CancelledError) as refresh_error:
                logger.error(f"Refresh database stats after failed operation: kb_id={kb_id}: {refresh_error}")
            raise

        await self._refresh_database_stats(kb_id)
        return result

    def _database_read_fields(
        self,
        row: Any,
        *,
        stats: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        """Convert a knowledge base record into the canonical fields shared by Summary and Detail."""
        kb_type = row.kb_type or "milvus"
        kb_class = (
            KnowledgeBaseFactory.get_kb_class(kb_type) if KnowledgeBaseFactory.is_type_supported(kb_type) else None
        )
        additional_params = (
            kb_class.normalize_additional_params(row.additional_params)
            if kb_class
            else dict(row.additional_params or {})
        )
        persisted_stats = additional_params.pop("stats", None)
        normalized_stats = self._normalize_database_stats(stats if stats is not None else persisted_stats)

        return {
            "kb_id": row.kb_id,
            "name": row.name,
            "description": row.description,
            "kb_type": kb_type,
            "embedding_model_spec": row.embedding_model_spec,
            "llm_model_spec": row.llm_model_spec,
            "query_params": dict(row.query_params or {}),
            "additional_params": additional_params,
            "share_config": self._normalize_share_config(row.share_config),
            "created_by": row.created_by,
            "created_at": row.created_at,
            **normalized_stats,
        }

    async def get_databases(self) -> list[KnowledgeBaseSummary]:
        """Get summaries of all knowledge bases."""
        from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository

        kb_repo = KnowledgeBaseRepository()
        rows = await kb_repo.get_all()
        all_databases: list[KnowledgeBaseSummary] = []
        for row in rows:
            kb_type = row.kb_type or "milvus"
            if not KnowledgeBaseFactory.is_type_supported(kb_type):
                logger.warning(f"Skip unsupported database: kb_id={row.kb_id}, kb_type={kb_type}")
                continue

            # Skip only the record with invalid metadata so one bad record cannot hide the whole list.
            try:
                database = KnowledgeBaseSummary(**self._database_read_fields(row))
            except Exception as e:
                logger.warning(f"Skip database with invalid metadata: kb_id={row.kb_id}, kb_type={kb_type}: {e}")
                continue
            all_databases.append(database)
        return all_databases

    @staticmethod
    def _database_info_accessible(user: dict, db_info: Any) -> bool:
        return resolve_knowledge_base_permission(user, db_info) != ResourcePermission.NONE

    async def check_accessible(self, user: dict, kb_id: str) -> bool:
        """Check whether a user can access the database.

        Args:
            user: User info dict
            kb_id: Database ID

        Returns:
            bool: Whether access is granted
        """
        # Superadmin can access everything
        if user.get("role") == "superadmin":
            return True

        from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository

        kb_repo = KnowledgeBaseRepository()
        kb = await kb_repo.get_by_kb_id(kb_id)
        if kb is None:
            return False

        return self._database_info_accessible(user, kb)

    async def get_accessible_database_info_by_uid(self, uid: str, kb_id: str) -> KnowledgeBaseSummary | None:
        """Get one accessible knowledge base by uid; return None when missing or not permitted."""
        normalized_kb_id = str(kb_id or "").strip()
        if not normalized_kb_id:
            return None

        databases = await self.get_databases_by_uid(uid)
        for database in databases:
            if database.kb_id == normalized_kb_id:
                return database
        return None

    def database_type_supports_documents(self, kb_type: str | None) -> bool:
        """Check whether a knowledge base type supports full document operations."""
        normalized_type = (kb_type or "milvus").lower()
        if not KnowledgeBaseFactory.is_type_supported(normalized_type):
            return False
        return KnowledgeBaseFactory.get_kb_class(normalized_type).supports_documents

    async def get_database_document_support(self, kb_id: str) -> tuple[KnowledgeBaseDetail | None, bool]:
        """Return the knowledge base info and whether it supports full document operations."""
        db_info = await self.get_database_info(kb_id)
        if not db_info:
            return None, False
        return db_info, self.database_type_supports_documents(db_info.kb_type)

    async def get_databases_by_uid(self, uid: str) -> list[KnowledgeBaseSummary]:
        """Get the knowledge base list by uid"""
        from yuxi.repositories.user_repository import UserRepository

        # Fetch user info from the database
        user_repo = UserRepository()
        user: User | None = await user_repo.get_by_uid(uid)
        if not user:
            logger.warning(f"User not found: {uid}")
            return []
        return await self.get_databases_by_user(user)

    async def get_databases_by_user(self, user: User | dict) -> list[KnowledgeBaseSummary]:
        """Get the knowledge base list by user permission"""

        # Build the user info dict (support User object or dict)
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

        all_databases = await self.get_databases()

        # Superadmin can see all knowledge bases
        filtered_databases: list[KnowledgeBaseSummary] = []
        for database in all_databases:
            permission = resolve_knowledge_base_permission(user_info, database)
            if permission == ResourcePermission.NONE:
                continue
            additional_params = database.additional_params
            if permission == ResourcePermission.READ:
                additional_params = redact_sensitive_params(additional_params)
            filtered_databases.append(
                replace(
                    database,
                    additional_params=additional_params,
                    effective_permission=permission,
                )
            )

        return filtered_databases

    async def database_name_exists(self, database_name: str) -> bool:
        """Check whether a knowledge base name already exists"""
        from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository
        from yuxi.storage.postgres.manager import pg_manager

        # Ensure pg_manager is initialized
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
        kb_instance = await self.get_kb_executor(kb_id)
        return await self._run_with_stats_refresh(
            kb_id,
            kb_instance.create_folder(kb_id, folder_name, parent_id),
        )

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
    ) -> KnowledgeBaseDetail:
        """
        Create a database.

        Args:
            database_name: Database name
            description: Database description
            kb_type: Knowledge base type, defaults to milvus
            embedding_model_spec: Embedding model spec
            llm_model_spec: LLM model spec
            share_config: Share config
            created_by: Creator uid
            created_by_department_id: Creator department ID
            **kwargs: Other config params

        Returns:
            Database info dict
        """
        if not KnowledgeBaseFactory.is_type_supported(kb_type):
            available_types = list(KnowledgeBaseFactory.get_available_types().keys())
            raise ValueError(f"Unsupported knowledge base type: {kb_type}. Available types: {available_types}")

        if await self.database_name_exists(database_name):
            raise KBNameConflictError(f"Tên kho kiến thức '{database_name}' đã tồn tại, vui lòng dùng tên khác")

        share_config = self._normalize_share_config(
            share_config,
            user_uid=created_by,
            department_id=created_by_department_id,
        )

        kb_instance = self._get_or_create_kb_instance(kb_type)
        additional_params = kwargs
        additional_params.setdefault("auto_generate_questions", False)
        if "reranker_config" in additional_params:
            raise ValueError("reranker_config đã bị loại bỏ, hãy dùng reranker_model spec trong tham số truy vấn")
        additional_params = kb_instance.normalize_additional_params(additional_params)

        if kb_instance.requires_embedding_model:
            if not embedding_model_spec:
                raise ValueError("embedding_model_spec không được để trống")

            from yuxi.models.providers.cache import model_cache

            info = model_cache.get_model_info(embedding_model_spec)
            if not info or info.model_type != "embedding":
                raise ValueError(f"Không hỗ trợ mô hình embedding: {embedding_model_spec}")
        else:
            embedding_model_spec = None

        from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository

        kb_repo = KnowledgeBaseRepository()
        alphabet = string.ascii_lowercase + string.digits
        while True:
            kb_id = "kb_" + "".join(secrets.choice(alphabet) for _ in range(10))
            if await kb_repo.get_by_kb_id(kb_id) is None:
                break

        query_params = kb_instance.get_default_query_params(kb_id)
        persisted_additional_params = {**additional_params, "stats": self._normalize_database_stats(None)}
        await kb_repo.create(
            {
                "kb_id": kb_id,
                "name": database_name,
                "description": description,
                "kb_type": kb_type,
                "embedding_model_spec": embedding_model_spec,
                "llm_model_spec": llm_model_spec,
                "query_params": query_params,
                "additional_params": persisted_additional_params,
                "share_config": share_config,
                "created_by": created_by,
            }
        )
        os.makedirs(os.path.join(kb_instance.work_dir, kb_id), exist_ok=True)

        logger.info(f"Created {kb_type} database: {database_name} ({kb_id}) with {additional_params}")
        database = await self.get_database_info(kb_id)
        if database is None:
            raise KBNotFoundError(f"Database {kb_id} not found after creation")
        return database

    async def delete_database(self, kb_id: str) -> dict:
        """Delete a database"""
        from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository

        try:
            kb_instance = await self.get_kb_executor(kb_id)
            result = await kb_instance.cleanup_database_resources(kb_id)
            await KnowledgeBaseRepository().delete(kb_id)
            return result
        except KBNotFoundError as e:
            logger.warning(f"Database {kb_id} not found during deletion: {e}")
            return {"message": "Xóa thành công"}

    async def add_file_record(
        self, kb_id: str, item: str, params: dict | None = None, operator_id: str | None = None
    ) -> dict:
        """Add file record to metadata"""
        config = await self.get_kb_config(kb_id)
        executor = self._get_or_create_kb_instance(config.kb_type)
        return await self._run_with_stats_refresh(
            kb_id,
            executor.add_file_record(
                kb_id,
                item,
                params,
                operator_id,
                additional_params=config.additional_params,
            ),
        )

    async def parse_file(self, kb_id: str, file_id: str, operator_id: str | None = None) -> dict:
        """Parse file to Markdown"""
        config = await self.get_kb_config(kb_id)
        executor = self._get_or_create_kb_instance(config.kb_type)
        return await self._run_with_stats_refresh(
            kb_id,
            executor.parse_file(
                kb_id,
                file_id,
                operator_id,
                additional_params=config.additional_params,
            ),
        )

    async def index_file(
        self, kb_id: str, file_id: str, operator_id: str | None = None, params: dict | None = None
    ) -> dict:
        """Index parsed file"""
        config = await self.get_kb_config(kb_id)
        executor = self._get_or_create_kb_instance(config.kb_type)
        return await self._run_with_stats_refresh(
            kb_id,
            executor.index_file(
                kb_id,
                file_id,
                operator_id,
                params=params,
                embedding_model_spec=config.embedding_model_spec,
                additional_params=config.additional_params,
            ),
        )

    async def update_file_params(self, kb_id: str, file_id: str, params: dict, operator_id: str | None = None) -> None:
        """Update file processing params"""
        config = await self.get_kb_config(kb_id)
        executor = self._get_or_create_kb_instance(config.kb_type)
        await executor.update_file_params(
            kb_id,
            file_id,
            params,
            operator_id,
            additional_params=config.additional_params,
        )

    async def aquery(self, query_text: str, kb_id: str, **kwargs) -> str:
        """Query the knowledge base asynchronously"""
        config = await self.get_kb_config(kb_id)
        executor = self._get_or_create_kb_instance(config.kb_type)
        return await executor.aquery(
            query_text,
            kb_id,
            config=config,
            **kwargs,
        )

    async def get_kb_query_params_config(self, kb_id: str) -> dict:
        """Get the knowledge base query param definitions, merged with the saved values."""
        config = await self.get_kb_config(kb_id)
        executor = self._get_or_create_kb_instance(config.kb_type)
        params = executor.get_query_params_config(kb_id=kb_id)
        for option in params.get("options", []):
            key = option.get("key")
            if key in config.query_options:
                option["default"] = config.query_options[key]
        return params

    async def update_kb_query_params(self, kb_id: str, params: dict[str, Any]) -> None:
        """Merge and persist the knowledge base query params."""
        from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository

        kb = await KnowledgeBaseRepository().merge_query_params_options(kb_id, params)
        if kb is None:
            raise KBNotFoundError(f"Database {kb_id} not found")

    async def export_data(self, kb_id: str, format: str = "zip", **kwargs) -> str:
        """Export knowledge base data"""
        kb_instance = await self.get_kb_executor(kb_id)
        return await kb_instance.export_data(kb_id, format=format, **kwargs)

    @staticmethod
    def _file_record_list_item(
        record,
        child_counts: dict[str, int] | None = None,
        creator: User | None = None,
    ) -> dict:
        child_counts = child_counts or {}
        file_id = getattr(record, "file_id")
        child_count = int(getattr(record, "virtual_children_count", 0) or child_counts.get(file_id, 0))
        created_by = getattr(record, "created_by", None)
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
            "chunk_count": int(getattr(record, "chunk_count", 0) or 0),
            "token_count": int(getattr(record, "token_count", 0) or 0),
            "created_by": created_by,
            "created_by_name": creator.username if creator else created_by,
            "created_by_avatar": creator.to_dict().get("avatar") if creator else None,
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

    async def get_database_info(self, kb_id: str, include_files: bool = False) -> KnowledgeBaseDetail | None:
        """Get the knowledge base details."""
        from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository

        kb_repo = KnowledgeBaseRepository()
        kb = await kb_repo.get_by_kb_id(kb_id)
        if kb is None:
            return None

        files = None
        files_truncated = False
        files_page_size = None
        if include_files:
            from yuxi.repositories.knowledge_file_repository import KnowledgeFileRepository

            repo = KnowledgeFileRepository()
            records, total = await repo.list_documents(kb_id=kb_id, page=1, page_size=500)
            files = {
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
            files_truncated = total > len(records)
            files_page_size = 500

        file_stats = await self._get_database_file_stats(kb_id)
        return KnowledgeBaseDetail(
            **self._database_read_fields(kb, stats=file_stats),
            mindmap=kb.mindmap,
            sample_questions=tuple(kb.sample_questions or []),
            files=files,
            files_truncated=files_truncated,
            files_page_size=files_page_size,
        )

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
        """Get a lightweight paginated file list by directory and filters."""
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

        # Listing and stats are independent; run in parallel (full-table stat aggregation is slow for large KBs).
        if include_stats:
            (records, total), stats = await asyncio.gather(
                repo.list_documents(
                    kb_id=kb_id,
                    parent_id=parent_id,
                    path_prefix=path_prefix,
                    status=status,
                    page=normalized_page,
                    page_size=normalized_page_size,
                    recursive=effective_recursive,
                    files_only=files_only,
                ),
                repo.get_kb_file_stats(kb_id),
            )
        else:
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
            stats = None

        folder_ids = [record.file_id for record in records if record.is_folder]
        creator_uids = [record.created_by for record in records if getattr(record, "created_by", None)]
        from yuxi.repositories.user_repository import UserRepository

        child_counts, creators = await asyncio.gather(
            repo.count_children_by_parent_ids(kb_id=kb_id, parent_ids=folder_ids),
            UserRepository().list_by_uids(creator_uids),
        )
        creators = {user.uid: user for user in creators}
        items = [
            self._file_record_list_item(record, child_counts, creators.get(getattr(record, "created_by", None)))
            for record in records
        ]
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

    async def search_document_files(
        self,
        knowledge_bases: list[dict],
        *,
        query: str | None = None,
        offset: int = 0,
        limit: int = 300,
        status: str | None = None,
        include_is_folder: bool = False,
        include_parent_id: bool = False,
    ) -> dict:
        """Search files by filename across a set of knowledge bases and return paginated results."""
        from yuxi.repositories.knowledge_file_repository import KnowledgeFileRepository

        normalized_offset = max(offset or 0, 0)
        normalized_limit = min(max(limit or 300, 1), KB_FILE_SEARCH_SCAN_LIMIT)
        normalized_query = (query or "").strip().lower()
        accepted_statuses = self._normalize_file_status_filter(status)

        repo = KnowledgeFileRepository()
        all_files = []
        use_sql_pagination = len(knowledge_bases) == 1
        candidate_limit = normalized_limit if use_sql_pagination else normalized_offset + normalized_limit
        query_offset = normalized_offset if use_sql_pagination else 0
        search_results = await asyncio.gather(
            *(
                self._search_kb_files(
                    repo,
                    kb,
                    query=normalized_query,
                    statuses=accepted_statuses,
                    offset=query_offset,
                    limit=candidate_limit,
                )
                for kb in knowledge_bases
            )
        )
        total = 0
        for kb, files, kb_total in search_results:
            total += kb_total
            kb_id = kb.get("kb_id")
            for file in files:
                item = {
                    "kb_id": kb_id,
                    "kb_name": kb.get("name"),
                    "file_id": file.file_id,
                    "filename": file.filename,
                    "file_type": file.file_type,
                    "status": file.status,
                    "created_at": str(file.created_at) if file.created_at else None,
                    "updated_at": str(file.updated_at) if file.updated_at else None,
                    "file_size": file.file_size,
                }
                if include_is_folder:
                    item["is_folder"] = bool(file.is_folder)
                if include_parent_id:
                    item["parent_id"] = file.parent_id
                all_files.append(item)

        if not use_sql_pagination:
            # Only multi-DB results need cross-DB merge by updated_at; single-DB results are already ordered.
            all_files.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
        paginated_files = (
            all_files if use_sql_pagination else all_files[normalized_offset : normalized_offset + normalized_limit]
        )
        return {
            "files": paginated_files,
            "total": total,
            "offset": normalized_offset,
            "limit": normalized_limit,
            "has_more": normalized_offset + normalized_limit < total,
        }

    @staticmethod
    def _normalize_file_status_filter(status: str | None) -> set[str] | None:
        if not status or status == "all":
            return None
        return {
            "indexed": {"indexed", "done"},
            "error_indexing": {"error_indexing", "failed"},
        }.get(status, {status})

    @staticmethod
    async def _search_kb_files(
        repo,
        kb: dict,
        *,
        query: str | None,
        statuses: set[str] | None,
        offset: int,
        limit: int,
    ) -> tuple[dict, list, int]:
        """Search files in one knowledge base; return an empty list when kb_id is missing, for parallel gather."""
        if not kb.get("kb_id"):
            return kb, [], 0
        files, total = await repo.search_files(
            kb_id=kb["kb_id"],
            filename_query=query,
            statuses=statuses,
            offset=offset,
            limit=limit,
            files_only=True,
        )
        return kb, files, total

    async def document_file_exists(self, kb_id: str, filename: str) -> bool:
        """Check whether a file with the given display filename or relative path exists in the knowledge base."""
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
        """Get file IDs page by page with a file-status cursor, for background batch jobs."""
        from yuxi.repositories.knowledge_file_repository import KnowledgeFileRepository

        return await KnowledgeFileRepository().list_file_ids_by_exact_statuses(
            kb_id=kb_id,
            statuses=statuses,
            after_file_id=after_file_id,
            limit=limit,
        )

    async def delete_folder(self, kb_id: str, folder_id: str) -> None:
        """Recursively delete a folder"""
        kb_instance = await self.get_kb_executor(kb_id)
        await self._run_with_stats_refresh(kb_id, kb_instance.delete_folder(kb_id, folder_id))

    async def delete_file(self, kb_id: str, file_id: str) -> None:
        """Delete a file"""
        kb_instance = await self.get_kb_executor(kb_id)
        await self._run_with_stats_refresh(kb_id, kb_instance.delete_file(kb_id, file_id))

    async def update_content(self, kb_id: str, file_ids: list[str], params: dict | None = None) -> list[dict]:
        """Update content (re-chunk)"""
        config = await self.get_kb_config(kb_id)
        executor = self._get_or_create_kb_instance(config.kb_type)
        return await self._run_with_stats_refresh(
            kb_id,
            executor.update_content(
                kb_id,
                file_ids,
                params or {},
                embedding_model_spec=config.embedding_model_spec,
                additional_params=config.additional_params,
            ),
        )

    async def repair_missing_file_stats(self, kb_id: str) -> dict:
        """Repair missing chunk/token stats of legacy files and refresh the knowledge base aggregate stats."""
        kb_instance = await self.get_kb_executor(kb_id)
        result = await kb_instance.repair_missing_file_stats(kb_id)
        result["stats"] = await self._refresh_database_stats(kb_id, result["stats"])
        return result

    async def get_file_basic_info(self, kb_id: str, file_id: str) -> dict:
        """Get basic file info (metadata only)"""
        kb_instance = await self.get_kb_executor(kb_id)
        return await kb_instance.get_file_basic_info(kb_id, file_id)

    async def get_file_content(self, kb_id: str, file_id: str) -> dict:
        """Get file content info (chunks and lines)"""
        kb_instance = await self.get_kb_executor(kb_id)
        return await kb_instance.get_file_content(kb_id, file_id)

    async def open_file_content(self, kb_id: str, file_id: str, offset: int = 0, limit: int = 800) -> dict:
        """Open the parsed Markdown content of a file in a line window"""
        kb_instance = await self.get_kb_executor(kb_id)
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
        kb_instance = await self.get_kb_executor(kb_id)
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
        """Get full file info (basic info + content info)"""
        kb_instance = await self.get_kb_executor(kb_id)
        return await kb_instance.get_file_info(kb_id, file_id)

    async def list_file_tree(
        self,
        kb_id: str,
        parent_id: str | None = None,
        recursive: bool = False,
        files_only: bool = False,
    ) -> dict:
        kb_instance = await self.get_kb_executor(kb_id)
        return await kb_instance.list_file_tree(kb_id, parent_id, recursive, files_only)

    async def read_file_preview(self, kb_id: str, file_id: str) -> dict:
        kb_instance = await self.get_kb_executor(kb_id)
        return await kb_instance.read_file_preview(kb_id, file_id)

    async def get_file_download(self, kb_id: str, file_id: str, variant: str = "original") -> dict:
        await self._require_kb_supports_documents(kb_id, "download")
        kb_instance = await self.get_kb_executor(kb_id)
        return await kb_instance.get_file_download(kb_id, file_id, variant)

    async def file_name_existed_in_db(self, kb_id: str | None, file_name: str | None) -> bool:
        """Check whether a file with the same name exists in the given database"""
        if not kb_id or not file_name:
            return False
        return await self.document_file_exists(kb_id, file_name)

    async def get_same_name_files(self, kb_id: str, filename: str) -> list[dict]:
        """Get the list of same-name files in one knowledge base.
        Compare by original filename directly.
        Return basic info: filename, size, upload time

        Args:
            kb_id: Database ID
            filename: Filename to check (original filename)

        Returns:
            Same-name file list, each item contains:
            - filename: Filename
            - size: File size
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
        """Check whether a file with the same content hash exists in the given database"""
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
    ) -> KnowledgeBaseDetail:
        """Update the database"""
        from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository

        kb_repo = KnowledgeBaseRepository()
        kb = await kb_repo.get_by_kb_id(kb_id)
        if kb is None:
            raise ValueError(f"Cơ sở kiến thức {kb_id} không tồn tại")

        kb_type = kb.kb_type or "milvus"
        if not KnowledgeBaseFactory.is_type_supported(kb_type):
            raise ValueError(f"Không hỗ trợ kiểu cơ sở kiến thức: {kb_type}")
        kb_class = KnowledgeBaseFactory.get_kb_class(kb_type)

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
                raise ValueError(
                    "Cấu hình trích xuất đồ thị đã bị khóa, vui lòng dùng API đặt lại đồ thị để cấu hình lại"
                )

            merged_additional_params = kb_class.normalize_additional_params(
                deep_merge(current_additional_params, additional_params)
            )
            update_data["additional_params"] = merged_additional_params

        if share_config is not None:
            update_data["share_config"] = self._normalize_share_config(
                share_config,
                user_uid=operator_uid,
                department_id=operator_department_id,
            )

        # Persist to the database
        await kb_repo.update(kb_id, update_data)

        database = await self.get_database_info(kb_id)
        if database is None:
            raise KBNotFoundError(f"Database {kb_id} not found after update")
        return database

    async def retrieve(self, kb_id: str, query: str, **options) -> dict:
        """Load the latest runtime metadata by kb_id and run retrieval."""
        config = await self.get_kb_config(kb_id)
        executor = self._get_or_create_kb_instance(config.kb_type)
        results = await executor.aquery(
            query,
            kb_id,
            config=config,
            agent_call=True,
            **options,
        )
        return executor.build_search_output(kb_id, results)

    async def open_document(
        self,
        kb_id: str,
        file_id: str,
        *,
        offset: int = 0,
        limit: int = 200,
    ) -> dict:
        """Open the parsed Markdown content of a file in a line window, returning an OpenOutputSchema dict.

        Knowledge bases without document operations (e.g. dify read-only sources) raise ValueError.
        """
        await self._require_kb_supports_documents(kb_id, "open")
        window = await self.open_file_content(kb_id, file_id, offset=offset, limit=limit)
        return OpenOutputSchema(kb_id=kb_id, file_id=file_id, **window).model_dump()

    async def find_in_document(
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
        """Locate keywords or regex matches inside a file, returning a FindOutputSchema dict.

        Knowledge bases without document operations (e.g. dify read-only sources) raise ValueError.
        """
        await self._require_kb_supports_documents(kb_id, "find")
        result = await self.find_file_content(
            kb_id,
            file_id,
            patterns,
            use_regex=use_regex,
            case_sensitive=case_sensitive,
            max_windows=max_windows,
            window_size=window_size,
        )
        return FindOutputSchema(kb_id=kb_id, file_id=file_id, **result).model_dump()

    async def _require_kb_supports_documents(self, kb_id: str, operation: str) -> None:
        """Check database metadata for document-operation support; raise ValueError when unsupported."""
        db_info, supports_documents = await self.get_database_document_support(kb_id)
        if not db_info:
            raise KBNotFoundError(f"Tài nguyên kho kiến thức '{kb_id}' không tồn tại")
        kb_type = db_info.kb_type.lower()
        if not supports_documents:
            operation_label = {
                "open": "xem tài liệu",
                "find": "tìm tài liệu",
                "download": "tải tệp",
            }.get(operation, operation)
            raise ValueError(f"{db_info.name or kb_type} chỉ hỗ trợ truy xuất, không hỗ trợ {operation_label}")

    # =============================================================================
    # Manager-specific methods
    # =============================================================================

    def get_supported_kb_types(self) -> dict[str, dict]:
        """Get the supported knowledge base types"""
        return KnowledgeBaseFactory.get_available_types()

    async def get_kb_instance_info(self) -> dict[str, dict]:
        """Get knowledge base instance info"""
        from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository

        counts: dict[str, int] = {}
        for row in await KnowledgeBaseRepository().get_all():
            kb_type = row.kb_type or "milvus"
            counts[kb_type] = counts.get(kb_type, 0) + 1

        info = {}
        for kb_type, kb_instance in self.kb_instances.items():
            info[kb_type] = {
                "work_dir": kb_instance.work_dir,
                "database_count": counts.get(kb_type, 0),
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

        # Count by knowledge base type
        for row in rows:
            kb_type = row.kb_type or "milvus"
            if kb_type not in stats["kb_types"]:
                stats["kb_types"][kb_type] = 0
            stats["kb_types"][kb_type] += 1

        stats["total_files"] = await KnowledgeFileRepository().count_all()

        return stats

    # =============================================================================
    # Data consistency check methods
    # =============================================================================

    async def detect_data_inconsistencies(self) -> dict:
        """Coordinate type executors to detect inconsistencies between external resources and primary data."""
        from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository

        inconsistencies = {
            "milvus": {"missing_collections": [], "missing_files": []},
            "total_missing_collections": 0,
            "total_missing_files": 0,
        }
        logger.info("Starting consistency check between vector database and metadata...")

        if "milvus" in self.kb_instances:
            try:
                rows = await KnowledgeBaseRepository().get_all()
                known_kb_ids = {row.kb_id for row in rows}
                managed_kb_ids = {row.kb_id for row in rows if (row.kb_type or "milvus") == "milvus"}
                milvus_inconsistencies = await self.kb_instances["milvus"].detect_data_inconsistencies(
                    known_kb_ids,
                    managed_kb_ids,
                )
                inconsistencies["milvus"] = milvus_inconsistencies
                inconsistencies["total_missing_collections"] = len(milvus_inconsistencies["missing_collections"])
                inconsistencies["total_missing_files"] = len(milvus_inconsistencies["missing_files"])
            except Exception as e:
                logger.error(f"Error detecting Milvus data inconsistencies: {e}")

        self._log_inconsistencies(inconsistencies)
        return inconsistencies

    def _log_inconsistencies(self, inconsistencies: dict) -> None:
        """Write the inconsistency detection result to the log"""
        total_missing_collections = inconsistencies["total_missing_collections"]
        total_missing_files = inconsistencies["total_missing_files"]

        if total_missing_collections == 0 and total_missing_files == 0:
            logger.info("Data consistency check completed, no inconsistencies found")
            return

        logger.warning("=" * 80)
        logger.warning("Data consistency check completed, found the following inconsistencies:")
        logger.warning("=" * 80)

        # Milvus inconsistencies
        milvus_missing = inconsistencies["milvus"]["missing_collections"]
        milvus_files_missing = inconsistencies["milvus"]["missing_files"]
        if milvus_missing or milvus_files_missing:
            logger.warning("Milvus inconsistencies:")
            logger.warning(f"  Missing collections: {len(milvus_missing)}")
            for collection_info in milvus_missing:
                logger.warning(
                    f"    - Collection: {collection_info['collection_name']}, entities: {collection_info['count']}"
                )
            logger.warning(f"  Missing file records: {len(milvus_files_missing)}")
            for file_info in milvus_files_missing:
                logger.warning(
                    f"    - Database: {file_info['kb_id']}, vectors: {file_info['vector_count']}, "
                    f"metadata files: {file_info['metadata_files_count']}"
                )

        logger.warning("=" * 80)
        logger.warning(
            f"Total: {total_missing_collections} missing collections, {total_missing_files} missing file records"
        )
        logger.warning("Suggestion: review these inconsistent records; clean up data or repair metadata if needed")
        logger.warning("=" * 80)

    async def manual_consistency_check(self) -> dict:
        """
        Manually trigger the data consistency check.

        Returns:
            Check result dict
        """
        logger.info("Manually triggered data consistency check...")
        return await self.detect_data_inconsistencies()
