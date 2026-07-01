import hashlib

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from yuxi.storage.postgres.manager import pg_manager
from yuxi.storage.postgres.models_business import APIKey, User
from yuxi.utils.datetime_utils import utc_now_naive

from yuxi.utils.auth_utils import AuthUtils

# Định nghĩa OAuth2 password bearer scheme, chỉ định token URL
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


# Get database session (asynchronous version)
# Lấy phiên cơ sở dữ liệu (phiên bản bất đồng bộ)
async def get_db():
    async with pg_manager.get_async_session_context() as db:
        yield db


async def _verify_api_key(key: str, db: AsyncSession) -> tuple[User | None, APIKey | None]:
    """Xác thực API Key và trả về đối tượng User và APIKey liên kết"""
    key_hash = hashlib.sha256(key.encode()).hexdigest()

    result = await db.execute(select(APIKey).filter(APIKey.key_hash == key_hash))
    api_key = result.scalar_one_or_none()

    if api_key is None:
        return None, None

    if not api_key.is_enabled:
        return None, None

    if api_key.expires_at and utc_now_naive() > api_key.expires_at:
        return None, None

    if api_key.user_id:
        result = await db.execute(select(User).filter(User.id == api_key.user_id))
        user = result.scalar_one_or_none()
        if user and not user.is_deleted:
            return user, api_key
        return None, None

    if api_key.department_id:
        result = await db.execute(
            select(User)
            .filter(
                User.department_id == api_key.department_id,
                User.role.in_(["admin", "superadmin"]),
                User.is_deleted == 0,
            )
            .order_by(User.role.desc(), User.id.asc())
            .limit(1)
        )
        user = result.scalar_one_or_none()
        if user:
            return user, api_key

    return None, None


# Get the current user (async version)
async def get_current_user(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Chứng chỉ không hợp lệ",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if authorization is None:
        return None

    if not authorization.startswith("Bearer "):
        return None

    token = authorization.split("Bearer ")[1]
    if not token:
        return None

    # Determine the authentication method based on the token prefix
    if token.startswith("yxkey_"):
        # Xác thực API Key
        user, api_key_obj = await _verify_api_key(token, db)
        if user is not None and api_key_obj is not None:
            api_key_obj.last_used_at = utc_now_naive()
            await db.commit()
        return user

    # Xác thực JWT Token
    try:
        payload = AuthUtils.verify_access_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).filter(User.id == int(user_id), User.is_deleted == 0))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    if user.is_login_locked():
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Tài khoản đã bị khóa, vui lòng thử lại sau",
            headers={"X-Lock-Remaining": str(user.get_remaining_lock_time())},
        )

    return user


# Lấy thông tin user đã đăng nhập (trả về 401 nếu chưa đăng nhập)
async def get_required_user(user: User | None = Depends(get_current_user)):
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Vui lòng đăng nhập trước khi truy cập",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.department_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Người dùng hiện tại chưa liên kết bộ phận",
        )
    return user


# Quyền admin
async def get_admin_user(current_user: User = Depends(get_required_user)):
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Yêu cầu quyền admin",
        )
    return current_user


# Quyền superadmin
async def get_superadmin_user(current_user: User = Depends(get_required_user)):
    if current_user.role != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Yêu cầu quyền superadmin",
        )
    return current_user
