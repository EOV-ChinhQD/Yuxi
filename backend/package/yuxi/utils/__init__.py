import os
from datetime import datetime
from zoneinfo import ZoneInfo

from yuxi.utils.hash_utils import hashstr as hashstr
from yuxi.utils.logging_config import logger

_VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def vietnam_now() -> datetime:
    """Trả về thời gian hiện tại theo múi giờ Việt Nam (Asia/Ho_Chi_Minh, UTC+7)."""
    return datetime.now(_VN_TZ)


def is_text_pdf(pdf_path):
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(pdf_path)
    try:
        total_pages = len(doc)
        if total_pages == 0:
            return False

        text_pages = 0
        for page_num in range(total_pages):
            page = doc[page_num]
            text = page.get_textpage().get_text_bounded()
            if text.strip():  # Kiểm tra xem có nội dung văn bản không
                text_pages += 1

        # Tính tỷ lệ số trang có nội dung văn bản
        text_ratio = text_pages / total_pages
        # Nếu hơn 50% số trang có nội dung văn bản thì coi là PDF dạng văn bản
        return text_ratio > 0.5
    finally:
        doc.close()


def get_docker_safe_url(base_url):
    if not base_url:
        return base_url

    if os.getenv("RUNNING_IN_DOCKER") == "true":
        # Thay thế tất cả các dạng địa chỉ local có thể có
        base_url = base_url.replace("http://localhost", "http://host.docker.internal")
        base_url = base_url.replace("http://127.0.0.1", "http://host.docker.internal")
        logger.info(f"Running in docker, using {base_url} as base url")
    return base_url
