"""
Document Processor Factory

Provides a unified oneofdocument processor creation and management interface
"""

import asyncio
from importlib import import_module
from typing import Any

from yuxi.knowledge.parser.base import BaseDocumentProcessor
from yuxi.utils import logger

# Processor instance cache
_PROCESSOR_CACHE: dict[str, BaseDocumentProcessor] = {}

# 处理器类型映射: processor_type -> (module_path, class_name)
PROCESSOR_TYPES = {
    "rapid_ocr": ("yuxi.knowledge.parser.rapid_ocr", "RapidOCRParser"),
    "mineru_ocr": ("yuxi.knowledge.parser.mineru", "MinerUParser"),
    "mineru_official": ("yuxi.knowledge.parser.mineru_official", "MinerUOfficialParser"),
    "pp_structure_v3_ocr": ("yuxi.knowledge.parser.pp_structure_v3", "PPStructureV3Parser"),
    "deepseek_ocr": ("yuxi.knowledge.parser.deepseek_ocr", "DeepSeekOCRParser"),
    "paddleocr_vl_1_6": ("yuxi.knowledge.parser.paddleocr_api", "PaddleOCRVLParser"),
    "paddleocr_pp_ocrv6": ("yuxi.knowledge.parser.paddleocr_api", "PaddleOCRPPOCRv6Parser"),
}


class DocumentProcessorFactory:
    """Document Processor Factory"""

    PROCESSOR_TYPES = PROCESSOR_TYPES

    @classmethod
    def _build_cache_key(cls, processor_type: str, kwargs: dict[str, Any]) -> str:
        if not kwargs:
            return processor_type

        kwargs_repr = "|".join(f"{key}={kwargs[key]!r}" for key in sorted(kwargs))
        return f"{processor_type}|{kwargs_repr}"

    @classmethod
    def _load_processor_class(cls, processor_type: str) -> type[BaseDocumentProcessor]:
        module_path, class_name = cls.PROCESSOR_TYPES[processor_type]
        module = import_module(module_path)
        processor_class = getattr(module, class_name)
        return processor_class

    @classmethod
    def get_processor(cls, processor_type: str, **kwargs) -> BaseDocumentProcessor:
        """
        Get document handler instance (Singleton pattern)

        Args:
            processor_type: Processor type
                - "rapid_ocr": RapidOCR Native OCR
                - "mineru_ocr": MinerU HTTP API Document parsing
                - "mineru_official": MinerU Official cloud service API document analysis
                - "pp_structure_v3_ocr": PP-Structure-V3 Layout analysis
                - "deepseek_ocr": DeepSeek-OCR SiliconFlow API
                - "paddleocr_vl_1_6": Phân tích tài liệu PaddleOCR-VL-1.6 Cloud API
                - "paddleocr_pp_ocrv6": Nhận dạng ký tự PP-OCRv6 Cloud API
            **kwargs: các tham số khởi tạo bộ xử lý

        Returns:
            BaseDocumentProcessor: Processor instance

        Raises:
            ValueError: Loại bộ xử lý không được hỗ trợ
        """
        if processor_type not in cls.PROCESSOR_TYPES:
            raise ValueError(f"Loại bộ xử lý không được hỗ trợ: {processor_type}. Các loại được hỗ trợ: {list(cls.PROCESSOR_TYPES.keys())}")

        # Use caching to avoid duplicate creation
        cache_key = cls._build_cache_key(processor_type, kwargs)
        if cache_key not in _PROCESSOR_CACHE:
            processor_class = cls._load_processor_class(processor_type)
            _PROCESSOR_CACHE[cache_key] = processor_class(**kwargs)
            logger.debug(f"Create a document processor: {processor_type}")

        return _PROCESSOR_CACHE[cache_key]

    @classmethod
    def process_file(cls, processor_type: str, file_path: str, params: dict | None = None) -> str:
        """
        Process the file using the specified processor (Convenience method)

        Args:
            processor_type: Processor type
            file_path: document path
            params: Processing parameters

        Returns:
            str: Extracted text

        Raises:
            DocumentProcessorException: Processing failed
        """
        processor = cls.get_processor(processor_type)
        return processor.process_file(file_path, params)

    @classmethod
    def check_health(cls, processor_type: str) -> dict[str, Any]:
        """
        examine the health status of the specified processor

        Args:
            processor_type: Processor type

        Returns:
            dict: health status information
        """
        try:
            processor = cls.get_processor(processor_type)
            return processor.check_health()
        except Exception as e:
            return {
                "status": "error",
                "message": f"Health check failed: {str(e)}",
                "details": {"error": str(e)},
            }

    @classmethod
    def check_all_health(cls) -> dict[str, dict[str, Any]]:
        """
        examine the health status of all processors

        Returns:
            dict: The health status of each processor
        """
        health_status = {}
        for processor_type in cls.PROCESSOR_TYPES:
            health_status[processor_type] = cls.check_health(processor_type)
        return health_status

    @classmethod
    async def check_all_health_async(cls) -> dict[str, dict[str, Any]]:
        async def run_check(processor_type: str) -> tuple[str, dict[str, Any]]:
            return processor_type, await asyncio.to_thread(cls.check_health, processor_type)

        results = await asyncio.gather(*(run_check(processor_type) for processor_type in cls.PROCESSOR_TYPES))
        return {processor_type: health for processor_type, health in results}

    @classmethod
    def get_available_processors(cls) -> list[str]:
        """Returns all available processor types"""
        return list(cls.PROCESSOR_TYPES.keys())

    @classmethod
    def clear_cache(cls):
        """Clear processor cache"""
        _PROCESSOR_CACHE.clear()
        logger.debug("Document processor cache cleared")
