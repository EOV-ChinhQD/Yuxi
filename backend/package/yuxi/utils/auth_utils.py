import hashlib
import os
import secrets
from datetime import timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError

from yuxi.utils.datetime_utils import utc_now

JWT_ALGORITHM = "HS256"
JWT_EXPIRATION = 7 * 24 * 60 * 60
JWT_AUDIENCE = "yuxi-know-api"
PUBLIC_DEFAULT_JWT_SECRET_KEY = "yuxi_know_secure_key"
PASSWORD_HASHER = PasswordHasher()


def _is_production_env() -> bool:
    return os.environ.get("YUXI_ENV", "development").strip().lower() in {"prod", "production"}


def _get_or_create_dev_env(name: str, value_factory) -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    if _is_production_env():
        raise ValueError(
            f"{name} chưa được cấu hình, vui lòng thiết lập giá trị ngẫu nhiên tĩnh trong .env.prod cho môi trường sản xuất"
        )

    value = value_factory()
    os.environ[name] = value
    print(
        f"{name} Not configured. The development environment has automatically generated a temporary random value, which will be regenerated after the service is restarted."
    )
    return value


def _get_jwt_secret_key() -> str:
    secret_key = _get_or_create_dev_env("JWT_SECRET_KEY", lambda: secrets.token_hex(32))
    if _is_production_env() and secret_key == PUBLIC_DEFAULT_JWT_SECRET_KEY:
        raise ValueError(
            "JWT_SECRET_KEY không thể sử dụng khóa mặc định công khai, vui lòng tạo khóa mạnh ngẫu nhiên mới"
        )
    return secret_key


def _get_jwt_issuer() -> str:
    instance_id = _get_or_create_dev_env("YUXI_INSTANCE_ID", lambda: f"instance-{secrets.token_hex(8)}")
    return f"yuxi-know:{instance_id}"


class AuthUtils:
    @staticmethod
    def generate_api_key() -> tuple[str, str, str]:
        random_part = secrets.token_hex(24)
        full_key = f"yxkey_{random_part}"
        key_hash = hashlib.sha256(full_key.encode()).hexdigest()
        key_prefix = full_key[:12]
        return full_key, key_hash, key_prefix

    @staticmethod
    def hash_password(password: str) -> str:
        return PASSWORD_HASHER.hash(password)

    @staticmethod
    def verify_password(stored_password: str, provided_password: str) -> bool:
        if not stored_password.startswith("$argon2"):
            return False
        try:
            return PASSWORD_HASHER.verify(stored_password, provided_password)
        except (InvalidHash, VerifyMismatchError, VerificationError):
            return False

    @staticmethod
    def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
        to_encode = data.copy()
        expire = utc_now() + (expires_delta or timedelta(seconds=JWT_EXPIRATION))
        to_encode.update({"exp": expire, "iss": _get_jwt_issuer(), "aud": JWT_AUDIENCE})
        return jwt.encode(to_encode, _get_jwt_secret_key(), algorithm=JWT_ALGORITHM)

    @staticmethod
    def decode_token(token: str) -> dict[str, Any] | None:
        try:
            return jwt.decode(
                token,
                _get_jwt_secret_key(),
                algorithms=[JWT_ALGORITHM],
                issuer=_get_jwt_issuer(),
                audience=JWT_AUDIENCE,
                options={"require": ["exp", "sub", "iss", "aud"]},
            )
        except (jwt.PyJWTError, ValueError):
            return None

    @staticmethod
    def verify_access_token(token: str) -> dict[str, Any]:
        try:
            return jwt.decode(
                token,
                _get_jwt_secret_key(),
                algorithms=[JWT_ALGORITHM],
                issuer=_get_jwt_issuer(),
                audience=JWT_AUDIENCE,
                options={"require": ["exp", "sub", "iss", "aud"]},
            )
        except jwt.ExpiredSignatureError:
            raise ValueError("Token đã hết hạn")
        except jwt.InvalidTokenError:
            raise ValueError("Token không hợp lệ")

    @staticmethod
    def generate_image_token(object_name: str, expires_in_seconds: int = 7200) -> str:
        """Generate a signature token for a specific image object in MinIO."""
        import hmac
        import hashlib
        import time

        expires_at = int(time.time()) + expires_in_seconds
        message = f"{object_name}:{expires_at}"
        sig = hmac.new(_get_jwt_secret_key().encode(), message.encode(), hashlib.sha256).hexdigest()
        return f"{sig}:{expires_at}"

    @staticmethod
    def verify_image_token(object_name: str, token: str) -> bool:
        """Verify the signature token for a specific image object."""
        import hmac
        import hashlib
        import time

        try:
            if ":" not in token:
                return False
            sig, expires_str = token.split(":", 1)
            expires_at = int(expires_str)
            if expires_at < time.time():
                return False
            message = f"{object_name}:{expires_at}"
            expected_sig = hmac.new(_get_jwt_secret_key().encode(), message.encode(), hashlib.sha256).hexdigest()
            return hmac.compare_digest(sig, expected_sig)
        except Exception:
            return False

    @staticmethod
    def sign_markdown_images(text: str, expires_in_seconds: int = 7200) -> str:
        """Find all /api/v1/knowledge/images/ URLs in markdown and sign them with a token."""
        import re

        if not isinstance(text, str):
            return text

        pattern = r"(/api/v1/knowledge/images/([^\)\"\s\?]+))"

        def replace_match(match):
            full_url = match.group(1)
            object_name = match.group(2)
            token = AuthUtils.generate_image_token(object_name, expires_in_seconds)
            if "?" in full_url:
                return f"{full_url}&token={token}"
            return f"{full_url}?token={token}"

        return re.sub(pattern, replace_match, text)
