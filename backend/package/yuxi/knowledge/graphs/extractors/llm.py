from __future__ import annotations

from typing import Any

import asyncio
import json_repair

from yuxi.models.chat import select_model

from .base import GraphExtractor

# Global Semaphore for LLM Graph Extraction to prevent rate limits
_global_llm_semaphore = None


def get_llm_semaphore(limit: int = 10) -> asyncio.Semaphore:
    global _global_llm_semaphore
    if _global_llm_semaphore is None:
        _global_llm_semaphore = asyncio.Semaphore(limit)
    return _global_llm_semaphore


DEFAULT_TRIPLE_EXTRACTION_PROMPT = """Vui lòng trích xuất các thực thể và mối quan hệ thực thể từ văn bản bên dưới, trả về JSON chuẩn, không in ra lời giải thích.
JSON Format:
{
  "relations": [
    {
      "source": {"text": "entity text", "label": "Entity type", "attributes": [{"text": "attribute value", "label": "Property name"}]},
      "target": {"text": "entity text", "label": "Entity type", "attributes": [{"text": "attribute value", "label": "Property name"}]},
      "text": "Relationship display text",
      "label": "Relationship type"
    }
  ]
}
"""

SCHEMA_INSTRUCTION = """Extract Schema constraints:
{schema}
"""


class LLMGraphExtractor(GraphExtractor):
    extractor_type = "llm"

    def validate_options(self) -> None:
        if not self.options.get("model_spec"):
            raise ValueError("Bộ trích xuất LLM cần model_spec")
        if self.options.get("prompt"):
            raise ValueError(
                "Bộ trích xuất đồ thị LLM không hỗ trợ Prompt tùy chỉnh đầy đủ, vui lòng sử dụng schema để cấu hình ràng buộc"
            )
        concurrency_count = self.options.get("concurrency_count", 1)
        try:
            concurrency_count = int(concurrency_count)
        except (TypeError, ValueError) as exc:
            raise ValueError("concurrency_count của bộ trích xuất LLM phải là số nguyên") from exc
        if concurrency_count < 1 or concurrency_count > 1000:
            raise ValueError("concurrency_count của bộ trích xuất LLM phải từ 1 đến 1000")
        if self.options.get("model_params") is not None and not isinstance(self.options["model_params"], dict):
            raise ValueError("model_params của bộ trích xuất LLM phải là object")

    async def extract(self, text: str, *, chunk_metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        self.validate_options()
        semaphore = get_llm_semaphore(10)
        async with semaphore:
            model = select_model(
                model_spec=self.options["model_spec"],
                timeout=60.0,
                model_params=self.options.get("model_params") or {},
            )
            prompt = self._build_prompt(text)
            response = await model.call(prompt, stream=False)
            parsed = json_repair.loads(response.content if response else "")
            return parsed

    def _build_prompt(self, text: str) -> str:
        extraction_prompt = DEFAULT_TRIPLE_EXTRACTION_PROMPT
        schema = str(self.options.get("schema") or "").strip()
        if schema:
            extraction_prompt = f"{extraction_prompt}\n{SCHEMA_INSTRUCTION.format(schema=schema)}"
        return f"{extraction_prompt}\n\nText:\n{text}"
