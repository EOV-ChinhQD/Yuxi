import re
import asyncio
from enum import Enum
from typing import Any

import json_repair

from yuxi.utils import logger
from yuxi.models import select_model


class RouteType(str, Enum):
    # --- Pre-Retrieval Classification (Định tuyến trước khi tìm kiếm) ---
    CHIT_CHAT = "CHIT_CHAT"
    OUT_OF_DOMAIN = "OUT_OF_DOMAIN"
    AMBIGUOUS = "AMBIGUOUS"
    EXACT_MATCH = "EXACT_MATCH"
    SUMMARIZATION = "SUMMARIZATION"
    STRUCTURED_AGGREGATION = "STRUCTURED_AGGREGATION"
    MULTI_HOP = "MULTI_HOP"
    NAIVE_SEARCH = "NAIVE_SEARCH"

    # --- Post-Retrieval Decision (Định tuyến sau khi tìm kiếm thất bại) ---
    # Nhãn này chỉ được kích hoạt bởi Agent Loop khi lần query đầu tiên trả về rỗng,
    # kích hoạt cơ chế rewrite query và thử lại tối đa 1 lần (MAX_REWRITE_ATTEMPTS = 1).
    RETRY_WITH_REWRITE = "RETRY_WITH_REWRITE"


class SemanticRouter:
    """
    Định tuyến ngữ nghĩa cho truy vấn người dùng, giảm thiểu các cuộc gọi
    vector DB không cần thiết và chống ảo giác.
    """

    # Heuristics cho Chit-chat (Full match hoặc rất ngắn)
    _CHIT_CHAT_PATTERN = re.compile(
        r"^(chào|xin chào|chào bạn|hi|hello|cảm ơn|thank you|ok|okay)[\s!\.]*$", re.IGNORECASE
    )

    # Heuristics cho Exact Match (Số hiệu văn bản, hợp đồng, quyết định...)
    _EXACT_MATCH_PATTERN = re.compile(
        r"\b(hd|tt|nđ|qđ|tt-gdtx|luật)-\d+[\w/-]*\b|\b(thông tư|nghị định|quyết định|hợp đồng)\s+(số\s+)?\d+[\w/-]*\b",
        re.IGNORECASE,
    )

    # Heuristics cho Summarization (Yêu cầu tóm tắt tài liệu cụ thể)
    _SUMMARIZATION_PATTERN = re.compile(
        r"^(tóm tắt|sơ lược|tóm lược)\s+(tài liệu|văn bản|hợp đồng|quy chế|quy định|thông tư|nghị định)\s+.+$",
        re.IGNORECASE,
    )

    # Ngưỡng tự tin tối thiểu từ LLM, nếu thấp hơn sẽ fallback về NAIVE_SEARCH
    CONFIDENCE_THRESHOLD = 0.7

    @classmethod
    def _heuristic_check(cls, query: str) -> RouteType | None:
        """Kiểm tra nhanh bằng Regex trước khi gọi LLM."""
        query_clean = query.strip().lower()
        if cls._CHIT_CHAT_PATTERN.match(query_clean):
            logger.info(f"[SemanticRouter] Heuristic matched CHIT_CHAT for query: '{query}'")
            return RouteType.CHIT_CHAT

        if cls._EXACT_MATCH_PATTERN.search(query_clean):
            logger.info(f"[SemanticRouter] Heuristic matched EXACT_MATCH for query: '{query}'")
            return RouteType.EXACT_MATCH

        if cls._SUMMARIZATION_PATTERN.match(query_clean):
            logger.info(f"[SemanticRouter] Heuristic matched SUMMARIZATION for query: '{query}'")
            return RouteType.SUMMARIZATION

        return None

    @classmethod
    async def route(
        cls, query: str, llm_model_spec: str = "gpt-4o-mini", chat_history: list[dict[str, str]] = None
    ) -> tuple[RouteType, dict[str, Any]]:
        """
        Phân loại câu hỏi thành 1 trong 8 Route Types.
        Trả về (RouteType, details_dict).
        """
        # 1. Fast Heuristic Check
        heuristic_route = cls._heuristic_check(query)
        if heuristic_route:
            return heuristic_route, {"confidence_score": 1.0, "reasoning": "Heuristic match"}

        # 2. LLM Classification
        logger.info(f"[SemanticRouter] Calling LLM Router for query: '{query[:60]}...'")

        prompt = f"""Select the best routing label for this enterprise query.
Labels:
1. CHIT_CHAT: General greeting/thanking.
2. OUT_OF_DOMAIN: Out-of-scope (weather, math, history).
3. AMBIGUOUS: Vague queries (e.g. "find that file").
4. EXACT_MATCH: Searching a specific ID/code (e.g. TT-15, HD-102).
5. SUMMARIZATION: Summarize a specific document.
6. STRUCTURED_AGGREGATION: Counting, summation, database query.
7. MULTI_HOP: Comparing/synthesizing multiple documents.
8. NAIVE_SEARCH: General search. Fallback if unsure.

Query: "{query}"

Output ONLY valid JSON:
{{
  "route_type": "<LABEL>",
  "confidence_score": <float 0-1>,
  "reasoning": "<10-word explanation>"
}}"""
        try:
            from yuxi.models.providers.cache import model_cache

            actual_model_spec = llm_model_spec
            if not model_cache.get_model_info(actual_model_spec):
                available = model_cache.get_all_specs("chat")
                if available:
                    actual_model_spec = available[0].spec
                    logger.info(
                        f"[SemanticRouter] Fallback model spec from '{llm_model_spec}' to '{actual_model_spec}'"
                    )
            model = select_model(model_spec=actual_model_spec)
            response = await asyncio.wait_for(model.call(prompt, stream=False), timeout=10.0)
            raw = response.content.strip()

            # Tìm JSON trong output
            match = re.search(r"\{[\s\S]*\}", raw)
            if not match:
                logger.warning(f"[SemanticRouter] LLM output not JSON. Raw: {raw}. Fallback to NAIVE_SEARCH")
                return RouteType.NAIVE_SEARCH, {"confidence_score": 0.0, "reasoning": "JSON parse error"}

            data = json_repair.loads(match.group())
            route_str = data.get("route_type", "NAIVE_SEARCH").upper()
            confidence = float(data.get("confidence_score", 0.0))
            reasoning = data.get("reasoning", "")

            if route_str not in RouteType.__members__:
                logger.warning(f"[SemanticRouter] Invalid route type '{route_str}'. Fallback to NAIVE_SEARCH")
                return RouteType.NAIVE_SEARCH, {
                    "confidence_score": confidence,
                    "reasoning": f"Invalid type parsed: {route_str}",
                }

            final_route = RouteType[route_str]

            if confidence < cls.CONFIDENCE_THRESHOLD:
                logger.warning(
                    f"[SemanticRouter] Low confidence {confidence} for route {final_route.value}. Fallback to NAIVE_SEARCH"
                )
                return RouteType.NAIVE_SEARCH, {
                    "confidence_score": confidence,
                    "reasoning": f"Low confidence fallback. Original reasoning: {reasoning}",
                }

            logger.info(f"[SemanticRouter] Successfully routed to {final_route.value} (conf: {confidence})")
            return final_route, data

        except TimeoutError:
            logger.error("[SemanticRouter] LLM timeout. Fallback to NAIVE_SEARCH")
            return RouteType.NAIVE_SEARCH, {"confidence_score": 0.0, "reasoning": "Timeout error"}
        except Exception as e:
            logger.error(f"[SemanticRouter] Error routing query: {e}. Fallback to NAIVE_SEARCH")
            return RouteType.NAIVE_SEARCH, {"confidence_score": 0.0, "reasoning": str(e)}
