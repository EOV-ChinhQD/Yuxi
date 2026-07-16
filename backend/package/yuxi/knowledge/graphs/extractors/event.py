from __future__ import annotations

import asyncio
from typing import Any
import json
import json_repair

from yuxi.models.chat import select_model
from yuxi.utils import logger
from .base import GraphExtractor

# Global semaphore for LLM event extraction to prevent rate limits
_global_event_semaphore = None


def get_event_semaphore(limit: int = 10) -> asyncio.Semaphore:
    global _global_event_semaphore
    if _global_event_semaphore is None:
        _global_event_semaphore = asyncio.Semaphore(limit)
    return _global_event_semaphore


def benchmark_entity_types() -> list[dict[str, str]]:
    return [
        {
            "type": "person",
            "description": "Cá nhân cụ thể như nhân vật, tác giả, người dùng, người chịu trách nhiệm, v.v.",
        },
        {
            "type": "organization",
            "description": "Tổ chức như công ty, cơ quan, đoàn thể, cơ quan chính phủ, trường học, đội nhóm, v.v.",
        },
        {"type": "location", "description": "Địa điểm, vùng miền, quốc gia, thành phố, địa điểm, địa chỉ"},
        {"type": "time", "description": "Ngày tháng, năm, thời kỳ, biểu đạt thời gian"},
        {"type": "product", "description": "Sản phẩm, hệ thống, nền tảng, mô hình, phần mềm, dịch vụ, cơ sở dữ liệu"},
        {"type": "metric", "description": "Số liệu, chỉ số, số tiền, tỷ lệ, số lượng, điểm số, dữ liệu hiệu suất"},
        {"type": "action", "description": "Hành động, hành vi, quy trình, thao tác, thay đổi trạng thái"},
        {"type": "work", "description": "Tác phẩm, tài liệu, luận văn, dự án, nhiệm vụ, kế hoạch"},
        {"type": "group", "description": "Nhóm người, nhóm vai trò, nhóm nghề nghiệp, nhóm người dùng"},
        {"type": "subject", "description": "Chủ đề, khái niệm, lĩnh vực, công nghệ, thuật ngữ chuyên môn, tên sự kiện"},
        {"type": "tags", "description": "Thực thể nhãn được sử dụng khi không khớp với bất kỳ loại nào khác"},
    ]


