import os
from pathlib import Path

import aiofiles
import yaml
from fastapi import APIRouter, Body, Depends, HTTPException
from yuxi import config, get_version
from yuxi.storage.postgres.models_business import User
from yuxi.utils.logging_config import logger

from server.utils.auth_middleware import get_admin_user, get_required_user

system = APIRouter(prefix="/system", tags=["system"])

# =============================================================================
# === Health Check Grouping ===
# =============================================================================


@system.get("/health")
async def health_check():
    """System health check interface (public interface)"""
    return {"status": "ok", "message": "Dịch vụ đang hoạt động bình thường", "version": get_version()}


from sqlalchemy import text
from server.utils.auth_middleware import get_admin_user

@system.get("/health/detailed")
async def detailed_health_check(current_user: User = Depends(get_admin_user)):
    """Detailed health check for internal databases and third-party systems."""
    health_status = {
        "status": "healthy",
        "postgres": "healthy",
        "neo4j": "healthy",
        "milvus": "healthy"
    }

    # 1. PostgreSQL check
    try:
        from yuxi.storage.postgres.manager import pg_manager
        async with pg_manager.get_async_session_context() as db:
            await db.execute(text("SELECT 1"))
    except Exception as e:
        health_status["postgres"] = f"unhealthy: {e}"
        health_status["status"] = "unhealthy"

    # 2. Neo4j check
    try:
        from yuxi.knowledge.graphs.milvus_graph_service import MilvusGraphService
        graph_service = MilvusGraphService()
        import asyncio
        await asyncio.to_thread(graph_service.driver.verify_connectivity)
    except Exception as e:
        health_status["neo4j"] = f"unhealthy: {e}"
        health_status["status"] = "unhealthy"

    # 3. Milvus check
    try:
        from yuxi.knowledge.graphs.milvus_graph_vector_store import MilvusGraphVectorStore
        store = MilvusGraphVectorStore()
        store._init_connection()
    except Exception as e:
        health_status["milvus"] = f"unhealthy: {e}"
        health_status["status"] = "unhealthy"

    return health_status


@system.get("/discovery")
async def discovery():
    """System capability discovery interface (public interface)"""
    return {
        "name": "Yuxi",
        "version": get_version(),
        "api_prefix": "/api",
        "capabilities": {
            "cli": {
                "min_cli_version": "0.1.0",
                "browser_login": True,
                "api_key_auth": True,
                "remote_config": True,
                "kb_upload": True,
            }
        },
        "endpoints": {
            "health": "/api/system/health",
            "auth_me": "/api/auth/me",
            "cli_auth_sessions": "/api/auth/cli/sessions",
            "cli_auth_authorize": "/auth/cli/authorize",
        },
    }


# =============================================================================
# === Configuration Management Group ===
# =============================================================================


@system.get("/config")
async def get_config(current_user: User = Depends(get_required_user)):
    """Lấy cấu hình hệ thống"""
    return config.dump_config()


