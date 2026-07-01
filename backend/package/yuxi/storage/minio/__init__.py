"""
MinIO storage module
Simplify the object storage functionality of
"""

# Export core functionality
from .client import MinIOClient, StorageError, UploadResult, aupload_file_to_minio, get_minio_client
from .utils import generate_unique_filename, get_file_size, upload_image_to_minio

# Export commonly used functions
__all__ = [
    # Core functions
    "MinIOClient",
    "get_minio_client",
    "aupload_file_to_minio",
    # Exception class
    "StorageError",
    "UploadResult",
    # Utility function
    "get_file_size",
    "generate_unique_filename",
    "upload_image_to_minio",
]
