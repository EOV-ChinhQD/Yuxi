import re
from yuxi.utils import logger

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.storage.postgres.manager import pg_manager
from yuxi.storage.postgres.models_business import APIKey, User, Department
from yuxi.repositories.user_repository import UserRepository
from yuxi.repositories.department_repository import DepartmentRepository
from server.utils.auth_middleware import (
    get_admin_user,
    get_superadmin_user,
    get_db,
    get_required_user,
)
from yuxi.utils.auth_utils import AuthUtils
from yuxi.services.user_identity_service import generate_unique_uid, validate_username, is_valid_phone_number
from yuxi.services.operation_log_service import log_operation
from yuxi.services.auth_service import (
    CLI_AUTH_POLL_INTERVAL_SECONDS,
    CLI_AUTH_SESSION_TTL_SECONDS,
    CLIAuthError,
    approve_cli_auth_session,
    create_cli_auth_session,
    exchange_cli_auth_token,
    get_cli_auth_session_for_user,
)
from yuxi.storage.minio import upload_image_to_minio
from yuxi.utils.datetime_utils import utc_now_naive

# OIDC certification related import
from yuxi.services.oidc_service import (
    get_oidc_config_handler,
    oidc_callback_handler,
    oidc_exchange_code_handler,
    oidc_login_url_handler,
)

# Create router
auth = APIRouter(prefix="/auth", tags=["authentication"])


# Request and response model
class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: int
    username: str
    uid: str  # user_id used to log in
    phone_number: str | None = None
    avatar: str | None = None
    role: str
    department_id: int | None = None
    department_name: str | None = None


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "user"
    phone_number: str | None = None
    department_id: int | None = None


class UserUpdate(BaseModel):
    username: str | None = None
    password: str | None = None
    role: str | None = None
    phone_number: str | None = None
    avatar: str | None = None
    department_id: int | None = None


class UserProfileUpdate(BaseModel):
    username: str | None = None
    phone_number: str | None = None


class UserResponse(BaseModel):
    id: int
    username: str
    uid: str
    phone_number: str | None = None
    avatar: str | None = None
    role: str
    department_id: int | None = None
    department_name: str | None = None  # Department name
    created_at: str
    last_login: str | None = None


class UserAccessOption(BaseModel):
    uid: str
    username: str
    role: str
    department_id: int | None = None
    department_name: str | None = None


class InitializeAdmin(BaseModel):
    uid: str  # Enter user ID directly
    password: str
    phone_number: str | None = None


class UsernameValidation(BaseModel):
    username: str


class UidGeneration(BaseModel):
    username: str
    uid: str
    is_available: bool


class OIDCConfigResponse(BaseModel):
    """OIDC Configure response"""

    enabled: bool
    login_url: str | None = None
    provider_name: str | None = "OIDC login"


class OIDCLoginResponse(BaseModel):
    """OIDC Login response"""

    access_token: str
    token_type: str
    user_id: int
    username: str
    uid: str
    phone_number: str | None = None
    avatar: str | None = None
    role: str
    department_id: int | None = None
    department_name: str | None = None


class CLIAuthSessionCreate(BaseModel):
    key_name: str | None = Field(default=None, max_length=100)


class CLIAuthTokenRequest(BaseModel):
    device_code: str


class CLIAuthSessionCreateResponse(BaseModel):
    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int


class CLIAuthSessionResponse(BaseModel):
    user_code: str
    status: str
    key_name: str
    created_at: str
    expires_at: str
    approved_at: str | None = None


class CLIAuthApproveResponse(BaseModel):
    user_code: str
    status: str
    approved_at: str | None = None


class CLIAuthTokenResponse(BaseModel):
    api_key: dict
    secret: str
    user: dict


# =============================================================================
# === Utility functions ===
# =============================================================================


def _raise_cli_auth_error(exc: CLIAuthError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"error": exc.code, "message": exc.message},
    ) from exc


# Routing: Login to get token
# =============================================================================
# === Authentication Group ===
# =============================================================================


