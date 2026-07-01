"""OIDC service module.

Unified package of OIDC Configuration, tool capabilities and authentication business processing logic
"""

import hashlib
import os
import secrets
import time
import urllib.parse
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from yuxi.repositories.user_repository import UserRepository
from yuxi.services.operation_log_service import log_operation
from yuxi.storage.postgres.models_business import Department, User
from yuxi.utils.auth_utils import AuthUtils
from yuxi.utils.datetime_utils import utc_now_naive
from yuxi.utils.logging_config import logger

# Front-end OIDC callback routing path (consistent with the routing in web/src/router/index.js)
FRONTEND_CALLBACK_PATH = "/auth/oidc/callback"
# Login page path
FRONTEND_LOGIN_PATH = "/login"


class OIDCConfig(BaseModel):
    """OIDC Configure model"""

    enabled: bool = Field(default=False, description="Bật xác thực OIDC")
    issuer_url: str = Field(default="", description="URL issuer của OIDC Provider")
    client_id: str = Field(default="", description="OIDC Client ID")
    client_secret: str = Field(default="", description="OIDC Client Secret")
    redirect_uri: str = Field(default="", description="URL callback OIDC")
    authorization_endpoint: str = Field(default="", description="URL endpoint ủy quyền")
    token_endpoint: str = Field(default="", description="URL endpoint Token")
    userinfo_endpoint: str = Field(default="", description="URL endpoint UserInfo")
    end_session_endpoint: str = Field(default="", description="URL endpoint đăng xuất")
    provider_name: str = Field(default="Đăng nhập OIDC", description="Tên nguồn xác thực, văn bản hiển thị trên nút đăng nhập")
    scopes: str = Field(default="openid profile email", description="Phạm vi scope yêu cầu")
    auto_create_user: bool = Field(default=True, description="Có tự động tạo người dùng không")
    default_role: str = Field(default="user", description="Vai trò mặc định của người dùng OIDC")
    default_department: str = Field(default="Người dùng OIDC", description="Bộ phận mặc định của người dùng OIDC")
    username_claim: str = Field(default="preferred_username", description="Trường ánh xạ tên người dùng")
    email_claim: str = Field(default="email", description="Trường ánh xạ email")
    name_claim: str = Field(default="name", description="Trường ánh xạ tên")
    use_raw_username: bool = Field(default=False, description="Có sử dụng tên người dùng gốc (không có tiền tố oidc) không")
    fetch_department_info: bool = Field(default=False, description="Có lấy thông tin bộ phận từ OIDC không")
    department_claim: str = Field(default="department", description="Trường ánh xạ thông tin bộ phận")
    force_prompt_login: bool = Field(default=False, description="Có ép buộc người dùng đăng nhập lại (thêm tham số prompt=login) không")

    @classmethod
    def from_env(cls) -> "OIDCConfig":
        """Load configuration from environment variables"""

        def _env(name: str, default: str = "") -> str:
            return os.environ.get(name, default).strip()

        enabled = os.environ.get("OIDC_ENABLED", "false").lower() == "true"

        if not enabled:
            return cls(enabled=False)

        return cls(
            enabled=enabled,
            provider_name=_env("OIDC_PROVIDER_NAME", "Đăng nhập OIDC"),
            issuer_url=_env("OIDC_ISSUER_URL"),
            client_id=_env("OIDC_CLIENT_ID"),
            client_secret=_env("OIDC_CLIENT_SECRET"),
            redirect_uri=_env("OIDC_REDIRECT_URI"),
            authorization_endpoint=_env("OIDC_AUTHORIZATION_ENDPOINT"),
            token_endpoint=_env("OIDC_TOKEN_ENDPOINT"),
            userinfo_endpoint=_env("OIDC_USERINFO_ENDPOINT"),
            end_session_endpoint=_env("OIDC_END_SESSION_ENDPOINT"),
            scopes=_env("OIDC_SCOPES", "openid profile email"),
            auto_create_user=os.environ.get("OIDC_AUTO_CREATE_USER", "true").lower() == "true",
            default_role=_env("OIDC_DEFAULT_ROLE", "user"),
            default_department=_env("OIDC_DEFAULT_DEPARTMENT", "Người dùng OIDC"),
            username_claim=_env("OIDC_USERNAME_CLAIM", "preferred_username"),
            email_claim=_env("OIDC_EMAIL_CLAIM", "email"),
            name_claim=_env("OIDC_NAME_CLAIM", "name"),
            use_raw_username=os.environ.get("OIDC_USE_RAW_USERNAME", "false").lower() == "true",
            fetch_department_info=os.environ.get("OIDC_FETCH_DEPARTMENT_INFO", "false").lower() == "true",
            department_claim=_env("OIDC_DEPARTMENT_CLAIM", "department"),
            force_prompt_login=os.environ.get("OIDC_FORCE_PROMPT_LOGIN", "true").lower() == "true",
        )

    def is_configured(self) -> bool:
        """Check whether the configuration required for login link generation is complete"""
        if not self.enabled:
            return False
        # Generating a login link only requires client_id + (issuer_url or authorization_endpoint)
        return bool(self.client_id and (self.issuer_url or self.authorization_endpoint))

    def is_token_exchange_configured(self) -> bool:
        """Check whether the configuration required to exchange authorization code for token is complete"""
        if not self.enabled:
            return False
        # Callback to exchange token requires client_id + client_secret + (issuer_url or token_endpoint)
        return bool(self.client_id and self.client_secret and (self.issuer_url or self.token_endpoint))


