from collections.abc import Callable
from typing import Any

from yuxi.knowledge.eval.metrics import EvaluationMetricsCalculator
from yuxi.knowledge.retrieval.multi_hop_retriever import detect_and_decompose, MultiHopRetriever
from yuxi.models.chat import ChatResponse
from yuxi.utils import logger


def normalize_query_result(query_result: Any) -> tuple[str, list[dict[str, Any]]]:
    if isinstance(query_result, dict):
        return query_result.get("answer", ""), query_result.get("retrieved_chunks", [])
    if isinstance(query_result, list):
        return "", query_result
    return "", []


def build_answer_prompt(query: str, retrieved_chunks: list[dict[str, Any]], max_docs: int = 5) -> str:
    context_docs = []
    for idx, chunk in enumerate(retrieved_chunks[:max_docs]):
        content = chunk.get("content", "")
        if content:
            context_docs.append(f"document {idx + 1}:\n{content}")

    context_text = "\\n\\n".join(context_docs)
    return (
        f"Based on the following contextual information, please answer the user's question.\n\n"
        f"Contextual information:{context_text}\n\n"
        f"User questions:{query}\n\n"
        "Please answer the question accurately based on contextual information.\n\n"
        "If relevant information is missing from the context please answer“Not enough information to answer”。\n\n"
    )


async def generate_answer_if_needed(
    *,
    query: str,
    generated_answer: str,
    retrieved_chunks: list[dict[str, Any]],
    retrieval_config: dict[str, Any],
    select_model_fn: Callable[..., Any],
) -> str:
    if generated_answer:
        return generated_answer
    if not retrieved_chunks or not retrieval_config.get("answer_llm"):
        return ""

    logger.debug(f"Use LLM {retrieval_config.get('answer_llm')} generate answer...")
    try:
        llm = select_model_fn(model_spec=retrieval_config["answer_llm"])
        response = await llm.call(build_answer_prompt(query, retrieved_chunks), stream=False)
        generated_answer = response.content if response else ""
        logger.debug(f"LLM generated answer length: {len(generated_answer) if generated_answer else 0}")
        return generated_answer
    except Exception as e:
        logger.error(f"LLM Failed to generate answer: {e}")
        return ""


async def evaluate_question(
    *,
    kb_instance: Any,
    kb_id: str,
    question_data: dict[str, Any],
    retrieval_config: dict[str, Any],
    has_gold_chunks: bool,
    has_gold_answers: bool,
    judge_llm: Any | None,
    select_model_fn: Callable[..., Any],
) -> dict[str, Any]:
    query = question_data["query"]
    
    is_multi_hop = False
    try:
        model_spec = retrieval_config.get("llm_model_spec") or "gpt-4o"
        decompose_result = await detect_and_decompose(query, model_spec=model_spec)
        if decompose_result and decompose_result["is_multi_hop"]:
            is_multi_hop = True
            mh_retriever = MultiHopRetriever(
                kb_id=kb_id, 
                model_spec=model_spec, 
                kb_instance=kb_instance, 
                retrieval_config=retrieval_config
            )
            # Parallel retrieve sub-queries
            retrieved_chunks_raw = await mh_retriever.parallel_retrieve(decompose_result["sub_queries"])
            query_result = {"answer": "", "chunks": retrieved_chunks_raw}
            logger.info(f"[Eval] Đã sử dụng Multi-hop cho truy vấn: {query}")
    except Exception as e:
        logger.error(f"[Eval] Lỗi phân rã Multi-hop: {e}")
        
    if not is_multi_hop:
        query_result = await kb_instance.aquery(query, kb_id, **retrieval_config)
        
    generated_answer, retrieved_chunks = normalize_query_result(query_result)
    generated_answer = await generate_answer_if_needed(
        query=query,
        generated_answer=generated_answer,
        retrieved_chunks=retrieved_chunks,
        retrieval_config=retrieval_config,
        select_model_fn=select_model_fn,
    )

    current_metrics = {}
    retrieval_scores = {}
    answer_scores = {}

    if has_gold_chunks and question_data.get("gold_chunk_ids"):
        retrieval_scores = EvaluationMetricsCalculator.calculate_retrieval_metrics(
            retrieved_chunks, question_data["gold_chunk_ids"]
        )
        current_metrics.update(retrieval_scores)

    if has_gold_answers and question_data.get("gold_answer"):
        if judge_llm:
            answer_scores = await EvaluationMetricsCalculator.calculate_answer_metrics(
                query=query,
                generated_answer=generated_answer,
                gold_answer=question_data["gold_answer"],
                judge_llm=judge_llm,
            )
            current_metrics.update(answer_scores)
        else:
            logger.warning("Need to calculate answer metrics but Judge LLM is not configured")

    return {
        "detail": {
            "query_text": query,
            "gold_chunk_ids": question_data.get("gold_chunk_ids"),
            "gold_answer": question_data.get("gold_answer"),
            "generated_answer": generated_answer,
            "retrieved_chunks": retrieved_chunks,
            "metrics": current_metrics,
        },
        "retrieval_scores": retrieval_scores,
        "answer_scores": answer_scores,
    }


def aggregate_metrics(
    retrieval_metrics_list: list[dict[str, float]],
    answer_metrics_list: list[dict[str, Any]],
    *,
    include_overall_score: bool = False,
) -> tuple[dict[str, Any], float | None]:
    overall_metrics = {}

    if retrieval_metrics_list:
        keys = retrieval_metrics_list[0].keys()
        for key in keys:
            overall_metrics[key] = sum(m.get(key, 0) for m in retrieval_metrics_list) / len(retrieval_metrics_list)

    if answer_metrics_list:
        scores = [m.get("score", 0) for m in answer_metrics_list]
        overall_metrics["answer_correctness"] = sum(scores) / len(scores) if scores else 0.0

    overall_score = EvaluationMetricsCalculator.calculate_overall_score(retrieval_metrics_list, answer_metrics_list)
    if include_overall_score:
        overall_metrics["overall_score"] = overall_score

    return overall_metrics, overall_score
