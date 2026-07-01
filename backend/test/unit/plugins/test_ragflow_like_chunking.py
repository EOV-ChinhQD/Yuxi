from __future__ import annotations

import os
import sys

sys.path.append(os.getcwd())

from yuxi.knowledge.chunking.ragflow_like.dispatcher import chunk_markdown
from yuxi.knowledge.chunking.ragflow_like.nlp import bullets_category, count_tokens
from yuxi.knowledge.chunking.ragflow_like.utils.semantic_utils import split_sentences_chinese
from yuxi.knowledge.chunking.ragflow_like.presets import (
    CHUNK_ENGINE_VERSION,
    CHUNK_PRESET_IDS,
    get_chunk_preset_options,
    get_default_chunk_parser_config,
    map_to_internal_parser_id,
    resolve_chunk_processing_params,
)
from yuxi.knowledge.utils.kb_utils import resolve_processing_params, sanitize_processing_params


def test_general_maps_to_naive() -> None:
    assert map_to_internal_parser_id("general") == "naive"


def test_resolve_chunk_processing_params_priority() -> None:
    resolved = resolve_chunk_processing_params(
        kb_additional_params={
            "chunk_preset_id": "book",
            "chunk_parser_config": {"chunk_token_num": 300, "delimiter": "\\n"},
        },
        file_processing_params={
            "chunk_preset_id": "qa",
            "chunk_parser_config": {"delimiter": "###", "overlapped_percent": 5},
        },
        request_params={
            "chunk_preset_id": "laws",
            "chunk_parser_config": {"chunk_token_num": 666},
        },
    )

    assert resolved["chunk_preset_id"] == "laws"
    assert resolved["chunk_engine_version"] == CHUNK_ENGINE_VERSION
    assert resolved["chunk_parser_config"] == {
        "chunk_token_num": 666,
        "delimiter": "###",
        "overlapped_percent": 5,
    }


def test_resolve_chunk_processing_params_returns_only_nested_keys() -> None:
    resolved = resolve_chunk_processing_params(
        kb_additional_params={"chunk_parser_config": {"chunk_token_num": 300}},
        file_processing_params={},
        request_params={},
    )

    assert resolved["chunk_parser_config"] == {"chunk_token_num": 300}
    assert resolved["chunk_preset_id"] == "general"
    assert resolved["chunk_engine_version"] == CHUNK_ENGINE_VERSION
    assert len(resolved) == 3


def test_qa_chunking_from_markdown_headings() -> None:
    content = """
# Question one
This is Answerone.

# # subquestion
This is Answertwo.
""".strip()

    chunks = chunk_markdown(
        markdown_content=content,
        file_id="file_1",
        filename="faq.md",
        processing_params={"chunk_preset_id": "qa", "chunk_parser_config": {}},
    )

    assert len(chunks) >= 1
    assert "question:" in chunks[0]["content"]
    assert "answer:" in chunks[0]["content"]


def test_chunk_records_include_reserved_position_fields() -> None:
    content = "First paragraph content.\n\nSecond paragraph content."

    chunks = chunk_markdown(
        markdown_content=content,
        file_id="file_pos",
        filename="pos.md",
        processing_params={
            "chunk_preset_id": "separator",
            "chunk_parser_config": {"delimiter": "\\n\\n"},
        },
    )

    assert chunks[0]["start_char_pos"] == 0
    assert chunks[0]["end_char_pos"] == len("First paragraph content.")
    assert chunks[0]["start_token_pos"] is None
    assert chunks[0]["end_token_pos"] is None
    assert "start_char_pos" in chunks[1]


def test_book_chunking_hierarchical_merge() -> None:
    content = """
Chapter 1 General Provisions
Section 1 Scope of application
This specification applies to test scenarios.
Section 2 Basic Principles
The principle of minimal changes should be followed.
""".strip()

    chunks = chunk_markdown(
        markdown_content=content,
        file_id="file_2",
        filename="book.txt",
        processing_params={"chunk_preset_id": "book", "chunk_parser_config": {"chunk_token_num": 256}},
    )

    assert len(chunks) >= 1
    assert any("Chapter 1" in ck["content"] for ck in chunks)


