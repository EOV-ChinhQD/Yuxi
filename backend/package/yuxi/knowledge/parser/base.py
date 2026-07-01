"""
document processor basic interface andabnormal definition

This individual module defines the unified oneofdocument processor interface, For OCR and document parsing services.
"""

from abc import ABC, abstractmethod
from typing import Any


class DocumentProcessorException(Exception):
    """Document processing exception base class"""

    def __init__(self, message: str, service_name: str = None, status_code: str = None):
        super().__init__(message)
        self.message = message
        self.service_name = service_name
        self.status_code = status_code

    def __str__(self):
        if self.service_name:
            return f"[{self.service_name}] {self.message}"
        return self.message


class OCRException(DocumentProcessorException):
    """OCR processing exception"""

    pass


class DocumentParserException(DocumentProcessorException):
    """Document parsing exception"""

    pass


class ServiceHealthCheckException(DocumentProcessorException):
    """Service health check exception"""

    pass


class BaseDocumentProcessor(ABC):
    """Document Processor Base Class"""

    @abstractmethod
    def process_file(self, file_path: str, params: dict[str, Any] | None = None) -> str:
        """
        Process files and return Extracted text

        Args:
            file_path: document path
            params: Processing parameters

        Returns:
            str: Extracted text content

        Raises:
            DocumentProcessorException: Throws when processing fails
        """
        pass

    @abstractmethod
    def check_health(self) -> dict[str, Any]:
        """
        examineService health status

        Returns:
            dict: health status information
                {
                    "status": "healthy" | "unhealthy" | "unavailable" | "error",
                    "message": "Status description",
                    "details": {...}  # Optional details
                }
        """
        pass

    @abstractmethod
    def get_service_name(self) -> str:
        """Return service name"""
        pass

    def supports_file_type(self, file_extension: str) -> bool:
        """
        examineWhether to support specified ofdocument type

        Args:
            file_extension: file extension (Contains points, like '.pdf')

        Returns:
            bool: Whether to support
        """
        return file_extension.lower() in self.get_supported_extensions()

    @abstractmethod
    def get_supported_extensions(self) -> list[str]:
        """Returns a list of supported file extensions"""
        pass
