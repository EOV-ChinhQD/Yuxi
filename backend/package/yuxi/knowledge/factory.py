from yuxi.knowledge.base import KBNotFoundError, KnowledgeBase
from yuxi.utils import logger


class KnowledgeBaseFactory:
    """Knowledge base factory class, responsible for creating different types of knowledge base instances"""

    # Registered knowledge base type mapping {kb_type: kb_class}
    _kb_types: dict[str, type[KnowledgeBase]] = {}

    @classmethod
    def register(cls, kb_class: type[KnowledgeBase]):
        """
        Register knowledge base type

        Args:
            kb_class: Knowledge base class
        """
        if not issubclass(kb_class, KnowledgeBase):
            raise ValueError("Knowledge base class must inherit from KnowledgeBase")
        if not kb_class.kb_type:
            raise ValueError("Knowledge base class must define kb_type")

        cls._kb_types[kb_class.kb_type] = kb_class
        # logger.info(f"Registered knowledge base type: {kb_class.kb_type}")

    @classmethod
    def create(cls, kb_type: str, work_dir: str, **kwargs) -> KnowledgeBase:
        """
        Create a knowledge base instance

        Args:
            kb_type: Knowledge base type
            work_dir: working directory
            **kwargs: other initialization parameters

        Returns:
            Knowledge Base Example

        Raises:
            KBNotFoundError: Unknown knowledge base type
        """
        if kb_type not in cls._kb_types:
            available_types = list(cls._kb_types.keys())
            raise KBNotFoundError(f"Unknown knowledge base type: {kb_type}. Available types: {available_types}")

        kb_class = cls._kb_types[kb_type]

        try:
            # Create instance
            instance = kb_class(work_dir, **kwargs)
            logger.info(f"Created {kb_type} knowledge base instance at {work_dir}")
            return instance
        except Exception as e:
            logger.error(f"Failed to create {kb_type} knowledge base: {e}")
            raise

    @classmethod
    def get_available_types(cls) -> dict[str, dict]:
        """
        Get all available ofKnowledge base types

        Returns:
            Knowledge base type information dictionary
        """
        result = {}
        for kb_type, kb_class in cls._kb_types.items():
            result[kb_type] = {
                "name": kb_class.name,
                "description": kb_class.description,
                "requires_embedding_model": kb_class.requires_embedding_model,
                "supports_documents": kb_class.supports_documents,
                "create_params": kb_class.get_create_params_config(),
            }
        return result

    @classmethod
    def get_kb_class(cls, kb_type: str) -> type[KnowledgeBase]:
        """
        Get the specified type ofKnowledge base class.

        Args:
            kb_type: Knowledge base type

        Returns:
            Knowledge base class
        """
        if kb_type not in cls._kb_types:
            available_types = list(cls._kb_types.keys())
            raise KBNotFoundError(f"Unknown knowledge base type: {kb_type}. Available types: {available_types}")
        return cls._kb_types[kb_type]

    @classmethod
    def is_type_supported(cls, kb_type: str) -> bool:
        """
        examineWhether to support specified ofKnowledge base class type

        Args:
            kb_type: Knowledge base type

        Returns:
            Whether to support
        """
        return kb_type in cls._kb_types
