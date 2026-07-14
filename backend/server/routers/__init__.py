import os

from fastapi import APIRouter

from server.routers.agent_invocation_router import agent_invocation_router
from server.routers.agent_router import agent_router
from server.routers.auth_dept_router import department
from server.routers.auth_router import auth
from server.routers.chat_router import chat
from server.routers.dashboard_router import dashboard
from server.routers.filesystem_router import filesystem_router
from server.routers.mcp_router import mcp
from server.routers.mention_router import mention_router
from server.routers.model_provider_router import model_providers
from server.routers.skill_router import skills, user_skills
from server.routers.system_router import system
from server.routers.system_task_router import tasks
from server.routers.tool_router import tools
from server.routers.user_router import user_router
from server.routers.workspace_router import workspace
from server.routers.audit_router import router as audit_router

_LITE_MODE = os.environ.get("LITE_MODE", "").lower() in ("true", "1")

router = APIRouter()

# Giao diện hệ thống cơ bản: kiểm tra sức khỏe, cấu hình, xác thực và luồng trò chuyện chính.
router.include_router(system)  # /api/system/* Trạng thái hệ thống và cấu hình toàn cầu
router.include_router(auth)  # /api/auth/* Đăng nhập, thông tin người dùng và ủy quyền đăng nhập trình duyệt CLI
router.include_router(agent_router)  # /api/agent/* Quản lý agent và trạng thái chạy
router.include_router(agent_invocation_router)  # /api/agent-invocation/* Gọi và đánh giá agent bên ngoài
router.include_router(chat)  # /api/chat/* Thread đối thoại, lịch sử tin nhắn và tệp đính kèm

# Management and workbench interface: background tasks, authority domains, and tool system configuration.
router.include_router(dashboard)  # /api/dashboard/* Dashboard aggregated data
router.include_router(department)  # /api/departments/* Department and authority related data
router.include_router(tasks)  # /api/tasks/* Background task query and management
router.include_router(mcp)  # /api/system/mcp-servers/* MCP service management
router.include_router(model_providers)  # /api/system/model-providers/* Independent model configuration
router.include_router(skills)  # /api/system/skills/* Skills management
router.include_router(user_skills)  # /api/skills/* User-available Skills
router.include_router(tools)  # /api/system/tools/* Tool list and configuration
router.include_router(user_router)  # /api/user/* User-level configuration and credentials
router.include_router(filesystem_router)  # /api/viewer/filesystem/* Workbench file system view
router.include_router(workspace)  # /api/workspace/* User personal workspace
router.include_router(mention_router)  # /api/mention/* Mention file search interface
router.include_router(audit_router)  # /api/audit/* Audit Log Compliance

if not _LITE_MODE:
    from server.routers.graph_router import graph
    from server.routers.knowledge_eval_router import evaluation
    from server.routers.knowledge_router import knowledge

    # The knowledge base and graph capabilities are heavily dependent, so this set of interfaces is skipped in LITE mode.
    router.include_router(knowledge)  # /api/knowledge/* Knowledge base management and retrieval
    router.include_router(evaluation)  # /api/evaluation/* Knowledge base evaluation
    router.include_router(graph)  # /api/graph/* Graph query and management