@auth.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    # Find users - supports user_id and phone_number login
    login_identifier = form_data.username  # username field in OAuth2 form as login identifier

    # Try to find by user_id
    result = await db.execute(select(User).filter(User.uid == login_identifier))
    user = result.scalar_one_or_none()

    # If not found by user_id, try to find it by phone_number
    if not user:
        result = await db.execute(select(User).filter(User.phone_number == login_identifier))
        user = result.scalar_one_or_none()

    # If the user does not exist, to prevent username enumeration attacks, a general error message is returned.
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tên đăng nhập hoặc mật khẩu không chính xác",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user has been deleted
    if user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản này đã bị hủy bỏ",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is in login locked state
    if user.is_login_locked():
        remaining_time = user.get_remaining_lock_time()
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Đăng nhập bị khóa, vui lòng đợi {remaining_time} giây rồi thử lại",
            headers={"WWW-Authenticate": "Bearer", "X-Lock-Remaining": str(remaining_time)},
        )

    # Verify password
    if not AuthUtils.verify_password(user.password_hash, form_data.password):
        # Wrong password, increase the number of failures
        user.increment_failed_login()
        await db.commit()

        # Log failed operations
        await log_operation(db, user.id if user else None, "Login failed", f"Wrong password, number of failures: {user.login_failed_count}")

        # Check if locking is required
        if user.is_login_locked():
            remaining_time = user.get_remaining_lock_time()
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Tài khoản đã bị khóa {remaining_time} giây do đăng nhập sai nhiều lần",
                headers={"WWW-Authenticate": "Bearer", "X-Lock-Remaining": str(remaining_time)},
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tên đăng nhập hoặc mật khẩu không chính xác",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Login successful, reset failure counter
    user.reset_failed_login()
    user.last_login = utc_now_naive()
    await db.commit()

    # Generate access token
    token_data = {"sub": str(user.id)}
    access_token = AuthUtils.create_access_token(token_data)

    # Record login operations
    await log_operation(db, user.id, "Log in")

    # Get department name
    department_name = None
    if user.department_id:
        result = await db.execute(select(Department.name).filter(Department.id == user.department_id))
        department_name = result.scalar_one_or_none()

    return {
        "access_token": access_token,
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


# =============================================================================
# === CLI browser login authorization group ===
# =============================================================================


@auth.post("/cli/sessions", response_model=CLIAuthSessionCreateResponse)
async def create_cli_session(data: CLIAuthSessionCreate, db: AsyncSession = Depends(get_db)):
    session, device_code = await create_cli_auth_session(db, key_name=data.key_name)
    return CLIAuthSessionCreateResponse(
        device_code=device_code,
        user_code=session.user_code,
        verification_uri="/auth/cli/authorize",
        expires_in=CLI_AUTH_SESSION_TTL_SECONDS,
        interval=CLI_AUTH_POLL_INTERVAL_SECONDS,
    )


@auth.get("/cli/sessions/{user_code}", response_model=CLIAuthSessionResponse)
async def get_cli_session(
    user_code: str,
    _current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        session = await get_cli_auth_session_for_user(db, user_code)
    except CLIAuthError as exc:
        _raise_cli_auth_error(exc)
    return CLIAuthSessionResponse(**session.to_dict())


@auth.post("/cli/sessions/{user_code}/approve", response_model=CLIAuthApproveResponse)
async def approve_cli_session(
    user_code: str,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        session = await approve_cli_auth_session(db, user_code, current_user)
    except CLIAuthError as exc:
        _raise_cli_auth_error(exc)
    return CLIAuthApproveResponse(**session.to_dict())


@auth.post("/cli/sessions/token", response_model=CLIAuthTokenResponse)
async def exchange_cli_session_token(data: CLIAuthTokenRequest, db: AsyncSession = Depends(get_db)):
    try:
        return await exchange_cli_auth_token(db, data.device_code)
    except CLIAuthError as exc:
        _raise_cli_auth_error(exc)


# Routing: Verify whether the administrator needs to be initialized
@auth.get("/check-first-run")
async def check_first_run():
    is_first_run = await pg_manager.async_check_first_run()
    return {"first_run": is_first_run}


# Routing: initialize administrator account
@auth.post("/initialize", response_model=Token)
async def initialize_admin(admin_data: InitializeAdmin, db: AsyncSession = Depends(get_db)):
    # Check if this is the first run
    if not await pg_manager.async_check_first_run():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hệ thống đã được khởi tạo, không thể tạo lại quản trị viên ban đầu",
        )

    # Create an administrator account
    hashed_password = AuthUtils.hash_password(admin_data.password)

    # Validate user ID format (only alphanumeric and underscore supported)
    if not re.match(r"^[a-zA-Z0-9_]+$", admin_data.uid):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User ID chỉ có thể chứa chữ cái, số và dấu gạch dưới",
        )

    if len(admin_data.uid) < 3 or len(admin_data.uid) > 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Độ dài User ID phải từ 3 đến 20 ký tự",
        )

    # Verify mobile phone number format (if provided)
    if admin_data.phone_number and not is_valid_phone_number(admin_data.phone_number):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Định dạng số điện thoại không chính xác")

    # Since this is the first initialization, the entered user_id is used directly.
    uid = admin_data.uid

    # Create default department
    dept_repo = DepartmentRepository()
    default_department = await dept_repo.create(
        {
            "name": "Bộ phận mặc định",
            "description": "Bộ phận mặc định được tạo khi khởi tạo hệ thống",
        }
    )

    # Create admin user
    user_repo = UserRepository()
    new_admin = await user_repo.create(
        {
            "username": admin_data.uid,
            "uid": uid,
            "phone_number": admin_data.phone_number,
            "avatar": None,
            "password_hash": hashed_password,
            "role": "superadmin",
            "department_id": default_department.id,
            "last_login": utc_now_naive(),
        }
    )

    # Generate access token
    token_data = {"sub": str(new_admin.id)}
    access_token = AuthUtils.create_access_token(token_data)

    # Record operations
    await log_operation(db, new_admin.id, "System initialization", "Create a super administrator account")

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": new_admin.id,
        "username": new_admin.username,
        "uid": new_admin.uid,
        "phone_number": new_admin.phone_number,
        "avatar": new_admin.avatar,
        "role": new_admin.role,
    }


