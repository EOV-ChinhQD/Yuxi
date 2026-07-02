"""
MinerU Official parser

use MinerU official cloud service API for Document parsing
"""

import os
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any

import requests

from yuxi.knowledge.parser.base import BaseDocumentProcessor, DocumentParserException
from yuxi.knowledge.parser.zip_utils import process_zip_file_sync
from yuxi.utils import hashstr, logger


class MinerUOfficialParser(BaseDocumentProcessor):
    """MinerU Official API parser"""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("MINERU_API_KEY")
        if not self.api_key:
            raise DocumentParserException("Biến môi trường MINERU_API_KEY chưa được thiết lập", "mineru_official", "missing_api_key")

        self.api_base = "https://mineru.net/api/v4"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def get_service_name(self) -> str:
        return "mineru_official"

    def get_supported_extensions(self) -> list[str]:
        """MinerU File formats supported by official API"""
        return [".pdf", ".doc", ".docx", ".ppt", ".pptx", ".png", ".jpg", ".jpeg"]

    def check_health(self) -> dict[str, Any]:
        """Check API availability and key validity"""
        try:
            # Use a simple test request to verify the API key
            # Since there is no dedicated ping interface, we try to create a request for a test task
            test_data = {"url": "https://cdn-mineru.openxlab.org.cn/demo/example.pdf", "is_ocr": True}

            response = requests.post(f"{self.api_base}/extract/task", headers=self.headers, json=test_data, timeout=10)

            # If 401 or a specific API error code is returned, there is a problem with the key
            if response.status_code == 401:
                return {"status": "unhealthy", "message": "API Key is invalid or expired", "details": {"error_code": "A0202"}}
            elif response.status_code == 403:
                return {"status": "unhealthy", "message": "API Insufficient key permissions", "details": {"error_code": "A0211"}}
            elif response.status_code == 200:
                # Parse the response to check if the task was successfully created
                try:
                    result = response.json()
                    if result.get("code") == 0:
                        return {
                            "status": "healthy",
                            "message": "MinerU Official API service available",
                            "details": {"api_base": self.api_base},
                        }
                    else:
                        return {
                            "status": "unhealthy",
                            "message": f"API return error: {result.get('msg', 'unknown error')}",
                            "details": {"error_code": result.get("code")},
                        }
                except Exception:
                    return {
                        "status": "healthy",
                        "message": "MinerU Official API service available",
                        "details": {"api_base": self.api_base},
                    }
            else:
                return {
                    "status": "unhealthy",
                    "message": f"API Service exception: HTTP {response.status_code}",
                    "details": {"status_code": response.status_code},
                }

        except requests.exceptions.Timeout:
            return {"status": "timeout", "message": "API Request timeout", "details": {"timeout": "10s"}}
        except requests.exceptions.ConnectionError:
            return {
                "status": "unavailable",
                "message": "Unable to connect to MinerU official API service",
                "details": {"api_base": self.api_base},
            }
        except Exception as e:
            return {"status": "error", "message": f"Health check failed: {str(e)}", "details": {"error": str(e)}}

    def process_file(self, file_path: str, params: dict[str, Any] | None = None) -> str:
        """
        use MinerU official API Process files

        Args:
            file_path: local document path
            params: Processing parameters
                - is_ocr: Whether to enable OCR (default: True)
                - enable_formula: Whether to enable formula recognition (default: True)
                - enable_table: Whether to enable table recognition (default: True)
                - language: Document language (default: "ch")
                - page_ranges: Page range (default: None)
                - model_version: model version "pipeline" or "vlm" (default: "pipeline")

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

        # Check API health status first
        health = self.check_health()
        if health["status"] != "healthy":
            raise DocumentParserException(
                f"MinerU Official API is not available: {health['message']}", self.get_service_name(), health["status"]
            )

        # Processing parameters
        params = params or {}

        # Since the official API does not support direct file upload, we need to upload the file to an accessible URL first
        # Here we use the batch file upload interface
        try:
            start_time = time.time()
            logger.info(f"MinerU Official Start processing: {os.path.basename(file_path)}")

            # Step 1: Application document upload link
            batch_id = self._upload_file(file_path, params)
            logger.info(f"File uploaded successfully, batch_id: {batch_id}")

            # Step 2: Polling task results
            result = self._poll_batch_result(batch_id)
            logger.info(f"Task completed, status: {result['state']}")

            zip_url = result.get("full_zip_url")

            try:
                zip_path = self._download_zip(zip_url)
            except Exception:
                text = self._download_and_extract(zip_url)
                processing_time = time.time() - start_time
                logger.info(
                    f"MinerU Official: {os.path.basename(file_path)} - {len(text)} character ({processing_time:.2f}s)"
                )
                return text

            try:
                image_bucket = params.get("image_bucket") or "knowledgebases"
                image_prefix = params.get("image_prefix") or "unknown/kb-images"

                processed = process_zip_file_sync(
                    zip_path,
                    image_bucket=image_bucket,
                    image_prefix=image_prefix,
                )
                text = processed["markdown_content"]
            except Exception:
                import zipfile

                text = ""
                logger.error(f"Extract full from zip file.md fail: {zip_path}, use the first md file")
                with zipfile.ZipFile(zip_path, "r") as zf:
                    md_files = [n for n in zf.namelist() if n.lower().endswith(".md")]
                    if md_files:
                        md_file = next((n for n in md_files if Path(n).name == "full.md"), md_files[0])
                        with zf.open(md_file) as f:
                            text = f.read().decode("utf-8")
            finally:
                try:
                    os.unlink(zip_path)
                except Exception:
                    pass

            processing_time = time.time() - start_time
            logger.info(
                f"MinerU Official Processed successfully: {os.path.basename(file_path)} - {len(text)} character ({processing_time:.2f}s)"
            )

            return text

        except Exception as e:
            if isinstance(e, DocumentParserException):
                raise
            processing_time = time.time() - start_time
            error_msg = f"MinerU Official Processing failed: {str(e)}"
            logger.error(f"{error_msg} ({processing_time:.2f}s)")
            raise DocumentParserException(error_msg, self.get_service_name(), "processing_failed")

    def _upload_file(self, file_path: str, params: dict[str, Any]) -> str:
        """Upload files and return batch_id"""
        filename = os.path.basename(file_path)

        data_id = params.get("data_id", filename)
        if len(data_id) > 30:
            data_id = data_id[:30] + "_" + hashstr(data_id, length=8)

        upload_data = {
            "enable_formula": params.get("enable_formula", True),
            "enable_table": params.get("enable_table", True),
            "language": params.get("language", "ch"),
            "files": [
                {
                    "name": filename,
                    "is_ocr": params.get("is_ocr", True),
                    "data_id": data_id,
                    "page_ranges": params.get("page_ranges"),
                }
            ],
        }

        # Apply for upload link
        response = requests.post(f"{self.api_base}/file-urls/batch", headers=self.headers, json=upload_data, timeout=30)

        if response.status_code != 200:
            raise DocumentParserException(
                f"Failed to apply for upload link: HTTP {response.status_code}", self.get_service_name(), "upload_url_failed"
            )

        result = response.json()
        if result.get("code") != 0:
            error_msg = result.get("msg", "unknown error")
            raise DocumentParserException(
                f"Failed to apply for upload link: {error_msg}", self.get_service_name(), f"api_error_{result.get('code', 'unknown')}"
            )

        batch_id = result["data"]["batch_id"]
        upload_urls = result["data"]["file_urls"]

        if not upload_urls:
            raise DocumentParserException("Không lấy được liên kết tải lên file", self.get_service_name(), "no_upload_url")

        # Upload files
        upload_url = upload_urls[0]
        with open(file_path, "rb") as f:
            upload_response = requests.put(upload_url, data=f, timeout=60)

        if upload_response.status_code != 200:
            raise DocumentParserException(
                f"File upload failed: HTTP {upload_response.status_code}", self.get_service_name(), "file_upload_failed"
            )

        return batch_id

    def _poll_batch_result(self, batch_id: str, max_wait_time: int = 600) -> dict[str, Any]:
        """Polling batch task results"""
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            response = requests.get(
                f"{self.api_base}/extract-results/batch/{batch_id}", headers=self.headers, timeout=30
            )

            if response.status_code != 200:
                raise DocumentParserException(
                    f"Failed to query task status: HTTP {response.status_code}", self.get_service_name(), "status_query_failed"
                )

            result = response.json()
            if result.get("code") != 0:
                error_msg = result.get("msg", "unknown error")
                raise DocumentParserException(
                    f"Failed to query task status: {error_msg}",
                    self.get_service_name(),
                    f"api_error_{result.get('code', 'unknown')}",
                )

            extract_results = result["data"].get("extract_result", [])
            if not extract_results:
                time.sleep(5)
                continue

            # Check the status of the first file
            file_result = extract_results[0]
            state = file_result.get("state")

            if state == "done":
                return file_result
            elif state == "failed":
                err_msg = file_result.get("err_msg", "unknown error")
                raise DocumentParserException(f"Phân tích tài liệu thất bại: {err_msg}", self.get_service_name(), "parsing_failed")

            # Keep waiting
            time.sleep(5)

        raise DocumentParserException("Hết thời gian xử lý nhiệm vụ", self.get_service_name(), "timeout")

    def _download_and_extract(self, zip_url: str) -> str:
        """Download and unzip the results file"""
        if not zip_url:
            raise DocumentParserException("Không lấy được liên kết tải kết quả", self.get_service_name(), "no_download_url")

        # Download file
        response = requests.get(zip_url, timeout=60)
        if response.status_code != 200:
            raise DocumentParserException(
                f"Download result failed: HTTP {response.status_code}", self.get_service_name(), "download_failed"
            )

        # Unzip to temporary directory
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_file:
            tmp_file.write(response.content)
            tmp_file.flush()

            try:
                with tempfile.TemporaryDirectory() as tmp_dir:
                    with zipfile.ZipFile(tmp_file.name, "r") as zip_ref:
                        zip_ref.extractall(tmp_dir)

                    # Find markdown files
                    md_files = list(Path(tmp_dir).glob("*.md"))
                    if md_files:
                        with open(md_files[0], encoding="utf-8") as f:
                            return f.read()

                    # If there is no markdown file, look for the json file
                    json_files = list(Path(tmp_dir).glob("*.json"))
                    if json_files:
                        import json

                        with open(json_files[0], encoding="utf-8") as f:
                            data = json.load(f)
                            # Try to extract text content
                            if isinstance(data, dict) and "content" in data:
                                return str(data["content"])
                            return str(data)

                    # If there are none, return the contents of the first text file
                    text_files = list(Path(tmp_dir).glob("*"))
                    if text_files:
                        with open(text_files[0], encoding="utf-8") as f:
                            return f.read()

                    raise DocumentParserException(
                        "Unable to extract text content from results", self.get_service_name(), "extract_content_failed"
                    )

            finally:
                os.unlink(tmp_file.name)

    def _download_zip(self, zip_url: str) -> str:
        """Download the resulting ZIP to a temporary file and return the path"""
        if not zip_url:
            raise DocumentParserException("Không lấy được liên kết tải kết quả", self.get_service_name(), "no_download_url")
        response = requests.get(zip_url, timeout=60)
        if response.status_code != 200:
            raise DocumentParserException(
                f"Download result failed: HTTP {response.status_code}", self.get_service_name(), "download_failed"
            )
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_file:
            tmp_file.write(response.content)
            tmp_file.flush()
            return tmp_file.name
