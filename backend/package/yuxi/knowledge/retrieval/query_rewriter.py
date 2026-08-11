import re
from typing import Any
import json_repair

from yuxi.utils import logger
from yuxi.models import select_model

def _heuristic_should_rewrite(query: str) -> bool:
    """
    Kiểm tra nhanh xem có nên rewrite query không để tiết kiệm token.
    Rewrite nếu:
    - Câu truy vấn ngắn (<= 5 từ)
    - Có chứa từ viết hoa toàn bộ (khả năng là viết tắt)
    """
    words = query.strip().split()
    if len(words) <= 5:
        return True
    
    # Phát hiện viết tắt (VD: HDSD, QCVN, Bơm ly tâm P-101)
    if any(w.isupper() and len(w) >= 2 for w in words):
        return True

    return False

class QueryRewriter:
    @staticmethod
    async def rewrite(query: str, llm_model_spec: str) -> list[str]:
        """
        Nhận vào câu truy vấn và trả về danh sách các chuỗi mở rộng (từ đồng nghĩa, viết tắt).
        Nếu không cần thiết, trả về rỗng.
        """
        if not _heuristic_should_rewrite(query):
            logger.debug(f"[QueryRewriter] Heuristic: Skip rewriting for '{query[:60]}'")
            return []

        logger.info(f"[QueryRewriter] Heuristic triggered, rewriting '{query[:60]}'...")

        prompt = f"""Phân tích câu hỏi sau và trả về JSON chứa các từ đồng nghĩa hoặc cách viết đầy đủ của từ viết tắt.
Không giải thích thêm. Chỉ mở rộng danh từ, thuật ngữ chuyên ngành. KHÔNG mở rộng các từ hỏi (như thế nào, tại sao).

Câu hỏi: {query}

Trả về JSON:
{{
  "original": "{query}",
  "expansions": ["từ đồng nghĩa 1", "từ đồng nghĩa 2"],
  "abbreviations": ["cách viết đầy đủ 1"]
}}

Lưu ý: Nếu không có từ đồng nghĩa nào phù hợp, để mảng rỗng [].
"""

        try:
            model = select_model(llm_model_spec)
            response = await model.ainvoke(prompt)
            raw_text = response.content if hasattr(response, "content") else str(response)

            data = json_repair.loads(raw_text)
            
            expansions = []
            if isinstance(data, dict):
                expansions.extend(data.get("expansions", []))
                expansions.extend(data.get("abbreviations", []))
                
            return [e for e in expansions if isinstance(e, str) and e.strip()]
        except Exception as e:
            logger.warning(f"[QueryRewriter] Failed to rewrite query: {e}")
            return []
