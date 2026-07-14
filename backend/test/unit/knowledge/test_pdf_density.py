import pytest
from unittest.mock import MagicMock, patch
from yuxi.knowledge.parser.density import PDFDensityAnalyzer


def test_analyze_page_text_only():
    analyzer = PDFDensityAnalyzer()
    
    # Mock fitz.Page
    page = MagicMock()
    page.get_text.return_value = "Hệ thống RAG hoạt động rất tốt trên môi trường thực tế. " * 20
    page.get_images.return_value = []
    
    page_type, metrics = analyzer.analyze_page(page)
    
    assert page_type == "text"
    assert metrics["chars_count"] > 300
    assert metrics["garbled_ratio"] == 0.0
    assert metrics["quality_score"] > 0.8


def test_analyze_page_scan_only():
    analyzer = PDFDensityAnalyzer()
    
    page = MagicMock()
    page.get_text.return_value = "chỉ có vài chữ"
    page.get_images.return_value = [1]
    
    page_type, metrics = analyzer.analyze_page(page)
    
    assert page_type == "scan"
    assert metrics["chars_count"] < 50


def test_analyze_page_garbled_font():
    analyzer = PDFDensityAnalyzer()
    
    page = MagicMock()
    page.get_text.return_value = " \ufffd \x00 " * 50
    page.get_images.return_value = []
    
    page_type, metrics = analyzer.analyze_page(page)
    
    # Large number of invalid characters should classify page as scan (so we OCR it)
    assert page_type == "scan"
    assert metrics["garbled_ratio"] > 0.3
    assert metrics["quality_score"] < analyzer.quality_score_threshold


def test_analyze_page_hybrid():
    analyzer = PDFDensityAnalyzer()
    
    page = MagicMock()
    page.get_text.return_value = "Hệ thống RAG hoạt động rất tốt trên môi trường thực tế. " * 20
    page.get_images.return_value = [1]
    
    page_type, metrics = analyzer.analyze_page(page)
    
    assert page_type == "hybrid"


@patch("fitz.open")
def test_analyze_document(mock_fitz_open):
    # Mock document containing 2 text pages
    doc = MagicMock()
    doc.__len__.return_value = 2
    
    page_1 = MagicMock()
    page_1.get_text.return_value = "Hệ thống RAG hoạt động rất tốt trên môi trường thực tế. " * 20
    page_1.get_images.return_value = []
    
    page_2 = MagicMock()
    page_2.get_text.return_value = "Tài liệu này chứa thông tin bảo mật và phân quyền truy cập." * 20
    page_2.get_images.return_value = []
    
    doc.__getitem__.side_effect = [page_1, page_2]
    mock_fitz_open.return_value = doc
    
    analyzer = PDFDensityAnalyzer()
    analysis = analyzer.analyze_document("dummy.pdf")
    
    assert analysis["total_pages"] == 2
    assert len(analysis["text_pages"]) == 2
    assert analysis["recommended_ocr"] == "disable"
