"""Kiểm tra tiền xử lý tệp PDF.

Module này thực hiện kiểm tra sơ bộ cây trang (page tree) của tệp PDF bằng pypdfium2 (BSD)
trước khi đưa vào các bộ phân tích như MinerU, PyPDFLoader... để phát hiện sớm các lỗi cấu trúc PDF.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium

from yuxi.knowledge.parser.base import DocumentParserException


@dataclass(slots=True)
class PDFPageLoadIssue:
    """Vị trí và thông tin lỗi khi tải trang PDF."""

    page_number: int
    message: str


def _format_page_numbers(page_numbers: list[int], *, limit: int = 8) -> str:
    """Định dạng danh sách số trang để thông báo lỗi ngắn gọn, dễ đọc."""
    visible = page_numbers[:limit]
    result = ", ".join(str(page_number) for page_number in visible)
    if len(page_numbers) > limit:
        result = f"{result}... (tổng cộng {len(page_numbers)} trang lỗi)"
    return result


def validate_pdf_page_tree_loadable(file_path: str | Path) -> None:
    """Kiểm tra cấu trúc cây trang PDF có thể tải từng trang hay không."""
    path = Path(file_path)

    try:
        doc = pdfium.PdfDocument(str(path))
    except Exception as exc:  # noqa: BLE001
        # pypdfium2 ném ngoại lệ PdfiumError khi tệp PDF được bảo vệ bằng mật khẩu
        if isinstance(exc, pdfium.PdfiumError) and "password" in str(exc).lower():
            raise DocumentParserException(
                "Tệp PDF đã được mã hóa hoặc yêu cầu mật khẩu, không thể thực hiện phân tích",
                "pdf_preflight",
                "encrypted_pdf",
            ) from exc
        raise DocumentParserException(
            f"Cấu trúc tệp PDF bất thường, không thể mở thư mục trang: {exc}",
            "pdf_preflight",
            "invalid_pdf_structure",
        ) from exc

    try:
        page_count = len(doc)
        if page_count <= 0:
            raise DocumentParserException(
                "Tệp PDF không có trang nào có thể phân tích",
                "pdf_preflight",
                "empty_pdf",
            )

        issues: list[PDFPageLoadIssue] = []
        for page_index in range(page_count):
            try:
                page = doc[page_index]
                # Truy cập kích thước trang để kích hoạt nạp đối tượng trang
                _ = page.get_size()
            except Exception as exc:  # noqa: BLE001
                issues.append(PDFPageLoadIssue(page_number=page_index + 1, message=str(exc)))

        if issues:
            bad_pages = _format_page_numbers([issue.page_number for issue in issues])
            first_error = issues[0].message or "Không thể nạp đối tượng trang"
            raise DocumentParserException(
                f"Cấu trúc trang PDF bất thường: Tài liệu khai báo có {page_count} trang, "
                f"nhưng trang ({bad_pages}) không phải đối tượng trang hợp lệ. "
                f"Lỗi chi tiết: {first_error}. Vui lòng kiểm tra hoặc in lại tệp PDF trước khi tải lên.",
                "pdf_preflight",
                "invalid_pdf_page_tree",
            )
    finally:
        doc.close()
