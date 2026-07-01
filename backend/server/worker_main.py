"""ARQ worker entrypoint."""

import asyncio
import os
import sys

# Must be placed at the top!
if sys.platform == "win32":
    # Add the previous level of the current file (main.py) (i.e. the root directory Yuxi) to sys.path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from yuxi.services.run_worker import WorkerSettings

__all__ = ["WorkerSettings"]