def test_book_chunking_should_apply_overlength_protection() -> None:
    content = "\n".join(
        [
            "Chapter 1 General Provisions",
            "Section 1 Scope of application",
            "Extra long text" * 1200,
            "Section 2 Basic Principles",
            "The principle of minimal changes should be followed.",
        ]
    )
    max_chunk_tokens = 180

    chunks = chunk_markdown(
        markdown_content=content,
        file_id="file_book_long",
        filename="book.txt",
        processing_params={
            "chunk_preset_id": "book",
            "chunk_parser_config": {"chunk_token_num": max_chunk_tokens, "delimiter": "\\n"},
        },
    )

    assert len(chunks) > 1
    assert max(count_tokens(ck["content"]) for ck in chunks) <= max_chunk_tokens


def test_split_sentences_chinese_should_keep_quote_boundary() -> None:
    text = '他说：“你好。”然后问：“你在吗？”最后结束！'
    sentences = split_sentences_chinese(text)

    assert sentences == ["他说：“你好。”", "然后问：“你在吗？”", "最后结束！"]


def test_markdown_heading_has_higher_weight_in_bullet_category() -> None:
    sections = [
        "# 3.2 Summary of personal income items and tax calculation and reporting methods",
        "1. Regarding the issue of pre-tax deductions for seasonal workers, temporary workers, etc., the following provisions will continue to be implemented.",
        "2. According to current regulations, subsidy income should be incorporated into wages and salaries.",
        "(1) Subsidies paid in excess of the proportion prescribed by the state are not tax-free welfare fees.",
    ]

    # This group should be selected first when hitting the markdown header pattern (BULLET_PATTERN subscript 4).
    assert bullets_category(sections) == 4


def test_mid_sentence_bullet_marker_should_not_be_treated_as_heading() -> None:
    sections = [
        "According to the aforementioned rules: 1. This is an enumeration in a sentence, not a chapter title, and cannot be regarded as a hierarchy.",
        "Continuation of the above: (2) This is also an enumeration expression in the text, not an independent title.",
        "# # 3.4 Personal tax treatment of transportation subsidies",
    ]
    assert bullets_category(sections) == 4


def test_chunk_preset_options_include_description() -> None:
    options = get_chunk_preset_options()
    assert {option["value"] for option in options} == CHUNK_PRESET_IDS
    assert all(isinstance(option.get("description"), str) and option["description"] for option in options)


def test_chunk_preset_defaults_only_include_strategy_specific_fields() -> None:
    for preset_id in CHUNK_PRESET_IDS:
        assert get_default_chunk_parser_config(preset_id) == {}


def test_laws_chunking_should_apply_overlength_protection() -> None:
    lines = ["# ### Implementation Regulations of the Enterprise Income Tax Law of the People's Republic of China", "##### Scan on WeChat: Share"]
    lines.extend(
        [f"No.{i}Article Description of the Implementation Rules of the Enterprise Income Tax Law, suitable for testing scenarios, ensuring that the length of the article is sufficient to verify the blocking strategy." for i in range(1, 260)]
    )
    content = "\n".join(lines)

    max_chunk_tokens = 180
    chunks = chunk_markdown(
        markdown_content=content,
        file_id="file_laws_long",
        filename="laws.docx",
        processing_params={
            "chunk_preset_id": "laws",
            "chunk_parser_config": {
                "chunk_token_num": max_chunk_tokens,
                "overlapped_percent": 20,
                "delimiter": "\\n",
            },
        },
    )

    assert len(chunks) > 1
    assert max(count_tokens(ck["content"]) for ck in chunks) <= max_chunk_tokens


def test_laws_chunking_should_prefer_sentence_boundary_split() -> None:
    line = "Article 1 The Implementing Rules of the Enterprise Income Tax Law are used to test the semantic boundaries of segmentation."
    content = line * 120

    chunks = chunk_markdown(
        markdown_content=content,
        file_id="file_laws_sentence",
        filename="laws.docx",
        processing_params={
            "chunk_preset_id": "laws",
            "chunk_parser_config": {
                "chunk_token_num": 120,
                "overlapped_percent": 0,
                "delimiter": "\\n",
            },
        },
    )

    assert len(chunks) > 1
    for ck in chunks:
        text = ck["content"].strip()
        assert text
        assert count_tokens(text) <= 120


