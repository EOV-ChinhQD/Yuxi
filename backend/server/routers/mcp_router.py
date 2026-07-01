"""MCP Server management routing"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.agents.mcp.service import (
    create_mcp_server,
    get_mcp_tools_stats,
    delete_mcp_server,
    get_all_mcp_servers,
    get_all_mcp_tools,
    get_mcp_server,
    set_server_enabled,
    toggle_tool_enabled,
    update_mcp_server,
)
from yuxi.storage.postgres.models_business import User
from yuxi.utils import logger
from server.utils.auth_middleware import get_admin_user, get_db, get_required_user

mcp = APIRouter(prefix="/system/mcp-servers", tags=["mcp"])


# =============================================================================
# === DTOs ===
# =============================================================================


class CreateMcpServerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(..., description="Mã định danh ổn định")
    name: str = Field(..., description="Tên hiển thị")
    transport: str = Field(..., description="Loại truyền tải: sse/streamable_http/stdio")
    url: str | None = Field(None, description="URL máy chủ (sse/streamable_http)")
    command: str | None = Field(None, description="Lệnh (stdio)")
    args: list | None = Field(None, description="Mảng tham số lệnh (stdio)")
    env: dict | None = Field(None, description="Biến môi trường (stdio)")
    description: str | None = Field(None, description="Mô tả")
    headers: dict | None = Field(None, description="HTTP Header")
    timeout: int | None = Field(None, description="Thời gian chờ HTTP (giây)")
    sse_read_timeout: int | None = Field(None, description="Thời gian chờ đọc SSE (giây)")
    tags: list | None = Field(None, description="Mảng tag")
    icon: str | None = Field(None, description="Biểu tượng (emoji)")


class UpdateMcpServerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, description="Tên hiển thị")
    transport: str | None = Field(None, description="Loại truyền tải")
    url: str | None = Field(None, description="URL máy chủ")
    command: str | None = Field(None, description="Lệnh (stdio)")
    args: list | None = Field(None, description="Mảng tham số lệnh (stdio)")
    env: dict | None = Field(None, description="Biến môi trường (stdio)")
    description: str | None = Field(None, description="Mô tả")
    headers: dict | None = Field(None, description="HTTP Header")
    timeout: int | None = Field(None, description="Thời gian chờ HTTP (giây)")
    sse_read_timeout: int | None = Field(None, description="Thời gian chờ đọc SSE (giây)")
    tags: list | None = Field(None, description="Mảng tag")
    icon: str | None = Field(None, description="Biểu tượng (emoji)")


class UpdateMcpServerStatusRequest(BaseModel):
    enabled: bool = Field(..., description="Có kích hoạt hay không")


# =============================================================================
# === Helpers ===
# =============================================================================


async def get_server_or_404(db: AsyncSession, slug: str):
    """Helper to get server or raise 404."""
    server = await get_mcp_server(db, slug)
    if not server:
        raise HTTPException(status_code=404, detail=f"Máy chủ '{slug}' không tồn tại")
    return server


# =============================================================================
# === MCP Server CRUD ===
# =============================================================================


@mcp.get("")
async def get_mcp_servers(
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """Obtain all MCP server configurations (ordinary users only obtain the basic information of desensitization)"""
    try:
        servers = await get_all_mcp_servers(db)
        if current_user.role in ["admin", "superadmin"]:
            return {"success": True, "data": [s.to_dict() for s in servers]}

        data = []
        for s in servers:
            data.append(
                {
                    "name": getattr(s, "name", ""),
                    "description": getattr(s, "description", None),
                    "icon": getattr(s, "icon", None),
                    "enabled": bool(getattr(s, "enabled", True)),
                    "tags": getattr(s, "tags", None) or [],
                }
            )
        return {"success": True, "data": data}
    except Exception as e:
        logger.error(f"Failed to get MCP servers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@mcp.post("")
async def create_mcp_server_route(
    request: CreateMcpServerRequest,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new MCP server"""
    # Check transfer type
    valid_transports = ("sse", "streamable_http", "stdio")
    if request.transport not in valid_transports:
        raise HTTPException(status_code=400, detail=f"Loại truyền tải phải là một trong {', '.join(valid_transports)}")

    # Validate required fields based on transfer type
    if request.transport in ("sse", "streamable_http") and not request.url:
        raise HTTPException(status_code=400, detail=f"Khi loại truyền tải là {request.transport}, url là bắt buộc")
    if request.transport == "stdio" and not request.command:
        raise HTTPException(status_code=400, detail="Khi loại truyền tải là stdio, command là bắt buộc")

    try:
        server = await create_mcp_server(
            db,
            slug=request.slug,
            name=request.name,
            transport=request.transport,
            url=request.url,
            command=request.command,
            args=request.args,
            env=request.env,
            description=request.description,
            headers=request.headers,
            timeout=request.timeout,
            sse_read_timeout=request.sse_read_timeout,
            tags=request.tags,
            icon=request.icon,
            created_by=current_user.username,
        )
        return {"success": True, "data": server.to_dict()}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to create MCP server: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@mcp.get("/{slug}")
