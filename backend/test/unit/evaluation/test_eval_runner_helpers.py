import sys
from pathlib import Path


EVAL_SCRIPTS = Path("/app/project-scripts/eval")
if EVAL_SCRIPTS.exists():
    sys.path.insert(0, str(EVAL_SCRIPTS))

from run_agentkit_local_smoke import (  # noqa: E402
    _arguments_equivalent,
    _prediction_needs_retry,
)
from run_e2e_viquad2 import hit_at_k, select_evidence  # noqa: E402
from run_when2call_local import _parse_relevance_gate  # noqa: E402


def test_hit_at_k_accepts_json_string_keys_and_integer_test_keys():
    assert hit_at_k({"1": True}, 1)
    assert hit_at_k({5: True}, 5)
    assert not hit_at_k({"1": False}, 1)


def test_select_evidence_keeps_ranked_documents_with_query_overlap():
    corpus = {"a": "lịch sử nước Việt", "b": "ẩm thực miền Trung", "c": "lịch sử Hà Nội"}
    assert select_evidence(["a", "b", "c"], corpus, "lịch sử Hà Nội", 2) == ["a", "c"]


def test_agent_argument_normalization_is_limited_to_punctuation_and_approved_qualifiers():
    assert _arguments_equivalent("tôi có lịch khác.", "tôi có lịch khác")
    assert _arguments_equivalent("Tiếng Anh giao tiếp", "Tiếng Anh")
    assert not _arguments_equivalent("Tiếng Anh nâng cao", "Tiếng Anh")


def test_agent_retries_parse_error_and_missing_explicit_time():
    tool = {
        "name": "reschedule_tutoring_session",
        "parameters": {
            "properties": {"new_date": {}, "new_time": {}},
            "required": ["new_date", "new_time"],
        },
    }
    assert _prediction_needs_retry({"decision": "parse_error"}, "", [tool])
    assert _prediction_needs_retry(
        {"decision": "tool_call", "tool_name": tool["name"], "arguments": {"new_date": "thứ Hai"}},
        "dời sang thứ Hai lúc 10 giờ sáng",
        [tool],
    )


def test_relevance_gate_rejects_unknown_tool_names_and_handles_invalid_json():
    assert _parse_relevance_gate('{"relevant_tool_names":["search", "unknown"]}', {"search"}) == ["search"]
    assert _parse_relevance_gate("not-json", {"search"}) is None
