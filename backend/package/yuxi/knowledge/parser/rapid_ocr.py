"""
RapidOCR parser - Pure OCR text recognition

use RapidOCR (PP-OCRv5) Perform text recognition
"""

import os
import tempfile
import time
from pathlib import Path

import fitz
import numpy as np
from PIL import Image
from rapidocr import EngineType, LangDet, LangRec, ModelType, OCRVersion, RapidOCR

from yuxi.knowledge.parser.base import BaseDocumentProcessor, OCRException
from yuxi.utils import logger


class RapidOCRParser(BaseDocumentProcessor):
    """RapidOCR parser - Text recognition using ONNX model"""

    def __init__(self, det_box_thresh: float = 0.3):
        self.ocr = None
        self.det_box_thresh = det_box_thresh

    def get_service_name(self) -> str:
        return "rapid_ocr"

    def get_supported_extensions(self) -> list[str]:
        return [".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"]

    def _get_model_params(self) -> dict[str, object]:
        return {
            "Det.engine_type": EngineType.ONNXRUNTIME,
            "Det.lang_type": LangDet.CH,
            "Det.model_type": ModelType.MOBILE,
            "Det.ocr_version": OCRVersion.PPOCRV5,
            "Det.box_thresh": self.det_box_thresh,
            "Cls.engine_type": EngineType.ONNXRUNTIME,
            "Rec.engine_type": EngineType.ONNXRUNTIME,
            "Rec.lang_type": LangRec.CH,
            "Rec.model_type": ModelType.MOBILE,
            "Rec.ocr_version": OCRVersion.PPOCRV5,
        }

    def check_health(self) -> dict:
        """Check if RapidOCR model is available"""
        try:
            test_ocr = RapidOCR(params=self._get_model_params())
            del test_ocr
            return {
                "status": "healthy",
                "message": "RapidOCR PP-OCRv5 Model available",
                "details": {"ocr_version": "PP-OCRv5", "engine": "onnxruntime"},
            }
        except Exception as e:
            return {"status": "error", "message": f"Model loading failed: {str(e)}", "details": {"error": str(e)}}

    def _load_model(self):
        """Lazy loading of OCR models"""
        if self.ocr is not None:
            return

        logger.info("Load RapidOCR model...")

        try:
            self.ocr = RapidOCR(params=self._get_model_params())
            logger.info(f"RapidOCR PP-OCRv5 Model loaded successfully (det_box_thresh={self.det_box_thresh})")
        except Exception as e:
            raise OCRException(f"Tải model RapidOCR thất bại: {str(e)}", self.get_service_name(), "load_failed")

    def process_image(self, image, params: dict | None = None) -> str:
        """
        Process a single picture and Extract text

        Args:
            image: image data,support:
                  - str: Image file path
                  - PIL.Image: PIL image object
                  - numpy.ndarray: numpypicture like array
            params: Processing parameters (Not currently in use)

        Returns:
            str: Extracted text content
        """
        self._load_model()

        try:
            # Handle different types of input
            if isinstance(image, str):
                image_path = image
                cleanup_needed = False
            else:
                # Create temporary files
                image_path = self._create_temp_image_file(image)
                cleanup_needed = True

            try:
                # Perform OCR
                start_time = time.time()
                result = self.ocr(image_path)
                processing_time = time.time() - start_time

                # Extract text
                if result.txts:
                    text = "\n".join(result.txts)
                    logger.info(
                        f"RapidOCR success: {os.path.basename(image_path) if isinstance(image, str) else 'temp_image'}"
                        f" ({processing_time:.2f}s)"
                    )
                    return text
                else:
                    logger.warning(f"RapidOCR Text not recognized: {image_path}")
                    return ""

            finally:
                # Clean temporary files
                if cleanup_needed and os.path.exists(image_path):
                    try:
                        os.remove(image_path)
                    except Exception as e:
                        logger.warning(f"Temporary file cleanup failed: {image_path} - {e}")

        except Exception as e:
            error_msg = f"Image OCR processing failed: {str(e)}"
            logger.error(error_msg)
            raise OCRException(error_msg, self.get_service_name(), "processing_failed")

    def _create_temp_image_file(self, image) -> str:
        """Save image data as temporary file"""
        try:
            # Use system temporary directory
            with tempfile.NamedTemporaryFile(mode="wb", suffix=".png", delete=False) as tmp_file:
                temp_path = tmp_file.name

                if isinstance(image, Image.Image):
                    image.save(temp_path)
                elif isinstance(image, np.ndarray):
                    Image.fromarray(image).save(temp_path)
                else:
                    raise ValueError("Loại hình ảnh không được hỗ trợ, phải là PIL.Image hoặc numpy.ndarray")

                return temp_path

        except Exception as e:
            raise OCRException(f"Tạo tệp hình ảnh tạm thời thất bại: {str(e)}", self.get_service_name(), "temp_file_error")

    def process_pdf(self, pdf_path: str, params: dict | None = None) -> str:
        """
        Process PDF files and extract text (streaming,Avoid memory usage)

        Args:
            pdf_path: PDF document path
            params: Processing parameters
                - zoom_x: Horizontal scaling (Default 2)
                - zoom_y: vertical zoom (Default 2)

        Returns:
            str: Extracted text
        """
        if not os.path.exists(pdf_path):
            raise OCRException(f"Tệp PDF không tồn tại: {pdf_path}", self.get_service_name(), "file_not_found")

        params = params or {}
        zoom_x = params.get("zoom_x", 2)
        zoom_y = params.get("zoom_y", 2)

        try:
            all_text = []
            pdf_doc = fitz.open(pdf_path)
            total_pages = pdf_doc.page_count

            logger.info(f"Start working with PDFs: {os.path.basename(pdf_path)} ({total_pages} Page)")

            # Stream each page to avoid loading all images into memory at once
            for page_num in range(total_pages):
                page = pdf_doc[page_num]

                # Convert to image
                mat = fitz.Matrix(zoom_x, zoom_y)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img_pil = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                # Process immediately, do not save to list
                text = self.process_image(img_pil)
                all_text.append(text)

                if (page_num + 1) % 10 == 0:
                    logger.info(f"Processed {page_num + 1}/{total_pages} Page")

            pdf_doc.close()

            result_text = "\n\n".join(all_text)
            logger.info(f"PDF OCR Finish: {os.path.basename(pdf_path)} - {len(result_text)} character")
            return result_text

        except OCRException:
            raise
        except Exception as e:
            error_msg = f"PDF OCR Processing failed: {str(e)}"
            logger.error(error_msg)
            raise OCRException(error_msg, self.get_service_name(), "pdf_processing_failed")

    def process_file(self, file_path: str, params: dict | None = None) -> str:
        """
        Process files (PDF or image)

        Args:
            file_path: document path
            params: Processing parameters

        Returns:
            str: Extracted text
        """
        file_ext = Path(file_path).suffix.lower()

        if not self.supports_file_type(file_ext):
            raise OCRException(f"Loại tệp không được hỗ trợ: {file_ext}", self.get_service_name(), "unsupported_file_type")

        if file_ext == ".pdf":
            return self.process_pdf(file_path, params)
        else:
            return self.process_image(file_path, params)
