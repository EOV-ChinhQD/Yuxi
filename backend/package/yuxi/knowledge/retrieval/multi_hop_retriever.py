import re
import json
import asyncio
from typing import List, Dict, Tuple, Any
from yuxi.utils import logger
from yuxi.models import select_model

_MULTI_HOP_PATTERNS = re.compile(
    r"\b(so sánh|khác nhau|khác biệt|giống nhau|tương đồng|"
    r"đồng thời|cả hai|cả .+ và|giữa .+ và|"
    r"máy .+ và máy|hệ thống .+ và hệ thống|thiết bị .+ và thiết bị)\b",
    re.IGNORECASE,
)

_SINGLE_HOP_EXCLUDE = re.compile(
    r"\b(một|duy nhất|chỉ|riêng)\b",
    re.IGNORECASE,
)

def _heuristic_is_multi_hop(question: str) -> bool:
    """Kiểm tra nhanh bằng regex trước khi gọi LLM."""
    if _SINGLE_HOP_EXCLUDE.search(question) and not _MULTI_HOP_PATTERNS.search(question):
        return False
    return bool(_MULTI_HOP_PATTERNS.search(question))

async def detect_and_decompose(question: str, llm_model_spec: str) -> Tuple[bool, List[str]]:
    """
    Phát hiện multi-hop và phân rã câu hỏi thành sub-queries.
    Returns: (is_multi_hop, sub_queries)
    """
    if not _heuristic_is_multi_hop(question):
        logger.debug(f"[MultiHop] Heuristic: single-hop — '{question[:60]}'")
        return False, []

    logger.info(f"[MultiHop] Heuristic triggered, calling LLM decomposer...")
    
    prompt = f"""Phân tích câu hỏi sau và trả về JSON. Không giải thích thêm.

Multi-hop = câu hỏi SO SÁNH hoặc hỏi về ÍT NHẤT 2 thực thể/thiết bị/quy trình khác nhau.
Single-hop = câu hỏi về 1 chủ đề duy nhất.

Câu hỏi: {question}

Trả về JSON:
{{
  "is_multi_hop": true/false,
  "reason": "lý do ngắn",
  "sub_queries": ["câu hỏi con 1 tự lập đầy đủ", "câu hỏi con 2 tự lập đầy đủ"]
}}

Lưu ý: nếu is_multi_hop=false thì sub_queries=[]. Tối đa 3 sub_queries.
"""

    try:
        model = select_model(model_spec=llm_model_spec)
        response = await asyncio.wait_for(model.call(prompt), timeout=15.0)
        raw = response.content.strip()

        # Tìm JSON trong output
        match = re.search(r'\{[\s\S]*\}', raw)
        if not match:
            logger.warning("[MultiHop] LLM did not return valid JSON, fallback to single-hop")
            return False, []

        data = json.loads(match.group())
        is_multi = bool(data.get("is_multi_hop", False))
        sub_queries = [q.strip() for q in data.get("sub_queries", []) if q.strip()]

        logger.info(
            f"[MultiHop] is_multi_hop={is_multi} | reason={data.get('reason', '')} | "
            f"sub_queries={sub_queries}"
        )

        if not is_multi or len(sub_queries) < 2:
            return False, []

        return True, sub_queries[:3]  # Tối đa 3 sub-queries

    except asyncio.TimeoutError:
        logger.warning("[MultiHop] LLM decomposer timeout — fallback to single-hop")
        return False, []
    except Exception as e:
        logger.warning(f"[MultiHop] Decompose error: {e} — fallback to single-hop")
        return False, []

async def multi_hop_retrieve_labeled(
    sub_queries: List[str],
    retriever: Any,
    **kwargs
) -> Dict[str, Any]:
    """
    Chạy retriever song song cho từng sub-query và gộp kết quả có gắn nhãn nguồn.
    """
    async def _retrieve_one(sub_q: str) -> List[Dict[str, Any]]:
        try:
            res = await retriever(sub_q, **kwargs)
            chunks = res.get("results", [])
            # Gắn nhãn nguồn vào đầu content để Agent dễ so sánh
            for c in chunks:
                if "content" in c:
                    c["content"] = f"[Nguồn tin cho câu hỏi con: {sub_q}]\n{c['content']}"
            return chunks
        except Exception as e:
            logger.error(f"[MultiHop] Retrieve failed for '{sub_q}': {e}")
            return []

    tasks = [
        _retrieve_one(q)
        for q in sub_queries
    ]
    results = await asyncio.gather(*tasks)

    # Gộp & loại bỏ trùng lặp dựa trên chunk_id hoặc content
    seen_ids = set()
    merged_results = []
    
    for chunk_list in results:
        for chunk in chunk_list:
            cid = chunk.get("chunk_id") or chunk.get("content", "")[:50]
            if cid not in seen_ids:
                seen_ids.add(cid)
                merged_results.append(chunk)

    logger.info(f"[MultiHop] Merged {len(merged_results)} unique chunks from {len(sub_queries)} sub-queries")
    
    return {
        "results": merged_results
    }