oidc_config = OIDCConfig.from_env()


class OIDCProviderMetadata:
    """OIDC Provider Metadata"""

    def __init__(self):
        self.authorization_endpoint: str | None = None
        self.token_endpoint: str | None = None
        self.userinfo_endpoint: str | None = None
        self.end_session_endpoint: str | None = None
        self.last_error: str | None = None
        self._loaded = False

    async def load(self, issuer_url: str) -> bool:
        """Load metadata from discovery endpoint"""
        if self._loaded:
            return True

        discovery_url = f"{issuer_url.rstrip('/')}/.well-known/openid-configuration"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(discovery_url, timeout=30.0)
                response.raise_for_status()
                metadata = response.json()

            self.authorization_endpoint = metadata.get("authorization_endpoint")
            self.token_endpoint = metadata.get("token_endpoint")
            self.userinfo_endpoint = metadata.get("userinfo_endpoint")
            self.end_session_endpoint = metadata.get("end_session_endpoint")

            # Login URL generation requires at least authorization_endpoint.
            if not self.authorization_endpoint:
                self.last_error = "discovery Response is missing authorization_endpoint"
                logger.error(f"Failed to load OIDC discovery: {self.last_error}, url={discovery_url}")
                return False

            self._loaded = True
            self.last_error = None
            logger.info(f"OIDC discovery loaded from {discovery_url}")
            return True

        except Exception as e:
            self.last_error = f"{type(e).__name__}: {repr(e)}"
            logger.error(f"Failed to load OIDC discovery: {self.last_error}, url={discovery_url}")
            return False