# Routing: Get current user information
# =============================================================================
# === User information grouping ===
# =============================================================================


@auth.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_required_user), db: AsyncSession = Depends(get_db)):
    """Get the personal information of the currently logged in user"""
    user_dict = current_user.to_dict()

    if current_user.department_id:
        result = await db.execute(select(Department.name).filter(Department.id == current_user.department_id))
        user_dict["department_name"] = result.scalar_one_or_none()

    return user_dict


# Route: update profile
@auth.put("/profile", response_model=UserResponse)
async def update_profile(
    profile_data: UserProfileUpdate,
    request: Request,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user's profile"""
    update_details = []

    # Update username (only the display name is allowed to be modified, user_id is not modified)
    if profile_data.username is not None:
        # Verify username format
        is_valid, error_msg = validate_username(profile_data.username)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg,
            )

        # Check if the username is already used by another user
        result = await db.execute(
            select(User).filter(User.username == profile_data.username, User.id != current_user.id)
        )
        existing_user = result.scalar_one_or_none()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tên người dùng đã tồn tại",
            )

        current_user.username = profile_data.username
        update_details.append(f"username: {profile_data.username}")

    # Update mobile phone number
    if profile_data.phone_number is not None:
        # If the mobile phone number is not empty, verify the format
        if profile_data.phone_number and not is_valid_phone_number(profile_data.phone_number):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Định dạng số điện thoại không chính xác")

        # Check whether the mobile phone number is already used by another user
        if profile_data.phone_number:
            result = await db.execute(
                select(User).filter(User.phone_number == profile_data.phone_number, User.id != current_user.id)
            )
            existing_phone = result.scalar_one_or_none()
            if existing_phone:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Số điện thoại đã được sử dụng bởi người dùng khác")

        current_user.phone_number = profile_data.phone_number
        update_details.append(f"Phone number: {profile_data.phone_number or 'Cleared'}")

    await db.commit()

    # Record operations
    if update_details:
        await log_operation(db, current_user.id, "Update profile", f"Update profile: {', '.join(update_details)}", request)

    return current_user.to_dict()


# Routing: Create new user (admin rights)
# =============================================================================
# === User management group ===
# =============================================================================


