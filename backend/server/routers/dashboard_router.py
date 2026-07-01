"""
Dashboard Router - Statistics and monitoring endpoints
Dashboard - statisticsand monitoring endpoints

Provides centralized dashboard APIs for monitoring system-wide statistics.
Provides system-level statistics and monitoring API interfaces for monitoring system operating status, user activities, tool calls, knowledge base usage, etc.
"""

import traceback
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Integer, String, cast, distinct, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from server.utils.auth_middleware import get_db, get_superadmin_user
from yuxi.repositories.agent_repository import AgentRepository
from yuxi.repositories.conversation_repository import ConversationRepository
from yuxi.storage.postgres.models_business import User
from yuxi.utils.datetime_utils import UTC, ensure_shanghai, shanghai_now, utc_now
from yuxi.utils.logging_config import logger


dashboard = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _get_time_group_format(column, time_range: str) -> Any:
    """
    Generate time point group Format surface expression based on database type.
    PostgreSQL use to_char + INTERVAL, SQLite uses datetime + strftime。
    """
    # Check if it is PostgreSQL (by detecting engine or using dialect)
    # PostgreSQL syntax is used directly here because all business data is now on PostgreSQL
    if time_range == "14hours":
        # Hourly: YYYY-MM-DD HH:00
        time_expr = func.to_char(column + text("INTERVAL '8 hours'"), "YYYY-MM-DD HH24:00")
    elif time_range == "14weeks":
        # Weekly: YYYY-WW
        time_expr = func.to_char(column + text("INTERVAL '8 hours'"), "YYYY-IW")
    else:  # 14days
        # Every day: YYYY-MM-DD
        time_expr = func.to_char(column + text("INTERVAL '8 hours'"), "YYYY-MM-DD")
    return time_expr


# =============================================================================
# Response Models
# =============================================================================


class UserActivityStats(BaseModel):
    """User activity statistics"""

    total_users: int
    active_users_24h: int
    active_users_30d: int
    daily_active_users: list[dict]  # Daily active users in the last 7 days


class ToolCallStats(BaseModel):
    """Tool call statistics"""

    total_calls: int
    successful_calls: int
    failed_calls: int
    success_rate: float
    most_used_tools: list[dict]
    tool_error_distribution: dict
    daily_tool_calls: list[dict]  # Number of daily tool calls in the last 7 days


class KnowledgeStats(BaseModel):
    """Knowledge base statistics"""

    total_databases: int
    total_files: int
    total_nodes: int
    total_storage_size: int  # byte
    databases_by_type: dict
    file_type_distribution: dict


class AgentAnalytics(BaseModel):
    """AI agent analysis"""

    total_agents: int
    agent_conversation_counts: list[dict]
    agent_satisfaction_rates: list[dict]
    agent_tool_usage: list[dict]
    top_performing_agents: list[dict]
    agent_names: dict[str, str] = {}  # agent_id -> agent_name mapping


class ConversationListItem(BaseModel):
    """Conversation list item"""

    thread_id: str
    uid: str
    agent_id: str
    title: str
    status: str
    message_count: int
    created_at: str
    updated_at: str


class ConversationDetailResponse(BaseModel):
    """Conversation detail"""

    thread_id: str
    uid: str
    agent_id: str
    title: str
    status: str
    message_count: int
    created_at: str
    updated_at: str
    total_tokens: int
    messages: list[dict]


# =============================================================================
# Conversation Management - Conversation Management
# =============================================================================


@dashboard.get("/conversations", response_model=list[ConversationListItem])
async def get_all_conversations(
    uid: str | None = None,
    agent_id: str | None = None,
    status: str = "active",
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_superadmin_user),
):
    """Get all conversations (super admin privileges)"""
    from yuxi.storage.postgres.models_business import Conversation, ConversationStats

    try:
        # Build query
        query = select(Conversation, ConversationStats).outerjoin(
            ConversationStats, Conversation.id == ConversationStats.conversation_id
        )

        # Apply filters
        if uid:
            query = query.filter(Conversation.uid == uid)
        if agent_id:
            query = query.filter(Conversation.agent_id == agent_id)
        if status != "all":
            query = query.filter(Conversation.status == status)

        # Order and paginate
        query = query.order_by(Conversation.updated_at.desc()).limit(limit).offset(offset)

        result = await db.execute(query)
        results = result.all()

        return [
            {
                "thread_id": conv.thread_id,
                "uid": conv.uid,
                "agent_id": conv.agent_id,
                "title": conv.title,
                "status": conv.status,
                "message_count": stats.message_count if stats else 0,
                "created_at": conv.created_at.isoformat(),
                "updated_at": conv.updated_at.isoformat(),
            }
            for conv, stats in results
        ]
    except Exception as e:
        logger.error(f"Error getting conversations: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to get conversations: {str(e)}")