class OIDCUtils:
    """OIDC Tools"""

    _metadata: OIDCProviderMetadata | None = None
    _state_store: dict[str, dict[str, Any]] = {}
    _login_code_store: dict[str, dict[str, Any]] = {}
    _state_ttl_seconds = 300
    _login_code_ttl_seconds = 60
    _last_metadata_error: str | None = None

    @classmethod
    def _cleanup_expired_state(cls) -> None:
        now = time.time()
        expired = [k for k, v in cls._state_store.items() if v["expires_at"] <= now]
        for key in expired:
            cls._state_store.pop(key, None)

    @classmethod
    def _cleanup_expired_login_code(cls) -> None:
        now = time.time()
        expired = [k for k, v in cls._login_code_store.items() if v["expires_at"] <= now]
        for key in expired:
            cls._login_code_store.pop(key, None)

    @classmethod
    async def get_metadata(cls) -> OIDCProviderMetadata | None:
        """Get OIDC Provider metadata"""
        if not oidc_config.enabled or not oidc_config.is_configured():
            cls._last_metadata_error = "OIDC Not enabled or basic configuration is incomplete"
            return None

        if cls._metadata is None:
            cls._metadata = OIDCProviderMetadata()

            if oidc_config.authorization_endpoint:
                cls._metadata.authorization_endpoint = oidc_config.authorization_endpoint
                cls._metadata.token_endpoint = oidc_config.token_endpoint
                cls._metadata.userinfo_endpoint = oidc_config.userinfo_endpoint
                cls._metadata.end_session_endpoint = oidc_config.end_session_endpoint
                cls._metadata._loaded = True
                cls._last_metadata_error = None
            else:
                success = await cls._metadata.load(oidc_config.issuer_url)
                if not success:
                    cls._last_metadata_error = cls._metadata.last_error or "OIDC discovery Loading failed"
                    return None

        if not cls._metadata.authorization_endpoint:
            cls._last_metadata_error = "OIDC Authorization endpoint is unavailable"
            return None

        cls._last_metadata_error = None

        return cls._metadata

    @classmethod
    def get_last_metadata_error(cls) -> str | None:
        """Get the latest OIDC metadata load error"""
        return cls._last_metadata_error

    @classmethod
    def generate_state(cls, redirect_path: str = "/") -> str:
        """Generate state parameters and store"""
        cls._cleanup_expired_state()
        state = secrets.token_urlsafe(32)
        cls._state_store[state] = {
            "redirect_path": redirect_path,
            "expires_at": time.time() + cls._state_ttl_seconds,
        }
        return state

    @classmethod
    def verify_state(cls, state: str) -> dict[str, Any] | None:
        """Verify state parameter"""
        state_data = cls._state_store.pop(state, None)
        if not state_data:
            return None
        if state_data["expires_at"] <= time.time():
            return None
        return {"redirect_path": state_data["redirect_path"]}

    @classmethod
    def generate_login_code(cls, payload: dict[str, Any]) -> str:
        """Generate a one-time short-term login code"""
        cls._cleanup_expired_login_code()
        code = secrets.token_urlsafe(32)
        cls._login_code_store[code] = {
            "payload": payload,
            "expires_at": time.time() + cls._login_code_ttl_seconds,
        }
        return code

    @classmethod
    def consume_login_code(cls, code: str) -> dict[str, Any] | None:
        """Consume a one-time short-term login code"""
        data = cls._login_code_store.pop(code, None)
        if not data:
            return None
        if data["expires_at"] <= time.time():
            return None
        return data["payload"]

    @classmethod
    def generate_nonce(cls) -> str:
        """Generate nonce parameter"""
        return secrets.token_urlsafe(32)

    @classmethod
    async def build_authorization_url(cls, redirect_path: str = "/") -> str | None:
        """Build authorization URL"""
        metadata = await cls.get_metadata()
        if not metadata or not metadata.authorization_endpoint:
            return None

        state = cls.generate_state(redirect_path)
        nonce = cls.generate_nonce()

        redirect_uri = oidc_config.redirect_uri
        if not redirect_uri:
            redirect_uri = "/api/auth/oidc/callback"

        params = {
            "client_id": oidc_config.client_id,
            "response_type": "code",
            "scope": oidc_config.scopes,
            "redirect_uri": redirect_uri,
            "state": state,
            "nonce": nonce,
        }

        # If forced login is configured, add the prompt=login parameter
        if oidc_config.force_prompt_login:
            params["prompt"] = "login"

        query_string = urllib.parse.urlencode(params)
        return f"{metadata.authorization_endpoint}?{query_string}"

    @classmethod
    async def exchange_code_for_token(cls, code: str) -> dict[str, Any] | None:
        """Exchange authorization code for token"""
        metadata = await cls.get_metadata()
        if not metadata or not metadata.token_endpoint:
            return None

        redirect_uri = oidc_config.redirect_uri or "/api/auth/oidc/callback"

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": oidc_config.client_id,
            "client_secret": oidc_config.client_secret,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    metadata.token_endpoint,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.json()

        except Exception as e:
            logger.error(f"Failed to exchange code for token: {e}")
            return None

    @classmethod
    async def get_userinfo(cls, access_token: str) -> dict[str, Any] | None:
        """Get user information"""
        metadata = await cls.get_metadata()
        if not metadata or not metadata.userinfo_endpoint:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    metadata.userinfo_endpoint,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.json()

        except Exception as e:
            logger.error(f"Failed to get userinfo: {e}")
            return None

    @classmethod
    async def build_logout_url(cls, id_token: str | None = None) -> str | None:
        """Build the logout URL"""
        metadata = await cls.get_metadata()
        if not metadata or not metadata.end_session_endpoint:
            return None

        params = {"client_id": oidc_config.client_id}

        if id_token:
            params["id_token_hint"] = id_token

        if oidc_config.redirect_uri:
            params["post_logout_redirect_uri"] = oidc_config.redirect_uri

        query_string = urllib.parse.urlencode(params)
        return f"{metadata.end_session_endpoint}?{query_string}"

    @classmethod
    def extract_user_info(cls, userinfo: dict[str, Any]) -> dict[str, Any]:
        """Extract user information from userinfo"""
        sub = userinfo.get("sub", "")

        username = userinfo.get(oidc_config.username_claim, "")
        if not username:
            username = userinfo.get("preferred_username", "")
        if not username:
            username = userinfo.get("email", "").split("@")[0]
        if not username:
            username = sub[:20]

        email = userinfo.get(oidc_config.email_claim, "")
        if not email:
            email = userinfo.get("email", "")

        name = userinfo.get(oidc_config.name_claim, "")
        if not name:
            name = userinfo.get("name", "")
        if not name:
            name = username

        department_name = None
        department_description = None
        if oidc_config.fetch_department_info:
            department_name = userinfo.get(oidc_config.department_claim)
            if not department_name:
                department_name = userinfo.get("department")

            # Get department description
            department_description = userinfo.get("department_description")
            if not department_description:
                department_description = userinfo.get("department_desc")

        return {
            "sub": sub,
            "username": username,
            "email": email,
            "name": name,
            "department_name": department_name,
            "department_description": department_description,
            "raw": userinfo,
        }