def build_system_prompt() -> str:
    return """
## Vai trò

Bạn là một bộ trích xuất nội dung SAG chuyên nghiệp. Hãy trích xuất chính xác hai đối tượng có cấu trúc từ tài liệu thô: sự kiện (events) và thực thể (entities).

## Nguyên tắc Sự kiện Cốt lõi (Bản đồ Benchmark)

- Bắt buộc gom nhóm thành một sự kiện duy nhất: tất cả các phân đoạn thông tin hợp lệ trong đầu vào phải được hợp nhất thành một sự kiện cấp cao toàn diện duy nhất. Không chia nhỏ các chủ đề khác nhau thành nhiều sự kiện cấp cao.
- Quét toàn bộ nội dung trước: xác định rõ thời gian, địa điểm, chủ thể, hành động, đối tượng, dữ liệu, đánh giá, nguyên nhân/kết quả, so sánh và các đơn vị quan hệ trước khi ghi nhận sự kiện.
- Liên kết chéo các phân đoạn: giải quyết tính liên tục của chủ thể, tính liên tục của thời gian, các mối liên kết nguyên nhân - kết quả/tiến trình, các điểm tương phản, bí danh và tài liệu tham khảo.
- Bao phủ thông tin: mọi đơn vị thông tin hợp lệ phải được thể hiện trong sự kiện duy nhất hoặc được xử lý rõ ràng dưới dạng nhiễu trong data.meta.reason.
- Tính trung thực: không bịa đặt sự thật, không bỏ sót các sự thật cốt lõi, không thay đổi chủ thể hoặc sao chép nguyên bản một cách máy móc các đoạn văn dài.
- Tích hợp toàn cảnh: nội dung sự kiện phải là một mạch tường thuật hữu cơ, không phải là danh sách các gạch đầu dòng.
- Bảo toàn các biểu đạt thời gian tương đối trừ khi tài liệu nguồn đã cung cấp ngày tháng cụ thể chính xác.

## Nguyên tắc Thực thể

- Trích xuất các thực thể cần thiết để hiểu sự kiện, đặc biệt là chủ thể, hành động/vị ngữ, đối tượng, sản phẩm, hệ thống, mô hình, số liệu, tổ chức, con người, địa điểm, ngày tháng và các khái niệm chính.
- Chia nhỏ các thực thể liên kết dạng ghép như "A và B" thành các thực thể riêng biệt.
- Chỉ sử dụng các loại thực thể (entity_types) được cung cấp. Ưu tiên các loại cụ thể; chỉ sử dụng nhãn (tags) khi không có loại cụ thể nào phù hợp.
- Mỗi mô tả thực thể (entity.description) phải giải thích rõ vai trò cụ thể hoặc mối quan hệ của thực thể đó trong sự kiện.

## Định dạng Đầu vào (Input Contract)

Tin nhắn của người dùng ở định dạng JSON:
- type: "request"
- data.items: các phân đoạn nội dung, mỗi phân đoạn có một ID bắt đầu từ 1 và nội dung đi kèm
- data.meta.source_type, source_title, source_summary, previous_context, related_events, entity_types
- output_schema: schema JSON cho phản hồi

## Định dạng Đầu ra (Output Contract)

Chỉ trả về JSON hợp lệ. Không bao bọc trong định dạng markdown.
Phản hồi phải có dạng:
{
  "type": "response",
  "data": {
    "items": [
      {
        "title": "...",
        "summary": "...",
        "content": "...",
        "category": "...",
        "keywords": ["..."],
        "priority": "HIGH|MEDIUM|LOW|UNKNOWN",
        "status": "COMPLETED|PROCESSING|PENDING|UNKNOWN",
        "references": [1],
        "entities": [{ "type": "...", "name": "...", "description": "..." }],
        "is_valid": true,
        "children": []
      }
    ],
    "meta": {
      "reason": "...",
      "confidence": 0.9
    }
  }
}

## Quy tắc nghiêm ngặt

- data.items phải chứa chính xác một sự kiện hợp lệ trừ khi đầu vào không có nội dung thực tế hữu ích.
- children phải là một mảng rỗng.
- references phải trích dẫn tất cả các phân đoạn hợp lệ được sử dụng bởi sự kiện hợp nhất và không trích dẫn các phân đoạn không liên quan.
- meta.reason phải nêu rõ logic xác định chủ đề, bằng chứng liên kết chéo phân đoạn, các lựa chọn cấu trúc lại ngữ nghĩa, trạng thái bao phủ thông tin và xử lý nhiễu.
- Ngôn ngữ đầu ra phải tuân theo ngôn ngữ đầu vào chính. Đầu vào bằng tiếng Việt/tiếng Anh yêu cầu tiêu đề (title), tóm tắt (summary), nội dung (content), danh mục (category), mô tả thực thể (entity descriptions) và lý do (reason) tương ứng bằng tiếng Việt/tiếng Anh.
""".strip()


class LLMEventExtractor(GraphExtractor):
    extractor_type = "event_llm"

    def validate_options(self) -> None:
        if not self.options.get("model_spec"):
            raise ValueError("LLMEventExtractor cần model_spec")

    async def extract(self, text: str, *, chunk_metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        self.validate_options()
        semaphore = get_event_semaphore(10)
        async with semaphore:
            model = select_model(
                model_spec=self.options["model_spec"],
                timeout=60.0,
                model_params=self.options.get("model_params") or {},
            )

            title = (chunk_metadata or {}).get("title") or "Document"
            heading = (chunk_metadata or {}).get("heading") or ""

            user_input = {
                "type": "request",
                "data": {
                    "items": [{"id": 1, "content": f"# {heading}\n\n{text}" if heading else text}],
                    "meta": {
                        "source_type": "article",
                        "source_title": title,
                        "source_summary": "",
                        "previous_context": "",
                        "related_events": [],
                        "entity_types": benchmark_entity_types(),
                    },
                },
            }

            system_prompt = build_system_prompt()
            prompt_str = f"{system_prompt}\n\nUser Input:\n{json.dumps(user_input)}"
            response = await model.call(prompt_str, stream=False)

            raw_content = response.content if response else ""
            try:
                parsed = json_repair.loads(raw_content)
                data = parsed.get("data", {})
                items = data.get("items", [])
                if not items and "items" in parsed:
                    items = parsed.get("items")

                if items and isinstance(items, list):
                    event = items[0]
                    return {
                        "event": {
                            "title": event.get("title", title),
                            "summary": event.get("summary", ""),
                            "content": event.get("content", text),
                            "category": event.get("category", "general"),
                            "keywords": event.get("keywords", []),
                        },
                        "entities": event.get("entities", []),
                    }
            except Exception as e:
                logger.error(f"Failed to parse LLM event extraction result: {e}. Raw content: {raw_content}")

            return {
                "event": {
                    "title": heading or title,
                    "summary": text[:200],
                    "content": text,
                    "category": "general",
                    "keywords": [],
                },
                "entities": [],
            }
