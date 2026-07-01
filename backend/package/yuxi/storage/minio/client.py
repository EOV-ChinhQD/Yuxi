"""
MinIO storage client
Simplifying of MinIO object storage operations
"""

import asyncio
import json
import mimetypes
import os
from contextlib import asynccontextmanager
from datetime import timedelta
from io import BytesIO

from urllib3 import BaseHTTPResponse
from yuxi.utils import logger

from minio import Minio
from minio.error import S3Error


class StorageError(Exception):
    """Storage-related exception base class"""

    pass


class StorageUploadError(StorageError):
    """Storage-related exception base class"""


class UploadResult:
    """Simplified upload results"""

    def __init__(self, url: str, bucket_name: str, object_name: str):
        self.url = url
        self.bucket_name = bucket_name
        self.object_name = object_name


class MinIOClient:
    """
    Simplified MinIO client class
    """

    PUBLIC_READ_BUCKETS = {"public"}

    # Bucket name related to knowledge base
    KB_BUCKETS = {
        "documents": "knowledgebases",
        "parsed": "knowledgebases",
        "images": "public",
    }

    def __init__(self):
        """Initialize the MinIO client"""
        self.endpoint = os.getenv("MINIO_URI") or "http://minio:9000"
        self.access_key = os.getenv("MINIO_ACCESS_KEY") or "minioadmin"
        self.secret_key = os.getenv("MINIO_SECRET_KEY") or "minioadmin"
        self._client = None

        # Set up a publicly accessible endpoint
        if os.getenv("RUNNING_IN_DOCKER"):
            host_ip = (os.getenv("HOST_IP") or "").strip()
            if not host_ip:
                host_ip = "localhost"
            if "://" in host_ip:
                host_ip = host_ip.split("://")[-1]
            host_ip = host_ip.rstrip("/")
            self.public_endpoint = f"{host_ip}:9000"
            logger.debug(f"Docker MinIOClient public_endpoint: {self.public_endpoint}")
        else:
            self.public_endpoint = "localhost:9000"
            logger.debug(f"Default_client: {self.public_endpoint}")

    @property
    def client(self) -> Minio:
        """Get a MinIO client instance"""
        if self._client is None:
            endpoint = self.endpoint
            if "://" in endpoint:
                endpoint = endpoint.split("://")[-1]

            self._client = Minio(
                endpoint=endpoint, access_key=self.access_key, secret_key=self.secret_key, secure=False
            )
        return self._client

    def ensure_bucket_exists(self, bucket_name: str) -> bool:
        """Make sure the bucket exists"""
        try:
            created = False
            if not self.client.bucket_exists(bucket_name=bucket_name):
                self.client.make_bucket(bucket_name=bucket_name)
                created = True
                logger.info(f"bucket '{bucket_name}' Created")

            self._ensure_public_read_access(bucket_name)

            if created and bucket_name in self.PUBLIC_READ_BUCKETS:
                logger.info(f"bucket '{bucket_name}' Configured to be publicly readable")

            return True
        except S3Error as e:
            logger.error(f"bucket '{bucket_name}' mistake: {e}")
            raise StorageError(f"Error with bucket '{bucket_name}': {e}")
        except StorageError:
            raise

    def upload_file(
        self, bucket_name: str, object_name: str, data: bytes, content_type: str | None = None
    ) -> UploadResult:
        """Upload files to MinIO"""
        try:
            self.ensure_bucket_exists(bucket_name=bucket_name)

            resolved_content_type = content_type or self._guess_content_type(object_name)
            data_stream = BytesIO(data)
            result = self.client.put_object(
                bucket_name=bucket_name,
                object_name=object_name,
                data=data_stream,
                length=len(data),
                content_type=resolved_content_type,
            )

            assert result is not None
            url = f"http://{self.public_endpoint}/{bucket_name}/{object_name}"

            return UploadResult(url, bucket_name, object_name)

        except S3Error as e:
            error_msg = f"Upload files '{object_name}' fail: {e}"
            logger.error(error_msg)
            raise StorageError(error_msg)

    async def aupload_file(
        self,
        bucket_name: str,
        object_name: str,
        data: bytes,
        content_type: str | None = None,
    ) -> UploadResult:
        result = await asyncio.to_thread(
            self.upload_file, bucket_name=bucket_name, object_name=object_name, data=data, content_type=content_type
        )
        return result

    def upload_file_from_path(self, bucket_name: str, object_name: str, file_path: str) -> UploadResult:
        """Upload file from file path"""
        try:
            with open(file_path, "rb") as file_data:
                data = file_data.read()

            return self.upload_file(bucket_name, object_name, data)

        except FileNotFoundError:
            raise StorageError(f"Tệp '{file_path}' không tồn tại")
        except Exception as e:
            raise StorageError(f"Tải lên tệp từ đường dẫn thất bại: {e}")

    def _guess_content_type(self, object_name: str) -> str:
        """Guess MIME type based on file name"""
        guessed_type, _ = mimetypes.guess_type(object_name)
        if guessed_type:
            return guessed_type

        ext = object_name.split(".")[-1].lower()
        content_types = {
            "md": "text/markdown",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "xls": "application/vnd.ms-excel",
            "zip": "application/zip",
            "webp": "image/webp",
            "bmp": "image/bmp",
            "tif": "image/tiff",
            "tiff": "image/tiff",
        }
        return content_types.get(ext, "application/octet-stream")

    def download_file(self, bucket_name: str, object_name: str) -> bytes:
        """Download file"""
        try:
            response = self.client.get_object(bucket_name=bucket_name, object_name=object_name)
            data = response.read()
            response.close()
            logger.info(f"Successfully downloaded '{object_name}' from bucket '{bucket_name}'")
            return data

        except S3Error as e:
            if e.code == "NoSuchKey":
                raise StorageError(f"Đối tượng '{object_name}' không tồn tại trong bucket '{bucket_name}'")
            raise StorageError(f"Tải xuống tệp thất bại: {e}")

    async def adownload_response(self, bucket_name: str, object_name: str) -> BaseHTTPResponse:
        """Download files asynchronously"""
        try:
            response = await asyncio.to_thread(
                self.client.get_object,
                bucket_name=bucket_name,
                object_name=object_name,
            )
            return response

        except S3Error as e:
            if e.code == "NoSuchKey":
                raise StorageError(f"Đối tượng '{object_name}' không tồn tại trong bucket '{bucket_name}'")
            raise StorageError(f"Tải xuống tệp thất bại: {e}")

    async def adownload_file(self, bucket_name: str, object_name: str) -> bytes:
        """Download files asynchronously"""
        try:
            response = await asyncio.to_thread(self.client.get_object, bucket_name=bucket_name, object_name=object_name)
            data = await asyncio.to_thread(response.read)
            response.close()
            logger.info(f"Successfully downloaded '{object_name}' from bucket '{bucket_name}'")
            return data

        except S3Error as e:
            if e.code == "NoSuchKey":
                raise StorageError(f"Đối tượng '{object_name}' không tồn tại trong bucket '{bucket_name}'")
            raise StorageError(f"Tải xuống tệp thất bại: {e}")

    def get_presigned_url(self, bucket_name: str, object_name: str, days=7) -> str:
        """Put minio on the internal network for access, and access it externally through the return proxy link"""
        res_url = self.client.get_presigned_url(
            method="GET", bucket_name=bucket_name, object_name=object_name, expires=timedelta(days=days)
        )
        return res_url

    def delete_file(self, bucket_name: str, object_name: str) -> bool:
        """Delete files"""
        try:
            self.client.remove_object(bucket_name=bucket_name, object_name=object_name)
            logger.info(f"successfully deleted '{object_name}' from bucket '{bucket_name}'")
            return True

        except S3Error as e:
            if e.code == "NoSuchKey":
                logger.warning(f"object to delete '{object_name}' does not exist")
                return False
            raise StorageError(f"Xóa tệp thất bại: {e}")

    async def adelete_file(self, bucket_name: str, object_name: str) -> bool:
        """Delete files"""
        result = await asyncio.to_thread(
            self.delete_file,
            bucket_name=bucket_name,
            object_name=object_name,
        )
        return result

    async def adelete_objects_by_prefix(self, bucket_name: str, prefix: str) -> int:
        """
        Delete objects by prefix

        Args:
            bucket_name: bucket name
            prefix: object prefix

        Returns:
            Number of objects deleted
        """
        deleted_count = 0

        def _delete_objects():
            nonlocal deleted_count
            try:
                objects = self.client.list_objects(bucket_name, prefix=prefix, recursive=True)
                for obj in objects:
                    try:
                        self.client.remove_object(bucket_name, obj.object_name)
                        deleted_count += 1
                    except S3Error as e:
                        logger.warning(f"Failed to delete {bucket_name}/{obj.object_name}: {e}")
            except S3Error as e:
                logger.warning(f"Failed to list objects in {bucket_name}/{prefix}: {e}")

        await asyncio.to_thread(_delete_objects)
        return deleted_count

    async def adelete_bucket(self, bucket_name: str) -> bool:
        """
        Delete bucket (Delete all objects first, Delete bucket again)

        Args:
            bucket_name: bucket name

        Returns:
            Is it successful?
        """
        try:
            # Delete all objects first
            await self.adelete_objects_by_prefix(bucket_name, "")
            # Delete bucket again
            await asyncio.to_thread(self.client.remove_bucket, bucket_name)
            logger.info(f"bucket deleted successfully: {bucket_name}")
            return True
        except S3Error as e:
            if e.code == "NoSuchBucket":
                logger.warning(f"bucket does not exist: {bucket_name}")
                return False
            raise StorageError(f"Xóa bucket thất bại: {e}")

    def file_exists(self, bucket_name: str, object_name: str) -> bool:
        """Check if the file exists"""
        try:
            self.client.stat_object(bucket_name=bucket_name, object_name=object_name)
            return True
        except S3Error as e:
            if e.code == "NoSuchKey":
                return False
            raise StorageError(f"Kiểm tra sự tồn tại của tệp thất bại: {e}")

    def stat_file(self, bucket_name: str, object_name: str) -> int | None:
        """Get the file size (bytes), return None if the file does not exist"""
        try:
            stat = self.client.stat_object(bucket_name=bucket_name, object_name=object_name)
            return stat.size
        except S3Error as e:
            if e.code == "NoSuchKey":
                return None
            raise StorageError(f"Lấy thông tin tệp thất bại: {e}")

    async def astat_file(self, bucket_name: str, object_name: str) -> int | None:
        """Get the file size (bytes) asynchronously, returning None if the file does not exist"""
        return await asyncio.to_thread(self.stat_file, bucket_name, object_name)

    def _ensure_public_read_access(self, bucket_name: str) -> None:
        """Set bucket policy to allow public reading of objects"""
        if bucket_name not in self.PUBLIC_READ_BUCKETS:
            return

        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": ["*"]},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{bucket_name}/*"],
                },
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": ["*"]},
                    "Action": ["s3:ListBucket"],
                    "Resource": [f"arn:aws:s3:::{bucket_name}"],
                },
            ],
        }

        try:
            self.client.set_bucket_policy(bucket_name=bucket_name, policy=json.dumps(policy))
        except S3Error as e:
            logger.warning(f"Set up bucket '{bucket_name}' Public read policy failed: {e}")
            raise StorageError(f"Không thể thiết lập chính sách truy cập công khai cho bucket: {e}")

    @asynccontextmanager
    async def temp_file_from_url(
        self,
        url: str,
        allowed_extensions: list[str] | None = None,
    ):
        """
        Asynchronous context manager: Download filearrive temporary document from MinIO URL, automatically clean up after use

        Args:
            url: MinIO document URL
            allowed_extensions: allow office extension column surface (optional)

        Yields:
            str: temporary document path

        Raises:
            StorageError: If the URL is invalid or the download fails
        """
        import tempfile
        from urllib.parse import urlparse

        # Verify URL
        if not url or not isinstance(url, str):
            raise StorageError("URL không được để trống")

        url = url.strip()

        if not url.startswith(("http://", "https://")):
            raise StorageError("URL MinIO không hợp lệ, chỉ cho phép http/https")

        parsed = urlparse(url)

        # Verify host
        endpoint_host = self.endpoint.split("://")[-1].split(":")[0]
        url_host = parsed.netloc.split(":")[0]

        if endpoint_host != url_host and url_host != os.environ.get("HOST_IP", "localhost"):
            raise StorageError(f"URL bên ngoài không được phép: {url_host}")

        # Check path traversal
        if ".." in url or "\\" in url:
            raise StorageError("URL chứa ký tự duyệt qua đường dẫn")

        # Verify extension
        if allowed_extensions and not any(url.endswith(ext) for ext in allowed_extensions):
            raise StorageError(f"Phần mở rộng tệp không đáp ứng yêu cầu, cho phép: {', '.join(allowed_extensions)}")

        # Parse bucket and object names
        path_parts = parsed.path.lstrip("/").split("/", 1)
        if len(path_parts) != 2:
            raise StorageError("Không thể phân tích URL MinIO")

        bucket_name, object_name = path_parts

        # Download file
        file_data = await self.adownload_file(bucket_name, object_name)
        logger.info(f"Successfully downloaded file from MinIO: {object_name} ({len(file_data)} bytes)")

        # Create temporary files
        if allowed_extensions:
            suffix = next((ext for ext in allowed_extensions if url.endswith(ext)), ".tmp")
        else:
            suffix = f".{object_name.split('.')[-1]}"

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="wb", suffix=suffix, delete=False) as temp_file:
                temp_file.write(file_data)
                temp_path = temp_file.name

            logger.info(f"File downloaded to temporary path: {temp_path}")
            yield temp_path

        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                    logger.info(f"Temporary files deleted: {temp_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete temporary files: {e}")


# Global client instance
_default_client = None


def get_minio_client() -> MinIOClient:
    """Get a MinIO client instance"""
    global _default_client
    if _default_client is None:
        _default_client = MinIOClient()
    return _default_client


async def aupload_file_to_minio(bucket_name: str, file_name: str, data: bytes) -> str:
    """
    Pass byteUpload files to MinIO's asynchronous interface and return the resource URL.
    The MIME type is automatically inferred internally by the MinIO client based on object_name.

    Args:
        bucket_name: bucket_name
        file_name : filename
        data: documentbyte stream
    Returns:
        str: File access URL
    """
    client = get_minio_client()
    upload_result = await client.aupload_file(bucket_name, file_name, data)
    return upload_result.url
