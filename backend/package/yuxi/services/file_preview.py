from __future__ import annotations

import asyncio
import mimetypes
import os
import shutil
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

MAX_BINARY_PREVIEW_SIZE_BYTES = 30 * 1024 * 1024
MAX_TEXT_PREVIEW_CHARS = 250_000

_MARKDOWN_EXTENSIONS = frozenset({".md", ".markdown", ".mdx"})
_PDF_EXTENSIONS = frozenset({".pdf"})
_HTML_EXTENSIONS = frozenset({".html", ".htm"})
_OFFICE_PDF_PREVIEW_EXTENSIONS = frozenset({".docx", ".pptx"})
_OFFICE_MEDIA_TYPES = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
_TEXT_EXTENSIONS = frozenset(
    {
        ".txt",
        ".text",
        ".log",
        ".json",
        ".jsonl",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".csv",
        ".tsv",
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".vue",
        ".css",
        ".less",
        ".scss",
        ".xml",
        ".sql",
        ".sh",
        ".bash",
        ".zsh",
        ".fish",
        ".env",
        ".dockerfile",
        ".gitignore",
        ".weather",
    }
)
_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"})
_BINARY_SIGNATURES = (
    b"\x7fELF",
    b"MZ",
    b"%PDF-",
    b"PK\x03\x04",
    b"PK\x05\x06",
    b"PK\x07\x08",
    b"\x89PNG\r\n\x1a\n",
    b"\xff\xd8\xff",
    b"GIF87a",
    b"GIF89a",
    b"RIFF",
)


def _office_preview_timeout_seconds() -> int:
    raw = os.getenv("OFFICE_PREVIEW_TIMEOUT_SECONDS", "60")
    try:
        return int(raw)
    except ValueError:
        return 60


OFFICE_PREVIEW_TIMEOUT_SECONDS = _office_preview_timeout_seconds()


class OfficePreviewConversionError(RuntimeError):
    """Office File conversion to PDF failed."""


def is_office_pdf_preview_file(path: str) -> bool:
    return PurePosixPath(path).suffix.lower() in _OFFICE_PDF_PREVIEW_EXTENSIONS


def is_binary_preview_type(preview_type: str) -> bool:
    return preview_type in {"image", "pdf"}


def render_preview_too_large_payload() -> dict:
    return {
        "content": None,
        "preview_type": "unsupported",
        "supported": False,
        "message": "The file is too large. Currently, only file previews within 30 MB are supported.",
        "truncated": False,
        "limit": MAX_BINARY_PREVIEW_SIZE_BYTES,
    }


def _office_converter_executable() -> str:
    executable = shutil.which("soffice") or shutil.which("libreoffice")
    if not executable:
        raise OfficePreviewConversionError("Xem trước Office PDF phụ thuộc vào LibreOffice, vui lòng cài đặt soffice/libreoffice trước")
    return executable


def _convert_office_to_pdf_sync(filename: str, content: bytes) -> bytes:
    suffix = PurePosixPath(filename).suffix.lower()
    if suffix not in _OFFICE_PDF_PREVIEW_EXTENSIONS:
        raise OfficePreviewConversionError("Loại tệp hiện tại không hỗ trợ chuyển đổi sang bản xem trước PDF")

    executable = _office_converter_executable()
    with tempfile.TemporaryDirectory(prefix="yuxi-office-preview-") as temp_dir:
        temp_path = Path(temp_dir)
        input_path = temp_path / f"source{suffix}"
        output_path = temp_path / "source.pdf"
        profile_path = temp_path / "lo-profile"
        profile_path.mkdir(parents=True, exist_ok=True)
        input_path.write_bytes(content)

        command = [
            executable,
            "--headless",
            "--nologo",
            "--nofirststartwizard",
            "--nodefault",
            "--nolockcheck",
            f"-env:UserInstallation={profile_path.resolve().as_uri()}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(temp_path),
            str(input_path),
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                timeout=OFFICE_PREVIEW_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise OfficePreviewConversionError(
                f"Office File conversion PDF timeout ({OFFICE_PREVIEW_TIMEOUT_SECONDS} Second)"
            ) from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).decode("utf-8", errors="ignore").strip()
            raise OfficePreviewConversionError(f"Chuyển đổi tệp Office sang PDF thất bại: {detail or 'LibreOffice thực thi thất bại'}")
        if not output_path.exists():
            detail = (result.stderr or result.stdout).decode("utf-8", errors="ignore").strip()
            raise OfficePreviewConversionError(f"Chuyển đổi tệp Office sang PDF thất bại: Không tạo được tệp PDF。{detail}")

        pdf_content = output_path.read_bytes()
        if not pdf_content.startswith(b"%PDF-"):
            raise OfficePreviewConversionError("Chuyển đổi tệp Office sang PDF thất bại: Tệp đầu ra không phải là PDF hợp lệ")
        return pdf_content


