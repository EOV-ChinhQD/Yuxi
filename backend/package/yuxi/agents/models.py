from typing import Any

from langchain.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from yuxi import config as sys_config
from yuxi.models.providers.cache import model_cache
from yuxi.utils import get_docker_safe_url
from yuxi.utils.logging_config import logger

_TOOL_IMAGE_USER_TEXT = "Images returned by read_file are attached below. Inspect them when answering."


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

    with _MODEL_CACHE_LOCK:
        cached = _MODEL_CACHE.get(cache_key)
        now = time.time()
        if cached and (now - cached.last_used <= cached.ttl):
            cached.last_used = now
            cached.hit_count += 1
            logger.debug(f"Cache HIT for LLM model: {fully_specified_name} (hits: {cached.hit_count})")
            return cached.llm

    # Double checked lock for creation
    with _MODEL_CACHE_LOCK:
        cached = _MODEL_CACHE.get(cache_key)
        if cached and (time.time() - cached.last_used <= cached.ttl):
            cached.last_used = time.time()
            cached.hit_count += 1
            return cached.llm

        api_key = info.api_key
        base_url = get_docker_safe_url(info.base_url)

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

        _MODEL_CACHE[cache_key] = CachedModel(llm)
        return llm


class _ToolCallChunkFixChatOpenAI(ChatOpenAI):
    """归一化流式 tool_call 续片中的空串 name/id，规避 v3 流式累积缺陷。"""

    def _get_request_payload(self, input_, *, stop=None, **kwargs):
        """Override to bridge tool image blocks to user messages."""
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        return _bridge_tool_images_to_user_messages(payload)

    async def _astream(self, *args, **kwargs):
        async for chunk in super()._astream(*args, **kwargs):
            _normalize_tool_call_chunks(chunk.message)
            yield chunk

    def _stream(self, *args, **kwargs):
        for chunk in super()._stream(*args, **kwargs):
            _normalize_tool_call_chunks(chunk.message)
            yield chunk


def _bridge_tool_images_to_user_messages(payload: dict[str, Any]) -> dict[str, Any]:
    """将工具调用返回的 image_url 块桥接到用户消息中，避免工具消息中包含图片导致的渲染问题。"""
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return payload
    if not any(isinstance(m, dict) and m.get("role") == "tool" and _tool_image_blocks(m) for m in messages):
        return payload

    bridged_messages: list[dict[str, Any]] = []
    pending_images: list[dict[str, Any]] = []

    def flush_pending_images() -> None:
        nonlocal pending_images
        if not pending_images:
            return

        bridged_messages.append(
            {
                "role": "user",
                "content": [{"type": "text", "text": _TOOL_IMAGE_USER_TEXT}, *pending_images],
            }
        )
        pending_images = []

    for message in messages:
        if not isinstance(message, dict):
            flush_pending_images()
            bridged_messages.append(message)
            continue

        role = message.get("role")
        if role != "tool":
            flush_pending_images()

        image_blocks = _tool_image_blocks(message) if role == "tool" else []
        if image_blocks:
            pending_images.extend(image_blocks)

            content = _text_without_images(message.get("content"), image_blocks)
            if not content:
                content = (
                    f"read_file returned {len(image_blocks)} image(s). "
                    "The image content is attached in the following user message for visual inspection."
                )
            message = {**message, "content": content}

        bridged_messages.append(message)

    flush_pending_images()

    return {**payload, "messages": bridged_messages}


def _normalize_tool_call_chunks(message) -> None:
    """把工具调用续片里空字符串的 name/id 归一化为 None。

    LangGraph v3 流式累积对 tool_call 字段是“后值覆盖”：部分 OpenAI 兼容提供商
    （siliconflow、阿里云百炼等）在续片里把 name/id 下发为空字符串 ""，会覆盖首片
    的真实值（siliconflow 丢 name、百炼丢 id），导致工具结果无法按 tool_call_id
    关联、工具状态停留在“进行中”。OpenAI 官方在续片里发 None 不会触发覆盖，这里
    把空串归一化为 None 对齐该行为。待上游修复 v3 协议后可移除。
    """
    for chunk in message.tool_call_chunks:
        if chunk.get("name") == "":
            chunk["name"] = None
        if chunk.get("id") == "":
            chunk["id"] = None


def _tool_image_blocks(message: dict[str, Any]) -> list[dict[str, Any]]:
    content = message.get("content")
    if not isinstance(content, list):
        return []
    return [
        block
        for block in content
        if isinstance(block, dict)
        and block.get("type") == "image_url"
        and isinstance(block.get("image_url"), dict)
        and isinstance(block["image_url"].get("url"), str)
    ]


def _text_without_images(content: Any, image_blocks: list[dict[str, Any]]) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    image_ids = {id(block) for block in image_blocks}
    parts: list[str] = []
    for block in content:
        if id(block) in image_ids:
            continue
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") in {"text", "input_text"}:
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(part for part in parts if part)
