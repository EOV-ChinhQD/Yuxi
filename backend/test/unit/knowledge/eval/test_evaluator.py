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

    assert "User Question: Question" in prompt
    assert "Content 0" in prompt
    assert "Content 4" in prompt
    assert "Content 5" not in prompt


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
