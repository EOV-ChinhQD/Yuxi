import asyncio
import sys
from pathlib import Path

APP_ROOT = Path("/home/chinh303/code/rag/Yuxi/backend").resolve()
for import_path in (APP_ROOT, APP_ROOT / "package"):
    import_path_str = str(import_path)
    if import_path_str not in sys.path:
        sys.path.insert(0, import_path_str)

from dotenv import load_dotenv
load_dotenv(APP_ROOT / ".env", override=False)
load_dotenv(APP_ROOT.parent / ".env", override=False)

from yuxi.storage.postgres.manager import pg_manager
from yuxi import knowledge_base

async def test_query():
    pg_manager.initialize()
    kb_id = "kb_yolstgjixa"
    kb = await knowledge_base._get_kb_for_database(kb_id)
    await kb._load_metadata()
    query = "Tại sao GraphRAG của Microsoft lại bị đánh giá là kém hiệu quả và tốn kém chi phí (exorbitant expense) khi đối mặt với sự thay đổi dữ liệu liên tục trong môi trường thực tế so với LightRAG?"
    print(f"llm_model_spec = {kb.databases_meta[kb_id].get('llm_model_spec')}")
    print(f"Querying KB {kb_id}: {query}")
    try:
        results = await knowledge_base.aquery(query, kb_id=kb_id, caller_uid="admin", use_graph_retrieval=True, final_top_k=20)
        print("\n=== RESULTS ===")
        for i, res in enumerate(results):
            print(f"[{i}] Score: {res.get('score')}")
            print(f"Content: {res.get('content')}\n")
    except Exception as e:
        import traceback
        traceback.print_exc()
if __name__ == "__main__":
    asyncio.run(test_query())
