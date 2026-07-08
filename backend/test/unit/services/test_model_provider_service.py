import os

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from yuxi.models.providers.builtin import BUILTIN_PROVIDERS
from yuxi.models.providers.service import (
    check_credential_status,
    _normalize_payload,
    _normalize_remote_model,
    fetch_remote_models,
)


def test_normalize_payload_accepts_enabled_chat_model():
    payload = _normalize_payload(
        {
            "provider_id": "openrouter-local",
            "display_name": "OpenRouter Local",
            "base_url": "https://openrouter.ai/api/v1",
            "enabled_models": [{"id": "anthropic/claude-sonnet-4.5", "type": "chat"}],
        }
    )

    assert payload["provider_id"] == "openrouter-local"
    assert payload["provider_type"] == "openai"
    assert "models_endpoint" not in payload
    assert "embedding_models_endpoint" not in payload
    assert payload["enabled_models"][0]["display_name"] == "anthropic/claude-sonnet-4.5"


def test_normalize_payload_accepts_anthropic_provider_type():
    payload = _normalize_payload(
        {
            "provider_id": "xiaomi-token-plan",
            "display_name": "Xiaomi Token Plan",
            "provider_type": "anthropic",
            "base_url": "https://token-plan-cn.xiaomimimo.com/anthropic",
            "capabilities": ["chat"],
            "enabled_models": [{"id": "mimo-v2.5-pro", "type": "chat", "source": "manual"}],
        }
    )

    assert payload["provider_type"] == "anthropic"
    assert payload["enabled_models"][0]["id"] == "mimo-v2.5-pro"


def test_normalize_payload_rejects_unknown_enabled_model_type():
    with pytest.raises(ValueError, match="phải là chat"):
        _normalize_payload(
            {
                "provider_id": "openrouter-local",
                "display_name": "OpenRouter Local",
                "base_url": "https://openrouter.ai/api/v1",
                "enabled_models": [{"id": "unknown-model", "type": "unknown"}],
            }
        )


def test_normalize_payload_allows_embedding_without_dimension():
    """embedding The dimension of the model is an optional field, and no error will be reported if it is not provided."""
    payload = _normalize_payload(
        {
            "provider_id": "embedding-local",
            "display_name": "Embedding Local",
            "base_url": "https://example.com/v1",
            "capabilities": ["embedding"],
            "embedding_base_url": "https://example.com/v1/embeddings",
            "enabled_models": [{"id": "text-embedding", "type": "embedding"}],
        }
    )
    assert payload["provider_id"] == "embedding-local"
    assert payload["enabled_models"][0].get("dimension") is None


def test_normalize_remote_model_preserves_detailed_model_config():
    model = _normalize_remote_model(
        {
            "id": "xiaomi/mimo-v2-omni",
            "name": "Xiaomi: MiMo-V2-Omni",
            "context_length": 262144,
            "architecture": {
                "input_modalities": ["text", "audio", "image", "video"],
                "output_modalities": ["text"],
            },
            "top_provider": {"max_completion_tokens": 65536},
            "supported_parameters": ["temperature", "tools"],
        }
    )

    assert model["id"] == "xiaomi/mimo-v2-omni"
    assert model["display_name"] == "Xiaomi: MiMo-V2-Omni"
    assert model["type"] == "chat"
    assert model["input_modalities"] == ["text", "audio", "image", "video"]
    assert model["max_completion_tokens"] == 65536
    assert model["raw_metadata"]["supported_parameters"] == ["temperature", "tools"]


def test_normalize_remote_model_uses_endpoint_model_type():
    model = _normalize_remote_model({"id": "BAAI/bge-m3", "object": "model"}, "embedding")

    assert model["id"] == "BAAI/bge-m3"
    assert model["type"] == "embedding"


