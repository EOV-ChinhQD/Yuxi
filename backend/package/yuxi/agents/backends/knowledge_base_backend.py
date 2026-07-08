from __future__ import annotations

from typing import Any


async def resolve_visible_knowledge_bases_for_context(context) -> list[dict[str, Any]]:
    from yuxi import knowledge_base

    uid = getattr(context, "uid", None)
    if not uid:
        setattr(context, "_visible_knowledge_bases", [])
        return []

    result = await knowledge_base.get_databases_by_uid(str(uid))
    databases = result.get("databases") or []
    import os
    # Filter out SiliconFlow databases if SILICONFLOW_API_KEY is not set
    databases = [
        db for db in databases
        if not (str(db.get("embedding_model_spec") or "").startswith("siliconflow") and not os.environ.get("SILICONFLOW_API_KEY"))
    ]
    # Filter TEST_RAG_PIPELINE databases to keep only the latest one
    test_dbs = [db for db in databases if str(db.get("name") or "").startswith("TEST_RAG_PIPELINE_")]
    if test_dbs:
        def get_suffix(db):
            try:
                return int(db.get("name").split("_")[-1])
            except Exception:
                return -1
        latest_test_db = max(test_dbs, key=get_suffix)
        databases = [latest_test_db]
    enabled_knowledges = getattr(context, "knowledges", None)
    if enabled_knowledges is not None:
        enabled_ids = {str(value).strip() for value in enabled_knowledges if str(value).strip()}
        databases = [db for db in databases if str(db.get("kb_id") or "").strip() in enabled_ids]

    setattr(context, "_visible_knowledge_bases", databases)
    return databases