@dashboard.get("/conversations/{thread_id}", response_model=ConversationDetailResponse)
async def get_conversation_detail(
    thread_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_superadmin_user),
):
    """Get specified conversation details (super administrator privileges)"""
    try:
        conv_manager = ConversationRepository(db)
        conversation = await conv_manager.get_conversation_by_thread_id(thread_id)

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Get messages and stats
        messages = await conv_manager.get_messages(conversation.id)
        stats = await conv_manager.get_stats(conversation.id)

        # Format messages
        message_list = []
        for msg in messages:
            msg_dict = {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "message_type": msg.message_type,
                "created_at": msg.created_at.isoformat(),
            }

            # Include tool calls if present
            if msg.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "tool_name": tc.tool_name,
                        "tool_input": tc.tool_input,
                        "tool_output": tc.tool_output,
                        "status": tc.status,
                    }
                    for tc in msg.tool_calls
                ]

            message_list.append(msg_dict)

        return {
            "thread_id": conversation.thread_id,
            "uid": conversation.uid,
            "agent_id": conversation.agent_id,
            "title": conversation.title,
            "status": conversation.status,
            "message_count": stats.message_count if stats else len(message_list),
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(),
            "total_tokens": stats.total_tokens if stats else 0,
            "messages": message_list,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation detail: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to get conversation detail: {str(e)}")


# =============================================================================
# User activity statistics (super administrator privileges)
# =============================================================================


@dashboard.get("/stats/users", response_model=UserActivityStats)
async def get_user_activity_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_superadmin_user),
):
    """Get user activity statistics (super administrator privileges)"""
    try:
        from yuxi.storage.postgres.models_business import Conversation, User

        now = utc_now()
        # PostgreSQL with asyncpg requires naive datetime for naive DateTime columns
        naive_now = now.replace(tzinfo=None)

        # Conversations may store either the numeric user primary key or the login uid string.
        # Join condition accounts for both representations.
        user_join_condition = Conversation.uid == User.uid

        # Basic user statistics (excluding deleted users)
        total_users_result = await db.execute(select(func.count(User.id)).filter(User.is_deleted == 0))
        total_users = total_users_result.scalar() or 0

        # Number of active users by time period (based on conversation activity, excluding deleted users)
        active_users_24h_result = await db.execute(
            select(func.count(distinct(User.id)))
            .select_from(Conversation)
            .join(User, user_join_condition)
            .filter(Conversation.updated_at >= naive_now - timedelta(days=1), User.is_deleted == 0)
        )
        active_users_24h = active_users_24h_result.scalar() or 0

        active_users_30d_result = await db.execute(
            select(func.count(distinct(User.id)))
            .select_from(Conversation)
            .join(User, user_join_condition)
            .filter(Conversation.updated_at >= naive_now - timedelta(days=30), User.is_deleted == 0)
        )
        active_users_30d = active_users_30d_result.scalar() or 0
        # Daily active users in the last 7 days (excluding deleted users)
        daily_active_users = []
        for i in range(7):
            day_start = naive_now - timedelta(days=i + 1)
            day_end = naive_now - timedelta(days=i)

            active_count_result = await db.execute(
                select(func.count(distinct(User.id)))
                .select_from(Conversation)
                .join(User, user_join_condition)
                .filter(Conversation.updated_at >= day_start, Conversation.updated_at < day_end, User.is_deleted == 0)
            )
            active_count = active_count_result.scalar() or 0

            daily_active_users.append({"date": day_start.strftime("%Y-%m-%d"), "active_users": active_count})

        return UserActivityStats(
            total_users=total_users,
            active_users_24h=active_users_24h,
            active_users_30d=active_users_30d,
            daily_active_users=list(reversed(daily_active_users)),  # in chronological order
        )

    except Exception as e:
        logger.error(f"Error getting user activity stats: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to get user activity stats: {str(e)}")


# =============================================================================
# Tool Call Statistics - Tool call statistics
# =============================================================================


