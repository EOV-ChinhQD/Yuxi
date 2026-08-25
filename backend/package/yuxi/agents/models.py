from langchain.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from yuxi import config as sys_config
from yuxi.models.providers.cache import model_cache
from yuxi.utils import get_docker_safe_url
from yuxi.utils.logging_config import logger


def resolve_chat_model_spec(model_spec: str | None, *, fallback: str | None = None) -> str:
    """Parse empty ModelConfiguration, do not swallow the existing Configuration but invalid ofModel value.

    This only handles the priority of when the Model is empty: request orConfiguration value, caller fallback, system defaultModel;
    Whether the specific Model exists, whether it is chatModel or not, it is still checked by model_cache.
    """
    for candidate in (model_spec, fallback, sys_config.default_model):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    raise ValueError("model spec không được để trống")


import time
import hashlib
import json
import asyncio
import threading
from typing import Any


class CachedModel:
    def __init__(self, llm: Any, ttl: float = 3600.0):
        self.llm = llm
        self.created_at = time.time()
        self.last_used = time.time()
        self.ttl = ttl
        self.hit_count = 0


_MODEL_CACHE: dict[tuple, CachedModel] = {}
_MODEL_CACHE_LOCK = threading.Lock()


def clear_model_cache():
    with _MODEL_CACHE_LOCK:
        _MODEL_CACHE.clear()
        logger.info("Model cache cleared manually.")


def get_model_cache_metrics() -> dict:
    with _MODEL_CACHE_LOCK:
        now = time.time()
        expired_keys = [k for k, v in _MODEL_CACHE.items() if now - v.last_used > v.ttl]
        for k in expired_keys:
            del _MODEL_CACHE[k]

        total_hits = sum(v.hit_count for v in _MODEL_CACHE.values())
        return {
            "cache_size": len(_MODEL_CACHE),
            "total_hits": total_hits,
            "evicted_count": len(expired_keys),
        }


async def warm_up_models():
    """Warm up popular models at startup."""
    try:
        from yuxi.models.providers.cache import model_cache

        available_specs = model_cache.get_all_specs("chat")
        specs_to_warm = []
        if sys_config.default_model:
            specs_to_warm.append(sys_config.default_model)
        for spec_info in available_specs:
            if spec_info.spec not in specs_to_warm:
                specs_to_warm.append(spec_info.spec)
            if len(specs_to_warm) >= 3:
                break

        logger.info(f"Warming up models: {specs_to_warm}")
        for spec in specs_to_warm:
            try:
                load_chat_model(spec)
            except Exception as e:
                logger.warning(f"Failed to warm up model {spec}: {e}")

        # Warm up tokenizers / nltk
        try:
            import nltk

            # Ensure it is downloaded or checked
            nltk.data.find("tokenizers/punkt_tab")
        except Exception as e:
            logger.warning(f"Failed to find nltk punkt_tab: {e}")

    except Exception as e:
        logger.warning(f"Error during models warm-up: {e}")


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

    # Build composite cache key
    provider = info.provider_type
    model_id = info.model_id
    endpoint = info.base_url
    api_key_hash = hashlib.sha256(info.api_key.encode("utf-8")).hexdigest() if info.api_key else ""

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    try:
        kwargs_serializable = {}
        for k, v in kwargs.items():
            if isinstance(v, (str, int, float, bool, type(None))):
                kwargs_serializable[k] = v
            else:
                kwargs_serializable[k] = str(v)
        serialized = json.dumps(kwargs_serializable, sort_keys=True)
        kwargs_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    except Exception:
        kwargs_hash = str(sorted(kwargs.items()))

    cache_key = (provider, model_id, endpoint, api_key_hash, loop, kwargs_hash)

    now = time.time()
    with _MODEL_CACHE_LOCK:
        # Evict expired models on access
        expired_keys = [k for k, v in _MODEL_CACHE.items() if now - v.last_used > v.ttl]
        for k in expired_keys:
            del _MODEL_CACHE[k]

        cached = _MODEL_CACHE.get(cache_key)
        if cached and (now - cached.last_used <= cached.ttl):
            cached.last_used = now
            cached.hit_count += 1
            logger.debug(f"Cache HIT for LLM model: {fully_specified_name} (hits: {cached.hit_count})")
            return cached.llm

    # ponytail: Instantiate model outside of lock to avoid blocking other threads/coroutines
    api_key = info.api_key
    base_url = get_docker_safe_url(info.base_url)
    if info.request_body_overrides:
        extra_body = dict(kwargs.get("extra_body") or {})
        extra_body.update(info.request_body_overrides)
        kwargs = {**kwargs, "extra_body": extra_body}

    metadata = dict(kwargs.pop("metadata", {}) or {})
    metadata.update(
        {
            "yuxi_provider_id": info.provider_id,
            "yuxi_provider_type": info.provider_type,
            "yuxi_model_id": info.model_id,
            "yuxi_model_spec": info.spec,
        }
    )
    kwargs["metadata"] = metadata

    logger.info(f"Cache MISS. Loading model {fully_specified_name} with provider_type={info.provider_type}")

    try:
        from yuxi.agents.backends.sandbox import sandbox_metrics
        sandbox_metrics.record_event("cache_miss")
    except Exception:
        pass

    if info.provider_type == "anthropic":
        from langchain_anthropic import ChatAnthropic

        llm = ChatAnthropic(
            model=info.model_id,
            api_key=SecretStr(api_key),
            base_url=base_url,
            **kwargs,
        )
    elif info.provider_type == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        llm = ChatGoogleGenerativeAI(
            model=info.model_id,
            google_api_key=SecretStr(api_key),
            max_retries=10,
            **kwargs,
        )
    else:
        llm = _ToolCallChunkFixChatOpenAI(
            model=info.model_id,
            api_key=SecretStr(api_key),
            base_url=base_url,
            stream_usage=True,
            **kwargs,
        )

    with _MODEL_CACHE_LOCK:
        _MODEL_CACHE[cache_key] = CachedModel(llm)
    return llm


class _ToolCallChunkFixChatOpenAI(ChatOpenAI):
    """Chuẩn hóa name/id rỗng trong tool_call streaming chunks để tránh lỗi tích lũy stream v3."""

    async def _astream(self, *args, **kwargs):
        async for chunk in super()._astream(*args, **kwargs):
            _normalize_tool_call_chunks(chunk.message)
            yield chunk

    def _stream(self, *args, **kwargs):
        for chunk in super()._stream(*args, **kwargs):
            _normalize_tool_call_chunks(chunk.message)
            yield chunk


def _normalize_tool_call_chunks(message) -> None:
    """Chuẩn hóa name/id rỗng trong tool_call chunks thành None.

    Cơ chế tích lũy stream LangGraph v3 ghi đè giá trị sau lên giá trị trước: một số nhà cung cấp tương thích
    OpenAI trả về chuỗi rỗng "" cho name/id ở các chunk tiếp theo, dẫn đến mất name/id gốc của chunk đầu.
    Hàm này chuẩn hóa chuỗi rỗng thành None để giữ lại định danh tool_call_id chính xác.
    """
    for chunk in message.tool_call_chunks:
        if chunk.get("name") == "":
            chunk["name"] = None
        if chunk.get("id") == "":
            chunk["id"] = None
