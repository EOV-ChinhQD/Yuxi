import re
import json
import uuid
import time
import asyncio
from typing import List, Dict, Any, Optional
from sqlalchemy import text, select

from yuxi.storage.postgres.manager import pg_manager
from yuxi.storage.postgres.models_business import (
    UserEpisodicMemory,
    UserProceduralMemory,
    RejectedMemoryLog,
)
from yuxi.agents.memory.milvus_store import MilvusMemoryStore
from yuxi import config as conf
from yuxi.models.providers.cache import model_cache
from yuxi.models import select_model
from yuxi.utils.logging_config import logger

class MemoryExtractorTask:
    def __init__(self):
        self.milvus_store = MilvusMemoryStore()
        # Regex heuristics for greeting/technical/trash filter
        self.ignore_patterns = [
            r"^(chào|hello|hi|cảm ơn|thank|bye|tạm biệt)",
            r"^(làm sao|hướng dẫn|cách để|làm thế nào|viết code|debug|sửa lỗi)",
            r"^(chạy docker|cài đặt|config|cấu hình|deploy)",
            r"^\s*$"
        ]

    def _should_ignore_content(self, text_content: str) -> bool:
        """Heuristic check to skip calls on irrelevant inputs"""
        cleaned = text_content.strip().lower()
        for pat in self.ignore_patterns:
            if re.search(pat, cleaned):
                return True
        return False

    def _get_high_reasoning_model(self):
        """Get high reasoning capacity model or default model"""
        available_specs = model_cache.get_all_specs("chat")
        # Try to find a Pro model first
        for info in available_specs:
            if "pro" in info.model_id.lower():
                try:
                    return select_model(info.spec)
                except Exception:
                    pass
        # Fallback to default config model
        return select_model(conf.default_model)

    async def extract_memory_from_dialogue(self, uid: str, thread_id: str, messages: List[Dict[str, Any]]) -> None:
        """
        Background task to extract memory facts using Postgres advisory lock to prevent race conditions.
        """
        if not messages:
            return

        # 1. Heuristic Filter: join messages and check if it's purely generic questions
        full_text = "\n".join([m.get("content", "") for m in messages if m.get("role") == "user"])
        if self._should_ignore_content(full_text):
            logger.info(f"Memory extraction skipped for user {uid} due to heuristic filter.")
            return

        # Generate lock key from user ID
        lock_id = hash(uid) % (2**31 - 1)

        # 2. Acquire Postgres Advisory Lock & Perform Transaction
        async with pg_manager.get_async_session_context() as session:
            try:
                # Lock session
                await session.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})
                logger.info(f"Advisory lock acquired for memory extraction of user {uid}")

                # Fetch active procedural rules to check for overrides
                stmt = select(UserProceduralMemory).where(
                    UserProceduralMemory.uid == uid,
                    UserProceduralMemory.is_active == True
                )
                res = await session.execute(stmt)
                active_rules = res.scalars().all()
                existing_rules_json = [
                    {"id": rule.id, "rule_text": rule.rule_text} for rule in active_rules
                ]

                # Format dialogue history
                dialogue_str = ""
                for msg in messages:
                    role = "User" if msg.get("role") == "user" else "Assistant"
                    dialogue_str += f"{role}: {msg.get('content')}\n"

                # 3. Call LLM to extract
                llm = self._get_high_reasoning_model()
                prompt = self._build_prompt(dialogue_str, existing_rules_json)
                
                logger.info(f"Sending dialog memory extraction to LLM for user {uid}")
                response = await llm.ainvoke(prompt)
                
                # Parse JSON output
                extracted_data = self._parse_llm_json(response.content)
                if not extracted_data:
                    logger.warning(f"Memory extraction LLM output could not be parsed for user {uid}")
                    return

                # 4. Process semantic facts (Milvus)
                await self._process_semantic_facts(uid, extracted_data.get("semantic", []), session)

                # 5. Process episodic memories (Postgres)
                await self._process_episodic_memories(uid, thread_id, extracted_data.get("episodic", []), session)

                # 6. Process procedural rules (Postgres)
                await self._process_procedural_rules(uid, extracted_data.get("procedural", []), session)

                # Commit changes
                await session.commit()
                logger.info(f"Memory extraction completed and saved for user {uid}")

            except Exception as e:
                logger.error(f"Error during memory extraction for user {uid}: {e}", exc_info=True)
                await session.rollback()

    def _build_prompt(self, dialogue_str: str, existing_rules: List[Dict[str, Any]]) -> str:
        existing_rules_str = json.dumps(existing_rules, ensure_ascii=False) if existing_rules else "[]"
        return f"""Bạn là một chuyên gia phân tích bộ nhớ cho Trợ lý ảo Yuxi.
Nhiệm vụ của bạn là đọc các tin nhắn gần đây của cuộc hội thoại và trích xuất các thông tin quan trọng của người dùng để lưu trữ vào bộ nhớ dài hạn.

Hãy phân tích và phân loại thông tin thành 3 loại bộ nhớ dưới dạng JSON:
1. semantic (Facts/Sở thích/Thông tin cá nhân): Các thông tin khách quan, sở thích bền vững về người dùng (ví dụ: "User đang học ngôn ngữ Go", "User làm ở phòng Kế toán", "User tên là Nam").
2. episodic (Sự kiện/Bối cảnh cụ thể): Các sự kiện cụ thể có mốc thời gian hoặc bối cảnh diễn ra (ví dụ: "User vừa ký hợp đồng HD-1234 hôm nay", "User phàn nàn về lỗi kết nối cơ sở dữ liệu").
3. procedural (Quy tắc hành vi/Quy tắc tương tác): Các luật xưng hô hoặc hướng dẫn cách bot phản hồi do user yêu cầu (ví dụ: "Hãy xưng là Mèo và kêu meow", "Luôn trả lời ngắn gọn", "Không dùng emoji").

RÀNG BUỘC BẢO MẬT & ĐỘ TIN CẬY (CONFIDENCE SCORE):
- Đánh giá độ tin cậy `confidence_score` (từ 0.0 đến 1.0) cho mỗi mẩu tin.
- Chỉ gán score >= 0.8 cho các thông tin cực kỳ rõ ràng, trực tiếp, chắc chắn và phản ánh đúng về bản thân user.
- Các câu nói đùa, kể về người khác (ví dụ: "đồng nghiệp của tôi thích Go"), giả định, hoặc câu hỏi kỹ thuật thuần túy ("làm sao để cài docker?") KHÔNG được trích xuất hoặc phải gán score rất thấp (< 0.5).

DANH SÁCH LUẬT PROCEDURAL ĐANG ACTIVE CỦA USER:
{existing_rules_str}
Nếu một luật procedural mới bạn trích xuất được xung đột hoặc ghi đè một luật cũ ở trên, hãy điền ID của luật cũ đó vào trường `supersedes_id` (là kiểu số nguyên, ví dụ: 1). Nếu không ghi đè, để `supersedes_id` là null.

ĐỐI TƯỢNG HỘI THOẠI CẦN PHÂN TÍCH:
---
{dialogue_str}
---

Đầu ra của bạn PHẢI là một đối tượng JSON hợp lệ duy nhất có định dạng dưới đây (Không thêm bất kỳ text nào khác ngoài JSON):
{{
  "semantic": [
    {{"fact_text": "Nội dung fact...", "confidence_score": 0.9}}
  ],
  "episodic": [
    {{"event_summary": "Tóm tắt sự kiện...", "sentiment_score": 0.5, "confidence_score": 0.85}}
  ],
  "procedural": [
    {{"rule_text": "Nội dung luật...", "confidence_score": 0.95, "supersedes_id": null}}
  ]
}}
"""

    def _parse_llm_json(self, content: str) -> Optional[Dict[str, Any]]:
        # Extract json block if wrapped in markdown
        cleaned = content.strip()
        match = re.search(r"```json\s*(.*?)\s*```", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            try:
                # Try simple json load
                return json.loads(content)
            except Exception:
                return None

    async def _process_semantic_facts(self, uid: str, facts: List[Dict[str, Any]], session) -> None:
        for f in facts:
            fact_text = f.get("fact_text", "").strip()
            score = float(f.get("confidence_score", 0.0))
            if not fact_text:
                continue

            if score < 0.8:
                # Log rejected fact
                log = RejectedMemoryLog(
                    uid=uid,
                    raw_fact=fact_text,
                    memory_type="semantic",
                    confidence_score=score
                )
                session.add(log)
                continue

            # Check conflict: query similar facts from Milvus
            similar_facts = await self.milvus_store.search_facts(uid, fact_text, limit=3)
            new_fact_id = str(uuid.uuid4())

            for old_fact in similar_facts:
                # Cosine similarity threshold > 0.85
                if old_fact.get("distance", 0.0) > 0.85:
                    logger.info(f"Semantic fact conflict detected: '{fact_text}' overrides '{old_fact['fact_text']}'")
                    await self.milvus_store.deactivate_fact(uid, old_fact["id"], superseded_by=new_fact_id)

            # Insert new fact
            await self.milvus_store.insert_fact(
                uid=uid,
                fact_id=new_fact_id,
                fact_text=fact_text,
                confidence_score=score
            )

    async def _process_episodic_memories(self, uid: str, thread_id: str, events: List[Dict[str, Any]], session) -> None:
        for e in events:
            summary = e.get("event_summary", "").strip()
            score = float(e.get("confidence_score", 0.0))
            sentiment = float(e.get("sentiment_score", 0.0))
            if not summary:
                continue

            if score < 0.8:
                log = RejectedMemoryLog(
                    uid=uid,
                    raw_fact=summary,
                    memory_type="episodic",
                    confidence_score=score
                )
                session.add(log)
                continue

            # Store in Postgres
            mem = UserEpisodicMemory(
                uid=uid,
                thread_id=thread_id,
                event_summary=summary,
                sentiment_score=sentiment,
                confidence_score=score,
                is_archived=False
            )
            session.add(mem)

    async def _process_procedural_rules(self, uid: str, rules: List[Dict[str, Any]], session) -> None:
        for r in rules:
            rule_text = r.get("rule_text", "").strip()
            score = float(r.get("confidence_score", 0.0))
            supersedes_id = r.get("supersedes_id")
            if not rule_text:
                continue

            if score < 0.8:
                log = RejectedMemoryLog(
                    uid=uid,
                    raw_fact=rule_text,
                    memory_type="procedural",
                    confidence_score=score
                )
                session.add(log)
                continue

            # Check if it supersedes an active rule
            if supersedes_id is not None:
                try:
                    old_id = int(supersedes_id)
                    # Fetch old rule to deactivate
                    stmt = select(UserProceduralMemory).where(
                        UserProceduralMemory.id == old_id,
                        UserProceduralMemory.uid == uid
                    )
                    res = await session.execute(stmt)
                    old_rule = res.scalar_one_or_none()
                    if old_rule:
                        old_rule.is_active = False
                        logger.info(f"Procedural rule ID {old_id} deactivated by user {uid}")
                except (ValueError, TypeError) as err:
                    logger.warning(f"Invalid supersedes_id '{supersedes_id}': {err}")

            # Store new rule
            new_rule = UserProceduralMemory(
                uid=uid,
                rule_text=rule_text,
                is_active=True,
                confidence_score=score
            )
            session.add(new_rule)
