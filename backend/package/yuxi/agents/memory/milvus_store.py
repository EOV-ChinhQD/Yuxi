import os
import time
from typing import Any, List, Dict, Optional
from pymilvus import (
    connections,
    utility,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    db,
)

from yuxi.models.providers.cache import model_cache
from yuxi.models.embed import select_embedding_model
from yuxi.utils import hashstr, logger

COLLECTION_NAME = "user_semantic_memory"
VECTOR_METRIC_TYPE = "COSINE"

class MilvusMemoryStore:
    def __init__(self):
        self.milvus_token = os.getenv("MILVUS_TOKEN") or ""
        self.milvus_uri = os.getenv("MILVUS_URI") or "http://localhost:19530"
        self.milvus_db = os.getenv("MILVUS_DB") or "yuxi"
        self.connection_alias = f"milvus_memory_{hashstr(self.milvus_uri, 6)}"
        self._init_connection()
        self.collection: Optional[Collection] = None

    def _init_connection(self) -> None:
        if not connections.has_connection(self.connection_alias):
            connections.connect(alias=self.connection_alias, uri=self.milvus_uri, token=self.milvus_token)
        try:
            if self.milvus_db not in db.list_database():
                db.create_database(self.milvus_db)
            db.using_database(self.milvus_db)
        except Exception as exc:
            logger.warning(f"Milvus memory database operation failed, using default: {exc}")

    def get_embedding_model_info(self) -> tuple:
        """Get spec and info of default embedding model"""
        embed_specs = model_cache.get_all_specs("embedding")
        if embed_specs:
            # Prefer gemini or models with 768 dimensions
            for spec_info in embed_specs:
                if "gemini" in spec_info.spec or spec_info.dimension == 768:
                    return spec_info.spec, spec_info.dimension or 768
            return embed_specs[0].spec, embed_specs[0].dimension or 768
        return "gemini:text-embedding-004", 768

    def get_or_create_collection(self) -> Collection:
        if self.collection is not None:
            return self.collection

        spec, dim = self.get_embedding_model_info()

        if utility.has_collection(COLLECTION_NAME, using=self.connection_alias):
            collection = Collection(name=COLLECTION_NAME, using=self.connection_alias)
            collection.load()
            self.collection = collection
            return collection

        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
            FieldSchema(name="uid", dtype=DataType.VARCHAR, max_length=64, is_partition_key=True),
            FieldSchema(name="fact_text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dim),
            FieldSchema(name="is_active", dtype=DataType.BOOL),
            FieldSchema(name="superseded_by", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="created_at", dtype=DataType.INT64),
            FieldSchema(name="confidence_score", dtype=DataType.FLOAT),
        ]

        schema = CollectionSchema(
            fields=fields,
            description="Long-term user semantic memory facts collection",
        )

        collection = Collection(name=COLLECTION_NAME, schema=schema, using=self.connection_alias)

        # Create vector index
        index_params = {"metric_type": VECTOR_METRIC_TYPE, "index_type": "IVF_FLAT", "params": {"nlist": 128}}
        collection.create_index("vector", index_params)

        collection.load()
        self.collection = collection
        return collection

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        spec, _ = self.get_embedding_model_info()
        model = select_embedding_model(spec)
        return await model.aencode(texts)

    async def insert_fact(
        self,
        uid: str,
        fact_id: str,
        fact_text: str,
        confidence_score: float,
        is_active: bool = True,
        superseded_by: str = "",
        created_at: Optional[int] = None,
    ) -> None:
        collection = self.get_or_create_collection()
        if created_at is None:
            created_at = int(time.time())

        vectors = await self.get_embeddings([fact_text])
        vector = vectors[0]

        data = [
            [fact_id],
            [uid],
            [fact_text],
            [vector],
            [is_active],
            [superseded_by],
            [created_at],
            [confidence_score],
        ]

        # Use upsert to handle updates cleanly
        collection.upsert(data)

    async def search_facts(self, uid: str, query_text: str, limit: int = 5) -> List[Dict[str, Any]]:
        collection = self.get_or_create_collection()
        vectors = await self.get_embeddings([query_text])
        vector = vectors[0]

        # Filter strictly by user (is_partition_key handles routing, but expression handles filtering)
        expr = f'uid == "{uid}" and is_active == true'
        search_params = {"metric_type": VECTOR_METRIC_TYPE, "params": {"nprobe": 10}}

        results = collection.search(
            data=[vector],
            anns_field="vector",
            param=search_params,
            limit=limit,
            expr=expr,
            output_fields=["id", "uid", "fact_text", "is_active", "superseded_by", "created_at", "confidence_score"],
        )

        output = []
        if results:
            for hits in results:
                for hit in hits:
                    entity = hit.entity
                    output.append({
                        "id": entity.get("id"),
                        "uid": entity.get("uid"),
                        "fact_text": entity.get("fact_text"),
                        "is_active": entity.get("is_active"),
                        "superseded_by": entity.get("superseded_by"),
                        "created_at": entity.get("created_at"),
                        "confidence_score": entity.get("confidence_score"),
                        "distance": hit.distance,
                    })
        return output

    async def deactivate_fact(self, uid: str, fact_id: str, superseded_by: str) -> None:
        collection = self.get_or_create_collection()
        # Query the existing fact to get details
        expr = f'id == "{fact_id}" and uid == "{uid}"'
        results = collection.query(expr=expr, output_fields=["fact_text", "created_at", "confidence_score", "vector"])
        if not results:
            logger.warning(f"deactivate_fact: Fact {fact_id} not found for user {uid}")
            return

        existing = results[0]
        # Re-upsert with is_active=False
        data = [
            [fact_id],
            [uid],
            [existing["fact_text"]],
            [existing["vector"]],
            [False],
            [superseded_by],
            [existing["created_at"]],
            [existing["confidence_score"]],
        ]
        collection.upsert(data)

    async def delete_all_user_facts(self, uid: str) -> None:
        """GDPR - right to be forgotten"""
        collection = self.get_or_create_collection()
        expr = f'uid == "{uid}"'
        collection.delete(expr)