@dashboard.get("/stats/tools", response_model=ToolCallStats)
async def get_tool_call_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_superadmin_user),
):
    """Get tool call statistics (super administrator privileges)"""
    try:
        from yuxi.storage.postgres.models_business import ToolCall

        now = utc_now()
        # PostgreSQL with asyncpg requires naive datetime for naive DateTime columns
        naive_now = now.replace(tzinfo=None)

        # Basic tool call statistics
        total_calls_result = await db.execute(select(func.count(ToolCall.id)))
        total_calls = total_calls_result.scalar() or 0

        successful_calls_result = await db.execute(select(func.count(ToolCall.id)).filter(ToolCall.status == "success"))
        successful_calls = successful_calls_result.scalar() or 0
        failed_calls = total_calls - successful_calls
        success_rate = round((successful_calls / total_calls * 100), 2) if total_calls > 0 else 0

        # Most commonly used tools
        most_used_tools_result = await db.execute(
            select(ToolCall.tool_name, func.count(ToolCall.id).label("count"))
            .group_by(ToolCall.tool_name)
            .order_by(func.count(ToolCall.id).desc())
            .limit(10)
        )
        most_used_tools = most_used_tools_result.all()
        most_used_tools = [{"tool_name": name, "count": count} for name, count in most_used_tools]

        # Tool error distribution
        tool_errors_result = await db.execute(
            select(ToolCall.tool_name, func.count(ToolCall.id).label("error_count"))
            .filter(ToolCall.status == "error")
            .group_by(ToolCall.tool_name)
        )
        tool_errors = tool_errors_result.all()
        tool_error_distribution = {name: count for name, count in tool_errors}

        # Number of daily tool calls in the last 7 days
        daily_tool_calls = []
        for i in range(7):
            day_start = naive_now - timedelta(days=i + 1)
            day_end = naive_now - timedelta(days=i)

            daily_count_result = await db.execute(
                select(func.count(ToolCall.id)).filter(ToolCall.created_at >= day_start, ToolCall.created_at < day_end)
            )
            daily_count = daily_count_result.scalar() or 0

            daily_tool_calls.append({"date": day_start.strftime("%Y-%m-%d"), "call_count": daily_count})

        return ToolCallStats(
            total_calls=total_calls,
            successful_calls=successful_calls,
            failed_calls=failed_calls,
            success_rate=success_rate,
            most_used_tools=most_used_tools,
            tool_error_distribution=tool_error_distribution,
            daily_tool_calls=list(reversed(daily_tool_calls)),
        )

    except Exception as e:
        logger.error(f"Error getting tool call stats: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to get tool call stats: {str(e)}")


# =============================================================================
# Knowledge base statistics (super administrator privileges)
# =============================================================================


@dashboard.get("/stats/knowledge", response_model=KnowledgeStats)
async def get_knowledge_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_superadmin_user),
):
    """Get knowledge base statistics (super administrator privileges)"""
    try:
        from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository
        from yuxi.repositories.knowledge_file_repository import KnowledgeFileRepository

        kb_repo = KnowledgeBaseRepository()
        file_repo = KnowledgeFileRepository()

        kb_rows = await kb_repo.get_all()
        total_databases = len(kb_rows)

        databases_by_type: dict[str, int] = {}
        files_by_type: dict[str, int] = {}
        total_files = 0
        total_nodes = 0
        total_storage_size = 0

        file_type_mapping = {
            "txt": "text file",
            "pdf": "PDF document",
            "docx": "Word document",
            "doc": "Word document",
            "md": "Markdown",
            "html": "HTML web page",
            "htm": "HTML web page",
            "json": "JSON data",
            "csv": "CSV table",
            "xlsx": "Excel table",
            "xls": "Excel table",
            "pptx": "PowerPoint",
            "ppt": "PowerPoint",
            "png": "PNG images",
            "jpg": "JPEG pictures",
            "jpeg": "JPEG pictures",
            "gif": "GIF pictures",
            "svg": "SVG pictures",
            "mp4": "MP4 video",
            "mp3": "MP3 audio",
            "zip": "ZIP compressed package",
            "rar": "RAR archive",
            "7z": "7Z compressed package",
        }

        for kb in kb_rows:
            kb_type = (kb.kb_type or "unknown").lower()
            display_type = {
                "faiss": "FAISS",
                "milvus": "Milvus",
                "dify": "Dify",
                "qdrant": "Qdrant",
                "elasticsearch": "Elasticsearch",
                "unknown": "unknown type",
            }.get(kb_type, kb.kb_type or "unknown type")
            databases_by_type[display_type] = databases_by_type.get(display_type, 0) + 1

            files = await file_repo.list_by_kb_id(kb.kb_id)
            total_files += len(files)
            for record in files:
                file_ext = (record.file_type or "").lower()
                display_name = file_type_mapping.get(file_ext, file_ext.upper() + "document" if file_ext else "other")
                files_by_type[display_name] = files_by_type.get(display_name, 0) + 1
                total_storage_size += int(record.file_size or 0)

        return KnowledgeStats(
            total_databases=total_databases,
            total_files=total_files,
            total_nodes=total_nodes,
            total_storage_size=total_storage_size,
            databases_by_type=databases_by_type,
            file_type_distribution=files_by_type,
        )

    except Exception as e:
        logger.error(f"Error getting knowledge stats: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to get knowledge stats: {str(e)}")