async def get_or_create_oidc_department(
    db,
    dept_name_from_oidc: str | None = None,
    dept_desc_from_oidc: str | None = None,
) -> Department | None:
    """Get or create the OIDC user's department"""
    # Clean and validate department names obtained from OIDC
    processed_dept_name = None
    processed_dept_desc = None

    if dept_name_from_oidc:
        # Remove leading and trailing spaces
        processed_dept_name = dept_name_from_oidc.strip()
        # Truncated to 50 characters (matches database limit)
        if len(processed_dept_name) > 50:
            processed_dept_name = processed_dept_name[:50]
        # If it is empty after processing, give up using it.
        if not processed_dept_name:
            processed_dept_name = None

    # Clean and validate department descriptions obtained from OIDC
    if dept_desc_from_oidc:
        processed_dept_desc = dept_desc_from_oidc.strip()
        # Truncated to 255 characters (matches database limit)
        if len(processed_dept_desc) > 255:
            processed_dept_desc = processed_dept_desc[:255]
        if not processed_dept_desc:
            processed_dept_desc = None

    # Finalize the department name: give priority to using the processed OIDC department name, otherwise use the default department name
    final_dept_name = processed_dept_name or oidc_config.default_department
    # Finalize department description: Priority is given to using the processed OIDC department description, otherwise the default description is used
    final_dept_desc = processed_dept_desc or f"{final_dept_name}department"

    result = await db.execute(select(Department).filter(Department.name == final_dept_name))
    dept = result.scalar_one_or_none()

    if dept:
        # The department already exists, return directly
        logger.info(f"Using existing department: {final_dept_name}")
        return dept

    # The department does not exist, create a new department
    dept = Department(
        name=final_dept_name,
        description=final_dept_desc,
    )
    db.add(dept)
    try:
        await db.commit()
        await db.refresh(dept)
        logger.info(f"Created OIDC department: {final_dept_name}")
    except IntegrityError:
        # The department may already exist during concurrent creation. Query again.
        await db.rollback()
        result = await db.execute(select(Department).filter(Department.name == final_dept_name))
        dept = result.scalar_one_or_none()

    return dept