@auth.post("/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Create new user (admin rights)"""
    user_repo = UserRepository()

    # Verify username
    is_valid, error_msg = validate_username(user_data.username)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )

    # Check if username already exists
    users = await user_repo.list_users()
    if any(u.username == user_data.username for u in users):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tên người dùng đã tồn tại",
        )

    # Check if the mobile number already exists (if provided)
    if user_data.phone_number:
        if await user_repo.exists_by_phone(user_data.phone_number):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Số điện thoại đã tồn tại",
            )

    # Generate unique uid
    existing_uids = await user_repo.get_all_uids()
    uid = generate_unique_uid(user_data.username, existing_uids)

    # Create new user
    hashed_password = AuthUtils.hash_password(user_data.password)

    # Check role permissions
    # It is prohibited to create a super administrator account (the system can only have one super administrator)
    if user_data.role == "superadmin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể tạo tài khoản superadmin",
        )

    # Administrators can only create ordinary users
    if current_user.role == "admin" and user_data.role != "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Quản trị viên chỉ có thể tạo tài khoản người dùng bình thường",
        )

    # Department allocation logic
    if current_user.role == "superadmin":
        # When the super administrator creates a user, use the specified department or default department.
        department_id = user_data.department_id
        if department_id is None:
            # Get default department
            dept_repo = DepartmentRepository()
            departments = await dept_repo.list_departments()
            default_dept = next((d for d in departments if d.name == "Default department"), None)
            department_id = default_dept.id if default_dept else None
    else:
        # When an ordinary administrator creates a user, the administrator's department is automatically inherited.
        department_id = current_user.department_id
        if department_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quản trị viên phải thuộc một bộ phận để tạo người dùng",
            )
        # Non-super administrators cannot specify departments
        if user_data.department_id is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Quản trị viên thông thường không thể chỉ định bộ phận",
            )

    new_user = await user_repo.create(
        {
            "username": user_data.username,
            "uid": uid,
            "phone_number": user_data.phone_number,
            "password_hash": hashed_password,
            "role": user_data.role,
            "department_id": department_id,
        }
    )

    # Record operations
    await log_operation(
        db, current_user.id, "Create user", f"Create user: {user_data.username}, Role: {user_data.role}", request
    )

    return new_user.to_dict()


# Routing: Get all users (admin rights)
@auth.get("/users", response_model=list[UserResponse])
async def read_users(
    skip: int = 0, limit: int = 100, current_user: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)
):
    user_repo = UserRepository()

    # Department isolation logic
    if current_user.role == "superadmin":
        # Super administrator can see all users
        users_with_dept = await user_repo.list_with_department(skip=skip, limit=limit)
    else:
        # Ordinary administrators can only see users in their own department
        users_with_dept = await user_repo.list_with_department(
            skip=skip, limit=limit, department_id=current_user.department_id
        )

    users = []
    for user, dept_name in users_with_dept:
        user_dict = user.to_dict()
        user_dict["department_name"] = dept_name
        users.append(user_dict)
    return users


def _ensure_user_in_current_department(current_user: User, target_user: User) -> None:
    if current_user.role == "superadmin":
        return
    if target_user.department_id != current_user.department_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ có thể quản lý người dùng thuộc bộ phận của mình",
        )


@auth.get("/users/access-options", response_model=list[UserAccessOption])
async def read_user_access_options(
    skip: int = 0,
    limit: int = 1000,
    current_user: User = Depends(get_admin_user),
):
    user_repo = UserRepository()
    if current_user.role == "superadmin":
        users_with_dept = await user_repo.list_with_department(skip=skip, limit=limit)
    else:
        users_with_dept = await user_repo.list_with_department(
            skip=skip, limit=limit, department_id=current_user.department_id
        )
    return [
        {
            "uid": user.uid,
            "username": user.username,
            "role": user.role,
            "department_id": user.department_id,
            "department_name": dept_name,
        }
        for user, dept_name in users_with_dept
    ]


# Routing: Get specific user information (administrator privileges)
@auth.get("/users/{user_id}", response_model=UserResponse)
async def read_user(user_id: int, current_user: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter(User.id == user_id, User.is_deleted == 0))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Người dùng không tồn tại",
        )
    _ensure_user_in_current_department(current_user, user)
    return user.to_dict()


