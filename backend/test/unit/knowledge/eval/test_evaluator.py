import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from yuxi.knowledge.eval.evaluator import aggregate_metrics, build_answer_prompt, normalize_query_result


def test_normalize_query_result_supports_dict_and_list():
    answer, chunks = normalize_query_result({"answer": "A", "retrieved_chunks": [{"content": "C"}]})
    assert answer == "A"
    assert chunks == [{"content": "C"}]

    answer, chunks = normalize_query_result([{"content": "C"}])
    assert answer == ""
    assert chunks == [{"content": "C"}]


def test_build_answer_prompt_uses_first_five_non_empty_chunks():
    chunks = [{"content": f"content{i}"} for i in range(6)] + [{"content": ""}]

    prompt = build_answer_prompt("question", chunks)

    assert "User questions:question" in prompt
    assert "content0" in prompt
    assert "content4" in prompt
    assert "content5" not in prompt


def test_aggregate_metrics_matches_service_output_shape():
    metrics, overall_score = aggregate_metrics(
        [{"recall@1": 1.0, "f1@1": 0.0}, {"recall@1": 0.0, "f1@1": 1.0}],
        [{"score": 1.0}, {"score": 0.0}],
        include_overall_score=True,
    )

    assert metrics["recall@1"] == 0.5
    assert metrics["f1@1"] == 0.5
    assert metrics["answer_correctness"] == 0.5
    assert metrics["overall_score"] == overall_score


from unittest.mock import AsyncMock, MagicMock
import pytest
from yuxi.knowledge.eval.evaluator import evaluate_question

@pytest.mark.asyncio
async def test_evaluate_question_uses_custom_judge_llm():
    kb_instance = MagicMock()
    kb_instance.aquery = AsyncMock(return_value={"answer": "Generated Answer", "retrieved_chunks": []})

    question_data = {
        "query": "What is the capital of France?",
        "gold_chunk_ids": [],
        "gold_answer": "Paris"
    }

    judge_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = '{"score": 1.0, "reasoning": "Correct answer"}'
    judge_llm.call = AsyncMock(return_value=mock_response)

    res = await evaluate_question(
        kb_instance=kb_instance,
        kb_id="test_kb",
        question_data=question_data,
        retrieval_config={"answer_llm": "test/llm"},
        has_gold_chunks=False,
        has_gold_answers=True,
        judge_llm=judge_llm,
        select_model_fn=MagicMock()
    )

    assert res["answer_scores"] == {"score": 1.0, "reasoning": "Correct answer"}
    judge_llm.call.assert_called_once()