# =============================================================================
# Agent analysis (super administrator privileges)
# =============================================================================


@dashboard.get("/stats/agents", response_model=AgentAnalytics)
async def get_agent_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_superadmin_user),
):
    """Get agent analysis (super administrator privileges)"""
    try:
        from yuxi.storage.postgres.models_business import Conversation, Message, MessageFeedback, ToolCall

        # Get all agents
        agents_result = await db.execute(
            select(Conversation.agent_id, func.count(Conversation.id).label("conversation_count")).group_by(
                Conversation.agent_id
            )
        )
        agents = agents_result.all()

        total_agents = len(agents)
        agent_conversation_counts = [{"agent_id": agent_id, "conversation_count": count} for agent_id, count in agents]

        # Agent satisfaction statistics
        agent_satisfaction = []
        for agent_id, _ in agents:
            total_feedbacks_result = await db.execute(
                select(func.count(MessageFeedback.id))
                .join(Message, MessageFeedback.message_id == Message.id)
                .join(Conversation, Message.conversation_id == Conversation.id)
                .filter(Conversation.agent_id == agent_id)
            )
            total_feedbacks = total_feedbacks_result.scalar() or 0

            positive_feedbacks_result = await db.execute(
                select(func.count(MessageFeedback.id))
                .join(Message, MessageFeedback.message_id == Message.id)
                .join(Conversation, Message.conversation_id == Conversation.id)
                .filter(Conversation.agent_id == agent_id, MessageFeedback.rating == "like")
            )
            positive_feedbacks = positive_feedbacks_result.scalar() or 0

            satisfaction_rate = round((positive_feedbacks / total_feedbacks * 100), 2) if total_feedbacks > 0 else 100

            agent_satisfaction.append(
                {"agent_id": agent_id, "satisfaction_rate": satisfaction_rate, "total_feedbacks": total_feedbacks}
            )

        # Agent tool usage statistics
        agent_tool_usage = []
        for agent_id, _ in agents:
            tool_usage_count_result = await db.execute(
                select(func.count(ToolCall.id))
                .join(Message, ToolCall.message_id == Message.id)
                .join(Conversation, Message.conversation_id == Conversation.id)
                .filter(Conversation.agent_id == agent_id)
            )
            tool_usage_count = tool_usage_count_result.scalar() or 0

            agent_tool_usage.append({"agent_id": agent_id, "tool_usage_count": tool_usage_count})

        # Top performing agents (ordered by number of conversations)
        top_performing_agents = []
        for i, (agent_id, conv_count) in enumerate(agents):
            # Get satisfaction data
            satisfaction_data = next(
                (s for s in agent_satisfaction if s["agent_id"] == agent_id), {"satisfaction_rate": 0}
            )

            top_performing_agents.append(
                {
                    "agent_id": agent_id,
                    "conversation_count": conv_count,
                    "satisfaction_rate": satisfaction_data["satisfaction_rate"],
                }
            )

        # Sort by number of conversations and take the top 5
        top_performing_agents.sort(key=lambda x: x["conversation_count"], reverse=True)
        top_performing_agents = top_performing_agents[:5]

        agent_slugs = [agent_id for agent_id, _ in agents if agent_id]
        agent_names = {}
        if agent_slugs:
            agent_repo = AgentRepository(db)
            agent_names = {agent.slug: agent.name for agent in await agent_repo.list_by_slugs(agent_slugs)}

        return AgentAnalytics(
            total_agents=total_agents,
            agent_conversation_counts=agent_conversation_counts,
            agent_satisfaction_rates=agent_satisfaction,
            agent_tool_usage=agent_tool_usage,
            top_performing_agents=top_performing_agents,
            agent_names=agent_names,
        )

    except Exception as e:
        logger.error(f"Error getting agent analytics: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to get agent analytics: {str(e)}")


