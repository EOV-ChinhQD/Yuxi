import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from yuxi.services.task_service import tasker
from yuxi.agents.mcp.service import ensure_builtin_mcp_servers_in_db
from yuxi.models.providers.service import ensure_builtin_model_providers_in_db
from yuxi.services.run_queue_service import close_queue_clients, get_redis_client
from yuxi.storage.postgres.manager import pg_manager
from yuxi.knowledge import knowledge_base
from yuxi.utils import logger
from yuxi.agents.backends.sandbox import init_sandbox_provider, shutdown_sandbox_provider
from yuxi import get_version
from yuxi.config import config


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan event manager"""
    # Initialize database connection
    try:
        pg_manager.initialize()
        await pg_manager.create_tables()
        await pg_manager.ensure_business_schema()
        await pg_manager.ensure_knowledge_schema()
    except Exception as e:
        logger.error(f"Failed to initialize database during startup: {e}")

    # Make sure the built-in MCP server definition exists in the database
    try:
        await ensure_builtin_mcp_servers_in_db()
    except Exception as e:
        logger.error(f"Failed to ensure builtin MCP servers during startup: {e}")

    try:
        from yuxi.agents.skills.service import init_builtin_skills

        async with pg_manager.get_async_session_context() as session:
            await init_builtin_skills(session)
    except Exception as e:
        logger.error(f"Failed to initialize builtin skills during startup: {e}")

    try:
        from yuxi.repositories.agent_repository import AgentRepository

        async with pg_manager.get_async_session_context() as session:
            repository = AgentRepository(session)
            await repository.ensure_default_agent()
            await repository.ensure_general_purpose_subagent()
            await repository.ensure_web_search_subagent()
            await repository.ensure_deep_research_agents()
    except Exception as e:
        logger.error(f"Failed to ensure default agent during startup: {e}")

    # Initialize built-in model supplier configuration
    try:
        async with pg_manager.get_async_session_context() as session:
            await ensure_builtin_model_providers_in_db(session)
    except Exception as e:
        logger.error(f"Failed to ensure builtin model providers during startup: {e}")

    # Initialize model cache (used by v2 model selection) and warm up
    try:
        from yuxi.models.providers.cache import model_cache
        from yuxi.models.providers.service import get_all_model_providers
        from yuxi.agents.models import warm_up_models

        async with pg_manager.get_async_session_context() as session:
            providers = await get_all_model_providers(session)
            model_cache.rebuild(providers)

        # Warm up models
        await warm_up_models()
    except Exception as e:
        logger.error(f"Failed to initialize model cache/warm-up during startup: {e}")

    # Initialize the knowledge base manager
    if os.environ.get("LITE_MODE", "").lower() in ("true", "1"):
        logger.info("LITE_MODE enabled, skipping knowledge base initialization")
    else:
        try:
            await knowledge_base.initialize()
        except Exception as e:
            logger.error(f"Failed to initialize knowledge base manager: {e}")

    # Warm up Redis (run queue)
    try:
        redis = await get_redis_client()
        await redis.ping()
    except Exception as e:
        logger.warning(f"Run queue redis unavailable on startup: {e}")

    # Start the runtime configuration synchronization thread (which periodically pulls configuration snapshots saved by the administrator from Redis)
    config.start_runtime_sync()

    try:
        init_sandbox_provider()
    except Exception as e:
        logger.error(f"Failed to initialize sandbox provider during startup: {e}")

    # =========================================================
    # 2. Core repair: Execute setup() here once, and pull down the table after it is built.
    # =========================================================
    checkpointer = AsyncPostgresSaver(pg_manager.langgraph_pool)
    await checkpointer.setup()
    print("LangGraph Checkpoint tables verified/created!")

    await tasker.start()
    
    # Start APScheduler for Episodic Decay Job (TTL)
    # NOTE: In a multi-worker deployment, this in-memory scheduler will run on each process.
    # To scale properly, configure a Redis or SQLAlchemy job store for APScheduler, or use a distributed lock.
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from yuxi.agents.memory.decay_job import run_episodic_decay_job
        import datetime

        scheduler = AsyncIOScheduler()
        # Schedule the job to run every 24 hours, starting now
        scheduler.add_job(
            run_episodic_decay_job,
            "interval",
            hours=24,
            next_run_time=datetime.datetime.now(datetime.timezone.utc)
        )
        scheduler.start()
        app.state.scheduler = scheduler
        logger.info("APScheduler started: scheduled episodic memory decay job every 24 hours.")
    except Exception as e:
        logger.error(f"Failed to start APScheduler for episodic memory decay: {e}", exc_info=True)

    logger.info(f"""

░██     ░██                       ░██
 ░██   ░██
  ░██ ░██   ░██    ░██ ░██    ░██ ░██
   ░████    ░██    ░██  ░██  ░██  ░██
    ░██     ░██    ░██   ░█████   ░██
    ░██     ░██   ░███  ░██  ░██  ░██
    ░██      ░█████░██ ░██    ░██ ░██  v{get_version()}

    """)
    logger.info("Yuxi backend startup complete")
    yield
    # Shutdown APScheduler
    if hasattr(app.state, "scheduler"):
        try:
            app.state.scheduler.shutdown()
            logger.info("APScheduler shut down successfully.")
        except Exception as e:
            logger.error(f"Failed to shutdown APScheduler: {e}", exc_info=True)

    await tasker.shutdown()
    shutdown_sandbox_provider()
    await close_queue_clients()
    await pg_manager.close()