@pytest.mark.asyncio
async def test_fetch_remote_models_loads_embedding_only_when_capability_enabled(monkeypatch):
    calls = []

    async def fake_fetch(client, provider, headers, endpoint, model_type):
        calls.append((endpoint, model_type))
        return [{"id": f"{model_type}-model", "type": model_type}]

    monkeypatch.setattr("yuxi.models.providers.service._fetch_models_from_endpoint", fake_fetch)

    class Provider:
        base_url = "https://example.com/v1"
        api_key = None
        api_key_env = None
        headers_json = {}
        capabilities = ["chat", "embedding", "rerank"]
        models_endpoint = "/models"
        embedding_models_endpoint = "/embeddings/models"
        rerank_models_endpoint = None

    models = await fetch_remote_models(Provider())

    assert calls == [("/models", "chat"), ("/embeddings/models", "embedding")]
    assert [model["type"] for model in models] == ["chat", "embedding"]


def test_normalize_payload_rejects_ollama_provider_type():
    with pytest.raises(ValueError, match="provider_type phải là"):
        _normalize_payload(
            {
                "provider_id": "ollama-local",
                "display_name": "Ollama Local",
                "provider_type": "ollama",
                "base_url": "http://localhost:11434",
            }
        )


def test_builtin_provider_templates_default_to_openai_provider_type():
    assert len(BUILTIN_PROVIDERS) >= 16
    provider_types = set()
    for provider in BUILTIN_PROVIDERS:
        payload = {
            "provider_id": provider["provider_id"],
            "display_name": provider["display_name"],
            "provider_type": provider.get("provider_type"),
        }
        if "base_url" in provider:
            payload["base_url"] = provider["base_url"]
        
        normalized = _normalize_payload(payload)
        provider_types.add(normalized["provider_type"])
    assert provider_types == {"openai", "gemini"}


def test_builtin_siliconflow_provider_includes_default_runnable_models():
    provider = next(item for item in BUILTIN_PROVIDERS if item["provider_id"] == "siliconflow-cn")
    models = {model["id"]: model for model in provider["enabled_models"]}

    assert provider["capabilities"] == ["chat", "embedding", "rerank"]
    assert provider["embedding_base_url"] == "https://api.siliconflow.cn/v1/embeddings"
    assert provider["rerank_base_url"] == "https://api.siliconflow.cn/v1/rerank"
    assert models["Pro/BAAI/bge-m3"]["type"] == "embedding"
    assert models["Pro/BAAI/bge-m3"]["dimension"] == 1024
    assert "base_url_override" not in models["Pro/BAAI/bge-m3"]
    assert models["Pro/BAAI/bge-reranker-v2-m3"]["type"] == "rerank"
    assert "base_url_override" not in models["Pro/BAAI/bge-reranker-v2-m3"]