async def get_mcp_server_route(
    slug: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single MCP server configuration"""
    try:
        server = await get_server_or_404(db, slug)
        return {"success": True, "data": server.to_dict()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get MCP server: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@mcp.put("/{slug}")
async def update_mcp_server_route(
    slug: str,
    request: UpdateMcpServerRequest,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Update MCP server configuration"""
    # Check transfer type
    valid_transports = ("sse", "streamable_http", "stdio")
    if request.transport is not None and request.transport not in valid_transports:
        raise HTTPException(status_code=400, detail=f"Loại truyền tải phải là một trong {', '.join(valid_transports)}")

    try:
        fields_set = request.model_fields_set
        update_kwargs = {}
        if "env" in fields_set:
            update_kwargs["env"] = request.env

        server = await update_mcp_server(
            db,
            slug=slug,
            name=request.name,
            description=request.description,
            transport=request.transport,
            url=request.url,
            command=request.command,
            args=request.args,
            headers=request.headers,
            timeout=request.timeout,
            sse_read_timeout=request.sse_read_timeout,
            tags=request.tags,
            icon=request.icon,
            updated_by=current_user.username,
            **update_kwargs,
        )
        return {"success": True, "data": server.to_dict()}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to update MCP server: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@mcp.delete("/{slug}")
async def delete_mcp_server_route(
    slug: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete MCP server"""
    try:
        # Check whether it is a built-in server in the system
        server = await get_mcp_server(db, slug)
        if server and server.created_by == "system":
            raise HTTPException(status_code=403, detail="Không thể xóa máy chủ MCP mặc định của hệ thống")

        deleted = await delete_mcp_server(db, slug)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Máy chủ '{slug}' không tồn tại")
        return {"success": True, "message": f"Máy chủ '{slug}' đã được xóa"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete MCP server: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# === MCP Server Operations ===
# =============================================================================


@mcp.post("/{slug}/test")
async def test_mcp_server(
    slug: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Test MCP server connection"""
    try:
        await get_server_or_404(db, slug)

        try:
            tools = await get_all_mcp_tools(slug)
            return {
                "success": True,
                "message": f"Kết nối thành công, tìm thấy tổng cộng {len(tools)} công cụ",
                "tool_count": len(tools),
            }
        except Exception as test_error:
            raise HTTPException(status_code=500, detail=f"Kết nối thất bại: {str(test_error)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test MCP server: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@mcp.put("/{slug}/status")
async def update_mcp_server_status_route(
    slug: str,
    request: UpdateMcpServerStatusRequest,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Update MCP server enablement status"""
    try:
        is_enabled, server = await set_server_enabled(db, slug, request.enabled, current_user.username)
        return {
            "success": True,
            "enabled": is_enabled,
            "data": server.to_dict(),
            "message": f"MCP '{slug}' đã {'thêm' if is_enabled else 'gỡ bỏ'}",
        }
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to toggle MCP server: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# === MCP Tool Management ===
# =============================================================================


@mcp.get("/{slug}/tools")
async def get_mcp_server_tools(
    slug: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a list of tools for the MCP server"""
    try:
        server = await get_server_or_404(db, slug)
        disabled_tools = server.disabled_tools or []

        try:
            # Get all tools (without filtering disabled_tools)
            tools = await get_all_mcp_tools(slug)
            tool_list = []

            for tool in tools:
                original_name = tool.name
                unique_id = tool.metadata.get("id") if tool.metadata else original_name

                tool_info = {
                    "name": original_name,
                    "id": unique_id,
                    "description": getattr(tool, "description", ""),
                    "enabled": original_name not in disabled_tools,
                }
                # Extract parameter information
                if hasattr(tool, "args_schema") and tool.args_schema:
                    schema = tool.args_schema.schema() if hasattr(tool.args_schema, "schema") else {}
                    tool_info["parameters"] = schema.get("properties", {})
                    tool_info["required"] = schema.get("required", [])
                else:
                    tool_info["parameters"] = {}
                    tool_info["required"] = []
                tool_list.append(tool_info)

            return {
                "success": True,
                "data": tool_list,
                "total": len(tool_list),
            }
        except Exception as tool_error:
            logger.error(f"Failed to get tools from MCP server '{slug}': {tool_error}")
            raise HTTPException(status_code=500, detail=f"Lấy công cụ thất bại: {str(tool_error)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get MCP server tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@mcp.post("/{slug}/tools/refresh")
async def refresh_mcp_server_tools(
    slug: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Refresh the tool list of the MCP server (clear cache and re-fetch)"""
    try:
        await get_server_or_404(db, slug)

        try:
            # Get all tools (without filtering disabled_tools)
            tools = await get_all_mcp_tools(slug)

            # Get statistics
            stats = get_mcp_tools_stats(slug)
            enabled_count = stats.get("enabled", len(tools)) if stats else len(tools)
            disabled_count = stats.get("disabled", 0) if stats else 0

            message = "Danh sách công cụ đã được làm mới"
            if disabled_count > 0:
                message += f", {enabled_count} đã kích hoạt, {disabled_count} đã vô hiệu hóa"
            else:
                message += f", tìm thấy tổng cộng {enabled_count} công cụ"

            return {
                "success": True,
                "message": message,
                "tool_count": enabled_count,
                "enabled_count": enabled_count,
                "disabled_count": disabled_count,
            }
        except Exception as tool_error:
            raise HTTPException(status_code=500, detail=f"Làm mới thất bại: {str(tool_error)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to refresh MCP server tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@mcp.put("/{slug}/tools/{tool_name}/toggle")
async def toggle_mcp_server_tool_route(
    slug: str,
    tool_name: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle the enabled status of an individual tool"""
    try:
        enabled, _ = await toggle_tool_enabled(db, slug, tool_name, current_user.username)
        return {
            "success": True,
            "tool_name": tool_name,
            "enabled": enabled,
            "message": f"Công cụ '{tool_name}' đã {'kích hoạt' if enabled else 'vô hiệu hóa'}",
        }
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to toggle MCP server tool: {e}")
        raise HTTPException(status_code=500, detail=str(e))