# Routing: Update user information (administrator privileges)
@auth.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).filter(User.id == user_id, User.is_deleted == 0))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Người dùng không tồn tại",
        )

    _ensure_user_in_current_department(current_user, user)

    # Check permissions
    if user.role == "superadmin" and current_user.role != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ có superadmin mới có thể sửa đổi tài khoản superadmin",
        )

    # The super administrator account cannot be downgraded (can only be modified by other super administrators)
    if user.role == "superadmin" and user_data.role and user_data.role != "superadmin" and current_user.id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không thể hạ cấp tài khoản superadmin",
        )

    if current_user.role == "admin":
        if user.role != "user":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Quản trị viên chỉ có thể sửa đổi tài khoản người dùng bình thường",
            )
        if user_data.role is not None and user_data.role != "user":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Quản trị viên chỉ có thể đặt vai trò người dùng là người dùng bình thường",
            )

    # Update information
    update_details = []

    if user_data.username is not None:
        # Check if the username is already used by another user
        result = await db.execute(select(User).filter(User.username == user_data.username, User.id != user_id))
        existing_user = result.scalar_one_or_none()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tên người dùng đã tồn tại",
            )
        user.username = user_data.username
        update_details.append(f"Tên người dùng: {user_data.username}")

    if user_data.password is not None:
        user.password_hash = AuthUtils.hash_password(user_data.password)
        update_details.append("Mật khẩu đã cập nhật")

    if user_data.role is not None:
        # Check to demote administrator to normal user
        if user.role == "admin" and user_data.role == "user" and user.department_id is not None:
            admin_count = await UserRepository().get_admin_count_in_department(
                user.department_id, exclude_user_id=user_id
            )
            if admin_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Không thể hạ cấp quản trị viên xuống người dùng bình thường vì người dùng này là quản trị viên duy nhất của bộ phận",
                )
        user.role = user_data.role
        update_details.append(f"Role: {user_data.role}")

    if user_data.phone_number is not None:
        user.phone_number = user_data.phone_number
        update_details.append(f"Phone number: {user_data.phone_number or 'Cleared'}")

    if user_data.avatar is not None:
        user.avatar = user_data.avatar
        update_details.append(f"avatar: {user_data.avatar or 'Cleared'}")

    # Department modification permission control (only super administrators can modify user departments)
    if user_data.department_id is not None and user_data.department_id != user.department_id:
        if current_user.role != "superadmin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chỉ có superadmin mới có thể sửa đổi bộ phận của người dùng",
            )

        # Check if this user is the only administrator of the current department
        if user.role == "admin" and user.department_id is not None:
            admin_count = await UserRepository().get_admin_count_in_department(
                user.department_id, exclude_user_id=user_id
            )
            if admin_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Không thể sửa đổi bộ phận của người dùng này vì họ là quản trị viên duy nhất của bộ phận hiện tại",
                )

        user.department_id = user_data.department_id
        update_details.append(f"Department ID: {user_data.department_id}")

    await db.commit()

    # Record operations
    await log_operation(db, current_user.id, "Update user", f"Update user ID {user_id}: {', '.join(update_details)}", request)

    return user.to_dict()


# Routing: Delete user (admin rights)
@auth.delete("/users/{user_id}", response_model=dict)
async def delete_user(
    user_id: int, request: Request, current_user: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).filter(User.id == user_id, User.is_deleted == 0))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Người dùng không tồn tại",
        )

    _ensure_user_in_current_department(current_user, user)

    # Cannot delete super administrator account
    if user.role == "superadmin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể xóa tài khoản superadmin",
        )

    if current_user.role == "admin" and user.role != "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Quản trị viên chỉ có thể xóa tài khoản người dùng bình thường",
        )

    # Check if you are the only administrator of the department
    if user.role == "admin" and current_user.role != "superadmin":
        result = await db.execute(
            select(func.count(User.id)).filter(
                User.department_id == user.department_id, User.role == "admin", User.is_deleted == 0
            )
        )
        admin_count = result.scalar()
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không thể xóa quản trị viên duy nhất của bộ phận",
            )

    # Cannot delete own account
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể xóa tài khoản của chính mình",
        )

    # Check if it has been deleted
    if user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Người dùng này đã bị xóa",
        )

    deletion_detail = f"Delete user: {user.username}, ID: {user.id}, Role: {user.role}"

    user.is_deleted = 1
    user.deleted_at = utc_now_naive()
    user.username = f"Logged out user-{user.id}"
    user.phone_number = None  # Clear the mobile phone number and release it for other users to use
    user.password_hash = "DELETED"  # Login prohibited
    user.avatar = None  # Clear avatar
    api_key_result = await db.execute(select(APIKey).filter(APIKey.user_id == user.id))
    for api_key in api_key_result.scalars().all():
        api_key.is_enabled = False

    await db.commit()

    # Record operations
    await log_operation(db, current_user.id, "Delete user", deletion_detail, request)

    return {"success": True, "message": "Người dùng đã được xóa"}