def test_builtin_dashscope_provider_includes_default_embedding_and_rerank_models():
    provider = next(item for item in BUILTIN_PROVIDERS if item["provider_id"] == "alibaba")
    models = {model["id"]: model for model in provider["enabled_models"]}

    assert provider["capabilities"] == ["chat", "embedding", "rerank"]
    assert provider["embedding_base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"
    assert provider["rerank_base_url"] == "https://dashscope.aliyuncs.com/compatible-api/v1/reranks"
    assert "embedding_models_endpoint" not in provider
    assert "rerank_models_endpoint" not in provider
    assert models["text-embedding-v4"]["type"] == "embedding"
    assert models["text-embedding-v4"]["dimension"] == 1024
    assert models["qwen3-rerank"]["type"] == "rerank"


def testcheck_credential_status_disabled_provider_always_ok():
    """The status of a non-enabled provider is always ok regardless of how the credentials are configured."""

    class Provider:
        is_enabled = False
        api_key = None
        api_key_env = None

    assert check_credential_status(Provider()) == "ok"


def testcheck_credential_status_direct_api_key_ok():
    """The enabled provider status of directly configured api_key is ok."""

    class Provider:
        is_enabled = True
        api_key = "sk-test"
        api_key_env = None

    assert check_credential_status(Provider()) == "ok"


def testcheck_credential_status_env_key_exists_ok(monkeypatch):
    """api_key_env The status is ok when the corresponding environment variable exists."""
    monkeypatch.setenv("TEST_API_KEY", "exists")

    class Provider:
        is_enabled = True
        api_key = None
        api_key_env = "TEST_API_KEY"

    assert check_credential_status(Provider()) == "ok"


def testcheck_credential_status_env_key_missing_warning(monkeypatch):
    """api_key_env When the corresponding environment variable does not exist, the status is warning."""
    monkeypatch.delenv("MISSING_KEY", raising=False)

    class Provider:
        is_enabled = True
        api_key = None
        api_key_env = "MISSING_KEY"

    assert check_credential_status(Provider()) == "warning"


def testcheck_credential_status_both_empty_warning():
    """api_key When neither api_key_env nor api_key_env is configured, the status is warning."""

    class Provider:
        is_enabled = True
        api_key = None
        api_key_env = None

    assert check_credential_status(Provider()) == "warning"


# ==================== Manually add model/source fields ====================


def test_normalize_payload_default_model_source_is_remote():
    """When source is not explicitly specified, remote is filled in by default after normalization, which is backward compatible with old data."""
    payload = _normalize_payload(
        {
            "provider_id": "openrouter-local",
            "display_name": "OpenRouter Local",
            "base_url": "https://openrouter.ai/api/v1",
            "enabled_models": [{"id": "anthropic/claude-sonnet-4.5", "type": "chat"}],
        }
    )

    assert payload["enabled_models"][0]["source"] == "remote"


def test_normalize_payload_accepts_manual_source():
    """source=manual Indicates a model manually added by the administrator, and normalization retains this label."""
    payload = _normalize_payload(
        {
            "provider_id": "custom-local",
            "display_name": "Custom Local",
            "base_url": "https://example.com/v1",
            "capabilities": ["chat"],
            "enabled_models": [{"id": "my-chat-model", "type": "chat", "source": "manual"}],
        }
    )

    assert payload["enabled_models"][0]["source"] == "manual"


def test_normalize_payload_rejects_invalid_source():
    """source Only manual or remote are allowed, other values ​​are considered illegal."""
    with pytest.raises(ValueError, match="phải là manual hoặc remote"):
        _normalize_payload(
            {
                "provider_id": "custom-local",
                "display_name": "Custom Local",
                "base_url": "https://example.com/v1",
                "enabled_models": [{"id": "x", "type": "chat", "source": "custom"}],
            }
        )


def test_normalize_payload_rejects_model_type_not_in_capabilities():
    """provider When only chat capability is declared, embedding type models are not allowed to be written."""
    with pytest.raises(ValueError, match="không nằm trong khả năng của provider"):
        _normalize_payload(
            {
                "provider_id": "chat-only",
                "display_name": "Chat Only",
                "base_url": "https://example.com/v1",
                "capabilities": ["chat"],
                "enabled_models": [{"id": "rogue-embedding", "type": "embedding", "dimension": 1024}],
            }
        )


def test_normalize_payload_allows_model_type_within_capabilities():
    """provider Also declare chat + embedding When , both types of models can be written normally."""
    payload = _normalize_payload(
        {
            "provider_id": "multi-cap",
            "display_name": "Multi Cap",
            "base_url": "https://example.com/v1",
            "capabilities": ["chat", "embedding"],
            "embedding_base_url": "https://example.com/v1/embeddings",
            "embedding_models_endpoint": "/embeddings/models",
            "enabled_models": [
                {"id": "chat-1", "type": "chat", "source": "manual"},
                {
                    "id": "embed-1",
                    "type": "embedding",
                    "source": "manual",
                    "dimension": 1024,
                },
            ],
        }
    )

    types = [model["type"] for model in payload["enabled_models"]]
    sources = [model["source"] for model in payload["enabled_models"]]
    assert types == ["chat", "embedding"]
    assert sources == ["manual", "manual"]
