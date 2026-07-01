from langchain.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from yuxi import config as sys_config
from yuxi.models.providers.cache import model_cache
from yuxi.utils import get_docker_safe_url
from yuxi.utils.logging_config import logger


def _normalize_tool_call_chunks(message) -> None:
    """Call the tool with the name of the empty string in the sequel/id normalized to None.

    LangGraph v3 streaming accumulation pair tool_call Field is "post value coverage": part OpenAI compatible provider
    (siliconflow, Alibaba Cloud Bailian, etc.) If you issue name/id as an empty string "" in the sequel, it will overwrite the first film.
    of real value (siliconflow loses name, Bailian loses id), causing the tool results to fail to be based on tool_call_id
    The status of association and tool stays at "in progress". OpenAI officially releases None in the sequel and will not trigger coverage, here
    Normalizing the empty string to None aligns this behavior. You can remove it after the upstream fixes the v3 protocol.
    """
    for chunk in message.tool_call_chunks:
        if chunk.get("name") == "":
            chunk["name"] = None
        if chunk.get("id") == "":
            chunk["id"] = None


class _ToolCallChunkFixChatOpenAI(ChatOpenAI):
    """Empty string name in normalized streaming tool_call continuation/id, circumventing v3 streaming cumulative flaws."""

    async def _astream(self, *args, **kwargs):
        async for chunk in super()._astream(*args, **kwargs):
            _normalize_tool_call_chunks(chunk.message)
            yield chunk

    def _stream(self, *args, **kwargs):
        for chunk in super()._stream(*args, **kwargs):
            _normalize_tool_call_chunks(chunk.message)
            yield chunk


def resolve_chat_model_spec(model_spec: str | None, *, fallback: str | None = None) -> str:
    """Parse empty ModelConfiguration, do not swallow the existing Configuration but invalid ofModel value.

    This only handles the priority of when the Model is empty: request orConfiguration value, caller fallback, system defaultModel;
    Whether the specific Model exists, whether it is chatModel or not, it is still checked by model_cache.
    """
    for candidate in (model_spec, fallback, sys_config.default_model):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    raise ValueError("model spec không được để trống")


def load_chat_model(fully_specified_name: str | None, **kwargs) -> BaseChatModel:
    fully_specified_name = resolve_chat_model_spec(fully_specified_name)

    info = model_cache.get_model_info(fully_specified_name)
    if not info:
        available_specs = model_cache.get_all_specs("chat")
        available_ids = [item.spec for item in available_specs[:10]]
        raise ValueError(
            f"Unknown model spec: '{fully_specified_name}'. "
            f"Available chat models ({len(available_specs)}): {available_ids}"
        )

    if info.model_type != "chat":
        raise ValueError(f"Model {fully_specified_name} is not a chat model (type={info.model_type})")

    api_key = info.api_key
    base_url = get_docker_safe_url(info.base_url)

    logger.debug(f"Loading model {fully_specified_name} with provider_type={info.provider_type}")

    if info.provider_type == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=info.model_id,
            api_key=SecretStr(api_key),
            base_url=base_url,
            **kwargs,
        )
    if info.provider_type == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=info.model_id,
            google_api_key=SecretStr(api_key),
            **kwargs,
        )

    return _ToolCallChunkFixChatOpenAI(
        model=info.model_id,
        api_key=SecretStr(api_key),
        base_url=base_url,
        stream_usage=True,
        **kwargs,
    )
