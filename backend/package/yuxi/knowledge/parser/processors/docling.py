import re
import time
from pathlib import Path
from typing import Any
from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions

from yuxi.knowledge.parser.base import BaseDocumentProcessor, DocumentProcessorException
from yuxi.knowledge.parser.models import ProcessingResult, ProcessingStatus, OCRPolicy
from yuxi.knowledge.parser.unified import _upload_image_to_minio, _parse_data_uri, _resolve_image_storage_params
from yuxi.utils import logger


class DoclingProcessor(BaseDocumentProcessor):
    """Docling Parser for converting PDF, DOCX, PPTX, XLSX to Markdown."""

    service_name = "docling"
    _converter_cache = {}

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def get_service_name(self) -> str:
        return self.service_name

    def get_supported_extensions(self) -> list[str]:
        return [".pdf", ".docx", ".pptx", ".xlsx"]

    def _get_converter(self, ocr_policy: OCRPolicy) -> DocumentConverter:
        do_ocr = ocr_policy != OCRPolicy.DISABLE
        cache_key = f"docling_ocr_{do_ocr}"

        if cache_key not in self._converter_cache:
            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = do_ocr
            pipeline_options.do_table_structure = True

            self._converter_cache[cache_key] = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
                    InputFormat.DOCX: None,
                    InputFormat.XLSX: None,
                    InputFormat.PPTX: None,
                }
            )
        return self._converter_cache[cache_key]

    def process(self, file_path: str, params: dict[str, Any] | None = None) -> ProcessingResult:
        params = params or {}
        image_bucket, image_prefix = _resolve_image_storage_params(params)

        ocr_policy_str = params.get("ocr_policy", "auto")
        try:
            ocr_policy = OCRPolicy(ocr_policy_str)
        except ValueError:
            ocr_policy = OCRPolicy.AUTO

        converter = self._get_converter(ocr_policy)
        path = Path(file_path)

        try:
            result = converter.convert(path)
        except Exception as e:
            return ProcessingResult(
                status=ProcessingStatus.FAILED,
                engine=self.service_name,
                ocr_used=(ocr_policy != OCRPolicy.DISABLE),
                error=DocumentProcessorException(f"Docling error: {str(e)}", self.service_name),
                metadata={"file": path.name, "error_type": "exception"},
            )

        if result.status.name != "SUCCESS":
            # Nếu partial success hoặc failure cứng
            return ProcessingResult(
                status=ProcessingStatus.FAILED,
                engine=self.service_name,
                ocr_used=(ocr_policy != OCRPolicy.DISABLE),
                error=DocumentProcessorException(f"Docling conversion failed: {result.status}", self.service_name),
                metadata={"file": path.name, "error_type": "conversion_status"},
            )

        doc = result.document

        # Xử lý hình ảnh
        replacements: list[str] = []
        if hasattr(doc, "pictures") and doc.pictures:
            for pic in doc.pictures:
                uri = str(pic.image.uri) if hasattr(pic, "image") and hasattr(pic.image, "uri") else ""
                if uri.startswith("data:"):
                    filename = "image"
                    try:
                        image_data, mime_type = _parse_data_uri(uri)
                        filename = f"image_{int(time.time() * 1000000)}.{mime_type.split('/')[-1]}"
                        url = _upload_image_to_minio(image_data, filename, image_bucket, image_prefix)
                        replacements.append(f"![{filename}]({url})")
                    except Exception as e:
                        logger.error(f"Failed to upload image {filename}: {e}")
                        replacements.append(f"[picture: {filename}]")
                else:
                    replacements.append("")

        try:
            markdown = doc.export_to_markdown()
            for replacement in replacements:
                markdown = re.sub(r"<!--\s*image\s*-->", replacement, markdown, count=1)
        except Exception as e:
            return ProcessingResult(
                status=ProcessingStatus.FAILED,
                engine=self.service_name,
                ocr_used=(ocr_policy != OCRPolicy.DISABLE),
                error=DocumentProcessorException(f"Docling markdown export error: {str(e)}", self.service_name),
                metadata={"file": path.name, "error_type": "export_error"},
            )

        # Kiểm tra layout confidence và suy thoái (degraded) bằng ngưỡng động dựa trên số trang
        page_count = 1
        if hasattr(result, "pages") and result.pages:
            try:
                page_count = len(result.pages)
            except TypeError:
                pass

        min_char_limit = max(50, 30 * page_count)
        status = ProcessingStatus.SUCCESS
        if len(markdown.strip()) < min_char_limit:
            status = ProcessingStatus.DEGRADED

        return ProcessingResult(
            status=status,
            engine=self.service_name,
            ocr_used=(ocr_policy != OCRPolicy.DISABLE),
            content=markdown,
            metadata={"file": path.name, "page_count": page_count, "min_char_limit": min_char_limit},
        )

    def process_file(self, file_path: str, params: dict[str, Any] | None = None) -> str:
        # Tương thích ngược với interface BaseDocumentProcessor cũ
        result = self.process(file_path, params)
        if not result.success:
            if result.error:
                raise result.error
            raise DocumentProcessorException("Processing failed", self.service_name)
        return result.content or ""

    def check_health(self) -> dict[str, Any]:
        return {"status": "healthy", "message": "Docling is a local library", "details": {}}
