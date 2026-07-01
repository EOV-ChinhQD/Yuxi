import hashlib
import os
import time
import uuid

from yuxi.utils.logging_config import logger


def is_text_pdf(pdf_path):
    import fitz

    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    if total_pages == 0:
        return False

    text_pages = 0
    for page_num in range(total_pages):
        page = doc.load_page(page_num)
        text = page.get_text()
        if text.strip():  # Check if there is text content
            text_pages += 1

    # Calculate the proportion of pages with text content
    text_ratio = text_pages / total_pages
    # If more than 50% of the page has text content, it is considered a text PDF
    return text_ratio > 0.5


def hashstr(input_string, length=None, with_salt=False, salt=None):
    """generatecharacter string of hash value
    Args:
        input_string: input character string
        length: intercept length, default is None, surface means not to intercept
        with_salt: Whether to add salt, the default is False
    """
    try:
        # Try encoding directly
        encoded_string = str(input_string).encode("utf-8")
    except UnicodeEncodeError:
        # If encoding fails, replace invalid characters
        encoded_string = str(input_string).encode("utf-8", errors="replace")

    if with_salt:
        if not salt:
            # Use a combination of timestamp + random number as salt to ensure uniqueness
            salt = f"{time.time()}_{uuid.uuid4().hex[:8]}"
        encoded_string = (encoded_string.decode("utf-8") + salt).encode("utf-8")

    hash = hashlib.sha256(encoded_string).hexdigest()
    if length:
        return hash[:length]
    return hash


def get_docker_safe_url(base_url):
    if not base_url:
        return base_url

    if os.getenv("RUNNING_IN_DOCKER") == "true":
        # Replace all possible local address forms
        base_url = base_url.replace("http://localhost", "http://host.docker.internal")
        base_url = base_url.replace("http://127.0.0.1", "http://host.docker.internal")
        logger.info(f"Running in docker, using {base_url} as base url")
    return base_url