async def find_user_by_oidc_sub(db, sub: str) -> User | None:
    """Find users via OIDC sub"""
    # Method 1: Check if there is a user whose uid is directly equal to "oidc:{sub}" (standard OIDC user)
    standard_oidc_uid = f"oidc:{sub}"
    # Placeholder binding records will be marked is_deleted=1, but we still need to query them to obtain the binding relationship
    result = await db.execute(select(User).filter(User.uid == standard_oidc_uid, User.is_deleted == 0))
    user = result.scalar_one_or_none()
    if user:
        return user

    # The binding placeholder user is marked as is_deleted=1 and needs to be queried including deleted.
    binding_result = await db.execute(
        select(User)
        .filter(User.uid.like(f"{standard_oidc_uid}:%"), User.is_deleted.in_([0, 1]))
        .order_by(User.id.asc())
    )
    binding_users = list(binding_result.scalars().all())
    if binding_users:
        for placeholder in binding_users:
            target_user_id = _extract_oidc_placeholder_target_user_id(placeholder.uid)
            if target_user_id is None:
                continue
            result = await db.execute(select(User).filter(User.id == target_user_id, User.is_deleted == 0))
            target_user = result.scalar_one_or_none()
            if target_user:
                logger.debug(f"Resolved OIDC binding placeholder {placeholder.uid} to user {target_user_id}")
                return target_user

    return None


async def find_deleted_oidc_user_by_sub(db, sub: str) -> User | None:
    """Find canceled OIDC accounts (standard and historical suffixes)"""
    oidc_uid = f"oidc:{sub}"

    result = await db.execute(select(User).filter(User.uid == oidc_uid, User.is_deleted == 1))
    deleted_user = result.scalar_one_or_none()
    if deleted_user:
        return deleted_user

    binding_result = await db.execute(
        select(User).filter(User.uid.like(f"{oidc_uid}:%"), User.is_deleted == 1).order_by(User.id.asc())
    )
    binding_users = list(binding_result.scalars().all())
    if binding_users:
        for placeholder in binding_users:
            target_user_id = _extract_oidc_placeholder_target_user_id(placeholder.uid)
            if target_user_id is None:
                continue
            result = await db.execute(select(User).filter(User.id == target_user_id, User.is_deleted == 1))
            target_user = result.scalar_one_or_none()
            if target_user:
                return target_user
    return None


def _extract_oidc_placeholder_target_user_id(uid: str) -> int | None:
    """Parse the real user ID from a placeholder uid, allowing colons in sub."""
    value = str(uid or "").strip()
    if not value.startswith("oidc:"):
        return None

    # The placeholder format always ends with `:{target_user_id}`, so splitting on the right side avoids colon interference in the sub.
    try:
        _prefix, target_user_id = value.rsplit(":", 1)
        return int(target_user_id)
    except ValueError:
        return None


async def _create_oidc_binding_placeholder(db, sub: str, target_user: User) -> None:
    """Create OIDC sub binding placeholder user (only used to record binding relationships, not used for Log in)

    In use_raw_username mode, we create oneindivualplaceholder user format: oidc:{sub}:{target_user_id},
    Placeholder users are marked is_deleted=1 (do not participate in actual login), used only to store binding relation,
    When querying find_user_by_oidc_sub, the placeholder record will be read and the binding of the real user will be parsed.
    In this way, the binding relationship can be kept verifiable without modifying the Usersurface structure of, preventing account fraud.

    Use passes in the same oneindivual db session to avoid cross-session consistency questions.
    """
    # Placeholder user format: oidc:{sub}:{target_user_id}, so find_user_by_oidc_sub can parse the target user ID
    oidc_placeholder_id = f"oidc:{sub}:{target_user.id}"
    # The placeholder user is marked as deleted and needs to be specifically included in the query to find it.
    result = await db.execute(select(User).filter(User.uid == oidc_placeholder_id, User.is_deleted.in_([0, 1])))
    if result.scalar_one_or_none():
        # The placeholder user already exists, no need to create it again
        return

    # Create a placeholder user: use a random password, mark it as deleted, not used for actual login, only store the binding relationship
    random_password = secrets.token_urlsafe(32)
    password_hash = AuthUtils.hash_password(random_password)

    # username uses oidc-binding-{sub_hash} to avoid conflicts, sub_hash is generated based on the complete sub
    sub_hash = hashlib.sha256(sub.encode()).hexdigest()[:8]
    username = f"oidc-binding-{sub_hash}"

    placeholder_user = User(
        username=username,
        uid=oidc_placeholder_id,
        phone_number=None,
        avatar=None,
        password_hash=password_hash,
        role=target_user.role,
        department_id=target_user.department_id,
        is_deleted=1,  # Marked as deleted and not involved in actual login
        last_login=utc_now_naive(),
    )

    try:
        db.add(placeholder_user)
        await db.commit()
        logger.info(
            f"Created OIDC binding placeholder (deleted) for sub {sub} -> user {target_user.id} ({target_user.uid})"
        )
    except IntegrityError:
        # Concurrent creation conflicts, ignored after rollback
        await db.rollback()
        logger.info(f"OIDC binding placeholder already exists for sub {sub}")