@system.post("/config")
async def update_config_single(key=Body(...), value=Body(...), current_user: User = Depends(get_admin_user)) -> dict:
    """Update a single configuration item"""
    if not isinstance(key, str) or key not in type(config).model_fields:
        raise HTTPException(status_code=400, detail=f"Mục cấu hình không xác định: {key}")
    if not config.can_update(key):
        raise HTTPException(status_code=400, detail=f"Mục cấu hình không thể sửa đổi: {key}")
    try:
        config.set_value(key, value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    config.save()
    return config.dump_config()


@system.post("/config/update")
async def update_config_batch(items: dict = Body(...), current_user: User = Depends(get_admin_user)) -> dict:
    """Cập nhật hàng loạt mục cấu hình"""
    try:
        config.update(items)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    config.save()
    return config.dump_config()


@system.get("/logs")
async def get_system_logs(levels: str | None = None, current_user: User = Depends(get_admin_user)):
    """Get system log

    Args:
        levels: Optional log level filtering, multiple levels separated by commas, such as "INFO,ERROR,DEBUG,WARNING"
    """
    try:
        from yuxi.utils.logging_config import LOG_FILE

        # Parse log level filter conditions
        level_filter = None
        if levels:
            level_filter = set(level.strip().upper() for level in levels.split(",") if level.strip())

        # Fix GBK encoding error: force utf-8 reading, ignore errors
        async with aiofiles.open(LOG_FILE, encoding="utf-8", errors="ignore") as f:
            # Read last 1000 lines
            lines = []
            async for line in f:
                filtered_line = line.rstrip("\n\r")
                # If log level filtering is specified, filter by level
                if level_filter:
                    # Log format: 2025-03-10 08:26:37,269 - INFO - module - message
                    # Extract log level
                    parts = filtered_line.split(" - ")
                    if len(parts) >= 2 and parts[1].strip() in level_filter:
                        lines.append(filtered_line + "\n")
                    # Continue reading to keep row count accurate
                    if len(lines) > 1000:
                        lines.pop(0)
                else:
                    lines.append(filtered_line + "\n")
                    if len(lines) > 1000:
                        lines.pop(0)

        log = "".join(lines)
        return {"log": log, "message": "success", "log_file": LOG_FILE}
    except Exception as e:
        logger.error(f"Failed to obtain system log: {e}")
        raise HTTPException(status_code=500, detail=f"Lấy nhật ký hệ thống thất bại: {str(e)}")


# =============================================================================
# === Information Management Group ===
# =============================================================================


async def load_info_config():
    """Load information configuration file"""
    try:
        # Configuration file path
        brand_file_path = os.environ.get("YUXI_BRAND_FILE_PATH", "package/yuxi/config/static/info.local.yaml")
        config_path = Path(brand_file_path)

        # Check if the file exists
        if not config_path.exists():
            logger.debug(f"The config file {config_path} does not exist, using default config")
            config_path = Path("package/yuxi/config/static/info.template.yaml")

        # Read configuration file asynchronously
        async with aiofiles.open(config_path, encoding="utf-8") as file:
            content = await file.read()

        # Inject version number placeholder
        content = content.replace("{{YUXI_VERSION}}", get_version())

        config = yaml.safe_load(content)

        return config

    except Exception as e:
        logger.error(f"Failed to load info config: {e}")
        return {}


@system.get("/info")
async def get_info_config():
    """Obtain system information configuration (public interface, no authentication required)"""
    try:
        config = await load_info_config()
        return {"success": True, "data": config}
    except Exception as e:
        logger.error(f"Failed to obtain information configuration: {e}")
        raise HTTPException(status_code=500, detail="Lấy cấu hình thông tin thất bại")


@system.post("/info/reload")
async def reload_info_config(current_user: User = Depends(get_admin_user)):
    """Reload information configuration"""
    try:
        config = await load_info_config()
        return {"success": True, "message": "Tải lại cấu hình thành công", "data": config}
    except Exception as e:
        logger.error(f"Failed to reload information configuration: {e}")
        raise HTTPException(status_code=500, detail="Tải lại cấu hình thông tin thất bại")


# =============================================================================
# === OCR service group ===
# =============================================================================


@system.get("/ocr/health")
async def check_ocr_services_health(current_user: User = Depends(get_admin_user)):
    """
    examine the health status of all OCR services
    Returns the availability information of each individualOCR service
    """
    from yuxi.knowledge.parser.factory import DocumentProcessorFactory

    try:
        # Use a unified health check interface
        health_status = await DocumentProcessorFactory.check_all_health_async()

        # Format health check response
        formatted_status = {}
        for service_name, health_info in health_status.items():
            formatted_status[service_name] = {
                "status": health_info.get("status", "unknown"),
                "message": health_info.get("message", ""),
                "details": health_info.get("details", {}),
            }

        # Calculate overall health status
        overall_status = (
            "healthy" if any(svc["status"] == "healthy" for svc in formatted_status.values()) else "unhealthy"
        )

        return {
            "overall_status": overall_status,
            "services": formatted_status,
            "message": "Kiểm tra sức khỏe dịch vụ OCR hoàn tất",
        }

    except Exception as e:
        logger.error(f"OCR health check failed: {str(e)}")
        return {
            "overall_status": "error",
            "services": {},
            "message": f"Kiểm tra sức khỏe OCR thất bại: {str(e)}",
        }
