import asyncio
import importlib
import inspect
from pathlib import Path

from yuxi.agents.base import BaseAgent
from yuxi.utils import logger
from yuxi.utils.singleton import SingletonMeta


class AgentManager(metaclass=SingletonMeta):
    def __init__(self):
        self._classes = {}
        self._instances = {}

    def register_agent(self, agent_class):
        self._classes[agent_class.__name__] = agent_class

    def init_all_agents(self):
        for agent_id in self._classes.keys():
            self.get_agent(agent_id)

    def get_agent(self, agent_id, reload=False, reload_graph=False, **kwargs):

        if reload or agent_id not in self._instances:
            agent_class = self._classes[agent_id]
            self._instances[agent_id] = agent_class()

        if reload_graph and agent_id in self._instances:
            self._instances[agent_id].reload_graph()

        return self._instances[agent_id]

    def get_agents(self):
        return list(self._instances.values())

    async def reload_all(self):
        for agent_id in self._classes.keys():
            self.get_agent(agent_id, reload=True)

    async def get_agents_info(self, include_configurable_items: bool = True):
        agents = self.get_agents()
        return await asyncio.gather(
            *[a.get_info(include_configurable_items=include_configurable_items) for a in agents]
        )

    def auto_discover_agents(self):
        """
        Auto-discover and register all agents in yuxi/agents/buildin/
        """
        # Get the path to the agents directory
        agents_dir = Path(__file__).parent

        # Iterate over all subdirectories
        for item in agents_dir.iterdir():
            # Skip non-directory, common directory, and __pycache__
            if not item.is_dir() or item.name.startswith("_"):
                continue

            # Check if there is an __init__.py file
            init_file = item / "__init__.py"
            if not init_file.exists():
                logger.warning(f"{item} is not a valid module")
                continue

            # Try to import module
            try:
                module_name = f"yuxi.agents.buildin.{item.name}"
                module = importlib.import_module(module_name)

                # Find all BaseAgent subclasses in the module
                for name, obj in inspect.getmembers(module):
                    if (
                        inspect.isclass(obj)
                        and issubclass(obj, BaseAgent)
                        and obj is not BaseAgent
                        and obj.__module__.startswith(module_name)
                    ):
                        logger.info(f"Auto-discovered agent: {obj.__name__} from {item.name}")
                        self.register_agent(obj)

            except Exception as e:
                logger.warning(f"Failed to load agent from {item.name}: {e}")


agent_manager = AgentManager()
agent_manager.auto_discover_agents()
agent_manager.init_all_agents()

__all__ = ["agent_manager"]


if __name__ == "__main__":
    pass