async def build_unique_oidc_username(db, preferred_username: str, sub: str) -> str:
    """Generate non-conflicting usernames for OIDC users"""
    base_username = preferred_username.strip() if preferred_username else ""
    if not base_username:
        base_username = f"oidc_{sub[:8]}"

    result = await db.execute(select(User.id).filter(User.username == base_username))
    if result.scalar_one_or_none() is None:
        return base_username

    hash_suffix = hashlib.sha256(sub.encode()).hexdigest()[:6]
    candidate = f"{base_username}-{hash_suffix}"
    result = await db.execute(select(User.id).filter(User.username == candidate))
    if result.scalar_one_or_none() is None:
        return candidate

    for i in range(2, 100):
        indexed_candidate = f"{candidate}-{i}"
        result = await db.execute(select(User.id).filter(User.username == indexed_candidate))
        if result.scalar_one_or_none() is None:
            return indexed_candidate

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Không thể tạo tên người dùng khả dụng, vui lòng liên hệ quản trị viên",
    )


async def create_oidc_user(db, user_info: dict, department_id: int | None = None) -> User:
    """Create OIDC user"""
    user_repo = UserRepository()

    sub = user_info["sub"]
    preferred_username = user_info["name"] or user_info["username"]

    # Determine whether uid has oidc prefix according to configuration
    if oidc_config.use_raw_username:
        uid = user_info["username"]
        result = await db.execute(select(User).filter(User.uid == uid, User.is_deleted == 0))
        existing_user = result.scalar_one_or_none()
        if existing_user:
            # The user already exists. You must verify whether the current sub has been bound to this user.
            # If the sub is not bound to the user, it cannot be reused directly, and there is a risk of account misuse.
            user_by_sub = await find_user_by_oidc_sub(db, sub)
            if user_by_sub and user_by_sub.id == existing_user.id:
                # sub has been correctly bound to the user, allowing return
                logger.info(f"User with raw uid {uid} already exists and bound to sub {sub}, returning existing user")
                return existing_user
            elif user_by_sub is None:
                # sub has not been bound to any user yet, you can bind sub to this existing user
                logger.info(f"Binding new OIDC sub {sub} to existing user with raw uid {uid}")
                await _create_oidc_binding_placeholder(db, sub, existing_user)
                return existing_user
            else:
                # sub is already bound to another user, conflict, creation refused
                logger.warning(
                    f"Cannot create OIDC user with raw uid {uid}: "
                    f"sub {sub} is already bound to another user {user_by_sub.id}, conflict"
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"UID {uid} đã tồn tại và định danh OIDC {sub} đã được liên kết với một tài khoản khác, vui lòng liên hệ với quản trị viên để giải quyết xung đột",
                )
    else:
        uid = f"oidc:{sub}"

    random_password = secrets.token_urlsafe(32)
    password_hash = AuthUtils.hash_password(random_password)

    username = await build_unique_oidc_username(db, preferred_username, sub)

    for retry_index in range(3):
        try:
            new_user = await user_repo.create(
                {
                    "username": username,
                    "uid": uid,
                    "phone_number": None,
                    "avatar": None,
                    "password_hash": password_hash,
                    "role": oidc_config.default_role,
                    "department_id": department_id,
                    "last_login": utc_now_naive(),
                }
            )
            logger.info(f"Created OIDC user: {new_user.username} ({uid})")

            # In use_raw_username mode, create a placeholder user record binding relationship
            if oidc_config.use_raw_username:
                await _create_oidc_binding_placeholder(db, sub, new_user)

            return new_user
        except IntegrityError:
            existing_user = await find_user_by_oidc_sub(db, sub)
            if existing_user:
                return existing_user
            username = await build_unique_oidc_username(db, f"{preferred_username}-{retry_index + 2}", sub)

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Tạo người dùng OIDC thất bại, vui lòng thử lại",
    )


