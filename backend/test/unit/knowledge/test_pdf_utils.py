"""Kiểm thử đơn vị cho module kiểm tra tiền xử lý tệp PDF (pdf_utils)"""

from pathlib import Path
import pytest
from pypdf import PdfWriter

from yuxi.knowledge.parser.base import DocumentParserException
from yuxi.knowledge.utils.pdf_utils import validate_pdf_page_tree_loadable


def _create_minimal_pdf(file_path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    with open(file_path, "wb") as f:
        writer.write(f)


def test_validate_pdf_page_tree_loadable_valid_pdf(tmp_path: Path):
    pdf_path = tmp_path / "valid.pdf"
    _create_minimal_pdf(pdf_path)

    # Không ném ngoại lệ với PDF hợp lệ
    validate_pdf_page_tree_loadable(pdf_path)


def test_validate_pdf_page_tree_loadable_invalid_structure(tmp_path: Path):
    corrupt_pdf = tmp_path / "corrupt.pdf"
    corrupt_pdf.write_bytes(b"not a valid pdf file structure")

    with pytest.raises(DocumentParserException) as exc_info:
        validate_pdf_page_tree_loadable(corrupt_pdf)

    assert exc_info.value.service_name == "pdf_preflight"
    assert exc_info.value.status_code == "invalid_pdf_structure"
