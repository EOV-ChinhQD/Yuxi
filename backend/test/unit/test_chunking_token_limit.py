"""Testpoint block token upper limit protection: general parser hard cuts points of over-long chunks.

nlp.py / general.py Only relies on re and the standard library, use sys.modules to bypass yuxi Bagof
Heavy dependency chain (langchain / pydantic / .env Configuration, etc.) to achieve pure unit testing.
Clean up sys.modules after running to avoid polluting other tests.
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

_PKG = Path(__file__).resolve().parents[2] / "package"

_STUB_NAMES = [
    "yuxi",
    "yuxi.knowledge",
    "yuxi.knowledge.chunking",
    "yuxi.knowledge.chunking.ragflow_like",
    "yuxi.knowledge.chunking.ragflow_like.parsers",
    "yuxi.knowledge.chunking.ragflow_like.nlp",
    "yuxi.knowledge.chunking.ragflow_like.parsers.general",
]

# Injected at runtime by the _isolated_modules fixture
nlp = None  # type: ignore[assignment]
general = None  # type: ignore[assignment]


@pytest.fixture(autouse=True, scope="module")
def _isolated_modules():
    """Loading nlp at the module level/general, clean up sys after running.modules Avoid contaminating other tests."""
    saved = {name: sys.modules.get(name) for name in _STUB_NAMES}

    for name in _STUB_NAMES[:5]:
        sys.modules.setdefault(name, types.ModuleType(name))

    def _load(name: str, rel: str):
        spec = importlib.util.spec_from_file_location(name, _PKG / rel)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod

    _nlp = _load(
        "yuxi.knowledge.chunking.ragflow_like.nlp",
        "yuxi/knowledge/chunking/ragflow_like/nlp.py",
    )
    sys.modules["yuxi.knowledge.chunking.ragflow_like"].nlp = _nlp  # type: ignore[attr-defined]

    _general = _load(
        "yuxi.knowledge.chunking.ragflow_like.parsers.general",
        "yuxi/knowledge/chunking/ragflow_like/parsers/general.py",
    )

    # Inject module-level variables for test case access
    global nlp, general  # noqa: PLW0603
    nlp = _nlp
    general = _general

    yield

    # Cleanup: restore original state
    for name in _STUB_NAMES:
        if saved[name] is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = saved[name]


# ── nlp.hard_split_by_token_limit ──────────────────────────────────


class TestHardSplitByTokenLimit:
    def test_short_text_unchanged(self):
        text = "This is a short text"
        result = nlp.hard_split_by_token_limit(text, 512)
        assert result == [text]

    def test_splits_long_chinese_text(self):
        text = ("Test content " * 1000).strip()  # ~2000 tokens
        result = nlp.hard_split_by_token_limit(text, 512)
        assert len(result) > 1
        for chunk in result:
            assert nlp.count_tokens(chunk) <= 512

    def test_optional_hard_limit_keeps_slightly_oversized_text(self):
        text = ("content " * 600).strip()  # ~600 tokens
        result = nlp.hard_split_by_token_limit(text, 512, hard_limit_token_num=768)
        assert result == [text]

    def test_optional_hard_limit_merges_short_tail(self):
        text = ("content " * 1270).strip()  # ~1270 tokens -> 512 + 758
        result = nlp.hard_split_by_token_limit(text, 512, hard_limit_token_num=768)
        assert len(result) == 2
        assert [nlp.count_tokens(chunk) for chunk in result] == [512, 758]

    def test_splits_long_english_text(self):
        text = ("hello world " * 1000).strip()  # ~2000 word tokens
        result = nlp.hard_split_by_token_limit(text, 512)
        assert len(result) > 1
        for chunk in result:
            assert nlp.count_tokens(chunk) <= 512

    def test_empty_text_returns_empty(self):
        assert nlp.hard_split_by_token_limit("", 512) == []

    def test_whitespace_only_returns_empty(self):
        assert nlp.hard_split_by_token_limit("   \n\t  ", 512) == []

    def test_zero_limit_floors_to_one(self):
        text = "a b c"  # 3 independent tokens (words)
        result = nlp.hard_split_by_token_limit(text, 0)
        # max_tokens = max(0, 1) = 1, each token is a separate chunk
        assert len(result) == 3

    def test_punctuation_only_text(self):
        text = "，。！？"
        result = nlp.hard_split_by_token_limit(text, 512)
        assert result == ["，。！？"]


# ── general._ensure_chunk_token_limit ──────────────────────────────


class TestEnsureChunkTokenLimit:
    def test_all_chunks_within_limit_pass_through(self):
        chunks = ["Short text one", "Short text two", "Short text three"]
        result = general._ensure_chunk_token_limit(chunks, 512)
        assert result == ["Short text one", "Short text two", "Short text three"]

    def test_slightly_oversized_chunk_passes_through(self):
        long_text = ("content " * 600).strip()  # ~600 tokens
        chunks = ["short text", long_text, "Short text two"]
        result = general._ensure_chunk_token_limit(chunks, 512)
        assert result == ["short text", long_text, "Short text two"]

    def test_oversized_chunk_gets_split_with_merged_tail(self):
        long_text = ("content " * 1270).strip()  # ~1270 tokens -> 512 + 758
        chunks = ["short text", long_text, "Short text two"]
        result = general._ensure_chunk_token_limit(chunks, 512)
        assert result[0] == "short text"
        assert result[-1] == "Short text two"
        middle_chunks = result[1:-1]
        assert len(middle_chunks) == 2
        assert [nlp.count_tokens(chunk) for chunk in middle_chunks] == [512, 758]

    def test_empty_chunks_filtered(self):
        chunks = ["valid text", "", "   ", "another paragraph"]
        result = general._ensure_chunk_token_limit(chunks, 512)
        assert result == ["valid text", "another paragraph"]

    def test_zero_limit_returns_stripped(self):
        chunks = ["  Text one  ", "Text 2"]
        result = general._ensure_chunk_token_limit(chunks, 0)
        assert result == ["Text one", "Text 2"]


# ── general.chunk_markdown integration ──────────────────────────────────


class TestGeneralChunkMarkdown:
    def test_normal_document_chunks_within_limit(self):
        doc = "# Title\n\nFirst paragraph content\n\nSecond paragraph content\n\nThird paragraph content"
        chunks = general.chunk_markdown(doc, {"chunk_token_num": 512})
        assert len(chunks) > 0
        for chunk in chunks:
            assert nlp.count_tokens(chunk) <= 512

    def test_oversized_single_line_gets_split(self):
        long_line = ("Operation and maintenance knowledge " * 800).strip()  # ~3200 tokens
        doc = f"# Operation and maintenance knowledge base\n\n{long_line}"
        chunks = general.chunk_markdown(doc, {"chunk_token_num": 512})
        assert len(chunks) > 1
        for chunk in chunks:
            assert nlp.count_tokens(chunk) <= 768

    def test_empty_document_returns_empty(self):
        assert general.chunk_markdown("", {"chunk_token_num": 512}) == []

    def test_default_config_uses_512(self):
        doc = "test\n" * 200
        chunks = general.chunk_markdown(doc)
        for chunk in chunks:
            assert nlp.count_tokens(chunk) <= 512


# ── laws parser return ──────────────────────────────────────────


class TestLawsParserRegression:
    """Verify nlp.hard_split_by_token_limit Can be called normally by laws parser."""

    def test_hard_split_produces_same_result(self):
        text = ("Regulatory content " * 1000).strip()
        result = nlp.hard_split_by_token_limit(text, 512)
        assert len(result) > 1
        for chunk in result:
            assert nlp.count_tokens(chunk) <= 512
