from __future__ import annotations

import asyncio
import base64
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest
import yuxi.knowledge.parser.unified as parser_unified
from docx import Document
from PIL import Image

from yuxi.knowledge.parser import Parser
from yuxi.knowledge.parser.factory import DocumentProcessorFactory
from yuxi.knowledge.parser.models import ProcessingResult, ProcessingStatus

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _build_pdf(file_path: Path, text: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(str(file_path))
    doc.close()


def _build_docx(file_path: Path, text: str) -> None:
    document = Document()
    document.add_paragraph(text)
    document.save(str(file_path))


def _build_png(file_path: Path) -> None:
    image = Image.new("RGB", (120, 80), "white")
    image.save(str(file_path))


def test_parser_parse_pdf_file_returns_markdown_text(tmp_path: Path):
    file_path = tmp_path / "parser_test.pdf"
    _build_pdf(file_path, "Parser PDF content. This is a longer string to make sure it is at least 50 characters long so docling does not degrade.")

    markdown = Parser.parse(str(file_path), params={"ocr_engine": "disable"})

    assert isinstance(markdown, str)
    assert "Parser" in markdown
    assert "content" in markdown
    assert len(markdown.strip()) > 0


def test_parser_parse_docx_file_returns_markdown_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    file_path = tmp_path / "parser_test.docx"
    _build_docx(file_path, "Parser DOCX content")

    # Tránh test phụ thuộc vào docling, trực tiếp xác thực parser thống nhất fallback về python-docx.
    def _raise_docling_error(*args, **kwargs):
        raise RuntimeError("force fallback to python-docx")

    monkeypatch.setattr(parser_unified, "_convert_with_docling", _raise_docling_error)

    markdown = Parser.parse(str(file_path))

    assert isinstance(markdown, str)
    assert "Parser DOCX content" in markdown
    assert len(markdown.strip()) > 0


def test_convert_with_docling_reinserts_image_links_in_document_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    file_path = tmp_path / "parser_test.docx"
    file_path.write_bytes(b"fake docx")
    first_image = base64.b64encode(b"first image").decode()
    second_image = base64.b64encode(b"second image").decode()
    fake_doc = SimpleNamespace(
        pictures=[
            SimpleNamespace(image=SimpleNamespace(uri=f"data:image/png;base64,{first_image}")),
            SimpleNamespace(image=SimpleNamespace(uri="https://example.test/remote.png")),
            SimpleNamespace(image=SimpleNamespace(uri=f"data:image/png;base64,{second_image}")),
        ],
        export_to_markdown=lambda: "before\n<!-- image -->\nremote\n<!-- image -->\nbetween\n<!-- image -->\nafter",
    )
    fake_result = SimpleNamespace(status=SimpleNamespace(name="SUCCESS"), document=fake_doc)
    uploaded_images: list[bytes] = []

    class FakeConverter:
        def convert(self, path: Path):
            assert path == file_path
            return fake_result

    def _fake_upload_image_to_minio(image_data, filename, bucket_name, object_prefix):
        uploaded_images.append(image_data)
        return f"https://example.test/{len(uploaded_images)}.png"

    monkeypatch.setattr(parser_unified, "_get_docling_converter", lambda: FakeConverter())
    monkeypatch.setattr(parser_unified, "_upload_image_to_minio", _fake_upload_image_to_minio)
    image_timestamps = iter([1.0, 2.0])
    monkeypatch.setattr(parser_unified.time, "time", lambda: next(image_timestamps))

    markdown = parser_unified._convert_with_docling(file_path)

    assert uploaded_images == [b"first image", b"second image"]
    assert markdown == (
        "before\n"
        "![image_1000000.png](https://example.test/1.png)\n"
        "remote\n"
        "\n"
        "between\n"
        "![image_2000000.png](https://example.test/2.png)\n"
        "after"
    )


def test_convert_with_docling_keeps_image_placeholder_when_upload_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    file_path = tmp_path / "parser_test.docx"
    file_path.write_bytes(b"fake docx")
    image = base64.b64encode(b"image data").decode()
    fake_doc = SimpleNamespace(
        pictures=[SimpleNamespace(image=SimpleNamespace(uri=f"data:image/png;base64,{image}"))],
        export_to_markdown=lambda: "before\n<!-- image -->\nafter",
    )
    fake_result = SimpleNamespace(status=SimpleNamespace(name="SUCCESS"), document=fake_doc)

    class FakeConverter:
        def convert(self, path: Path):
            assert path == file_path
            return fake_result

    def _raise_upload_error(*args, **kwargs):
        raise RuntimeError("upload failed")

    monkeypatch.setattr(parser_unified, "_get_docling_converter", lambda: FakeConverter())
    monkeypatch.setattr(parser_unified, "_upload_image_to_minio", _raise_upload_error)
    monkeypatch.setattr(parser_unified.time, "time", lambda: 1.0)

    markdown = parser_unified._convert_with_docling(file_path)

    assert markdown == "before\n[picture: image_1000000.png]\nafter"


def test_parser_parse_png_file_returns_markdown_text_with_mocked_ocr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    file_path = tmp_path / "parser_test.png"
    _build_png(file_path)

    async def _fake_parse_image_async(file, params=None):
        return "Parser PNG content"

    monkeypatch.setattr(parser_unified, "parse_image_async", _fake_parse_image_async)

    markdown = Parser.parse(str(file_path), params={"ocr_engine": "rapid_ocr"})

    assert isinstance(markdown, str)
    assert "Parser PNG content" in markdown
    assert len(markdown.strip()) > 0


def test_parse_image_uses_ocr_engine_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    file_path = tmp_path / "parser_test.png"
    _build_png(file_path)
    captured = {}

    def _fake_process_file(processor_type, file, params=None):
        captured["processor_type"] = processor_type
        captured["file"] = file
        captured["params"] = params
        return "OCR content"

    monkeypatch.setattr(DocumentProcessorFactory, "process_file", _fake_process_file)

    result = parser_unified.parse_image(
        str(file_path),
        params={
            "ocr_engine": "mineru_ocr",
            "backend": "old-backend",
            "ocr_engine_config": {"backend": "pipeline", "formula_enable": False},
        },
    )

    assert result == "OCR content"
    assert captured["processor_type"] == "mineru_ocr"
    assert captured["file"] == str(file_path)
    assert captured["params"]["backend"] == "pipeline"
    assert captured["params"]["formula_enable"] is False


def test_parse_image_ignores_enable_ocr(tmp_path: Path) -> None:
    file_path = tmp_path / "parser_test.png"
    _build_png(file_path)

    with pytest.raises(ValueError, match="bắt buộc phải bật OCR"):
        parser_unified.parse_image(str(file_path), params={"ocr_engine": "disable", "enable_ocr": "rapid_ocr"})



@pytest.mark.asyncio
async def test_parser_aparse_pdf_file_returns_markdown_text(tmp_path: Path):
    file_path = tmp_path / "parser_test_async.pdf"
    _build_pdf(file_path, "Async Parser PDF content. This is a longer string to make sure it is at least 50 characters long so docling does not degrade.")

    markdown = await Parser.aparse(str(file_path), params={"ocr_engine": "disable"})

    assert isinstance(markdown, str)
    assert "Async" in markdown
    assert "content" in markdown
    assert len(markdown.strip()) > 0


def test_parse_pdf_uses_config_default_ocr_when_engine_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import yuxi

    file_path = tmp_path / "parser_test.pdf"
    _build_pdf(file_path, "Parser PDF content. This is a longer string to make sure it is at least 50 characters long so docling does not degrade.")
    captured = {}

    class _FakeProcessor:
        def __init__(self, processor_type):
            self.processor_type = processor_type

        def process_file(self, file, params=None):
            captured["processor_type"] = self.processor_type
            captured["file"] = file
            captured["params"] = params
            return "default OCR content"

    def _fake_get_processor(processor_type, **kwargs):
        return _FakeProcessor(processor_type)

    monkeypatch.setattr(yuxi.config, "default_ocr_engine", "mineru_ocr")
    monkeypatch.setattr(DocumentProcessorFactory, "get_processor", _fake_get_processor)

    result = parser_unified.parse_pdf(str(file_path), params={})

    assert isinstance(result, ProcessingResult)
    assert result.status is ProcessingStatus.SUCCESS
    assert result.content == "default OCR content"
    assert captured["processor_type"] == "mineru_ocr"
    assert captured["file"] == str(file_path)


def test_parse_pdf_keeps_explicit_disable_when_default_ocr_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import yuxi

    file_path = tmp_path / "parser_test.pdf"
    _build_pdf(file_path, "Parser PDF content. This is a longer string to make sure it is at least 50 characters long so docling does not degrade.")

    class _FakeProcessor:
        def process(self, file, params=None):
            return ProcessingResult(
                status=ProcessingStatus.SUCCESS,
                engine="docling",
                ocr_used=False,
                content="Parser PDF content. This is a longer string to make sure it is at least 50 characters long so docling does not degrade.",
            )

    monkeypatch.setattr(yuxi.config, "default_ocr_engine", "mineru_ocr")
    monkeypatch.setattr(DocumentProcessorFactory, "get_processor", lambda processor_type: _FakeProcessor())

    result = parser_unified.parse_pdf(str(file_path), params={"ocr_engine": "disable"})

    assert isinstance(result, ProcessingResult)
    assert result.status is ProcessingStatus.SUCCESS
    assert "Parser PDF content. This is a longer string to make sure it is at least 50 characters long so docling does not degrade." in result.content


@pytest.mark.asyncio
async def test_parser_aparse_image_file_with_mineru_when_available():
    file_path = DATA_DIR / "test_image.png"
    assert file_path.exists(), f"Tệp kiểm thử không tồn tại: {file_path}"

    health = await asyncio.to_thread(DocumentProcessorFactory.check_health, "mineru_ocr")
    if health.get("status") != "healthy":
        pytest.skip(f"mineru_ocr không khả dụng: {health.get('message', 'unknown')}")

    markdown = await Parser.aparse(
        str(file_path),
        params={"ocr_engine": "mineru_ocr", "backend": "pipeline"},
    )

    assert isinstance(markdown, str)
    assert len(markdown) > 100
    assert len(markdown.strip()) > 0


def test_density_analyzer_with_stratified_sampling(tmp_path: Path):
    from yuxi.knowledge.parser.density import PDFDensityAnalyzer
    analyzer = PDFDensityAnalyzer()
    
    # Create a PDF with 20 pages (to trigger sampling > 15 pages)
    file_path = tmp_path / "density_test_sampled.pdf"
    doc = fitz.open()
    for i in range(20):
        page = doc.new_page()
        # insert > 100 characters
        page.insert_text((72, 72), f"Page {i} Parser PDF content. This is page {i} text layer. We need to make sure this page has more than 100 characters to pass the threshold test cleanly.")
    doc.save(str(file_path))
    doc.close()
    
    analysis = analyzer.analyze_document(file_path)
    assert analysis["total_pages"] == 20
    assert analysis["is_sampled"] is True
    assert analysis["analyzed_pages_count"] == 15  # 5 first, 5 middle, 5 last
    assert analysis["recommended_ocr"] == "disable"
    assert analysis["confidence_score"] == 1.0  # all pages are clean text
    assert len(analysis["pages_detail"]) == 15


def test_docling_processor_dynamic_degradation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from yuxi.knowledge.parser.processors.docling import DoclingProcessor
    from yuxi.knowledge.parser.models import ProcessingStatus
    
    processor = DoclingProcessor()
    
    # Mock DocumentConverter
    class FakeConverter:
        def convert(self, path):
            # 10 pages, but only 200 chars -> degraded (min_char_limit = max(50, 30*10) = 300)
            fake_doc = SimpleNamespace(
                export_to_markdown=lambda: "A" * 200
            )
            fake_pages = [SimpleNamespace() for _ in range(10)]
            return SimpleNamespace(
                status=SimpleNamespace(name="SUCCESS"),
                document=fake_doc,
                pages=fake_pages
            )
            
    monkeypatch.setattr(processor, "_get_converter", lambda ocr_policy: FakeConverter())
    
    result = processor.process(str(tmp_path / "dummy.pdf"))
    assert result.status == ProcessingStatus.DEGRADED
    assert result.metadata["page_count"] == 10
    assert result.metadata["min_char_limit"] == 300

