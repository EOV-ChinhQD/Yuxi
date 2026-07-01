from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class ToolExtraMetadata:
    """Meta-dữ liệu bổ sung (đăng ký bằng decorator)"""

    category: str = ""  # Phân loại: buildin, knowledge, mysql, subagents, debug
    tags: list[str] = field(default_factory=list)
    display_name: str = ""  # Tên hiển thị
    icon: str = ""
    config_guide: str = ""  # Hướng dẫn cấu hình


# Global registry: tool_name -> ToolExtraMetadata
_extra_registry: dict[str, ToolExtraMetadata] = {}

# List of global tool instances (automatically collected by the @tool decorator)
_all_tool_instances: list = []


def get_extra_metadata(tool_name: str) -> ToolExtraMetadata | None:
    """Get tool additional metadata"""
    return _extra_registry.get(tool_name)


def get_all_extra_metadata() -> dict[str, ToolExtraMetadata]:
    """Get all additional metadata"""
    return _extra_registry.copy()


def get_all_tool_instances() -> list:
    """Get all tool instances (provided by @tool Decorators automatically collected)"""
    return _all_tool_instances


# Extended decorator based on langchain.tool
def tool(
    category: str = "",
    tags: list[str] = None,
    display_name: str = "",
    icon: str = "",
    config_guide: str = "",
    name_or_callable: str | Callable | None = None,
    description: str | None = None,
    args_schema: type | None = None,
    return_direct: bool = False,
):
    """Decorator mở rộng dựa trên langchain.tool, đồng thời đăng ký meta-dữ liệu.

    Cách sử dụng:
    @tool(category="buildin", tags=["tinh-toan"], display_name="Calculator")
    def calculator(a: float, b: float, operation: str) -> float:
        ...
    """
    from langchain.tools import tool as langchain_tool

    # First apply the langchain tool decorator
    langchain_decorator = langchain_tool(
        name_or_callable=name_or_callable,
        description=description,
        args_schema=args_schema,
        return_direct=return_direct,
    )

    def decorator(func: Callable) -> Callable:
        # Apply the langchain decorator
        tool_obj = langchain_decorator(func)

        # Register additional metadata
        tool_name = tool_obj.name
        _extra_registry[tool_name] = ToolExtraMetadata(
            category=category,
            tags=tags or [],
            display_name=display_name,
            icon=icon,
            config_guide=config_guide,
        )

        # Automatic collection tool example
        tool_obj.handle_tool_error = True
        _all_tool_instances.append(tool_obj)

        return tool_obj

    return decorator
