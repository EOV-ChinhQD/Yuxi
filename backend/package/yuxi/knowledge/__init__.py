import os

from ..config import config
from .factory import KnowledgeBaseFactory
from .implementations.dify import DifyKB
from .implementations.milvus import MilvusKB
from .implementations.notion import NotionKB
from .manager import KnowledgeBaseManager

_LITE_MODE = os.environ.get("LITE_MODE", "").lower() in ("true", "1")
_SKIP_APP_INIT = os.environ.get("YUXI_SKIP_APP_INIT") == "1"

if not _LITE_MODE:
    # Register knowledge base type
    KnowledgeBaseFactory.register(MilvusKB)

KnowledgeBaseFactory.register(DifyKB)
KnowledgeBaseFactory.register(NotionKB)

# Create a knowledge base manager
work_dir = os.path.join(config.save_dir, "knowledge_base_data")
knowledge_base = KnowledgeBaseManager(work_dir)

__all__ = ["knowledge_base"]