# Routing: validate username and generate user_id
@auth.post("/validate-username", response_model=UidGeneration)
async def validate_username_and_generate_uid(
    validation_data: UsernameValidation,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Verify username format and generate usable user_id"""
    # Verify username format
    is_valid, error_msg = validate_username(validation_data.username)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )

    # Check if username already exists
    result = await db.execute(select(User).filter(User.username == validation_data.username))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tên người dùng đã tồn tại",
        )

    # Generate unique uid
    result = await db.execute(select(User.uid))
    existing_uids = [uid for (uid,) in result.all()]
    uid = generate_unique_uid(validation_data.username, existing_uids)

    return UidGeneration(username=validation_data.username, uid=uid, is_available=True)


# Routing: Check if uid is available
@auth.get("/check-uid/{uid}")
async def check_uid_availability(
    uid: str, current_user: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)
):
    """Check if uid is available"""
    result = await db.execute(select(User).filter(User.uid == uid))
    existing_user = result.scalar_one_or_none()
    return {"uid": uid, "is_available": existing_user is None}


# Routing: Upload user avatar
@auth.post("/upload-avatar")
async def upload_user_avatar(
    file: UploadFile = File(...), current_user: User = Depends(get_required_user), db: AsyncSession = Depends(get_db)
):
    """Upload user avatar"""
    try:
        avatar_url = await upload_image_to_minio(
            file,
            object_prefix=f"avatar/{current_user.id}",
            max_size_bytes=5 * 1024 * 1024,
            too_large_message="Kích thước tệp không được vượt quá 5MB",
        )

        current_user.avatar = avatar_url
        await db.commit()
        await log_operation(db, current_user.id, "Upload avatar", f"Update avatar: {avatar_url}")

        return {"success": True, "avatar_url": avatar_url, "message": "Tải lên ảnh đại diện thành công"}

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Tải lên ảnh đại diện thất bại: {str(e)}")


# Routing: Simulate user login (only for super administrators)
@auth.post("/impersonate/{user_id}", response_model=Token)
async def impersonate_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(get_superadmin_user),
    db: AsyncSession = Depends(get_db),
):
    """Super administrator simulates login of other users"""
    # Find target users
    result = await db.execute(select(User).filter(User.id == user_id, User.is_deleted == 0))
    target_user = result.scalar_one_or_none()
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Người dùng không tồn tại",
        )

    # Cannot impersonate super administrator
    if target_user.role == "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không thể giả lập tài khoản superadmin",
        )

    # Generate access token
    token_data = {"sub": str(target_user.id)}
    access_token = AuthUtils.create_access_token(token_data)

    # Get department name
    department_name = None
    if target_user.department_id:
        result = await db.execute(select(Department.name).filter(Department.id == target_user.department_id))
        department_name = result.scalar_one_or_none()

    # Recording operations (dangerous operation flags)
    await log_operation(db, current_user.id, "⚠️ Dangerous operation-Impersonate user", f"Impersonate user: {target_user.username}", request)

    # Console warning log
    logger.warning(f"⚠️ [Dangerous operation] super administrator {current_user.username} Impersonate logged in user: {target_user.username}")

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": target_user.id,
        "username": target_user.username,
        "uid": target_user.uid,
        "phone_number": target_user.phone_number,
        "avatar": target_user.avatar,
        "role": target_user.role,
        "department_id": target_user.department_id,
        "department_name": department_name,
    }


# =============================================================================
# === OIDC Certification Group ===
# =============================================================================


@auth.get("/oidc/config", response_model=OIDCConfigResponse)
async def get_oidc_config():
    """Get OIDC configuration (for front-end use)"""
    return await get_oidc_config_handler()


@auth.get("/oidc/login-url")
async def get_oidc_login_url(redirect_path: str = "/"):
    """Get OIDC login URL"""
    return await oidc_login_url_handler(redirect_path)


@auth.get("/oidc/callback", response_class=RedirectResponse)
async def oidc_callback(request: Request, code: str, state: str, db: AsyncSession = Depends(get_db)):
    """Handling OIDC callbacks - Redirect to front-end Vue route"""
    return await oidc_callback_handler(code, state, db, request)


@auth.post("/oidc/exchange-code", response_model=OIDCLoginResponse)
async def oidc_exchange_code(code: str = Body(..., embed=True)):
    """Use one-time code to exchange OIDC login data"""
    return await oidc_exchange_code_handler(code)
