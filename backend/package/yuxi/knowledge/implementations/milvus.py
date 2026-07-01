import asyncio
import os
import time
import traceback
import weakref
from dataclasses import MISSING, dataclass, field, fields
from functools import partial
from typing import Any

from pymilvus import (
    AnnSearchRequest,
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    Function,
    FunctionType,
    WeightedRanker,
    connections,
    db,
    utility,
)

from yuxi.knowledge.base import FileStatus, KnowledgeBase
from yuxi.knowledge.chunking.ragflow_like.dispatcher import chunk_markdown
from yuxi.knowledge.chunking.ragflow_like.nlp import count_tokens
from yuxi.knowledge.parser.unified import Parser
from yuxi.knowledge.utils.kb_utils import resolve_processing_params
from yuxi.models.providers.cache import model_cache
from yuxi.repositories.knowledge_chunk_repository import KnowledgeChunkRepository
from yuxi.repositories.knowledge_file_repository import KnowledgeFileRepository
from yuxi.utils import hashstr, logger

MILVUS_AVAILABLE = True
CONTENT_SPARSE_FIELD = "content_sparse"
CONTENT_ANALYZER_PARAMS = {"type": "chinese"}
VECTOR_METRIC_TYPE = "COSINE"
MILVUS_CHUNK_EMBED_BATCH_SIZE = 200
MILVUS_QUERY_OFFLOAD_LIMIT = 8
_milvus_query_offload_semaphore_refs: dict[
    int,
    tuple[weakref.ReferenceType[asyncio.AbstractEventLoop], weakref.ReferenceType[asyncio.Semaphore]],
] = {}


def _get_milvus_query_offload_semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    loop_id = id(loop)
    entry = _milvus_query_offload_semaphore_refs.get(loop_id)
    if entry is not None:
        loop_ref, semaphore_ref = entry
        semaphore = semaphore_ref()
        if loop_ref() is loop and semaphore is not None:
            return semaphore

    semaphore = asyncio.Semaphore(MILVUS_QUERY_OFFLOAD_LIMIT)

    def cleanup(ref, stale_loop_id=loop_id):
        current_entry = _milvus_query_offload_semaphore_refs.get(stale_loop_id)
        if current_entry is not None and current_entry[1] is ref:
            _milvus_query_offload_semaphore_refs.pop(stale_loop_id, None)

    _milvus_query_offload_semaphore_refs[loop_id] = (weakref.ref(loop), weakref.ref(semaphore, cleanup))
    return semaphore


async def _run_milvus_query_io(func, /, *args, **kwargs):
    semaphore = _get_milvus_query_offload_semaphore()
    await semaphore.acquire()
    task = asyncio.create_task(asyncio.to_thread(func, *args, **kwargs))

    def release_capacity(completed_task: asyncio.Task):
        semaphore.release()
        if completed_task.cancelled():
            return
        completed_task.exception()

    task.add_done_callback(release_capacity)
    return await asyncio.shield(task)


@dataclass(kw_only=True)
class MilvusRetrievalConfig:
    search_mode: str = field(
        default="vector",
        metadata={
            "label": "Chế độ tìm kiếm",
            "type": "select",
            "options": [
                {"value": "vector", "label": "Tìm kiếm vector", "description": "Chỉ sử dụng độ tương đồng vector"},
                {"value": "keyword", "label": "Tìm kiếm toàn văn BM25", "description": "Chỉ sử dụng tìm kiếm BM25 của Milvus"},
                {"value": "hybrid", "label": "Tìm kiếm hỗn hợp", "description": "Tìm kiếm kết hợp vector Milvus và BM25"},
            ],
            "description": "Chọn chế độ tìm kiếm",
        },
    )
    final_top_k: int = field(
        default=10,
        metadata={
            "label": "Số lượng Chunk trả về",
            "type": "number",
            "min": 1,
            "max": 100,
            "description": "Số lượng tài liệu trả về cho frontend sau khi rerank",
        },
    )
    similarity_threshold: float = field(
        default=0.0,
        metadata={
            "label": "Ngưỡng tương đồng (0-1)",
            "type": "number",
            "min": 0.0,
            "max": 1.0,
            "step": 0.1,
            "description": "Lọc các kết quả có độ tương đồng thấp hơn giá trị này",
        },
    )
    bm25_top_k: int = field(
        default=50,
        metadata={
            "label": "Số lượng BM25 recall",
            "type": "number",
            "min": 1,
            "max": 200,
            "description": "Số lượng ứng viên BM25 trong tìm kiếm toàn văn BM25 và tìm kiếm hỗn hợp",
        },
    )
    vector_weight: float = field(
        default=0.7,
        metadata={
            "label": "Trọng số tìm kiếm vector",
            "type": "number",
            "min": 0.0,
            "max": 1.0,
            "step": 0.1,
            "description": "Trọng số kết hợp kết quả recall vector trong tìm kiếm hỗn hợp",
        },
    )
    bm25_weight: float = field(
        default=0.3,
        metadata={
            "label": "Trọng số BM25",
            "type": "number",
            "min": 0.0,
            "max": 1.0,
            "step": 0.1,
            "description": "Trọng số kết hợp kết quả recall BM25 trong tìm kiếm hỗn hợp",
        },
    )
    bm25_drop_ratio_search: float = field(
        default=0.0,
        metadata={
            "label": "Tỷ lệ loại bỏ mục thưa BM25",
            "type": "number",
            "min": 0.0,
            "max": 1.0,
            "step": 0.1,
            "description": "Tỷ lệ loại bỏ mục thưa điểm thấp khi tìm kiếm BM25, giá trị càng lớn tìm kiếm càng nhanh nhưng có thể giảm khả năng recall",
        },
    )
    include_distances: bool = field(
        default=True,
        metadata={"label": "Hiển thị độ tương đồng", "type": "boolean", "description": "Hiển thị điểm tương đồng trong kết quả"},
    )
    use_graph_retrieval: bool = field(
        default=False,
        metadata={"label": "Bật tìm kiếm đồ thị", "type": "boolean", "description": "Có bật tìm kiếm khuếch tán thực thể và bộ ba (triplet) hay không"},
    )
    graph_entity_top_k: int = field(
        default=10,
        metadata={
            "label": "Số lượng thực thể đồ thị recall",
            "type": "number",
            "min": 1,
            "max": 100,
            "depend_on": ("use_graph_retrieval", True),
            "description": "Số lượng thực thể được recall qua Query",
        },
    )
    graph_triple_top_k: int = field(
        default=10,
        metadata={
            "label": "Số lượng bộ ba đồ thị recall",
            "type": "number",
            "min": 1,
            "max": 100,
            "depend_on": ("use_graph_retrieval", True),
            "description": "Số lượng bộ ba được recall qua Query",
        },
    )
    graph_max_nodes: int = field(
        default=10000,
        metadata={
            "label": "Số lượng nút tối đa tìm kiếm đồ thị",
            "type": "number",
            "min": 100,
            "max": 50000,
            "depend_on": ("use_graph_retrieval", True),
            "description": "Số lượng nút tối đa được đọc trong đồ thị con khuếch tán 2-hop",
        },
    )
    graph_top_k: int = field(
        default=20,
        metadata={
            "label": "Số lượng Chunk đồ thị recall",
            "type": "number",
            "min": 1,
            "max": 200,
            "depend_on": ("use_graph_retrieval", True),
            "description": "Số lượng Chunk được recall từ đường dẫn đồ thị sau khi chạy PPR",
        },
    )
    graph_weight: float = field(
        default=1.0,
        metadata={
            "label": "Trọng số kết hợp tìm kiếm đồ thị",
            "type": "number",
            "min": 0.0,
            "max": 5.0,
            "step": 0.1,
            "depend_on": ("use_graph_retrieval", True),
            "description": "Trọng số của kết quả tìm kiếm đồ thị khi kết hợp thứ hạng",
        },
    )
    ppr_damping: float = field(
        default=0.85,
        metadata={
            "label": "Hệ số giảm chấn PPR",
            "type": "number",
            "min": 0.1,
            "max": 0.99,
            "step": 0.01,
            "depend_on": ("use_graph_retrieval", True),
            "description": "Hệ số giảm chấn của Personalized PageRank",
        },
    )
    use_reranker: bool = field(
        default=False,
        metadata={"label": "Bật reranker", "type": "boolean", "description": "Có sử dụng model tinh lọc để xếp hạng lại kết quả tìm kiếm hay không"},
    )
    reranker_model: str = field(
        default="",
        metadata={
            "label": "Model reranker",
            "type": "select",
            "depend_on": ("use_reranker", True),
            "description": "Chọn model reranker cho truy vấn này",
            "options_provider": "rerank_models",
        },
    )
    recall_top_k: int = field(
        default=50,
        metadata={
            "label": "Số lượng recall",
            "type": "number",
            "min": 10,
            "max": 200,
            "depend_on": ("use_reranker", True),
            "description": "Số lượng ứng viên được giữ lại trong tìm kiếm vector hoặc hỗn hợp (có hiệu lực khi bật reranker)",
        },
    )


