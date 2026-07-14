import pytest
from yuxi.core.feature_manager import FeatureManager
from yuxi.knowledge.chunking.ragflow_like.dispatcher import chunk_markdown

def test_dispatcher_with_naive_by_default():
    FeatureManager.reset_overrides()
    # FeatureManager disabled by default
    markdown = "# Chương 1\nNội dung 1\n## Mục 1.1\nNội dung 1.1"
    records = chunk_markdown(markdown, "file_123", "test.md", {"chunk_preset_id": "general"})
    assert len(records) > 0
    # Naive chunker output records should not have heading_path populated (or empty list)
    for r in records:
        assert r["heading_path"] == []
        assert r["chunk_version"] == "v1.0"
        assert r["status"] == "pending"

def test_dispatcher_with_structural_enabled():
    FeatureManager.reset_overrides()
    FeatureManager.override(FeatureManager.STRUCTURAL_CHUNKING, True)
    
    markdown = "# Chương 1\nNội dung 1\n## Mục 1.1\nNội dung 1.1"
    records = chunk_markdown(markdown, "file_123", "test.md", {"chunk_preset_id": "general"})
    assert len(records) > 0
    # Structural chunker records should populate heading_path
    heading_paths = [r["heading_path"] for r in records]
    assert any(h == ["Chương 1"] for h in heading_paths) or any(h == ["Chương 1", "Mục 1.1"] for h in heading_paths)
    for r in records:
        assert r["chunk_version"] == "v1.0"
        assert r["status"] == "pending"
    
    FeatureManager.reset_overrides()
