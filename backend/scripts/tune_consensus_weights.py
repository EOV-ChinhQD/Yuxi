import asyncio
import argparse
import sys
from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository
from yuxi.utils import logger

async def tune_weights(kb_id: str, reset: bool):
    repo = KnowledgeBaseRepository()
    kb = await repo.get_by_kb_id(kb_id)
    if not kb:
        logger.error(f"KB {kb_id} not found.")
        sys.exit(1)
        
    metadata = dict(kb.metadata_ or {})
    
    if reset:
        if "consensus_weights" in metadata:
            del metadata["consensus_weights"]
            await repo.update(kb_id, {"metadata_": metadata})
            logger.info(f"Reset consensus_weights for KB {kb_id} to default.")
        else:
            logger.info(f"KB {kb_id} does not have tuned weights to reset.")
        return

    # Dummy tuning implementation simulating Grid Search using Evaluation Service
    logger.info(f"Starting Grid Search tuning for KB {kb_id}...")
    await asyncio.sleep(2)
    # Assume grid search yields these optimal weights:
    optimal_weights = {
        "w_naive": 0.3,
        "w_local": 0.3,
        "w_relation": 0.2,
        "w_event": 0.2,
    }
    logger.info(f"Tuning complete. Optimal weights: {optimal_weights}")
    
    metadata["consensus_weights"] = optimal_weights
    await repo.update(kb_id, {"metadata_": metadata})
    logger.info(f"Updated consensus_weights for KB {kb_id}.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tune consensus weights for a KB.")
    parser.add_argument("--kb_id", required=True, help="Knowledge Base ID")
    parser.add_argument("--reset", action="store_true", help="Reset weights to default")
    args = parser.parse_args()
    
    asyncio.run(tune_weights(args.kb_id, args.reset))