def test_laws_chunking_should_prefer_article_level_before_item_level() -> None:
    content = """
No. 6 Chapter Special Tax Adjustment
No.106 strip No. 38 of the Enterprise Income Tax Law stipulates that a withholding agent may be designated under certain circumstances, including:
(one)There are direct or indirect control relationships in terms of funds, operations, purchases and sales, etc.;
(two) can represent the enterprise to implement other binding behaviors.
No.one hundred and seven strip The tax authorities can determine the taxable income in accordance with the law.
""".strip()

    chunks = chunk_markdown(
        markdown_content=content,
        file_id="file_laws_article",
        filename="laws.docx",
        processing_params={
            "chunk_preset_id": "laws",
            "chunk_parser_config": {
                "chunk_token_num": 1000,
                "overlapped_percent": 0,
                "delimiter": "\\n",
            },
        },
    )

    # As long as the items under the item are not broken into independent fragments, the goal of "item-level priority" can be met.
    target_chunks = [ck["content"] for ck in chunks if "No.106 strip" in ck["content"]]
    assert target_chunks
    assert any("(one)" in chunk and "(two)" in chunk for chunk in target_chunks)


def test_laws_markdown_articles_should_not_collapse_into_chapter_chunk() -> None:
    content = """
# # Chapter 1 General Provisions
- **Article 1** This law is formulated in order to regulate guarantee activities and ensure the realization of creditor's rights.
- **Article 2** In lending activities, parties may set up guarantees in accordance with the law.
- **Article 3** Guarantee activities should follow the principles of equality, voluntariness, fairness and good faith.
""".strip()

    chunks = chunk_markdown(
        markdown_content=content,
        file_id="file_laws_markdown_article",
        filename="laws.md",
        processing_params={
            "chunk_preset_id": "laws",
            "chunk_parser_config": {
                "chunk_token_num": 120,
                "overlapped_percent": 0,
                "delimiter": "\\n",
            },
        },
    )

    first_article_chunks = [ck["content"] for ck in chunks if "Article 1" in ck["content"]]
    assert first_article_chunks
    # When splitting at the strip level, the first and second strips should not be merged into the same block.
    assert all("Article 2" not in chunk for chunk in first_article_chunks)
    assert max(count_tokens(ck["content"]) for ck in chunks) <= 120


def test_sanitize_processing_params_should_drop_non_persistent_fields() -> None:
    sanitized = sanitize_processing_params(
        {
            "chunk_preset_id": "general",
            "chunk_parser_config": {"chunk_token_num": 300},
            "ocr_engine": "mineru_ocr",
            "ocr_engine_config": {},
            "auto_index": True,
            "content_hashes": {"a.md": "hash-a"},
            "enable_ocr": "mineru_ocr",
            "_preprocessed_map": {"a.md": {"path": "/tmp/a.md"}},
        }
    )

    assert sanitized == {
        "chunk_preset_id": "general",
        "chunk_parser_config": {"chunk_token_num": 300},
        "ocr_engine": "mineru_ocr",
        "ocr_engine_config": {},
    }


def test_resolve_processing_params_keeps_ocr_fields_and_chunk_params() -> None:
    resolved = resolve_processing_params(
        kb_additional_params={
            "chunk_preset_id": "book",
            "chunk_parser_config": {"delimiter": "\n", "chunk_token_num": 300},
        },
        file_processing_params={
            "ocr_engine": "mineru_ocr",
            "ocr_engine_config": {"backend": "pipeline"},
            "chunk_preset_id": "qa",
            "chunk_parser_config": {"overlapped_percent": 10},
            "content_hashes": {"a.md": "hash-a"},
        },
        request_params={
            "auto_index": True,
            "chunk_preset_id": "laws",
            "chunk_parser_config": {"chunk_token_num": 666},
        },
    )

    assert resolved["ocr_engine"] == "mineru_ocr"
    assert resolved["ocr_engine_config"] == {"backend": "pipeline"}
    assert resolved["chunk_preset_id"] == "laws"
    assert resolved["chunk_parser_config"] == {
        "delimiter": "\n",
        "chunk_token_num": 666,
        "overlapped_percent": 10,
    }
    assert "content_hashes" not in resolved
    assert "enable_ocr" not in resolved
    assert "auto_index" not in resolved


def test_resolve_processing_params_defaults_ocr_fields() -> None:
    resolved = resolve_processing_params(
        kb_additional_params={},
        file_processing_params={"ocr_engine_config": "invalid", "enable_ocr": "mineru_ocr"},
    )

    assert resolved["ocr_engine"] == "disable"
    assert resolved["ocr_engine_config"] == {}
    assert "enable_ocr" not in resolved
