import re
from typing import List, Dict, Any
from sqlalchemy import select, or_

from yuxi.storage.postgres.models_business import UserEpisodicMemory, UserProceduralMemory
from yuxi.agents.memory.milvus_store import MilvusMemoryStore
from yuxi.utils.logging_config import logger

class MemoryInjector:
    def __init__(self):
        self.milvus_store = MilvusMemoryStore()

    async def get_memories_for_prompt(self, db_session, uid: str, query_text: str) -> Dict[str, Any]:
        """
        Lấy các Procedural Rules (mới nhất, không filter ngữ nghĩa) và 
        truy vấn Semantic/Episodic Memories liên quan đến câu hỏi.
        """
        memories = {
            "procedural_rules": [],
            "semantic_facts": [],
            "episodic_events": []
        }

        try:
            # 1. Lấy top 10 Procedural Rules đang active mới nhất
            stmt_proc = (
                select(UserProceduralMemory)
                .where(
                    UserProceduralMemory.uid == uid,
                    UserProceduralMemory.is_active == True
                )
                .order_by(UserProceduralMemory.updated_at.desc())
                .limit(10)
            )
            res_proc = await db_session.execute(stmt_proc)
            proc_records = res_proc.scalars().all()
            memories["procedural_rules"] = [r.rule_text for r in proc_records]

            # 2. Truy vấn Semantic Facts liên quan từ Milvus
            similar_facts = await self.milvus_store.search_facts(uid, query_text, limit=5)
            memories["semantic_facts"] = [f["fact_text"] for f in similar_facts]

            # 3. Truy vấn Episodic Events liên quan từ Postgres (sử dụng Keyword Search / Fallback to Recent)
            # Tách từ khóa đơn giản để tìm kiếm ILIKE trên Postgres
            keywords = [w for w in re.split(r"\s+", query_text) if len(w) > 2]
            
            event_records = []
            if keywords:
                # Tìm các event chứa bất kỳ từ khóa nào
                conditions = [UserEpisodicMemory.event_summary.ilike(f"%{kw}%") for kw in keywords[:5]]
                stmt_event = (
                    select(UserEpisodicMemory)
                    .where(
                        UserEpisodicMemory.uid == uid,
                        UserEpisodicMemory.is_archived == False,
                        or_(*conditions)
                    )
                    .order_by(UserEpisodicMemory.timestamp.desc())
                    .limit(5)
                )
                res_event = await db_session.execute(stmt_event)
                event_records = res_event.scalars().all()

            # Fallback: Nếu không tìm thấy event liên quan theo từ khóa, lấy top 5 event mới nhất
            if not event_records:
                stmt_event_fallback = (
                    select(UserEpisodicMemory)
                    .where(
                        UserEpisodicMemory.uid == uid,
                        UserEpisodicMemory.is_archived == False
                    )
                    .order_by(UserEpisodicMemory.timestamp.desc())
                    .limit(5)
                )
                res_event_fallback = await db_session.execute(stmt_event_fallback)
                event_records = res_event_fallback.scalars().all()

            memories["episodic_events"] = [e.event_summary for e in event_records]

        except Exception as e:
            logger.error(f"Error injecting memories for user {uid}: {e}", exc_info=True)

        return memories
