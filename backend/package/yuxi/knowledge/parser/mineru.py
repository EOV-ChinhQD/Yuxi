"""
MinerU Document parser

Use MinerU service for document layout point analysis and content extraction
"""

import os
import tempfile
import time
from pathlib import Path

import requests

from yuxi.knowledge.parser.base import BaseDocumentProcessor, DocumentParserException
from yuxi.knowledge.parser.zip_utils import process_zip_file_sync
from yuxi.utils import logger


class MinerUParser(BaseDocumentProcessor):
    """MinerU Document parser - Document understanding and parsing using HTTP API"""

    def __init__(self, server_url: str | None = None):
        self.server_url = server_url or os.getenv("MINERU_API_URI") or "http://localhost:30001"
        self.parse_endpoint = f"{self.server_url}/file_parse"

    def get_service_name(self) -> str:
        return "mineru_ocr"

    def get_supported_extensions(self) -> list[str]:
        """MinerU Supports PDF and multiple image formats"""
        return [".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"]

    def check_health(self) -> dict:
        """Check MinerU service health status"""
        try:
            # Try accessing the OpenAPI JSON endpoint to check if the service is available
            health_url = f"{self.server_url}/openapi.json"
            response = requests.get(health_url, timeout=5)

            if response.status_code == 200:
                try:
                    openapi_data = response.json()
                    # Check if file_parse endpoint is included
                    has_file_parse = "/file_parse" in openapi_data.get("paths", {})

                    if has_file_parse:
                        return {
                            "status": "healthy",
                            "message": "MinerU The service is running normally",
                            "details": {
                                "server_url": self.server_url,
                                "api_version": openapi_data.get("info", {}).get("version", "unknown"),
                            },
                        }
                    else:
                        return {
                            "status": "unhealthy",
                            "message": "MinerU The service is missing a necessary endpoint",
                            "details": {"server_url": self.server_url},
                        }
                except Exception as e:
                    return {
                        "status": "unhealthy",
                        "message": f"MinerU Response format error: {str(e)}",
                        "details": {"server_url": self.server_url},
                    }
            else:
                return {
                    "status": "unhealthy",
                    "message": f"MinerU Service response exception: {response.status_code}",
                    "details": {"server_url": self.server_url},
                }

        except requests.exceptions.ConnectionError:
            return {
                "status": "unavailable",
                "message": "MinerU Service cannot connect,Please check whether the service is started",
                "details": {"server_url": self.server_url},
            }
        except requests.exceptions.Timeout:
            return {
                "status": "timeout",
                "message": "MinerU Service connection timeout",
                "details": {"server_url": self.server_url},
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"MinerU Health check failed: {str(e)}",
                "details": {"server_url": self.server_url, "error": str(e)},
            }

    def process_file(self, file_path: str, params: dict | None = None) -> str:
        """
        use MinerU to process documents

        Args:
            file_path: document path
            params: Processing parameters
                - lang_list: Language list (default: ["ch"])
                - backend: backend type (default: "hybrid-auto-engine")
                - parse_method: parsing method (default: "auto")
                - start_page_id: Starting page number (default: 0)
                - end_page_id: end page number (default: 99999)
                - formula_enable: Enable formula parsing (default: True)
                - table_enable: Enable table parsing (default: True)
                - image_analysis: Enable images/Chart analysis (default: True)
                - server_url: OpenAI Compatible service address (*-http-client Optional for backend)

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

        # Parse parameters
        params = params or {}

        data = {
            "lang_list": params.get("lang_list", ["ch"]),
            "backend": params.get("backend", "hybrid-auto-engine"),
            "parse_method": params.get("parse_method", "auto"),
            "formula_enable": params.get("formula_enable", True),
            "table_enable": params.get("table_enable", True),
            "image_analysis": params.get("image_analysis", True),
            "start_page_id": params.get("start_page_id", 0),
            "end_page_id": params.get("end_page_id", 99999),
            "return_md": True,
            "response_format_zip": True,
            "return_images": True,
        }

        server_url = params.get("server_url")
        if server_url:
            data["server_url"] = server_url

        try:
            start_time = time.time()

            logger.info(
                f"MinerU Start processing: {os.path.basename(file_path)} (backend={data['backend']}, lang={data['lang_list']})"
            )

            # Open the file and send the request
            with open(file_path, "rb") as f:
                files = {"files": (os.path.basename(file_path), f, "application/octet-stream")}

                # Send a POST request
                response = requests.post(
                    self.parse_endpoint,
                    files=files,
                    data=data,
                    timeout=int(os.environ.get("MINERU_TIMEOUT", 1800)),  # 30 minutes timeout
                )

            # Check response status
            logger.debug(
                f"MinerU response status: {response.status_code}, Content-Type: {response.headers.get('content-type')}"
            )

            if response.status_code != 200:
                error_detail = "unknown error"
                try:
                    error_data = response.json()
                    error_detail = error_data.get("detail", str(error_data))
                except Exception:
                    error_detail = response.text or f"HTTP {response.status_code}"

                logger.error(f"MinerU HTTP error {response.status_code}: {error_detail}")
                raise DocumentParserException(
                    f"MinerU Processing failed: {error_detail}",
                    self.get_service_name(),
                    f"http_{response.status_code}",
                )

            # Parse response
            try:
                # Get ZIP data directly from response content
                zip_data = response.content

                # Save to temporary file and process
                with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_zip:
                    tmp_zip.write(zip_data)
                    tmp_zip.flush()

                    try:
                        image_bucket = params.get("image_bucket") or "knowledgebases"
                        image_prefix = params.get("image_prefix") or "unknown/kb-images"

                        processed = process_zip_file_sync(
                            tmp_zip.name,
                            image_bucket=image_bucket,
                            image_prefix=image_prefix,
                        )
                        text = processed["markdown_content"]
                    finally:
                        os.unlink(tmp_zip.name)

                if not text:
                    logger.error("MinerU No text content was returned")
                    raise DocumentParserException(
                        "MinerU No text content was returned",
                        self.get_service_name(),
                        "no_content",
                    )

                processing_time = time.time() - start_time
                logger.info(
                    f"MinerU Processed successfully: {os.path.basename(file_path)} - {len(text)} character ({processing_time:.2f}s)"
                )

                return text

            except Exception as e:
                raise DocumentParserException(
                    f"MinerU Response parsing failed: {str(e)}",
                    self.get_service_name(),
                    "response_parse_error",
                )

        except DocumentParserException:
            raise
        except requests.exceptions.Timeout:
            error_msg = f"MinerU Processing timeout ({time.time() - start_time:.2f}s), The MINERU_TIMEOUT environment variable can be configured."
            logger.error(error_msg)
            raise DocumentParserException(error_msg, self.get_service_name(), "timeout")
        except requests.exceptions.ConnectionError:
            error_msg = "MinerU Connection failed,Please check if the service is running"
            logger.error(error_msg)
            raise DocumentParserException(error_msg, self.get_service_name(), "connection_error")
        except Exception as e:
            error_msg = f"MinerU Processing failed: {str(e)}"
            logger.error(f"{error_msg} ({time.time() - start_time:.2f}s)")
            raise DocumentParserException(error_msg, self.get_service_name(), "processing_failed")
