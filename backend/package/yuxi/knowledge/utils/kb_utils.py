import hashlib
import time

from yuxi.knowledge.chunking.ragflow_like.presets import resolve_chunk_processing_params
from yuxi.utils import hashstr, logger
from yuxi.utils.datetime_utils import utc_isoformat

_DROPPED_PROCESSING_PARAM_KEYS = {
    "_preprocessed_map",
    "auto_index",
    "content_hashes",
    "file_sizes",
    "enable_ocr",
}


def sanitize_processing_params(params: dict | None) -> dict | None:
    """Remove parameters that should not be written to single-file metadata."""
    if not params:
        return None

    return {key: value for key, value in params.items() if key not in _DROPPED_PROCESSING_PARAM_KEYS}


def resolve_processing_params(
    kb_additional_params: dict | None,
    file_processing_params: dict | None,
    request_params: dict | None = None,
) -> dict:
    merged_params = sanitize_processing_params(merge_processing_params(file_processing_params, request_params)) or {}
    merged_params["ocr_engine"] = merged_params.get("ocr_engine") or "disable"
    if not isinstance(merged_params.get("ocr_engine_config"), dict):
        merged_params["ocr_engine_config"] = {}

    chunk_params = resolve_chunk_processing_params(
        kb_additional_params=kb_additional_params,
        file_processing_params=file_processing_params,
        request_params=request_params,
    )
    merged_params.update(chunk_params)
    return merged_params


async def calculate_content_hash(data: bytes | bytearray) -> str:
    """Calculate SHA of file contents-256 Hash value."""
    sha256 = hashlib.sha256()
    sha256.update(data)
    return sha256.hexdigest()


async def prepare_item_metadata(item: str, content_type: str, kb_id: str, params: dict | None = None) -> dict:
    """
    Prepare MinIO file metadata; URL import must first pass fetch-url is preprocessed into MinIO document.

    Args:
        item: MinIO URL
        content_type: Content type, currently only supports "file"
        kb_id: Database ID
        params: Processing parameters, optional
    """
    # Check whether there is preprocessing information (for the case of URL to HTML file)
    if params and "_preprocessed_map" in params and item in params["_preprocessed_map"]:
        pre_info = params["_preprocessed_map"][item]

        # Use preprocessing information
        filename = pre_info.get("filename", item)  # Usually the original URL

        # Truncate filename to fit database limit (512 chars), retaining partial suffix information if possible
        if len(filename) > 500:
            filename_display = filename[:400] + "..." + filename[-90:]
        else:
            filename_display = filename

        file_type = "html"  # Force conversion to html type for subsequent processing as a file
        item_path = pre_info["path"]  # MinIO path
        content_hash = pre_info["content_hash"]

        # Use item(url) to generate ID to ensure that the ID will be different even if the same URL is added multiple times (coordinate with time)
        # Or should we base it on hash? No, it is more consistent with the upload logic based on time
        file_id = f"file_{hashstr(item + str(time.time()), 6)}"

        metadata = {
            "kb_id": kb_id,
            "filename": filename_display,
            "path": item_path,
            "file_type": file_type,
            "status": "indexing",
            "created_at": utc_isoformat(),
            "file_id": file_id,
            "content_hash": content_hash,
            "size": pre_info.get("file_size"),
            "parent_id": params.get("parent_id"),
        }

        if params:
            safe_params = sanitize_processing_params(params) or {}
            # Overwrite content_type to file to ensure that subsequent parsing follows the file process (MinIO download -> HTML parsing)
            # Instead of trying to crawl again as a URL
            safe_params["content_type"] = "file"
            safe_params["original_source"] = item  # Save full URL to JSON field to avoid database field length limit
            metadata["processing_params"] = safe_params

        return metadata

    if content_type == "file":
        if not is_minio_url(item):
            raise ValueError(f"File source must be a MinIO URL: {item}")

        logger.debug(f"Processing MinIO file: {item}")
        _, object_name = parse_minio_url(item)
        filename = object_name.rsplit("/", 1)[-1]

        import re

        timestamp_pattern = r"^(.+)_(\d{13})(\.[^.]+)$"
        match = re.match(timestamp_pattern, filename)
        filename_display = match.group(1) + match.group(3) if match else filename
        source_path = _normalize_source_path(params.get("source_path")) if params else None
        if source_path:
            filename_display = source_path

        file_type = filename_display.rsplit(".", 1)[-1].lower() if "." in filename_display else ""
        item_path = item

        content_hash = None
        if params and "content_hashes" in params and isinstance(params["content_hashes"], dict):
            content_hash = params["content_hashes"].get(item)

        if not content_hash:
            raise ValueError(f"Missing content_hash for file: {item}")

        file_sizes = params.get("file_sizes") if params else None
        if not isinstance(file_sizes, dict):
            file_sizes = {}
        file_size = file_sizes.get(item)
        file_id = f"file_{hashstr(str(item_path) + str(time.time()), 6)}"

    else:
        raise ValueError(f"Unsupported content_type: {content_type}")

    metadata = {
        "kb_id": kb_id,
        "filename": filename_display,  # Use display file name
        "path": item_path,
        "file_type": file_type,
        "status": "indexing",
        "created_at": utc_isoformat(),
        "file_id": file_id,
        "content_hash": content_hash,
        "size": file_size,
        "parent_id": params.get("parent_id") if params else None,
    }

    # Save processing parameters to metadata
    if params:
        metadata["processing_params"] = sanitize_processing_params(params)

    return metadata


