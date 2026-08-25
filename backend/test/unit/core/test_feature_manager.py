# Unit tests for FeatureManager
import os
from unittest.mock import patch
import pytest
from yuxi.core.feature_manager import FeatureManager

def test_feature_manager_default_false():
    FeatureManager.reset_overrides()
    # STRUCTURAL_CHUNKING mặc định BẬT theo thiết kế fork; các flag khác mặc định TẮT
    assert FeatureManager.is_enabled(FeatureManager.STRUCTURAL_CHUNKING)
    assert not FeatureManager.is_enabled(FeatureManager.EVENT_EXTRACTION)

def test_feature_manager_env_override():
    FeatureManager.reset_overrides()
    with patch.dict(os.environ, {FeatureManager.STRUCTURAL_CHUNKING: "true", FeatureManager.EVENT_EXTRACTION: "1"}):
        assert FeatureManager.is_enabled(FeatureManager.STRUCTURAL_CHUNKING)
        assert FeatureManager.is_enabled(FeatureManager.EVENT_EXTRACTION)

def test_feature_manager_env_false():
    FeatureManager.reset_overrides()
    with patch.dict(os.environ, {FeatureManager.STRUCTURAL_CHUNKING: "false", FeatureManager.EVENT_EXTRACTION: "0"}):
        # Env=false vẫn không tắt được flag mặc định bật; phải dùng override
        assert FeatureManager.is_enabled(FeatureManager.STRUCTURAL_CHUNKING)
        assert not FeatureManager.is_enabled(FeatureManager.EVENT_EXTRACTION)

def test_feature_manager_manual_override():
    FeatureManager.reset_overrides()
    FeatureManager.override(FeatureManager.STRUCTURAL_CHUNKING, True)
    assert FeatureManager.is_enabled(FeatureManager.STRUCTURAL_CHUNKING)

    FeatureManager.override(FeatureManager.STRUCTURAL_CHUNKING, False)
    assert not FeatureManager.is_enabled(FeatureManager.STRUCTURAL_CHUNKING)

    FeatureManager.reset_overrides()
    assert FeatureManager.is_enabled(FeatureManager.STRUCTURAL_CHUNKING)
