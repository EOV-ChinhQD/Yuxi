import pytest
import asyncio
import threading
from unittest.mock import MagicMock, patch
from yuxi.agents.models import load_chat_model, clear_model_cache, get_model_cache_metrics
from yuxi.agents.backends.sandbox.backend import ProvisionerSandboxBackend, sandbox_metrics
from deepagents.backends.protocol import ExecuteResponse


class DummyModelInfo:
    def __init__(self, spec, provider_type, model_id, api_key="test-key", base_url="http://test.ai"):
        self.spec = spec
        self.provider_type = provider_type
        self.model_id = model_id
        self.api_key = api_key
        self.base_url = base_url
        self.model_type = "chat"


@pytest.fixture(autouse=True)
def clean_caches():
    clear_model_cache()
    sandbox_metrics.total_runs = 0
    sandbox_metrics.timeouts = 0
    sandbox_metrics.crashes = 0
    sandbox_metrics.runtimes.clear()


@patch("yuxi.models.providers.cache.model_cache.get_model_info")
@patch("langchain_openai.ChatOpenAI")
def test_model_cache_hits_and_misses(mock_chat_openai, mock_get_model_info):
    mock_get_model_info.return_value = DummyModelInfo("openai:gpt-4o", "openai", "gpt-4o")
    
    # Verify initial cache is empty
    metrics = get_model_cache_metrics()
    assert metrics["cache_size"] == 0
    assert metrics["total_hits"] == 0

    # First load - Cache Miss
    model1 = load_chat_model("openai:gpt-4o")
    assert model1 is not None
    
    metrics = get_model_cache_metrics()
    assert metrics["cache_size"] == 1
    assert metrics["total_hits"] == 0
    
    # Second load - Cache Hit
    model2 = load_chat_model("openai:gpt-4o")
    assert model1 is model2  # Same instance
    
    metrics = get_model_cache_metrics()
    assert metrics["cache_size"] == 1
    assert metrics["total_hits"] == 1


@patch("yuxi.models.providers.cache.model_cache.get_model_info")
@patch("langchain_openai.ChatOpenAI")
def test_model_cache_keys_with_different_loops(mock_chat_openai, mock_get_model_info):
    mock_get_model_info.return_value = DummyModelInfo("openai:gpt-4o", "openai", "gpt-4o")

    # Mock different event loops
    loop1 = MagicMock()
    loop2 = MagicMock()

    with patch("asyncio.get_running_loop", return_value=loop1):
        model1 = load_chat_model("openai:gpt-4o")

    with patch("asyncio.get_running_loop", return_value=loop2):
        model2 = load_chat_model("openai:gpt-4o")

    assert model1 is not model2  # Different loops must have different instances
    metrics = get_model_cache_metrics()
    assert metrics["cache_size"] == 2


@patch("yuxi.models.providers.cache.model_cache.get_model_info")
@patch("langchain_openai.ChatOpenAI")
def test_model_cache_thread_safety(mock_chat_openai, mock_get_model_info):
    mock_get_model_info.return_value = DummyModelInfo("openai:gpt-4o", "openai", "gpt-4o")

    instances = []
    
    def worker():
        model = load_chat_model("openai:gpt-4o")
        instances.append(model)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All threads running in sync context (no loop) should get the exact same instance
    assert len(instances) == 5
    first_instance = instances[0]
    for inst in instances:
        assert inst is first_instance

    metrics = get_model_cache_metrics()
    assert metrics["cache_size"] == 1
    assert metrics["total_hits"] == 4


def test_sandbox_execute_success():
    backend = ProvisionerSandboxBackend(thread_id="test-thread", uid="test-uid")
    mock_client = MagicMock()
    backend._get_client = MagicMock(return_value=mock_client)

    # Mock normal execution result
    mock_exec_response = MagicMock()
    mock_exec_response.data.output = "hello world"
    mock_exec_response.data.exit_code = 0
    mock_client.shell.exec_command.return_value = mock_exec_response

    response = backend.execute("echo 'hello world'")
    assert response.exit_code == 0
    assert response.output == "hello world"
    assert sandbox_metrics.total_runs == 1
    assert sandbox_metrics.timeouts == 0
    assert sandbox_metrics.crashes == 0


def test_sandbox_execute_timeout():
    backend = ProvisionerSandboxBackend(thread_id="test-thread", uid="test-uid")
    mock_client = MagicMock()
    backend._get_client = MagicMock(return_value=mock_client)

    # Mock timeout exception raising
    mock_client.shell.exec_command.side_effect = Exception("Read timeout encountered")

    response = backend.execute("sleep 10")
    assert response.exit_code == 124
    assert "code execution" in response.output
    assert sandbox_metrics.total_runs == 1
    assert sandbox_metrics.timeouts == 1
    assert sandbox_metrics.crashes == 0


