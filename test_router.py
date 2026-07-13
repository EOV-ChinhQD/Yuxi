import sys
import os
import asyncio
from pprint import pprint

# Setup path so we can import yuxi
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend', 'package')))

from yuxi.knowledge.retrieval.router import SemanticRouter

async def test_router():
    queries = [
        # CHIT_CHAT
        "Chào bạn",
        "Xin chào",
        "Ok",
        "Cảm ơn",
        
        # EXACT_MATCH
        "Cho tôi xem hợp đồng HD-1234",
        "Điều khoản thanh toán trong HD-4567 là gì?",
        "Thông tư 15/2026/TT-BXD quy định thế nào?",
        
        # SUMMARIZATION
        "Tóm tắt toàn bộ hợp đồng HD-9999",
        "Tóm tắt tài liệu quy chế công ty",
        
        # STRUCTURED_AGGREGATION
        "Có bao nhiêu hợp đồng trong tháng 5?",
        "Tổng doanh thu quý 2 là bao nhiêu?",
        
        # AMBIGUOUS
        "Tìm tài liệu đó đi",
        "Tóm tắt nó lại",
        
        # OUT_OF_DOMAIN
        "Thời tiết hôm nay thế nào?",
        "Ai là tổng thống Mỹ?",
        "1 + 1 bằng mấy?",
        
        # MULTI_HOP
        "So sánh quy trình A và quy trình B",
        "Chính sách nghỉ phép của công ty A khác gì so với công ty B?",
        
        # NAIVE_SEARCH
        "Quy định nghỉ phép là gì?",
        "Làm sao để thanh toán công tác phí?",
        
        # EDGE CASES
        "Chào bạn, hợp đồng HD-1234 hết hạn chưa?"  # Should NOT be CHIT_CHAT, probably EXACT_MATCH or NAIVE_SEARCH
    ]
    
    print("=== BẮT ĐẦU TEST SEMANTIC ROUTER ===")
    for q in queries:
        print(f"\nQuery: '{q}'")
        try:
            route, details = await SemanticRouter.route(q, llm_model_spec="gpt-4o-mini")
            print(f" -> Route: {route.value}")
            print(f" -> Details: {details}")
        except Exception as e:
            print(f" -> ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_router())
