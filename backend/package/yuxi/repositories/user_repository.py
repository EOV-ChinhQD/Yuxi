"""User data access layer - Repository"""

from datetime import UTC
from datetime import datetime as dt
from typing import Annotated, Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.storage.postgres.manager import pg_manager
from yuxi.storage.postgres.models_business import APIKey, User


def _utc_now() -> dt:
    # Use naive datetime to match PostgreSQL TIMESTAMP WITHOUT TIME ZONE columns
    return dt.now(UTC).replace(tzinfo=None)


class UserRepository:
    """User data access layer"""

    async def get_by_id(self, id: int) -> User | None:
        """Get user based on ID"""
        async with pg_manager.get_async_session_context() as session:
            return await self.get_by_id_with_db(session, id)

    async def get_by_id_with_db(self, db: AsyncSession, id: int) -> User | None:
        """Get users based on ID using specified db"""
        result = await db.execute(select(User).where(User.id == id))
        return result.scalar_one_or_none()

    async def get_by_uid(self, uid: str) -> User | None:
        """Get user based on uid"""
        async with pg_manager.get_async_session_context() as session:
            return await self.get_by_uid_with_db(session, uid)

    async def get_by_uid_with_db(self, db: AsyncSession, uid: str) -> User | None:
        """Get users using specified db"""
        result = await db.execute(select(User).where(User.uid == uid))
        return result.scalar_one_or_none()

    async def get_by_phone(self, phone: str) -> User | None:
        """Get users based on mobile phone number"""
        async with pg_manager.get_async_session_context() as session:
            result = await session.execute(select(User).where(User.phone_number == phone))
            return result.scalar_one_or_none()

    async def list_users(
        self, skip: int = 0, limit: int = 100, department_id: int | None = None, role: str | None = None
    ) -> list[User]:
        """Get user list"""
        async with pg_manager.get_async_session_context() as session:
            query = select(User).where(User.is_deleted == 0)
            if department_id is not None:
                query = query.where(User.department_id == department_id)
            if role is not None:
                query = query.where(User.role == role)
            query = query.order_by(User.id.asc()).offset(skip).limit(limit)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def list_with_department(
        self, skip: int = 0, limit: int = 100, department_id: int | None = None, role: str | None = None
    ) -> Annotated[list[tuple[User, str | None]], "User list, including department names"]:
        """Get a list of users, including department names"""
        async with pg_manager.get_async_session_context() as session:
            from yuxi.storage.postgres.models_business import Department

            query = (
                select(User, Department.name.label("department_name"))
                .outerjoin(Department, User.department_id == Department.id)
                .where(User.is_deleted == 0)
            )
            if department_id is not None:
                query = query.where(User.department_id == department_id)
            if role is not None:
                query = query.where(User.role == role)
            query = query.order_by(User.id.asc()).offset(skip).limit(limit)
            result = await session.execute(query)
            return list(result.all())

    async def create(self, data: dict[str, Any]) -> User:
        """Create user"""
        async with pg_manager.get_async_session_context() as session:
            user = User(**data)
            session.add(user)
            await session.commit()
            await session.refresh(user)
        return user

    async def update(self, id: int, data: dict[str, Any]) -> User | None:
        """Update user"""
        async with pg_manager.get_async_session_context() as session:
            result = await session.execute(select(User).where(User.id == id, User.is_deleted == 0))
            user = result.scalar_one_or_none()
            if user is None:
                return None
            for key, value in data.items():
                if key != "id":
                    setattr(user, key, value)
        return user

    async def soft_delete(self, id: int, username: str | None = None, phone_number: str | None = None) -> bool:
        """Soft delete user"""
        async with pg_manager.get_async_session_context() as session:
            result = await session.execute(select(User).where(User.id == id, User.is_deleted == 0))
            user = result.scalar_one_or_none()
            if user is None:
                return False
            user.is_deleted = 1

            user.deleted_at = _utc_now()
            if username:
                import hashlib

                hash_suffix = hashlib.sha256(user.uid.encode()).hexdigest()[:4]
                user.username = f"Logged out user-{hash_suffix}"
            if phone_number:
                user.phone_number = None
            api_key_result = await session.execute(select(APIKey).where(APIKey.user_id == user.id))
            for api_key in api_key_result.scalars().all():
                api_key.is_enabled = False
        return True

    async def exists_by_uid(self, uid: str) -> bool:
        """Check if uid exists"""
        async with pg_manager.get_async_session_context() as session:
            result = await session.execute(select(User.id).where(User.uid == uid))
            return result.scalar_one_or_none() is not None

    async def exists_by_phone(self, phone: str) -> bool:
        """Check if mobile phone number exists"""
        async with pg_manager.get_async_session_context() as session:
            result = await session.execute(select(User.id).where(User.phone_number == phone))
            return result.scalar_one_or_none() is not None

    async def count(self, department_id: int | None = None) -> int:
        """Count the number of users"""
        async with pg_manager.get_async_session_context() as session:
            query = select(func.count(User.id)).where(User.is_deleted == 0)
            if department_id is not None:
                query = query.where(User.department_id == department_id)
            result = await session.execute(query)
            return result.scalar() or 0

    async def get_all_uids(self) -> list[str]:
        """Get all uids"""
        async with pg_manager.get_async_session_context() as session:
            result = await session.execute(select(User.uid))
            return [uid for (uid,) in result.all()]

    async def get_admin_count_in_department(self, department_id: int, exclude_user_id: int | None = None) -> int:
        """Number of administrators in the statistics department"""
        async with pg_manager.get_async_session_context() as session:
            query = select(func.count(User.id)).where(
                User.department_id == department_id, User.role == "admin", User.is_deleted == 0
            )
            if exclude_user_id is not None:
                query = query.where(User.id != exclude_user_id)
            result = await session.execute(query)
            return result.scalar() or 0
