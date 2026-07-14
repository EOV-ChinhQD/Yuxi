import re
import json
import asyncio
from enum import Enum
from typing import Tuple, Dict, Any, List

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
    _CHIT_CHAT_PATTERN = re.compile(r"^(chào|xin chào|chào bạn|hi|hello|cảm ơn|thank you|ok|okay)[\s!\.]*$", re.IGNORECASE)
    
    # Ngưỡng tự tin tối thiểu từ LLM, nếu thấp hơn sẽ fallback về NAIVE_SEARCH
    CONFIDENCE_THRESHOLD = 0.7
    
    @classmethod
    def _heuristic_check(cls, query: str) -> RouteType | None:
        """Kiểm tra nhanh bằng Regex trước khi gọi LLM."""
        query_clean = query.strip().lower()
        if cls._CHIT_CHAT_PATTERN.match(query_clean):
            logger.info(f"[SemanticRouter] Heuristic matched CHIT_CHAT for query: '{query}'")
            return RouteType.CHIT_CHAT
            
        return None

    @classmethod
    async def route(cls, query: str, llm_model_spec: str = "gpt-4o-mini", chat_history: List[Dict[str, str]] = None) -> Tuple[RouteType, Dict[str, Any]]:
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
        
        prompt = f"""Bạn là bộ định tuyến truy vấn (Semantic Router) của một hệ thống RAG doanh nghiệp. 
Nhiệm vụ của bạn là phân loại câu hỏi của người dùng vào ĐÚNG MỘT trong các nhãn sau.

CÁC NHÃN ĐỊNH TUYẾN:
1. CHIT_CHAT: Giao tiếp thông thường toàn câu (chào hỏi, cảm ơn).
2. OUT_OF_DOMAIN: Hỏi vấn đề ngoài lề (Thời tiết, tin tức chung, lịch sử, toán học cơ bản không liên quan công việc).
3. AMBIGUOUS: Truy vấn quá mơ hồ ("Tìm tài liệu đó đi" mà không nói tài liệu nào).
4. EXACT_MATCH: Truy vấn có chứa MÃ SỐ, ID CỤ THỂ, SỐ HIỆU VĂN BẢN (VD: HD-1234, thông tư 15) và chỉ nhằm mục đích tra cứu thông tin của văn bản đó.
5. SUMMARIZATION: Yêu cầu tóm tắt TOÀN BỘ một tài liệu/quy chế cụ thể. Lưu ý: Nếu yêu cầu tóm tắt nhưng không nói rõ tài liệu nào, hãy chọn AMBIGUOUS.
6. STRUCTURED_AGGREGATION: Các câu hỏi tính toán, đếm số lượng, tổng doanh thu ("Có bao nhiêu hợp đồng trong tháng 5?").
7. MULTI_HOP: So sánh, đối chiếu, tổng hợp đa chiều giữa từ 2 đối tượng/vấn đề trở lên ("So sánh quy trình A và quy trình B").
8. NAIVE_SEARCH: Tra cứu kiến thức, định nghĩa, thông tin thông thường ("Quy định nghỉ phép là gì?"). Chọn nhãn này nếu không chắc chắn.

TRUY VẤN CỦA NGƯỜI DÙNG:
"{query}"

YÊU CẦU ĐẦU RA: 
Trích xuất dưới dạng JSON hợp lệ với cấu trúc sau, KHÔNG giải thích thêm:
{{
  "route_type": "<CHỌN_1_NHÃN_Ở_TRÊN>",
  "confidence_score": <số thực từ 0.0 đến 1.0>,
  "reasoning": "<Lý do ngắn gọn dưới 20 từ>"
}}
"""
        try:
            model = select_model(model_spec=llm_model_spec)
            response = await asyncio.wait_for(model.call(prompt, stream=False), timeout=10.0)
            raw = response.content.strip()
            
            # Tìm JSON trong output
            match = re.search(r'\{[\s\S]*\}', raw)
            if not match:
                logger.warning(f"[SemanticRouter] LLM output not JSON. Raw: {raw}. Fallback to NAIVE_SEARCH")
                return RouteType.NAIVE_SEARCH, {"confidence_score": 0.0, "reasoning": "JSON parse error"}
                
            data = json_repair.loads(match.group())
            route_str = data.get("route_type", "NAIVE_SEARCH").upper()
            confidence = float(data.get("confidence_score", 0.0))
            reasoning = data.get("reasoning", "")
            
            if route_str not in RouteType.__members__:
                logger.warning(f"[SemanticRouter] Invalid route type '{route_str}'. Fallback to NAIVE_SEARCH")
                return RouteType.NAIVE_SEARCH, {"confidence_score": confidence, "reasoning": f"Invalid type parsed: {route_str}"}
            
            final_route = RouteType[route_str]
            
            if confidence < cls.CONFIDENCE_THRESHOLD:
                logger.warning(f"[SemanticRouter] Low confidence {confidence} for route {final_route.value}. Fallback to NAIVE_SEARCH")
                return RouteType.NAIVE_SEARCH, {"confidence_score": confidence, "reasoning": f"Low confidence fallback. Original reasoning: {reasoning}"}
                
            logger.info(f"[SemanticRouter] Successfully routed to {final_route.value} (conf: {confidence})")
            return final_route, data
            
        except asyncio.TimeoutError:
            logger.error("[SemanticRouter] LLM timeout. Fallback to NAIVE_SEARCH")
            return RouteType.NAIVE_SEARCH, {"confidence_score": 0.0, "reasoning": "Timeout error"}
        except Exception as e:
            logger.error(f"[SemanticRouter] Error routing query: {e}. Fallback to NAIVE_SEARCH")
            return RouteType.NAIVE_SEARCH, {"confidence_score": 0.0, "reasoning": str(e)}