def _retrieval_config_options() -> list[dict[str, Any]]:
    options = []
    for config_field in fields(MilvusRetrievalConfig):
        metadata = dict(config_field.metadata)
        options_provider = metadata.pop("options_provider", None)
        default = None if config_field.default is MISSING else config_field.default
        option = {
            "key": config_field.name,
            "default": default,
            **metadata,
        }
        if options_provider == "rerank_models":
            option["options"] = [
                {"label": info.display_name, "value": info.spec} for info in model_cache.get_all_specs("rerank")
            ]
        options.append(option)
    return options


class MilvusKB(KnowledgeBase):
    """Production-grade vector library based on Milvus"""

    kb_type = "milvus"
    name = "Milvus"
    description = "Production-grade vector knowledge base based on Milvus, suitable for high-performance deployment"

    def __init__(self, work_dir: str, **kwargs):
        """
        initialization Milvus knowledge base

        Args:
            work_dir: working directory
            **kwargs: Other configuration parameters
        """
        super().__init__(work_dir)

        if not MILVUS_AVAILABLE:
            raise ImportError("pymilvus is not installed. Please install it with: pip install pymilvus")

        # Milvus configuration
        # self.milvus_host = kwargs.get('milvus_host', os.getenv('MILVUS_HOST', 'localhost'))
        # self.milvus_port = kwargs.get('milvus_port', int(os.getenv('MILVUS_PORT', '19530')))
        self.milvus_token = kwargs.get("milvus_token", os.getenv("MILVUS_TOKEN") or "")
        self.milvus_uri = kwargs.get("milvus_uri", os.getenv("MILVUS_URI") or "http://localhost:19530")
        self.milvus_db = kwargs.get("milvus_db") or "yuxi"

        # connection name
        self.connection_alias = f"milvus_{hashstr(work_dir, 6)}"

        # Storage collection mapping {kb_id: Collection}
        self.collections: dict[str, Any] = {}

        # Initialize connection
        self._init_connection()

        logger.info("MilvusKB initialized")

    def _init_connection(self):
        """Initialize Milvus connection"""
        try:
            # Connect to Milvus
            connections.connect(alias=self.connection_alias, uri=self.milvus_uri, token=self.milvus_token)

            # Create database if it does not exist
            try:
                if self.milvus_db not in db.list_database():
                    db.create_database(self.milvus_db)
                db.using_database(self.milvus_db)
            except Exception as e:
                logger.warning(f"Database operation failed, using default: {e}")

            logger.info(f"Connected to Milvus at {self.milvus_uri}")

        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            raise

    async def _create_kb_instance(self, kb_id: str, kb_config: dict) -> Any:
        """Create a Milvus collection"""
        logger.info(f"Creating Milvus collection for {kb_id}")

        if not (metadata := self.databases_meta.get(kb_id)):
            raise ValueError(f"Database {kb_id} not found")

        embedding_model_spec = metadata.get("embedding_model_spec")
        if not embedding_model_spec:
            raise ValueError(f"Embedding model spec not found for database {kb_id}")

        embedding_info = model_cache.get_model_info(embedding_model_spec)
        if not embedding_info or embedding_info.model_type != "embedding":
            raise ValueError(f"Unsupported embedding model: {embedding_model_spec}")

        collection_name = kb_id

        try:
            # Check if the collection exists
            if utility.has_collection(collection_name, using=self.connection_alias):
                collection = Collection(name=collection_name, using=self.connection_alias)

                # Check if embedding model matches
                description = collection.description
                expected_model = embedding_info.model_id

                if expected_model not in description:
                    logger.warning(
                        f"Collection {collection_name} model mismatch: "
                        f"expected='{expected_model}', found_in_description='{description}'"
                    )
                    utility.drop_collection(collection_name, using=self.connection_alias)
                    return self._create_new_collection(collection_name, embedding_info, kb_id)

                if not self._collection_supports_bm25(collection):
                    logger.warning(f"Collection {collection_name} schema does not support BM25, recreating")
                    utility.drop_collection(collection_name, using=self.connection_alias)
                    return self._create_new_collection(collection_name, embedding_info, kb_id)

                logger.info(f"Retrieved existing collection: {collection_name}")
                return collection
            else:
                logger.info(f"Collection {collection_name} not found, creating new one")
                return self._create_new_collection(collection_name, embedding_info, kb_id)

        except (connections.MilvusException, RuntimeError) as e:
            logger.error(f"Error checking collection {collection_name}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error while managing collection {collection_name}: {e}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            raise

    def _create_new_collection(self, collection_name: str, embedding_info: Any, kb_id: str) -> Collection:
        """Create a new Milvus collection"""
        embedding_dim = embedding_info.dimension or 1024
        model_name = embedding_info.model_id

        # Define collection Schema
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
            FieldSchema(
                name="content",
                dtype=DataType.VARCHAR,
                max_length=65535,
                enable_analyzer=True,
                analyzer_params=CONTENT_ANALYZER_PARAMS,
            ),
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="file_id", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="chunk_index", dtype=DataType.INT64),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=embedding_dim),
            FieldSchema(name=CONTENT_SPARSE_FIELD, dtype=DataType.SPARSE_FLOAT_VECTOR),
        ]
        bm25_function = Function(
            name="content_bm25",
            input_field_names=["content"],
            output_field_names=[CONTENT_SPARSE_FIELD],
            function_type=FunctionType.BM25,
        )

        schema = CollectionSchema(
            fields=fields,
            description=f"Knowledge base collection for {kb_id} using {model_name}",
            functions=[bm25_function],
        )

        # Create a collection
        collection = Collection(name=collection_name, schema=schema, using=self.connection_alias)

        # Create index
        index_params = {"metric_type": VECTOR_METRIC_TYPE, "index_type": "IVF_FLAT", "params": {"nlist": 1024}}
        collection.create_index("embedding", index_params)
        sparse_index_params = {
            "metric_type": "BM25",
            "index_type": "SPARSE_INVERTED_INDEX",
            "params": {"inverted_index_algo": "DAAT_MAXSCORE"},
        }
        collection.create_index(CONTENT_SPARSE_FIELD, sparse_index_params)

        logger.info(f"Created new Milvus collection: {collection_name} '{model_name=}', {embedding_dim=}")

        return collection

    def _collection_supports_bm25(self, collection: Collection) -> bool:
        """Checks if the collection has the schema required by Milvus built-in BM25."""
        fields = {field.name: field for field in collection.schema.fields}
        content_field = fields.get("content")
        sparse_field = fields.get(CONTENT_SPARSE_FIELD)
        if not content_field or content_field.dtype != DataType.VARCHAR:
            return False
        if content_field.params.get("enable_analyzer") is not True:
            return False
        if not sparse_field or sparse_field.dtype != DataType.SPARSE_FLOAT_VECTOR:
            return False

        for function in collection.schema.functions:
            if (
                function.type == FunctionType.BM25
                and function.input_field_names == ["content"]
                and function.output_field_names == [CONTENT_SPARSE_FIELD]
            ):
                return True
        return False

    async def _initialize_kb_instance(self, instance: Any) -> None:
        """Initialize Milvus collection (load into memory)"""
        try:
            instance.load()
            logger.info("Milvus collection loaded into memory")
        except Exception as e:
            logger.warning(f"Failed to load collection into memory: {e}")

    def _get_embedding_function(self, embedding_model_spec: str, *, sync: bool = False):
        """Get the embedding encoding function. sync=True Returns the synchronous version, otherwise returns the asynchronous version."""
        from yuxi.models.embed import select_embedding_model

        model = select_embedding_model(embedding_model_spec)
        batch_size = int(getattr(model, "batch_size", 40) or 40)
        method = model.batch_encode if sync else model.abatch_encode
        return partial(method, batch_size=batch_size)

    async def _get_milvus_collection(self, kb_id: str):
        """Get or create a Milvus collection"""
        if kb_id in self.collections:
            return self.collections[kb_id]

        if kb_id not in self.databases_meta:
            return None

        try:
            # Create a collection
            collection = await self._create_kb_instance(kb_id, {})
            await self._initialize_kb_instance(collection)

            self.collections[kb_id] = collection
            return collection

        except Exception as e:
            logger.error(f"Failed to create Milvus collection for {kb_id}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def _split_text_into_chunks(self, text: str, file_id: str, filename: str, params: dict) -> list[dict]:
        """Split text into chunks"""
        return chunk_markdown(text, file_id, filename, params)

    def _calculate_chunk_stats(self, chunks: list[dict]) -> dict[str, int]:
        return {
            "chunk_count": len(chunks),
            "token_count": sum(count_tokens(chunk["content"]) for chunk in chunks),
        }

    def _build_chunk_pg_records(self, kb_id: str, chunks: list[dict]) -> list[dict[str, Any]]:
        return [
            {
                "chunk_id": chunk["chunk_id"],
                "file_id": chunk["file_id"],
                "kb_id": kb_id,
                "chunk_index": chunk["chunk_index"],
                "content": chunk["content"],
                "start_char_pos": chunk.get("start_char_pos"),
                "end_char_pos": chunk.get("end_char_pos"),
                "start_token_pos": chunk.get("start_token_pos"),
                "end_token_pos": chunk.get("end_token_pos"),
                "graph_indexed": bool(chunk.get("graph_indexed", False)),
                "ent_ids": chunk.get("ent_ids"),
                "tags": chunk.get("tags"),
                "extraction_result": chunk.get("extraction_result"),
            }
            for chunk in chunks
        ]

    async def _insert_chunks_to_stores(
        self,
        kb_id: str,
        file_id: str,
        collection: Collection,
        chunks: list[dict],
        embeddings: list,
    ) -> None:
        if not chunks:
            return

        entities = [
            [chunk["id"] for chunk in chunks],
            [chunk["content"] for chunk in chunks],
            [chunk["chunk_id"] for chunk in chunks],
            [chunk["file_id"] for chunk in chunks],
            [chunk["chunk_index"] for chunk in chunks],
            embeddings,
        ]
        chunk_repo = KnowledgeChunkRepository()

        def _insert_milvus_records():
            collection.insert(entities)

        pg_task = chunk_repo.batch_upsert(self._build_chunk_pg_records(kb_id, chunks))
        milvus_task = asyncio.to_thread(_insert_milvus_records)
        results = await asyncio.gather(pg_task, milvus_task, return_exceptions=True)
        errors = [result for result in results if isinstance(result, Exception)]
        if not errors:
            return

        logger.error(f"Chunk double-write failed for file {file_id}, rolling back PostgreSQL and Milvus chunks")
        try:
            await chunk_repo.delete_by_file_id(file_id)
        except Exception as cleanup_error:
            logger.error(f"Failed to rollback PostgreSQL chunks for {file_id}: {cleanup_error}")
        try:
            await self._delete_file_chunks_from_milvus(collection, file_id)
        except Exception as cleanup_error:
            logger.error(f"Failed to rollback Milvus chunks for {file_id}: {cleanup_error}")
        raise errors[0]

    async def _embed_and_store_chunks(
        self,
        kb_id: str,
        file_id: str,
        collection: Collection,
        chunks: list[dict],
        embedding_function,
        *,
        chunk_batch_size: int = MILVUS_CHUNK_EMBED_BATCH_SIZE,
    ) -> None:
        """Batch embedding and storing of chunks to Milvus and PostgreSQL"""
        if not chunks:
            return

        chunk_batch_size = max(int(chunk_batch_size), 1)
        for start in range(0, len(chunks), chunk_batch_size):
            batch_chunks = chunks[start : start + chunk_batch_size]
            texts = [chunk["content"] for chunk in batch_chunks]
            embeddings = await embedding_function(texts)
            await self._insert_chunks_to_stores(
                kb_id,
                file_id,
                collection,
                batch_chunks,
                embeddings,
            )

    async def _delete_file_chunks_from_milvus(self, collection: Collection, file_id: str) -> None:
        expr = f'file_id == "{file_id}"'
        results = collection.query(expr=expr, output_fields=["id"], limit=1)

        if not results:
            logger.info(f"File {file_id} not found in Milvus, skipping delete operation")
            return

        def _delete_from_milvus():
            collection.delete(expr)
            logger.info(f"Deleted chunks for file {file_id} from Milvus")

        await asyncio.to_thread(_delete_from_milvus)

    async def _hydrate_chunk_sources(self, kb_id: str, chunks: list[dict]) -> None:
        file_ids = sorted(
            {str(file_id) for chunk in chunks if (file_id := (chunk.get("metadata") or {}).get("file_id"))}
        )
        if not file_ids:
            return

        filenames = await KnowledgeFileRepository().get_filenames_by_file_ids(kb_id=kb_id, file_ids=file_ids)
        for chunk in chunks:
            metadata = chunk.get("metadata")
            if not isinstance(metadata, dict):
                continue
            metadata["source"] = filenames.get(str(metadata.get("file_id") or ""), "") or "unknown source"

    async def _build_file_name_expr(self, kb_id: str, file_name: str | None) -> str | None:
        if not file_name:
            return None

        matched_file_ids = await KnowledgeFileRepository().list_file_ids_by_filename_contains(
            kb_id=kb_id,
            filename_pattern=file_name,
        )
        if not matched_file_ids:
            return 'file_id == "__no_matching_file__"'
        escaped_ids = [file_id.replace('"', '\\"') for file_id in matched_file_ids]
        if len(escaped_ids) == 1:
            return f'file_id == "{escaped_ids[0]}"'
        joined_ids = '", "'.join(escaped_ids)
        return f'file_id in ["{joined_ids}"]'

    async def index_file(
        self, kb_id: str, file_id: str, operator_id: str | None = None, params: dict | None = None
    ) -> dict:
        """
        Index parsed file (Status: INDEXING -> INDEXED/ERROR_INDEXING)

        Args:
            kb_id: Database ID
            file_id: File ID
            operator_id: ID of the user performing the operation
            params: Override processing params to apply during indexing (merged on top of stored params)

        Returns:
            Updated file metadata
        """
        if kb_id not in self.databases_meta:
            raise ValueError(f"Database {kb_id} not found")

        # Get/Create collection
        collection = await self._get_milvus_collection(kb_id)
        if not collection:
            raise ValueError(f"Failed to get Milvus collection for {kb_id}")

        embedding_model_spec = self.databases_meta[kb_id].get("embedding_model_spec")
        embedding_function = self._get_embedding_function(embedding_model_spec)

        file_meta = await self._load_file_meta(kb_id, file_id)
        allowed_statuses = {
            FileStatus.PARSED,
            FileStatus.ERROR_INDEXING,
            FileStatus.INDEXED,
            "done",
        }
        params = resolve_processing_params(
            kb_additional_params=self.databases_meta.get(kb_id, {}).get("metadata"),
            file_processing_params=file_meta.get("processing_params"),
            request_params=params,
        )

        claim_data = {
            "status": FileStatus.INDEXING,
            "processing_params": params,
            "error_message": None,
        }
        if operator_id:
            claim_data["updated_by"] = operator_id

        claimed_record = await KnowledgeFileRepository().update_fields_if_status(
            kb_id=kb_id,
            file_id=file_id,
            allowed_statuses=allowed_statuses,
            data=claim_data,
        )
        if claimed_record is None:
            current_meta = await self._load_file_meta(kb_id, file_id)
            current_status = current_meta.get("status")
            raise ValueError(
                f"Cannot index file with status '{current_status}'. "
                f"File must be parsed first (status should be one of: {', '.join(allowed_statuses)})"
            )

        file_meta = self._file_record_to_meta(claimed_record)
        if not file_meta.get("markdown_file"):
            await self._mark_file_unparsed(kb_id, file_id, operator_id)
            raise ValueError("File has not been parsed yet (no markdown_file)")

        logger.debug(f"[index_file] file_id={file_id}, processing_params={params}")

        try:
            # Read markdown
            markdown_content = await self._read_markdown_from_minio(file_meta["markdown_file"])
            filename = file_meta.get("filename")

            # Split
            chunks = self._split_text_into_chunks(markdown_content, file_id, filename, params)
            logger.info(
                f"Split {filename} into {len(chunks)} chunks with params: "
                f"chunk_preset_id={params.get('chunk_preset_id')}, "
                f"chunk_parser_config={params.get('chunk_parser_config')}"
            )

            chunk_stats = self._calculate_chunk_stats(chunks)

            # Clean up existing chunks if any (for re-indexing)
            await self.delete_file_chunks_only(kb_id, file_id)

            if chunks:
                await self._embed_and_store_chunks(kb_id, file_id, collection, chunks, embedding_function)

            logger.info(f"Indexed file {file_id} into Milvus")

            # Update status
            update_data = {"status": FileStatus.INDEXED, "error_message": None, **chunk_stats}
            if operator_id:
                update_data["updated_by"] = operator_id
            updated_record = await KnowledgeFileRepository().update_fields(
                file_id=file_id,
                kb_id=kb_id,
                data=update_data,
            )
            result = (
                self._file_record_to_meta(updated_record)
                if updated_record is not None
                else {
                    **file_meta,
                    **chunk_stats,
                    "status": FileStatus.INDEXED,
                    "error": None,
                }
            )

            await self.refresh_database_stats(kb_id)
            return result

        except Exception as e:
            logger.error(f"Indexing failed for {file_id}: {e}")
            update_data = {"status": FileStatus.ERROR_INDEXING, "error_message": str(e)}
            if operator_id:
                update_data["updated_by"] = operator_id
            await KnowledgeFileRepository().update_fields(file_id=file_id, kb_id=kb_id, data=update_data)
            raise

    async def update_content(self, kb_id: str, file_ids: list[str], params: dict | None = None) -> list[dict]:
        """Update content - Re-parse the file based on file_ids and update the vector library"""
        if kb_id not in self.databases_meta:
            raise ValueError(f"Database {kb_id} not found")

        collection = await self._get_milvus_collection(kb_id)
        if not collection:
            raise ValueError(f"Failed to get Milvus collection for {kb_id}")

        embedding_model_spec = self.databases_meta[kb_id].get("embedding_model_spec")
        embedding_function = self._get_embedding_function(embedding_model_spec)

        # Handle default parameters
        if params is None:
            params = {}
        processed_items_info = []

        for file_id in file_ids:
            try:
                file_meta = await self._load_file_meta(kb_id, file_id)
            except ValueError:
                logger.warning(f"File {file_id} not found in metadata, skipping")
                continue

            file_path = file_meta.get("path")
            filename = file_meta.get("filename")

            if not file_path:
                logger.warning(f"File path not found for {file_id}, skipping")
                continue

            try:
                # Update status is processing
                resolved_params = resolve_processing_params(
                    kb_additional_params=self.databases_meta.get(kb_id, {}).get("metadata"),
                    file_processing_params=file_meta.get("processing_params"),
                    request_params=params,
                )
                file_meta["processing_params"] = resolved_params
                file_meta["status"] = FileStatus.INDEXING
                await KnowledgeFileRepository().update_fields(
                    file_id=file_id,
                    kb_id=kb_id,
                    data={"status": FileStatus.INDEXING, "processing_params": resolved_params},
                )

                # Reparse the file as markdown
                parse_params = {**resolved_params, "image_bucket": "public", "image_prefix": f"{kb_id}/kb-images"}
                markdown_content = await Parser.aparse(source=file_path, params=parse_params)

                # Regenerate chunks
                chunks = self._split_text_into_chunks(markdown_content, file_id, filename, resolved_params)
                logger.info(f"Split {filename} into {len(chunks)} chunks")
                chunk_stats = self._calculate_chunk_stats(chunks)

                # Delete existing chunks first, retaining file metadata
                await self.delete_file_chunks_only(kb_id, file_id)

                if chunks:
                    await self._embed_and_store_chunks(kb_id, file_id, collection, chunks, embedding_function)

                logger.info(f"Updated file {file_path} in Milvus. Done.")

                # Update metadata status
                file_meta["status"] = FileStatus.INDEXED
                file_meta.update(chunk_stats)
                await KnowledgeFileRepository().update_fields(
                    file_id=file_id,
                    kb_id=kb_id,
                    data={"status": FileStatus.INDEXED, "error_message": None, **chunk_stats},
                )
                await self.refresh_database_stats(kb_id)

                # Return updated file information
                updated_file_meta = file_meta.copy()
                updated_file_meta["status"] = FileStatus.INDEXED
                updated_file_meta.update(chunk_stats)
                updated_file_meta["file_id"] = file_id
                processed_items_info.append(updated_file_meta)

            except Exception as e:
                logger.error(f"update file {file_path} fail: {e}, {traceback.format_exc()}")
                await KnowledgeFileRepository().update_fields(
                    file_id=file_id,
                    kb_id=kb_id,
                    data={"status": FileStatus.ERROR_INDEXING, "error_message": str(e)},
                )

                # Returns failed file information
                failed_file_meta = file_meta.copy()
                failed_file_meta["status"] = FileStatus.ERROR_INDEXING
                failed_file_meta["error"] = str(e)
                failed_file_meta["file_id"] = file_id
                processed_items_info.append(failed_file_meta)

        return processed_items_info

    def _build_chunk_from_hit(
        self,
        hit: Any,
        score: float,
        include_distances: bool,
        score_field: str | None = None,
    ) -> dict:
        """Convert Milvus Hit into the Chunk structure returned uniformly by the knowledge base."""
        entity = hit.entity
        file_id = entity.get("file_id")
        metadata = {
            "source": "unknown source",
            "chunk_id": entity.get("chunk_id"),
            "file_id": file_id,
            "chunk_index": entity.get("chunk_index"),
        }
        chunk = {"content": entity.get("content", ""), "metadata": metadata, "score": float(score or 0.0)}
        if score_field:
            chunk[score_field] = float(score or 0.0)
        if include_distances:
            chunk["distance"] = hit.distance
        return chunk

    async def aquery(self, query_text: str, kb_id: str, agent_call: bool = False, **kwargs) -> list[dict]:
        """Asynchronous query knowledge base"""
        collection = await self._get_milvus_collection(kb_id)
        if not collection:
            raise ValueError(f"Database {kb_id} not found")

        query_params = self._get_query_params(kb_id)
        # Merge query parameters: kwargs (temporary parameters) have higher priority than query_params (persistent parameters)
        # This allows users to temporarily override persistence configuration within a single query
        merged_kwargs = {**query_params, **kwargs}

        try:
            # Query parameters (read from merged_kwargs)
            logger.debug(f"Query params: {merged_kwargs}")
            final_top_k = int(merged_kwargs.get("final_top_k", 10))
            final_top_k = max(final_top_k, 1)
            similarity_threshold = float(merged_kwargs.get("similarity_threshold", 0.2))
            metric_type = VECTOR_METRIC_TYPE
            include_distances = bool(merged_kwargs.get("include_distances", True))
            search_mode = str(merged_kwargs.get("search_mode", "vector")).lower()
            if search_mode not in {"vector", "keyword", "hybrid"}:
                search_mode = "vector"

            use_reranker = bool(merged_kwargs.get("use_reranker", False))
            use_graph_retrieval = bool(merged_kwargs.get("use_graph_retrieval", False))
            if use_reranker or use_graph_retrieval:
                recall_top_k = int(merged_kwargs.get("recall_top_k", 50))
                recall_top_k = max(recall_top_k, final_top_k)
            else:
                recall_top_k = final_top_k

            file_expr = await self._build_file_name_expr(kb_id, merged_kwargs.get("file_name"))
            if file_expr:
                logger.debug(f"Using filter expression: {file_expr}")

            output_fields = ["content", "chunk_id", "file_id", "chunk_index"]
            retrieved_chunks: list[dict] = []
            if search_mode == "vector":
                embedding_model_spec = self.databases_meta[kb_id].get("embedding_model_spec")
                embedding_function = self._get_embedding_function(embedding_model_spec, sync=True)
                query_embedding = await _run_milvus_query_io(embedding_function, [query_text])

                search_params = {"metric_type": metric_type, "params": {"nprobe": 10}}

                results = await _run_milvus_query_io(
                    collection.search,
                    data=query_embedding,
                    anns_field="embedding",
                    param=search_params,
                    limit=recall_top_k,
                    expr=file_expr,
                    output_fields=output_fields,
                )

                if results and len(results) > 0 and len(results[0]) > 0:
                    for hit in results[0]:
                        similarity = hit.distance if metric_type == VECTOR_METRIC_TYPE else 1 / (1 + hit.distance)
                        if similarity < similarity_threshold:
                            continue

                        retrieved_chunks.append(self._build_chunk_from_hit(hit, similarity, include_distances))

                logger.debug(
                    f"Milvus vector query response: {len(retrieved_chunks)} chunks found (after similarity filtering)"
                )

            elif search_mode == "keyword":
                bm25_top_k = int(merged_kwargs.get("bm25_top_k", recall_top_k))
                bm25_top_k = max(bm25_top_k, 1)
                bm25_drop_ratio_search = float(merged_kwargs.get("bm25_drop_ratio_search", 0.0))
                bm25_search_params = {
                    "metric_type": "BM25",
                    "params": {"drop_ratio_search": bm25_drop_ratio_search},
                }

                results = await _run_milvus_query_io(
                    collection.search,
                    data=[query_text],
                    anns_field=CONTENT_SPARSE_FIELD,
                    param=bm25_search_params,
                    limit=bm25_top_k,
                    expr=file_expr,
                    output_fields=output_fields,
                )

                if results and len(results) > 0 and len(results[0]) > 0:
                    for hit in results[0]:
                        retrieved_chunks.append(
                            self._build_chunk_from_hit(hit, hit.distance, include_distances, score_field="bm25_score")
                        )

                logger.debug(f"Milvus BM25 query response: {len(retrieved_chunks)} chunks found")
            else:
                embedding_model_spec = self.databases_meta[kb_id].get("embedding_model_spec")
                embedding_function = self._get_embedding_function(embedding_model_spec, sync=True)
                query_embedding = await _run_milvus_query_io(embedding_function, [query_text])
                bm25_top_k = int(merged_kwargs.get("bm25_top_k", recall_top_k))
                bm25_top_k = max(bm25_top_k, 1)
                bm25_drop_ratio_search = float(merged_kwargs.get("bm25_drop_ratio_search", 0.0))
                vector_weight = float(merged_kwargs.get("vector_weight", 0.7))
                bm25_weight = float(merged_kwargs.get("bm25_weight", 0.3))

                vector_request = AnnSearchRequest(
                    data=query_embedding,
                    anns_field="embedding",
                    param={"metric_type": metric_type, "params": {"nprobe": 10}},
                    limit=recall_top_k,
                    expr=file_expr,
                )
                bm25_request = AnnSearchRequest(
                    data=[query_text],
                    anns_field=CONTENT_SPARSE_FIELD,
                    param={
                        "metric_type": "BM25",
                        "params": {"drop_ratio_search": bm25_drop_ratio_search},
                    },
                    limit=bm25_top_k,
                    expr=file_expr,
                )
                results = await _run_milvus_query_io(
                    collection.hybrid_search,
                    reqs=[vector_request, bm25_request],
                    rerank=WeightedRanker(vector_weight, bm25_weight),
                    limit=recall_top_k,
                    output_fields=output_fields,
                )
                if results and len(results) > 0 and len(results[0]) > 0:
                    for hit in results[0]:
                        score = float(hit.distance or 0.0)
                        if score < similarity_threshold:
                            continue
                        retrieved_chunks.append(
                            self._build_chunk_from_hit(hit, score, include_distances, score_field="hybrid_score")
                        )

                logger.debug(f"Milvus hybrid query response: {len(retrieved_chunks)} chunks found")

            if use_graph_retrieval:
                graph_chunks = await self._retrieve_graph_chunks(query_text, kb_id, retrieved_chunks, merged_kwargs)
                if graph_chunks:
                    graph_weight = float(merged_kwargs.get("graph_weight", 1.0))
                    retrieved_chunks = self._fuse_chunk_rankings(retrieved_chunks, graph_chunks, graph_weight)

            if not retrieved_chunks:
                return []

            await self._hydrate_chunk_sources(kb_id, retrieved_chunks)

            if not use_reranker:
                return retrieved_chunks[:final_top_k]

            # Use a reordering model
            reranker_model = merged_kwargs.get("reranker_model")
            if not reranker_model:
                raise ValueError(
                    "Reranker model must be specified when use_reranker=True. "
                    "Please provide reranker_model in query parameters."
                )

            try:
                from yuxi.models.rerank import get_reranker

                reranker = get_reranker(reranker_model)
                try:
                    rerank_start = time.time()
                    documents_text = [chunk["content"] for chunk in retrieved_chunks]
                    rerank_scores = await reranker.acompute_score([query_text, documents_text], normalize=True)

                    for chunk, rerank_score in zip(retrieved_chunks, rerank_scores):
                        chunk["rerank_score"] = float(rerank_score)

                    retrieved_chunks.sort(
                        key=lambda item: item.get("rerank_score", item.get("score", 0.0)), reverse=True
                    )
                    elapsed = time.time() - rerank_start
                    logger.info(f"Reranking completed for {kb_id} in {elapsed:.3f}s with model {reranker_model}")
                finally:
                    await reranker.aclose()

            except Exception as exc:  # noqa: BLE001
                logger.error(f"Reranking failed: {exc}, falling back to vector scores")

            # Return results uniformly
            return retrieved_chunks[:final_top_k]

        except Exception as e:
            logger.error(f"Milvus query error: {e}, {traceback.format_exc()}")
            return []

    async def _retrieve_graph_chunks(
        self,
        query_text: str,
        kb_id: str,
        base_chunks: list[dict],
        query_params: dict[str, Any],
    ) -> list[dict]:
        try:
            from yuxi.knowledge.graphs.milvus_graph_service import MilvusGraphService
            from yuxi.knowledge.graphs.milvus_graph_vector_store import MilvusGraphVectorStore

            embedding_model_spec = self.databases_meta[kb_id].get("embedding_model_spec")
            if not embedding_model_spec:
                return []

            entity_top_k = max(int(query_params.get("graph_entity_top_k", 10)), 1)
            triple_top_k = max(int(query_params.get("graph_triple_top_k", 10)), 1)
            graph_top_k = max(int(query_params.get("graph_top_k", 20)), 1)
            graph_max_nodes = max(int(query_params.get("graph_max_nodes", 10000)), 1)

            vector_store = await _run_milvus_query_io(MilvusGraphVectorStore)
            entity_hits, triple_hits = await asyncio.gather(
                vector_store.search_entities(
                    kb_id=kb_id,
                    query_text=query_text,
                    embedding_model_spec=embedding_model_spec,
                    top_k=entity_top_k,
                ),
                vector_store.search_triples(
                    kb_id=kb_id,
                    query_text=query_text,
                    embedding_model_spec=embedding_model_spec,
                    top_k=triple_top_k,
                ),
            )
            seed_weights = await self._build_graph_seed_weights(kb_id, base_chunks, entity_hits, triple_hits)
            if not seed_weights:
                return []

            graph_service = MilvusGraphService()
            graph_scores = await graph_service.query_and_rank_chunks_by_ppr(
                kb_id,
                seed_weights,
                max_nodes=graph_max_nodes,
                top_k=graph_top_k,
                damping=float(query_params.get("ppr_damping", 0.85)),
            )
            if not graph_scores:
                return []

            chunks = await KnowledgeChunkRepository().list_by_chunk_ids([chunk_id for chunk_id, _ in graph_scores])
            score_by_chunk_id = dict(graph_scores)
            return [
                self._build_chunk_from_record(chunk, score_by_chunk_id[chunk.chunk_id], score_field="graph_score")
                for chunk in chunks
            ]
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Graph retrieval failed for {kb_id}: {exc}")
            return []

    async def _build_graph_seed_weights(
        self,
        kb_id: str,
        base_chunks: list[dict],
        entity_hits: list[dict[str, Any]],
        triple_hits: list[dict[str, Any]],
    ) -> dict[str, float]:
        seed_weights: dict[str, float] = {}

        def add_seed(entity_id: str | None, score: float, weight: float) -> None:
            if not entity_id:
                return
            seed_weights[entity_id] = seed_weights.get(entity_id, 0.0) + max(float(score or 0.0), 0.0) * weight

        for hit in entity_hits:
            add_seed(hit.get("id"), hit.get("score", 0.0), 1.0)

        for hit in triple_hits:
            score = float(hit.get("score") or 0.0)
            add_seed(hit.get("source_id"), score, 0.8)
            add_seed(hit.get("target_id"), score, 0.8)

        chunk_scores = {
            chunk.get("metadata", {}).get("chunk_id"): float(chunk.get("score") or 0.0)
            for chunk in base_chunks
            if chunk.get("metadata", {}).get("chunk_id")
        }
        if chunk_scores:
            chunks = await KnowledgeChunkRepository().list_by_chunk_ids(list(chunk_scores))
            for chunk in chunks:
                for entity_id in chunk.ent_ids or []:
                    add_seed(entity_id, chunk_scores.get(chunk.chunk_id, 0.0), 0.3)

        total = sum(seed_weights.values())
        if total <= 0:
            return {}
        return {entity_id: weight / total for entity_id, weight in seed_weights.items()}

    def _build_chunk_from_record(self, chunk: Any, score: float, score_field: str | None = None) -> dict:
        metadata = {
            "source": "unknown source",
            "chunk_id": chunk.chunk_id,
            "file_id": chunk.file_id,
            "chunk_index": chunk.chunk_index,
        }
        result = {"content": chunk.content, "metadata": metadata, "score": float(score or 0.0)}
        if score_field:
            result[score_field] = float(score or 0.0)
        return result

    def _fuse_chunk_rankings(
        self,
        base_chunks: list[dict],
        graph_chunks: list[dict],
        graph_weight: float,
    ) -> list[dict]:
        fused: dict[str, dict[str, Any]] = {}
        rrf_k = 60.0

        def merge_chunk(chunk: dict, rank: int, weight: float, source: str) -> None:
            chunk_id = chunk.get("metadata", {}).get("chunk_id")
            if not chunk_id:
                return
            score = weight / (rrf_k + rank)
            existing = fused.get(chunk_id)
            if existing is None:
                existing = {**chunk, "fusion_score": 0.0, "fusion_sources": []}
                fused[chunk_id] = existing
            existing["fusion_score"] += score
            existing["score"] = existing["fusion_score"]
            existing["fusion_sources"].append(source)
            if source == "graph" and "graph_score" in chunk:
                existing["graph_score"] = chunk["graph_score"]

        for rank, chunk in enumerate(base_chunks, start=1):
            merge_chunk(chunk, rank, 1.0, "chunk")
        for rank, chunk in enumerate(graph_chunks, start=1):
            merge_chunk(chunk, rank, max(graph_weight, 0.0), "graph")

        return sorted(fused.values(), key=lambda item: item.get("fusion_score", 0.0), reverse=True)

    async def delete_file_chunks_only(self, kb_id: str, file_id: str) -> None:
        """Only deletes the file's chunks data, retaining metadata (for update operations)"""
        chunk_repo = KnowledgeChunkRepository()
        if await chunk_repo.count_graph_indexed_by_file_id(file_id):
            from yuxi.knowledge.graphs.milvus_graph_service import MilvusGraphService

            try:
                await MilvusGraphService().delete_file_graph(kb_id, file_id)
            except Exception as e:
                logger.error(f"Failed to delete graph data for file {file_id}: {e}")
        await chunk_repo.delete_by_file_id(file_id)
        collection = await self._get_milvus_collection(kb_id)

        if collection:
            # First check whether the file exists to avoid unnecessary deletion operations
            try:
                await self._delete_file_chunks_from_milvus(collection, file_id)
            except Exception as e:
                logger.error(f"Error checking file existence in Milvus: {e}")
        await KnowledgeFileRepository().update_fields(
            file_id=file_id,
            kb_id=kb_id,
            data={"chunk_count": 0, "token_count": 0},
        )
        await self.refresh_database_stats(kb_id)

    async def delete_file(self, kb_id: str, file_id: str) -> None:
        """Delete files (including metadata)"""
        # First delete the chunks data in Milvus
        await self.delete_file_chunks_only(kb_id, file_id)

        await KnowledgeFileRepository().delete(file_id)
        await self.refresh_database_stats(kb_id)

    async def get_file_basic_info(self, kb_id: str, file_id: str) -> dict:
        """Get basic file information (metadata only)"""
        return {"meta": await self._load_file_meta(kb_id, file_id)}

    async def _get_file_content_from_meta(self, file_id: str, file_meta: dict) -> dict:
        content_info = {"lines": []}
        try:
            chunks = await KnowledgeChunkRepository().list_by_file_id(file_id)
            content_info["lines"] = [
                {
                    "id": chunk.chunk_id,
                    "content": chunk.content,
                    "chunk_order_index": chunk.chunk_index,
                    "start_char_pos": chunk.start_char_pos,
                    "end_char_pos": chunk.end_char_pos,
                    "start_token_pos": chunk.start_token_pos,
                    "end_token_pos": chunk.end_token_pos,
                    "graph_indexed": chunk.graph_indexed,
                    "ent_ids": chunk.ent_ids,
                    "tags": chunk.tags,
                    "extraction_result": chunk.extraction_result,
                }
                for chunk in chunks
            ]
        except Exception as e:
            logger.error(f"Failed to get file content from PostgreSQL: {e}")

        if not content_info["lines"]:
            logger.warning(f"No chunks found in PostgreSQL for file {file_id}, file may not have been indexed")

        # Try to read markdown content if available
        if file_meta.get("markdown_file"):
            try:
                content = await self._read_markdown_from_minio(file_meta["markdown_file"])
                content_info["content"] = content
            except Exception as e:
                logger.error(f"Failed to read markdown file for {file_id}: {e}")

        return content_info

    async def get_file_content(self, kb_id: str, file_id: str) -> dict:
        """Get file content information (chunks and lines)"""
        file_meta = await self._load_file_meta(kb_id, file_id)
        return await self._get_file_content_from_meta(file_id, file_meta)

    async def get_file_info(self, kb_id: str, file_id: str) -> dict:
        """Get complete information about the file (basic information+content information)"""
        file_meta = await self._load_file_meta(kb_id, file_id)
        content_info = await self._get_file_content_from_meta(file_id, file_meta)
        return {"meta": file_meta, **content_info}

    def delete_database(self, kb_id: str) -> dict:
        """Delete the database while clearing the collection in Milvus"""
        # Drop Milvus collection
        try:
            if utility.has_collection(kb_id, using=self.connection_alias):
                utility.drop_collection(kb_id, using=self.connection_alias)
                logger.info(f"Dropped Milvus collection for {kb_id}")
            else:
                logger.info(f"Milvus collection {kb_id} does not exist, skipping")
        except Exception as e:
            logger.error(f"Failed to drop Milvus collection {kb_id}: {e}")

        from yuxi.knowledge.graphs.milvus_graph_vector_store import MilvusGraphVectorStore

        MilvusGraphVectorStore().drop_graph_collections(kb_id)

        # Call base method to delete local files and metadata
        return super().delete_database(kb_id)

    def get_query_params_config(self, kb_id: str, **kwargs) -> dict:
        """Get the query parameter configuration of the Milvus knowledge base"""
        return {"type": "milvus", "options": _retrieval_config_options()}

    def __del__(self):
        """clean connection"""
        try:
            if hasattr(self, "connection_alias"):
                connections.disconnect(self.connection_alias)
        except Exception:  # noqa: S110
            pass
