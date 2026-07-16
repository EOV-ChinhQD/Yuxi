from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv
from sqlalchemy import func, select


APP_ROOT = Path(__file__).resolve().parents[1]
for import_path in (APP_ROOT, APP_ROOT / "package"):
    import_path_str = str(import_path)
    if import_path_str not in sys.path:
        sys.path.insert(0, import_path_str)

SUPERADMIN_UID = "zwj"
SUPERADMIN_NAME = "Zhang Wenjie"
SUPERADMIN_PHONE_NUMBER = "15251638888"
SUPERADMIN_PASSWORD = "zwj12138"
DEFAULT_USER_PASSWORD = "yuxi123456"


class DepartmentSeed(TypedDict):
    name: str
    description: str
    prefix: str
    normal_count: int

DEPARTMENTS: list[DepartmentSeed] = [
    {"name": "R&D Department", "description": "Responsible for product research and development and technical platform construction", "prefix": "dev", "normal_count": 5},
    {"name": "Product Department", "description": "Responsible for product planning, requirement analysis, and project advancement", "prefix": "prod", "normal_count": 5},
    {"name": "Operations Department", "description": "Responsible for business operations, user support, and content maintenance", "prefix": "ops", "normal_count": 4},
]

class SeedError(Exception):
    pass


def load_project_env() -> None:
    load_dotenv(APP_ROOT / ".env", override=False)
    load_dotenv(APP_ROOT.parent / ".env", override=False)
    load_dotenv(Path.cwd() / ".env", override=False)


async def ensure_uninitialized(session) -> None:
    from yuxi.storage.postgres.models_business import User

    user_count = await session.scalar(select(func.count(User.id)))
    # if user_count:
    #     raise SeedError(f"Hệ thống đã được khởi tạo: bảng users đã có {user_count} người dùng, tập lệnh đã thoát.")

    superadmin_count = await session.scalar(select(func.count(User.id)).where(User.role == "superadmin"))
    if superadmin_count:
        raise SeedError("Hệ thống đã được khởi tạo: Đã tồn tại siêu quản trị viên, kịch bản đã thoát.")


async def seed_initial_users() -> None:
    from yuxi.utils.auth_utils import AuthUtils
    from yuxi.storage.postgres.manager import pg_manager
    from yuxi.storage.postgres.models_business import Department, User
    from yuxi.utils.datetime_utils import utc_now_naive

    try:
        pg_manager.initialize()
        await pg_manager.create_business_tables()
        await pg_manager.ensure_business_schema()

        async with pg_manager.get_async_session_context() as session:
            await ensure_uninitialized(session)

            departments: dict[str, Department] = {}
            for department_seed in DEPARTMENTS:
                department = Department(
                    name=department_seed["name"],
                    description=department_seed["description"],
                )
                session.add(department)
                departments[department_seed["prefix"]] = department

            await session.flush()

            users = [
                User(
                    username=SUPERADMIN_NAME,
                    uid=SUPERADMIN_UID,
                    phone_number=SUPERADMIN_PHONE_NUMBER,
                    password_hash=AuthUtils.hash_password(SUPERADMIN_PASSWORD),
                    role="superadmin",
                    department_id=departments["dev"].id,
                    last_login=utc_now_naive(),
                )
            ]

            for department_seed in DEPARTMENTS:
                department = departments[department_seed["prefix"]]
                for index in range(1, 3):
                    users.append(
                        User(
                            username=f"{department_seed['name']} Admin {index}",
                            uid=f"{department_seed['prefix']}_admin_{index}",
                            password_hash=AuthUtils.hash_password(DEFAULT_USER_PASSWORD),
                            role="admin",
                            department_id=department.id,
                        )
                    )
                for index in range(1, department_seed["normal_count"] + 1):
                    users.append(
                        User(
                            username=f"{department_seed['name']} User {index}",
                            uid=f"{department_seed['prefix']}_user_{index:02d}",
                            password_hash=AuthUtils.hash_password(DEFAULT_USER_PASSWORD),
                            role="user",
                            department_id=department.id,
                        )
                    )

            session.add_all(users)
    finally:
        await pg_manager.close()


def main() -> int:
    load_project_env()
    try:
        asyncio.run(seed_initial_users())
    except SeedError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Failed to initialize seed users: {exc}", file=sys.stderr)
        return 1

    print(
        f"Initialization completed: Created superadmin {SUPERADMIN_NAME} ({SUPERADMIN_UID}), "
        "3 departments, 6 department admins, and 14 normal users."
    )
    print("Superadmin password: zwj12138")
    print("Default password for department admins and normal users: yuxi123456")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())