def test_sandbox_execute_crash():
    backend = ProvisionerSandboxBackend(thread_id="test-thread", uid="test-uid")
    mock_client = MagicMock()
    backend._get_client = MagicMock(return_value=mock_client)

    # Mock connection refused/fatal crash exception raising
    mock_client.shell.exec_command.side_effect = Exception("Connection refused")

    response = backend.execute("some-invalid-command")
    assert response.exit_code == 1
    assert "FatalError: Sandbox crashed." in response.output
    assert sandbox_metrics.total_runs == 1
    assert sandbox_metrics.timeouts == 0
    assert sandbox_metrics.crashes == 1


def test_nli_claim_importance_score():
    from yuxi.knowledge.grounding.nli_verifier import NLIVerifier

    # Factual claims with numbers or key documents terms should have higher scores
    claim_high = "Nghị định 15/2020/NĐ-CP có hiệu lực thi hành kể từ ngày 15 tháng 4 năm 2020."
    claim_low = "Thảo luận."

    score_high = NLIVerifier.score_claim_importance(claim_high)
    score_low = NLIVerifier.score_claim_importance(claim_low)

    assert score_high > score_low
    assert score_low < 0  # Should be penalized for length and lack of factual cues


@pytest.mark.asyncio
@patch("yuxi.knowledge.grounding.nli_verifier.NLIVerifier._run_batch_nli")
async def test_nli_verify_claims_limit_and_skipped(mock_run_batch_nli):
    from yuxi.knowledge.grounding.nli_verifier import NLIVerifier
    from yuxi.config import config

    # Mock config limit to 2
    config.max_nli_claims = 2

    claims = [
        "Nghị định 15/2020 có hiệu lực từ năm 2020.",  # Factual (high score)
        "Doanh thu năm 2023 đạt 100 tỷ đồng.",        # Factual (high score)
        "Xin chào quý khách hàng.",                   # Low score / greeting
        "Cảm ơn bạn đã hỏi.",                         # Low score / greeting
    ]
    chunks = ["Ngữ cảnh mẫu"]

    # Mock _run_batch_nli returns entailment for verified
    mock_run_batch_nli.return_value = [
        {"claim": claims[0], "score": 0.9, "label": "entailment"},
        {"claim": claims[1], "score": 0.9, "label": "entailment"},
    ]

    results = await NLIVerifier.verify_claims(claims, chunks)

    # 2 high priority claims should be verified, 2 low priority should be skipped
    assert len(results) == 4
    
    # Verify mapping and order preservation
    res_map = {r["claim"]: r for r in results}
    assert res_map[claims[0]]["label"] == "entailment"
    assert res_map[claims[1]]["label"] == "entailment"
    assert res_map[claims[2]]["label"] == "skipped"
    assert res_map[claims[3]]["label"] == "skipped"


def test_system_prompt_builder():
    from yuxi.agents.buildin.chatbot.prompt import SystemPromptBuilder
    
    builder = SystemPromptBuilder()
    prompt = builder.build(
        virtual_path_prefix="/prefix",
        outputs_path="/prefix/outputs",
        uploads_path="/prefix/uploads",
        workspace_path="/prefix/workspace"
    )

    assert "Bạn BẮT BUỘC phải SUY NGHĨ" in prompt
    assert "Yuxi" in prompt
    assert "/prefix/outputs" in prompt
    assert "/prefix/uploads" in prompt
    assert "/prefix/workspace" in prompt
    assert "<| RÀNG BUỘC BẢO MẬT VÀ PHẢN HỒI CHO NGƯỜI DÙNG |>" in prompt


@pytest.mark.asyncio
async def test_hybrid_router_heuristic():
    from yuxi.knowledge.retrieval.router import SemanticRouter, RouteType

    # Chit Chat
    route, details = await SemanticRouter.route("Xin chào")
    assert route == RouteType.CHIT_CHAT
    assert details["confidence_score"] == 1.0

    # Exact Match
    route, details = await SemanticRouter.route("Hợp đồng số HD-902-1234 có gì?")
    assert route == RouteType.EXACT_MATCH
    assert details["confidence_score"] == 1.0

    # Summarization
    route, details = await SemanticRouter.route("Tóm tắt tài liệu hướng dẫn sử dụng")
    assert route == RouteType.SUMMARIZATION
    assert details["confidence_score"] == 1.0