async def restore_deleted_oidc_user(db, deleted_user: User, user_info: dict) -> User:
    """Recover a logged out OIDC user and return a logged in user"""
    preferred_username = user_info["name"] or user_info["username"]

    deleted_user.is_deleted = 0
    deleted_user.deleted_at = None
    deleted_user.last_login = utc_now_naive()
    deleted_user.phone_number = None
    deleted_user.avatar = None

    if deleted_user.username.startswith("Logged out user-"):
        deleted_user.username = await build_unique_oidc_username(db, preferred_username, user_info["sub"])

    if deleted_user.password_hash == "DELETED":
        random_password = secrets.token_urlsafe(32)
        deleted_user.password_hash = AuthUtils.hash_password(random_password)

    await db.commit()
    await db.refresh(deleted_user)
    logger.info(f"Restored deleted OIDC user: {deleted_user.username} ({deleted_user.uid})")
    return deleted_user


async def update_oidc_user_login(db, user: User) -> None:
    """Update OIDC user login time"""
    user.last_login = utc_now_naive()
    await db.commit()


def _redirect_to_callback(exchange_code: str) -> RedirectResponse:
    """After success, redirect to the front-end OIDC callback page, carrying only one-time code"""
    url = f"{FRONTEND_CALLBACK_PATH}?{urlencode({'code': exchange_code})}"
    return RedirectResponse(url=url, status_code=302)


def _redirect_to_login_with_error(error_message: str) -> RedirectResponse:
    """Redirect to login page with error message on failure"""
    url = f"{FRONTEND_LOGIN_PATH}?{urlencode({'oidc_error': error_message})}"
    return RedirectResponse(url=url, status_code=302)


async def get_oidc_config_handler():
    """Get OIDC configuration (for front-end use)"""
    if not oidc_config.enabled or not oidc_config.is_configured():
        return {"enabled": False}

    provider_name = oidc_config.provider_name
    return {"enabled": True, "provider_name": provider_name}