# =============================================================================
# Basic statistics (super administrator privileges)
# =============================================================================


@dashboard.get("/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_superadmin_user),
):
    """Get basic statistics (super administrator privileges)"""
    from yuxi.storage.postgres.models_business import Conversation, Message, MessageFeedback

    try:
        # Basic counts
        total_conversations_result = await db.execute(select(func.count(Conversation.id)))
        total_conversations = total_conversations_result.scalar() or 0

        active_conversations_result = await db.execute(
            select(func.count(Conversation.id)).filter(Conversation.status == "active")
        )
        active_conversations = active_conversations_result.scalar() or 0

        total_messages_result = await db.execute(select(func.count(Message.id)))
        total_messages = total_messages_result.scalar() or 0

        total_users_result = await db.execute(select(func.count(User.id)).filter(User.is_deleted == 0))
        total_users = total_users_result.scalar() or 0

        # Feedback statistics
        total_feedbacks_result = await db.execute(select(func.count(MessageFeedback.id)))
        total_feedbacks = total_feedbacks_result.scalar() or 0

        like_count_result = await db.execute(
            select(func.count(MessageFeedback.id)).filter(MessageFeedback.rating == "like")
        )
        like_count = like_count_result.scalar() or 0

        # Calculate satisfaction rate
        satisfaction_rate = round((like_count / total_feedbacks * 100), 2) if total_feedbacks > 0 else 100

        return {
            "total_conversations": total_conversations,
            "active_conversations": active_conversations,
            "total_messages": total_messages,
            "total_users": total_users,
            "feedback_stats": {
                "total_feedbacks": total_feedbacks,
                "satisfaction_rate": satisfaction_rate,
            },
        }
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard stats: {str(e)}")


# =============================================================================
# Feedback management (super administrator privileges)
# =============================================================================


class FeedbackListItem(BaseModel):
    """feedback list items"""

    id: int
    uid: str
    username: str | None
    avatar: str | None
    rating: str
    reason: str | None
    created_at: str
    message_content: str
    conversation_title: str | None
    agent_id: str


@dashboard.get("/feedbacks", response_model=list[FeedbackListItem])
async def get_all_feedbacks(
    rating: str | None = None,
    agent_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_superadmin_user),
):
    """Get all feedback records (super administrator privileges)"""
    from yuxi.storage.postgres.models_business import Conversation, Message, MessageFeedback, User

    try:
        query = (
            select(MessageFeedback, Message, Conversation, User)
            .join(Message, MessageFeedback.message_id == Message.id)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .outerjoin(User, MessageFeedback.uid == User.uid)
        )

        # Apply filters
        if rating and rating in ["like", "dislike"]:
            query = query.filter(MessageFeedback.rating == rating)
        if agent_id:
            query = query.filter(Conversation.agent_id == agent_id)

        # Order by creation time (most recent first)
        query = query.order_by(MessageFeedback.created_at.desc())

        results = await db.execute(query)
        results = results.all()

        # Debug logging (privacy-safe)
        logger.info(f"Found {len(results)} feedback records")
        # Removed sensitive user data from logs for privacy compliance

        return [
            {
                "id": feedback.id,
                "message_id": feedback.message_id,
                "uid": feedback.uid,
                "username": user.username if user else None,
                "avatar": user.avatar if user else None,
                "rating": feedback.rating,
                "reason": feedback.reason,
                "created_at": feedback.created_at.isoformat(),
                "message_content": message.content,
                "conversation_title": conversation.title,
                "agent_id": conversation.agent_id,
            }
            for feedback, message, conversation, user in results
        ]
    except Exception as e:
        logger.error(f"Error getting feedbacks: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to get feedbacks: {str(e)}")


# =============================================================================
# Call to analyze time series statistics (super administrator privileges)
# =============================================================================


class TimeSeriesStats(BaseModel):
    """time series statistics"""

    data: list[dict]  # [{"date": "2024-01-01", "data": {"item1": 50, "item2": 30}, "total": 80}, ...]
    categories: list[str]  # All category names
    total_count: int
    average_count: float
    peak_count: int
    peak_date: str
    agent_names: dict[str, str] | None = None  # agent_id -> agent_name mapping (type=agents only)


