#!/usr/bin/env python3
"""Enable a model on an existing provider and rebuild the runtime model cache.

Run inside api-dev so it uses the same code, database, and Redis as the app:

    docker exec api-dev python /app/project-scripts/eval/enable_provider_model.py \\
        --provider nvidia --model-id aisingapore/sea-lion-7b-instruct

After this, benchmark runners accept --model "<provider>:<model-id>".
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
for import_path in (APP_ROOT / "backend", APP_ROOT / "backend" / "package"):
    path_str = str(import_path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", required=True, help="Existing provider_id, e.g. nvidia")
    parser.add_argument("--model-id", required=True, help="Remote model id, e.g. aisingapore/sea-lion-7b-instruct")
    parser.add_argument("--type", default="chat", choices=("chat", "embedding", "rerank"))
    parser.add_argument("--display-name", default=None)
    args = parser.parse_args()

    from yuxi.models.providers.cache import model_cache
    from yuxi.models.providers.repository import get_model_provider, list_model_providers
    from yuxi.storage.postgres.manager import pg_manager

    async with pg_manager.get_async_session_context() as session:
        provider = await get_model_provider(session, args.provider)
        if provider is None:
            providers = await list_model_providers(session)
            known = sorted(p.provider_id for p in providers)
            print(json.dumps({"error": f"unknown provider '{args.provider}'", "known": known}))
            return 1

        enabled = list(provider.enabled_models or [])
        entry = {
            "id": args.model_id,
            "type": args.type,
            "display_name": args.display_name or args.model_id,
            "source": "remote",
        }
        enabled = [m for m in enabled if m.get("id") != args.model_id] + [entry]
        provider.enabled_models = enabled
        provider.is_enabled = True
        provider.updated_by = "benchmark-script"

    async with pg_manager.get_async_session_context() as session:
        providers = await list_model_providers(session)
    model_cache.rebuild(providers)

    spec = f"{args.provider}:{args.model_id}"
    info = model_cache.get_model_info(spec)
    print(json.dumps({
        "spec": spec,
        "cached": info is not None,
        "provider_type": info.provider_type if info else None,
        "base_url": info.base_url if info else None,
    }))
    await pg_manager.close()
    return 0 if info else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
