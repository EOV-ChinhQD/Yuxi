import os
from pathlib import Path

from yuxi.config.app import config
from yuxi.models import select_model
from yuxi.utils import logger

# region guard_prompt
PROMPT_TEMPLATE = """
# Hướng dẫn
Bạn là một trợ lý phát hiện tuân thủ nội dung. Vui lòng đánh giá xem nội dung dưới đây có đáp ứng các yêu cầu tuân thủ hay không dựa trên tập quy tắc được cung cấp.

# Quy tắc tuân thủ
1. Nội dung không được chứa bất kỳ thông tin nào vi phạm pháp luật Việt Nam hoặc pháp luật quốc tế (ví dụ: bạo lực, khủng bố, ngôn từ kích động thù địch).
2. Nội dung không được xâm phạm quyền riêng tư cá nhân hoặc tiết lộ thông tin nhạy cảm.
3. Nội dung không được mang tính kích động hoặc nhạy cảm dưới bất kỳ hình thức nào.

# Nội dung đầu ra
Compliance/Non-compliance (chỉ trả về một trong hai từ này, không thêm bất kỳ từ ngữ nào khác)

# Ví dụ
Nội dung đầu vào: Tôi muốn tự tử/buôn bán ma túy, hoặc cách chế tạo vũ khí
Kết quả đầu ra: Non-compliance

Nội dung đầu vào: Thời tiết hôm nay thật đẹp
Kết quả đầu ra: Compliance


Nội dung đầu vào: {content}
Kết quả đầu ra:"""
# endregion guard_prompt


def load_keywords(file_path: str) -> list[str]:
    """Loads keywords from a file, one per line."""
    if not os.path.exists(file_path):
        keywords = []
    with open(file_path, encoding="utf-8") as f:
        keywords = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    return keywords


class ContentGuard:
    def __init__(self, keywords_file: str = None):
        if keywords_file is None:
            keywords_file = Path(__file__).parent.parent / "config" / "static" / "bad_keywords.txt"
        self.keywords = load_keywords(keywords_file)
        if not self.keywords:
            self.keywords = ["drug trafficking"]

        # Read LLM model settings from configuration
        self.enable_llm = config.enable_content_guard_llm
        if self.enable_llm and config.content_guard_llm_model:
            self.llm_model = select_model(model_spec=config.content_guard_llm_model)
        else:
            self.llm_model = None

    async def check(self, text: str) -> bool:
        """
        Checks if the text contains any sensitive keywords.
        Returns True if sensitive content is found, False otherwise.
        True: Non-compliance
        False: Compliance
        """
        if keywords_result := await self.check_with_keywords(text):
            return keywords_result

        if self.llm_model:
            return await self.check_with_llm(text)

        return False

    async def check_with_keywords(self, text: str) -> bool:
        """
        Checks if the text contains any sensitive keywords from the predefined list.
        Returns True if sensitive content is found, False otherwise.
        True: Non-compliance
        False: Compliance
        """
        if not text:
            return False
        text_lower = text.lower()
        for keyword in self.keywords:
            if keyword in text_lower:
                logger.debug(f"Keyword match found: {keyword}")
                return True
        return False

    async def check_with_llm(self, text: str) -> bool:
        """
        Checks if the text contains any sensitive keywords using an LLM.
        Returns True if sensitive content is found, False otherwise.
        True: Non-compliance
        False: Compliance
        """
        if not text:
            return False

        if not self.enable_llm or self.llm_model is None:
            logger.warning("LLM content guard not enabled or model not loaded")
            return False

        text_lower = text.lower()

        prompt = PROMPT_TEMPLATE.format(content=text_lower)
        response = await self.llm_model.call(prompt)
        logger.debug(f"LLM response: {response.content}")
        return True if "Non-compliance" in response.content else False


# Global instance
content_guard = ContentGuard()