@dashboard.get("/stats/calls/timeseries", response_model=TimeSeriesStats)
async def get_call_timeseries_stats(
    type: str = "models",  # models/agents/tokens/tools
    time_range: str = "14days",  # 14hours/14days/14weeks
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_superadmin_user),
):
    """Get call analysis time series statistics (super administrator privileges)"""
    try:
        from yuxi.storage.postgres.models_business import Conversation, Message, ToolCall

        # Calculation time range (using Beijing time UTC+8)
        now = utc_now()
        local_now = shanghai_now()

        if time_range == "14hours":
            intervals = 14
            # Contains current hour: starting 13 hours ago
            start_time = now - timedelta(hours=intervals - 1)
            group_format = _get_time_group_format(Message.created_at, time_range)
            base_local_time = ensure_shanghai(start_time)
        elif time_range == "14weeks":
            intervals = 14
            # Contains the current week: starting 13 weeks ago and aligned to Monday 00:00 of the current week
            local_start = local_now - timedelta(weeks=intervals - 1)
            local_start = local_start - timedelta(days=local_start.weekday())
            local_start = local_start.replace(hour=0, minute=0, second=0, microsecond=0)
            start_time = local_start.astimezone(UTC)
            group_format = _get_time_group_format(Message.created_at, time_range)
            base_local_time = local_start
        else:  # 14days (default)
            intervals = 14
            # Includes current day: starting 13 days ago
            start_time = now - timedelta(days=intervals - 1)
            group_format = _get_time_group_format(Message.created_at, time_range)
            base_local_time = ensure_shanghai(start_time)

        # Convert start_time to naive UTC datetime for PostgreSQL query
        # PostgreSQL with asyncpg and naive DateTime columns requires naive datetime objects
        query_start_time = start_time.replace(tzinfo=None)

        # Query data based on type
        if type == "models":
            # Model call statistics (based on number of messages, grouped by model)
            # Extract model information from extra_metadata of message
            category_expr = cast(Message.extra_metadata["response_metadata"]["model_name"], String)
            query_result = await db.execute(
                select(
                    group_format.label("date"),
                    func.count(Message.id).label("count"),
                    category_expr.label("category"),
                )
                .filter(Message.role == "assistant", Message.created_at >= query_start_time)
                .filter(Message.extra_metadata.isnot(None))
                .group_by(group_format, category_expr)
                .order_by(group_format)
            )
            query = query_result.all()
        elif type == "agents":
            # Agent call statistics (based on conversation update time, grouped by agent)
            # Create independent time formatter for conversations (using PostgreSQL-compatible to_char + INTERVAL)
            conv_group_format = _get_time_group_format(Conversation.updated_at, time_range)

            query_result = await db.execute(
                select(
                    conv_group_format.label("date"),
                    func.count(Conversation.id).label("count"),
                    Conversation.agent_id.label("category"),
                )
                .filter(Conversation.updated_at.isnot(None))
                .filter(Conversation.updated_at >= query_start_time)
                .group_by(conv_group_format, Conversation.agent_id)
                .order_by(conv_group_format)
            )
            query = query_result.all()
        elif type == "tokens":
            # Token consumption statistics (differentiate between input/output tokens)
            # First query input tokens
            from sqlalchemy import literal

            input_query_result = await db.execute(
                select(
                    group_format.label("date"),
                    func.sum(
                        func.coalesce(
                            cast(cast(Message.extra_metadata["usage_metadata"]["input_tokens"], String), Integer), 0
                        )
                    ).label("count"),
                    literal("input_tokens").label("category"),
                )
                .filter(
                    Message.created_at >= query_start_time,
                    Message.extra_metadata.isnot(None),
                    Message.extra_metadata["usage_metadata"].isnot(None),
                )
                .group_by(group_format)
                .order_by(group_format)
            )
            input_query = input_query_result.all()

            # Query output tokens
            output_query_result = await db.execute(
                select(
                    group_format.label("date"),
                    func.sum(
                        func.coalesce(
                            cast(cast(Message.extra_metadata["usage_metadata"]["output_tokens"], String), Integer), 0
                        )
                    ).label("count"),
                    literal("output_tokens").label("category"),
                )
                .filter(
                    Message.created_at >= query_start_time,
                    Message.extra_metadata.isnot(None),
                    Message.extra_metadata["usage_metadata"].isnot(None),
                )
                .group_by(group_format)
                .order_by(group_format)
            )
            output_query = output_query_result.all()

            # Merge two query results
            input_results = input_query
            output_results = output_query
            results = input_results + output_results
        elif type == "tools":
            # Tool call statistics (grouped by tool name)
            # Create independent time formatter for tool calls (using PostgreSQL compatible to_char + INTERVAL)
            tool_group_format = _get_time_group_format(ToolCall.created_at, time_range)

            query_result = await db.execute(
                select(
                    tool_group_format.label("date"),
                    func.count(ToolCall.id).label("count"),
                    ToolCall.tool_name.label("category"),
                )
                .filter(ToolCall.created_at >= query_start_time)
                .group_by(tool_group_format, ToolCall.tool_name)
                .order_by(tool_group_format)
            )
            query = query_result.all()
        else:
            raise HTTPException(status_code=422, detail=f"Invalid type: {type}")

        if type != "tokens":
            results = query

        # Handling stacked data formats
        # First collect all categories
        categories = set()
        for result in results:
            if hasattr(result, "category") and result.category:
                categories.add(result.category)

        # If there is no category data, provide a default category
        if not categories:
            if type == "models":
                categories.add("unknown_model")
            elif type == "agents":
                categories.add("unknown_agent")
            elif type == "tokens":
                categories.update(["input_tokens", "output_tokens"])
            elif type == "tools":
                categories.add("unknown_tool")

        categories = sorted(list(categories))

        agent_names = None
        if type == "agents" and categories:
            agent_slugs = [c for c in categories if c]
            if agent_slugs:
                agent_repo = AgentRepository(db)
                agent_names = {agent.slug: agent.name for agent in await agent_repo.list_by_slugs(agent_slugs)}

        # Reorganize data: group data for each category by time point
        time_data = {}

        def normalize_week_key(raw_key: str) -> str:
            base_date = datetime.strptime(f"{raw_key}-1", "%Y-%W-%w")
            iso_year, iso_week, _ = base_date.isocalendar()
            return f"{iso_year}-{iso_week:02d}"

        for result in results:
            date_key = result.date
            if time_range == "14weeks":
                date_key = normalize_week_key(date_key)
            category = getattr(result, "category", "unknown")
            count = result.count

            if date_key not in time_data:
                time_data[date_key] = {}

            time_data[date_key][category] = count

        # Fill in missing time points (using Beijing time)
        data = []
        # Start from the starting point (Beijing time)
        current_time = base_local_time

        if time_range == "14hours":
            delta = timedelta(hours=1)
        elif time_range == "14weeks":
            delta = timedelta(weeks=1)
        else:
            delta = timedelta(days=1)

        for i in range(intervals):
            if time_range == "14hours":
                date_key = current_time.strftime("%Y-%m-%d %H:00")
            elif time_range == "14weeks":
                iso_year, iso_week, _ = current_time.isocalendar()
                date_key = f"{iso_year}-{iso_week:02d}"
            else:
                date_key = current_time.strftime("%Y-%m-%d")

            # Get data at this point in time
            day_data = time_data.get(date_key, {})
            day_total = sum(day_data.values())

            # Make sure all categories have values ​​(missing ones are filled with 0s)
            for category in categories:
                if category not in day_data:
                    day_data[category] = 0

            data.append({"date": date_key, "data": day_data, "total": day_total})
            current_time += delta

        # Calculate statistical indicators
        if type == "tools":
            # For tool calls, displays the total for all times (consistent with ToolStatsComponent)
            from yuxi.storage.postgres.models_business import ToolCall

            total_count_result = await db.execute(select(func.count(ToolCall.id)))
            total_count = total_count_result.scalar() or 0
        else:
            # Other types use sums of time series data
            total_count = sum(item["total"] for item in data)

        average_count = round(total_count / intervals, 2) if intervals > 0 else 0
        peak_data = max(data, key=lambda x: x["total"]) if data else {"total": 0, "date": ""}

        return TimeSeriesStats(
            data=data,
            categories=categories,
            total_count=total_count,
            average_count=average_count,
            peak_count=peak_data["total"],
            peak_date=peak_data["date"],
            agent_names=agent_names,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting call timeseries stats: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to get call timeseries stats: {str(e)}")
