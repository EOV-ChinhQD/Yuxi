import asyncio
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent
for import_path in (APP_ROOT, APP_ROOT / "package"):
    import_path_str = str(import_path)
    if import_path_str not in sys.path:
        sys.path.insert(0, import_path_str)

from dotenv import load_dotenv
from sqlalchemy import update

def load_project_env() -> None:
    load_dotenv(APP_ROOT / ".env", override=False)
    load_dotenv(APP_ROOT.parent / ".env", override=False)
    load_dotenv(Path.cwd() / ".env", override=False)

async def update_admin_password():
    from yuxi.utils.auth_utils import AuthUtils
    from yuxi.storage.postgres.manager import pg_manager
    from yuxi.storage.postgres.models_business import User
    
    pg_manager.initialize()
    async with pg_manager.get_async_session_context() as session:
        new_hash = AuthUtils.hash_password("admin123456")
        await session.execute(
            update(User).where(User.uid == 'admin').values(password_hash=new_hash)
        )
        await session.commit()
    print("Password for 'admin' updated to 'admin123456'.")

def main():
    load_project_env()
    asyncio.run(update_admin_password())

if __name__ == "__main__":
    main()
