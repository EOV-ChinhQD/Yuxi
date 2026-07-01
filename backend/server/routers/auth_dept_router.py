"""
Department management routing
Provides departmentof addition, deletion, modification and query interface, only super administrator can access ask
"""

import re

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy import delete as sqlalchemy_delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.storage.postgres.models_business import APIKey, Department, User
from yuxi.repositories.department_repository import DepartmentRepository
from yuxi.repositories.user_repository import UserRepository
from server.utils.auth_middleware import get_superadmin_user, get_admin_user, get_db
from yuxi.utils.auth_utils import AuthUtils
from yuxi.services.operation_log_service import log_operation
from yuxi.services.user_identity_service import is_valid_phone_number

# Create router
department = APIRouter(prefix="/departments", tags=["department"])


# =============================================================================
# === Request and response model ===
# =============================================================================


class DepartmentCreate(BaseModel):
    """Create department request"""

    name: str
    description: str | None = None
    # Required administrator information
    admin_uid: str
    admin_password: str
    admin_phone: str | None = None


class DepartmentUpdate(BaseModel):
    """Update department request"""

    name: str | None = None
    description: str | None = None


class DepartmentResponse(BaseModel):
    """department response"""

    id: int
    name: str
    description: str | None = None
    created_at: str
    user_count: int = 0


# =============================================================================
# === Department Management Routing ===
# =============================================================================


@department.get("", response_model=list[DepartmentResponse])
async def get_departments(current_user: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    """Get a list of all departments (accessible to administrators)"""
    dept_repo = DepartmentRepository()
    return await dept_repo.list_with_user_count()


@department.get("/{department_id}", response_model=DepartmentResponse)
async def get_department(
    department_id: int, current_user: User = Depends(get_superadmin_user), db: AsyncSession = Depends(get_db)
):
    """Get specified department details"""
    result = await db.execute(select(Department).filter(Department.id == department_id))
    department = result.scalar_one_or_none()

    if not department:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bộ phận không tồn tại")

    # Get the number of users under the department
    user_count_result = await db.execute(
        select(func.count(User.id)).filter(User.department_id == department_id, User.is_deleted == 0)
    )
    user_count = user_count_result.scalar()

    return {**department.to_dict(), "user_count": user_count}


@department.post("", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(
    department_data: DepartmentCreate,
    request: Request,
    current_user: User = Depends(get_superadmin_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new department and create an administrator for the department"""
    dept_repo = DepartmentRepository()
    user_repo = UserRepository()

    # Check if the department name already exists
    if await dept_repo.exists_by_name(department_data.name):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tên bộ phận đã tồn tại")

    # Verify administrator uid format
    admin_uid = department_data.admin_uid
    if not re.match(r"^[a-zA-Z0-9_]+$", admin_uid):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID người dùng chỉ được chứa chữ cái, số và dấu gạch dưới",
        )

    if len(admin_uid) < 3 or len(admin_uid) > 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Độ dài ID người dùng phải từ 3 đến 20 ký tự",
        )

    # Check if uid already exists
    if await user_repo.exists_by_uid(admin_uid):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID người dùng đã tồn tại",
        )

    # Check if the mobile number already exists (if provided)
    admin_phone = department_data.admin_phone
    if admin_phone:
        if not is_valid_phone_number(admin_phone):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Định dạng số điện thoại không chính xác")
        if await user_repo.exists_by_phone(admin_phone):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Số điện thoại đã tồn tại",
            )

    # Create department
    new_department = await dept_repo.create(
        {
            "name": department_data.name,
            "description": department_data.description,
        }
    )

    # Create admin user
    hashed_password = AuthUtils.hash_password(department_data.admin_password)
    await user_repo.create(
        {
            "username": admin_uid,
            "uid": admin_uid,
            "phone_number": admin_phone,
            "password_hash": hashed_password,
            "role": "admin",
            "department_id": new_department.id,
        }
    )

    # Record operations
    await log_operation(
        db, current_user.id, "Tạo bộ phận", f"Tạo bộ phận: {department_data.name}, và tạo quản trị viên: {admin_uid}", request
    )

    return {**new_department.to_dict(), "user_count": 1}


@department.put("/{department_id}", response_model=DepartmentResponse)
async def update_department(
    department_id: int,
    department_data: DepartmentUpdate,
    request: Request,
    current_user: User = Depends(get_superadmin_user),
    db: AsyncSession = Depends(get_db),
):
    """Update department information"""
    result = await db.execute(select(Department).filter(Department.id == department_id))
    department = result.scalar_one_or_none()

    if not department:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bộ phận không tồn tại")

    # If you want to modify the name, check whether the new name already exists
    if department_data.name and department_data.name != department.name:
        result = await db.execute(select(Department).filter(Department.name == department_data.name))
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tên bộ phận đã tồn tại")
        department.name = department_data.name

    if department_data.description is not None:
        department.description = department_data.description

    await db.commit()
    await db.refresh(department)

    # Record operations
    await log_operation(db, current_user.id, "Cập nhật bộ phận", f"Cập nhật bộ phận: {department.name}", request)

    # Get the number of users under the department
    user_count_result = await db.execute(
        select(func.count(User.id)).filter(User.department_id == department_id, User.is_deleted == 0)
    )
    user_count = user_count_result.scalar()

    return {**department.to_dict(), "user_count": user_count}


@department.delete("/{department_id}", status_code=status.HTTP_200_OK)
async def delete_department(
    department_id: int,
    request: Request,
    current_user: User = Depends(get_superadmin_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete department"""
    # Check if the department exists
    result = await db.execute(select(Department).filter(Department.id == department_id))
    department = result.scalar_one_or_none()

    if not department:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bộ phận không tồn tại")

    if department.id == 1:  # The default department ID is 1
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Không cho phép xóa bộ phận mặc định")

    department_name = department.name
    result = await db.execute(select(User).filter(User.department_id == department_id))
    department_users = result.scalars().all()

    if department_users:
        for user in department_users:
            user.department_id = 1  # Move users in the deleted department to the default department

    await db.execute(sqlalchemy_delete(APIKey).where(APIKey.department_id == department_id))
    await db.delete(department)
    await db.commit()

    # Record operations
    if department_users:
        detail = f"Xóa bộ phận: {department_name}, di chuyển {len(department_users)} người dùng sang bộ phận mặc định"
    else:
        detail = f"Xóa bộ phận: {department_name}"
    await log_operation(db, current_user.id, "Xóa bộ phận", detail, request)

    return {"success": True, "message": "Bộ phận đã được xóa"}