def _normalize_source_path(value: object) -> str | None:
    """The normalized client passes in the of upload source path, which is only used to display the file name in the knowledge based document tree.

    source_path is used to retain the relative level of the CLI Table of contents when uploading. It won't be taken as real here
    Storage path use: backslashes will be converted to slashes, the beginning of "./" will be removed, the absolute path and
    ".." Parent directory jumps will be rejected.
    """
    if not isinstance(value, str):
        return None
    normalized = value.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if not normalized or normalized.startswith("/"):
        return None
    parts = [part for part in normalized.split("/") if part and part != "."]
    if not parts or any(part == ".." for part in parts):
        return None
    display_path = "/".join(parts)
    if len(display_path) > 512:
        raise ValueError("source_path is too long")
    return display_path


def merge_processing_params(metadata_params: dict | None, request_params: dict | None) -> dict:
    """
    Merge Processing parameters: priority use request parameter, if missing, of parameter in useMetadata

    Args:
        metadata_params: Save of parameters in Metadata
        request_params: of parameters provided in the request

    Returns:
        dict: Merged parameters
    """
    merged_params = {}

    # First use parameters from metadata as default values
    if metadata_params:
        merged_params.update(metadata_params)

    # Then override it with request parameters if provided
    if request_params:
        merged_params.update(request_params)

    logger.debug(
        "Merged processing params: "
        f"metadata_keys={list(metadata_params.keys()) if metadata_params else []}, "
        f"request_keys={list(request_params.keys()) if request_params else []}, "
        f"merged_keys={list(merged_params.keys())}"
    )
    return merged_params


def is_minio_url(file_path: str) -> bool:
    """Check whether the MinIO storage URL is generated by this system."""
    from urllib.parse import urlparse

    parsed_url = urlparse(file_path)
    if parsed_url.scheme == "minio":
        return bool(parsed_url.netloc and parsed_url.path.lstrip("/"))

    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        return False

    path_parts = parsed_url.path.lstrip("/").split("/", 1)
    if len(path_parts) != 2:
        return False

    from yuxi.storage.minio.client import MinIOClient

    known_buckets = set(MinIOClient.KB_BUCKETS.values()) | MinIOClient.PUBLIC_READ_BUCKETS
    return path_parts[0] in known_buckets


def parse_minio_url(file_path: str) -> tuple[str, str]:
    """
    parseMinIO URL, extract bucket name and object name

    support standard HTTP/HTTPS URL Format:
    - http(s)://host/bucket-name/path/to/object

    Args:
        file_path: MinIO file URL (http:// or https://)

    Returns:
        tuple[str, str]: (bucket_name, object_name)

    Raises:
        ValueError: Nếu không thể phân tích URL
    """
    try:
        from urllib.parse import unquote, urlparse

        # Parse URL
        parsed_url = urlparse(file_path)

        # For the minio:// protocol, the bucket name is in netloc
        if parsed_url.scheme == "minio":
            bucket_name = parsed_url.netloc
            object_name = unquote(parsed_url.path.lstrip("/"))
        else:
            # For the http/https protocol, the bucket name is in the first part of the path
            object_name = parsed_url.path.lstrip("/")
            path_parts = object_name.split("/", 1)
            if len(path_parts) > 1:
                bucket_name = path_parts[0]
                object_name = unquote(path_parts[1])
            else:
                raise ValueError(f"Không thể phân tích tên bucket trong URL MinIO: {file_path}")

        logger.debug(f"Parsed MinIO URL: bucket_name={bucket_name}, object_name={object_name}")
        return bucket_name, object_name

    except Exception as e:
        logger.error(f"Failed to parse MinIO URL {file_path}: {e}")
        raise ValueError(f"Không thể phân tích URL MinIO: {file_path}")