async def convert_office_to_pdf(filename: str, content: bytes) -> bytes:
    return await asyncio.to_thread(_convert_office_to_pdf_sync, filename, content)


def detect_preview_type(path: str, raw_content: bytes) -> tuple[str, bool, str | None]:
    suffix = PurePosixPath(path).suffix.lower()
    mime_type, _encoding = mimetypes.guess_type(path)
    head = raw_content[:1024]

    if suffix in _IMAGE_EXTENSIONS or (mime_type and mime_type.startswith("image/")):
        return "image", True, None

    if suffix in _PDF_EXTENSIONS or mime_type == "application/pdf" or head.startswith(b"%PDF-"):
        return "pdf", True, None

    if suffix in _MARKDOWN_EXTENSIONS:
        return "markdown", True, None

    if suffix in _HTML_EXTENSIONS:
        return "html", True, None

    if suffix in _TEXT_EXTENSIONS:
        return "text", True, None

    if b"\x00" in head:
        return "unsupported", False, "The current file is a binary file and preview is not currently supported."

    if any(head.startswith(signature) for signature in _BINARY_SIGNATURES):
        if head.startswith(b"RIFF") and b"WEBP" in head[:16]:
            return "image", True, None
        return "unsupported", False, "The current file format does not support preview yet"

    if mime_type:
        if mime_type.startswith("text/"):
            return "text", True, None
        if mime_type in {"application/json", "application/xml", "application/javascript"}:
            return "text", True, None
        if mime_type.startswith("application/"):
            return "unsupported", False, "The current file format does not support preview yet"

    if not raw_content:
        return "text", True, None

    try:
        raw_content.decode("utf-8")
        return "text", True, None
    except UnicodeDecodeError:
        return "unsupported", False, "The current file is not readable text and preview is not currently supported."


def render_preview_payload(path: str, raw_content: bytes) -> dict:
    preview_type, supported, message = detect_preview_type(path, raw_content)

    if is_binary_preview_type(preview_type) or not supported:
        return {
            "content": None,
            "preview_type": preview_type,
            "supported": supported,
            "message": message,
            "truncated": False,
            "limit": None,
        }

    try:
        content = raw_content.decode("utf-8")
    except UnicodeDecodeError:
        return {
            "content": None,
            "preview_type": "unsupported",
            "supported": False,
            "message": "The current file is not UTF-8 Text, preview is not supported yet",
            "truncated": False,
            "limit": None,
        }

    truncated = len(content) > MAX_TEXT_PREVIEW_CHARS
    if truncated:
        content = content[:MAX_TEXT_PREVIEW_CHARS]

    return {
        "content": content,
        "preview_type": preview_type,
        "supported": True,
        "message": message,
        "truncated": truncated,
        "limit": MAX_TEXT_PREVIEW_CHARS,
    }


def detect_media_type(path: str, raw_content: bytes | None = None) -> str:
    """Detect response media type, preferring file signatures over filename suffixes."""
    head = (raw_content or b"")[:512]

    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):
        return "image/gif"
    if head.startswith(b"RIFF") and b"WEBP" in head[:16]:
        return "image/webp"
    if head.startswith(b"BM"):
        return "image/bmp"
    if head.startswith(b"%PDF-"):
        return "application/pdf"

    stripped_head = head.lstrip()
    if stripped_head.startswith(b"<svg") or stripped_head.startswith(b"<?xml"):
        suffix = PurePosixPath(path).suffix.lower()
        if suffix == ".svg" or b"<svg" in stripped_head[:256]:
            return "image/svg+xml"

    suffix = PurePosixPath(path).suffix.lower()
    if suffix in _OFFICE_MEDIA_TYPES:
        return _OFFICE_MEDIA_TYPES[suffix]

    return mimetypes.guess_type(path)[0] or "application/octet-stream"