async def oidc_callback_handler(code: str, state: str, db, request: Request | None = None):
    """Handling OIDC callbacks - Redirect to front-end Vue route"""

    if not oidc_config.is_token_exchange_configured():
        return _redirect_to_login_with_error("OIDC The configuration is incomplete, please contact the administrator")

    if not OIDCUtils.verify_state(state):
        return _redirect_to_login_with_error("The login session has expired, please return to the login page and try again")

    token_response = await OIDCUtils.exchange_code_for_token(code)
    if not token_response:
        return _redirect_to_login_with_error("Unable to obtain access token, please return to the login page and try again")

    access_token = token_response.get("access_token")
    if not access_token:
        return _redirect_to_login_with_error("Unable to obtain access token, please return to the login page and try again")

    userinfo = await OIDCUtils.get_userinfo(access_token)
    if not userinfo:
        return _redirect_to_login_with_error("Unable to obtain user information, please return to the login page and try again")

    extracted_info = OIDCUtils.extract_user_info(userinfo)
    sub = extracted_info["sub"]

    if not sub:
        return _redirect_to_login_with_error("Unable to obtain user ID, please return to the login page and try again")

    # Search for users: always search via sub first to ensure that the binding relationship is verifiable
    user_by_sub = await find_user_by_oidc_sub(db, sub)

    if oidc_config.use_raw_username:
        # Use original username pattern
        username = extracted_info["username"]
        user = None
        if username:
            result = await db.execute(select(User).filter(User.uid == username, User.is_deleted == 0))
            user_by_name = result.scalar_one_or_none()

            if user_by_sub:
                # sub is already bound to a user
                if user_by_name and user_by_sub.id == user_by_name.id:
                    # The user bound by sub is the user with the found username -> Verification passed
                    user = user_by_name
                    logger.info(f"OIDC user logged in with raw username: {username} (sub: {sub})")
                else:
                    # sub is already bound to another user, there is a conflict, and login is refused.
                    conflict_name = user_by_sub.username if not user_by_name else user_by_name.username
                    logger.warning(
                        f"OIDC sub {sub} is already bound to a different user, "
                        f"login rejected to prevent account hijacking (conflict: {conflict_name})"
                    )
                    return _redirect_to_login_with_error("The OIDC logo has been bound to another account. Please contact the administrator to resolve the binding conflict.")
            else:
                # sub is not bound to any user yet
                if user_by_name:
                    # The username exists and sub is not bound -> allow login and create a binding record
                    # Without modifying the table structure, we create a placeholder user oidc:{sub} to record the binding relationship
                    # This placeholder user will not be used to log in, but is only used to store the sub -> user binding relationship.
                    user = user_by_name
                    logger.info(f"Binding new OIDC sub {sub} to existing user with raw username: {username}")
                    # Create a bound placeholder user (created silently in the background and does not affect existing users)
                    await _create_oidc_binding_placeholder(db, sub, user_by_name)
                else:
                    # Username does not exist, need to create a new user
                    if oidc_config.auto_create_user:
                        user = None  # Let subsequent logic be created
                    else:
                        return _redirect_to_login_with_error("The user does not exist, please contact the administrator to open an account")
        else:
            # Username is not obtained, fall back to search by sub
            user = user_by_sub
    else:
        # Standard OIDC mode, search by sub
        user = user_by_sub

    if user:
        await update_oidc_user_login(db, user)
        logger.info(f"OIDC user logged in: {user.username}")
    elif oidc_config.auto_create_user:
        deleted_user = await find_deleted_oidc_user_by_sub(db, sub)
        if deleted_user:
            user = await restore_deleted_oidc_user(db, deleted_user, extracted_info)
            logger.info(f"OIDC deleted user restored and logged in: {user.username}")
        else:
            # Get department information from user information
            dept_name = extracted_info.get("department_name")
            dept_desc = extracted_info.get("department_description")
            dept = await get_or_create_oidc_department(db, dept_name, dept_desc)
            department_id = dept.id if dept else None
            user = await create_oidc_user(db, extracted_info, department_id)
    else:
        return _redirect_to_login_with_error("The user has not registered, please contact the administrator to open an account")

    if user.is_deleted:
        return _redirect_to_login_with_error("The account has been canceled")

    token_data = {"sub": str(user.id)}
    jwt_token = AuthUtils.create_access_token(token_data)

    await log_operation(db, user.id, "OIDC Log in", request=request)

    department_name = None
    if user.department_id:
        result = await db.execute(select(Department.name).filter(Department.id == user.department_id))
        department_name = result.scalar_one_or_none()

    response_data = {
        "access_token": jwt_token,
        "token_type": "bearer",
        "user_id": user.id,
        "username": user.username,
        "uid": user.uid,
        "phone_number": user.phone_number,
        "avatar": user.avatar,
        "role": user.role,
        "department_id": user.department_id,
        "department_name": department_name,
    }

    exchange_code = OIDCUtils.generate_login_code(response_data)
    return _redirect_to_callback(exchange_code)


async def oidc_exchange_code_handler(code: str) -> dict:
    """Exchange login response data with one-time code"""
    token_data = OIDCUtils.consume_login_code(code)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã đăng nhập không hợp lệ hoặc đã hết hạn, vui lòng đăng nhập lại",
        )
    return token_data


async def oidc_login_url_handler(redirect_path: str = "/"):
    """Get OIDC login URL"""
    if not oidc_config.enabled or not oidc_config.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Đăng nhập OIDC tạm thời không khả dụng, vui lòng liên hệ quản trị viên",
        )

    login_url = await OIDCUtils.build_authorization_url(redirect_path)
    if not login_url:
        metadata_error = OIDCUtils.get_last_metadata_error()
        if metadata_error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Tạo liên kết đăng nhập thất bại: {metadata_error}",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Tạo liên kết đăng nhập thất bại, vui lòng thử lại sau hoặc liên hệ quản trị viên",
        )

    return {"login_url": login_url}
