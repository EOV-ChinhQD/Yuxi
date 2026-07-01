"""
PP-Structure-V3 Document parser

Use PP-Structure-V3 Perform document layout analysis and content extraction
"""

import base64
import os
import time
from pathlib import Path
from typing import Any

import requests

from yuxi.knowledge.parser.base import BaseDocumentProcessor, DocumentParserException
from yuxi.utils import logger


class PPStructureV3Parser(BaseDocumentProcessor):
    """PP-Structure-V3 Document parser - Use PP-Structure-V3 Perform layout analysis"""

    def __init__(self, server_url: str | None = None):
        self.server_url = server_url or os.getenv("PADDLEX_URI") or "http://localhost:8080"
        self.base_url = self.server_url.rstrip("/")
        self.endpoint = f"{self.base_url}/layout-parsing"

    def get_service_name(self) -> str:
        return "pp_structure_v3_ocr"

    def get_supported_extensions(self) -> list[str]:
        """PP-Structure-V3 Supports PDF and multiple image formats"""
        return [".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"]

    def _encode_file_to_base64(self, file_path: str) -> str:
        """Encode file to Base64"""
        with open(file_path, "rb") as file:
            encoded = base64.b64encode(file.read()).decode("utf-8")
            return encoded

    def _process_file_input(self, file_input: str) -> str:
        """Handle file input: local file path, URL or Base64 content"""
        # Check if it is a local file path
        if os.path.exists(file_input):
            logger.info(f"📁 Local file detected: {file_input}")
            logger.info(f"📏 file size: {os.path.getsize(file_input) / 1024 / 1024:.2f} MB")
            return self._encode_file_to_base64(file_input)

        # Check if it is a URL
        elif file_input.startswith(("http://", "https://")):
            logger.info(f"🌐 URL detected: {file_input}")
            return file_input

        # Otherwise Base64 encoded content is assumed
        else:
            logger.info(f"📝 Assuming Base64 encoded content, length: {len(file_input)} character")
            return file_input

    def _call_layout_api(
        self,
        file_input: str,
        file_type: int | None = None,
        use_table_recognition: bool = True,
        use_formula_recognition: bool = True,
        use_seal_recognition: bool = False,
        **kwargs,
    ) -> dict[str, Any]:
        """Call PP-Structure-V3 layout parsing API"""
        # Handle file input
        processed_file_input = self._process_file_input(file_input)
        payload = {"file": processed_file_input}

        # Add core parameters
        optional_params = {
            "fileType": file_type,
            "useTableRecognition": use_table_recognition,
            "useFormulaRecognition": use_formula_recognition,
            "useSealRecognition": use_seal_recognition,
        }

        # Add non-empty parameters
        for key, value in optional_params.items():
            if value is not None:
                payload[key] = value

        # Add additional kwargs parameters
        for key, value in kwargs.items():
            if value is not None:
                payload[key] = value

        response = requests.post(self.endpoint, json=payload, headers={"Content-Type": "application/json"}, timeout=300)

        if response.status_code == 200:
            return response.json()
        else:
            error_msg = f"PP-Structure-V3 API request failed: {response.status_code}"
            try:
                error_result = response.json()
                raise DocumentParserException(f"{error_msg}: {error_result}", self.get_service_name(), "api_error")
            except Exception:
                raise DocumentParserException(f"{error_msg}: {response.text}", self.get_service_name(), "api_error")

    def _parse_api_result(self, api_result: dict[str, Any], file_path: str) -> dict[str, Any]:
        """Parse API return results"""
        # Basic information
        parsed_result = {
            "success": True,
            "file_path": file_path,
            "file_name": os.path.basename(file_path),
            "log_id": api_result.get("logId"),
            "total_pages": 0,
            "pages": [],
            "full_text": "",
            "summary": {},
        }

        result_data = api_result.get("result", {})
        layout_results = result_data.get("layoutParsingResults", [])

        # Data information
        parsed_result["total_pages"] = len(layout_results)

        # Statistics
        total_tables = 0
        total_formulas = 0
        all_text_content = []

        # Parse each page of results
        for page_result in layout_results:
            # Markdown content
            if "markdown" in page_result:
                markdown = page_result["markdown"]
                if markdown.get("text"):
                    all_text_content.append(markdown["text"])

            # Detailed identification results
            if "prunedResult" in page_result:
                pruned = page_result["prunedResult"]

                # Table identification
                table_result = pruned.get("table_result", [])
                total_tables += len(table_result)

                # Formula recognition
                formula_result = pruned.get("formula_result", [])
                total_formulas += len(formula_result)

        # Summarize full text content
        parsed_result["full_text"] = "\n\n".join(all_text_content)

        # Summary statistics
        parsed_result["summary"] = {
            "total_tables": total_tables,
            "total_formulas": total_formulas,
            "total_characters": len(parsed_result["full_text"]),
        }

        return parsed_result

    def check_health(self) -> dict:
        """Check PP-Structure-V3 Service health status"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)

            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "message": "PP-Structure-V3 The service is running normally",
                    "details": {"server_url": self.server_url},
                }
            else:
                return {
                    "status": "unhealthy",
                    "message": f"PP-Structure-V3 Service response exception: {response.status_code}",
                    "details": {"server_url": self.server_url},
                }

        except requests.exceptions.ConnectionError:
            return {
                "status": "unavailable",
                "message": "PP-Structure-V3 Service cannot connect,Please check whether the service is started",
                "details": {"server_url": self.server_url},
            }
        except requests.exceptions.Timeout:
            return {
                "status": "timeout",
                "message": "PP-Structure-V3 Service connection timeout",
                "details": {"server_url": self.server_url},
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"PP-Structure-V3 Health check failed: {str(e)}",
                "details": {"server_url": self.server_url, "error": str(e)},
            }

    def process_file(self, file_path: str, params: dict | None = None) -> str:
        """
        Use PP-Structure-V3 to process document

        Args:
            file_path: document path
            params: Processing parameters
                - use_table_recognition: Enable table recognition (default: True)
                - use_formula_recognition: Enable formula recognition (default: True)
                - use_seal_recognition: Enable stamp recognition (default: False)

        Returns:
            str: Extracted Markdown text
        """
        if not os.path.exists(file_path):
            raise DocumentParserException(f"Tệp không tồn tại: {file_path}", self.get_service_name(), "file_not_found")

        file_ext = Path(file_path).suffix.lower()
        if not self.supports_file_type(file_ext):
            raise DocumentParserException(
                f"Unsupported file types: {file_ext}", self.get_service_name(), "unsupported_file_type"
            )

        # Check service health status first
        health = self.check_health()
        if health["status"] != "healthy":
            raise DocumentParserException(
                f"PP-Structure-V3 Service unavailable: {health['message']}", self.get_service_name(), health["status"]
            )

        try:
            start_time = time.time()
            params = params or {}

            # Determine file type
            file_type = 0 if file_ext == ".pdf" else 1

            logger.info(f"PP-Structure-V3 Start processing: {os.path.basename(file_path)}")

            # Call API
            api_result = self._call_layout_api(
                file_input=file_path,
                file_type=file_type,
                use_table_recognition=params.get("use_table_recognition", True),
                use_formula_recognition=params.get("use_formula_recognition", True),
                use_seal_recognition=params.get("use_seal_recognition", False),
            )

            # Check if API call is successful
            if api_result.get("errorCode") != 0:
                raise DocumentParserException(
                    f"PP-Structure-V3 API error: {api_result.get('errorMsg', 'unknown error')}",
                    self.get_service_name(),
                    "api_error",
                )

            # Parse results
            result = self._parse_api_result(api_result, file_path)
            text = result.get("full_text", "")

            processing_time = time.time() - start_time
            logger.info(
                f"PP-Structure-V3 Processed successfully: {os.path.basename(file_path)} - {len(text)} character ({processing_time:.2f}s)"
            )

            # Record statistics
            summary = result.get("summary", {})
            if summary:
                logger.info(f"  statistics: {summary.get('total_tables', 0)} sheet, {summary.get('total_formulas', 0)} formula")

            return text

        except DocumentParserException:
            raise
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"PP-Structure-V3 Processing failed: {str(e)}"
            logger.error(f"{error_msg} ({processing_time:.2f}s)")
            raise DocumentParserException(error_msg, self.get_service_name(), "processing_failed")
