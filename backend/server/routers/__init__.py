import os

from fastapi import APIRouter

from server.routers.auth_router import auth
from server.routers.agent_router import agent_router
from server.routers.chat_router import chat
from server.routers.dashboard_router import dashboard
from server.routers.auth_dept_router import department
from server.routers.mcp_router import mcp
from server.routers.model_provider_router import model_providers
from server.routers.skill_router import skills, user_skills
from server.routers.system_router import system
from server.routers.system_task_router import tasks
from server.routers.tool_router import tools
from server.routers.user_router import user_router
from server.routers.filesystem_router import filesystem_router
from server.routers.workspace_router import workspace
from server.routers.mention_router import mention_router

_LITE_MODE = os.environ.get("LITE_MODE", "").lower() in ("true", "1")

router = APIRouter()

# Basic system interface: health check, configuration, authentication and chat main link.
router.include_router(system)  # /api/system/* System status and global configuration
router.include_router(auth)  # /api/auth/* Login, user information and CLI browser login authorization
router.include_router(agent_router)  # /api/agent/* Agent management and running state
router.include_router(chat)  # /api/chat/* Conversation threads, message history and attachments

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

if not _LITE_MODE:
    from server.routers.graph_router import graph
    from server.routers.knowledge_router import knowledge
    from server.routers.knowledge_eval_router import evaluation

    # The knowledge base and graph capabilities are heavily dependent, so this set of interfaces is skipped in LITE mode.
    router.include_router(knowledge)  # /api/knowledge/* Knowledge base management and retrieval
    router.include_router(evaluation)  # /api/evaluation/* Knowledge base evaluation
    router.include_router(graph)  # /api/graph/* Graph query and management
