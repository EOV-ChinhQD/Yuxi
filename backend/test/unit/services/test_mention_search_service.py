from __future__ import annotations

import base64
from pathlib import Path
import pytest

import ormsgpack
import yuxi.services.mention_search_service as mention_service


class _FakeRedis:
    def __init__(self):
        self.data: dict[str, str] = {}
        self.expire_calls: dict[str, int] = {}
        self.delete_calls: list[str] = []

    async def get(self, key: str) -> str | None:
        return self.data.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.data[key] = value
        if ex is not None:
            self.expire_calls[key] = ex

    async def delete(self, key: str) -> None:
        self.delete_calls.append(key)
        self.data.pop(key, None)


@pytest.fixture
def mock_sandbox_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Create simulated workspace, upload, and output directories
    workspace_dir = tmp_path / "shared" / "user_1" / "workspace"
    uploads_dir = tmp_path / "threads" / "thread_1" / "user-data" / "uploads"
    outputs_dir = tmp_path / "threads" / "thread_1" / "user-data" / "outputs"

    workspace_dir.mkdir(parents=True, exist_ok=True)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    # Mock sandbox_paths function
    monkeypatch.setattr(mention_service, "sandbox_workspace_dir", lambda t, u: workspace_dir)
    monkeypatch.setattr(mention_service, "sandbox_uploads_dir", lambda t: uploads_dir)
    monkeypatch.setattr(mention_service, "sandbox_outputs_dir", lambda t: outputs_dir)

    return {
        "workspace": workspace_dir,
        "uploads": uploads_dir,
        "outputs": outputs_dir,
    }


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> _FakeRedis:
    redis = _FakeRedis()

    async def mock_get_redis():
        return redis

    monkeypatch.setattr(mention_service, "get_redis_client", mock_get_redis)
    return redis


@pytest.mark.asyncio
async def test_scan_pruned_files_and_exclude_dirs(mock_sandbox_paths):
    workspace = mock_sandbox_paths["workspace"]

    # Create regular file
    (workspace / "main.py").write_text("print('hello')")
    (workspace / "utils.py").write_text("def run(): pass")

    # Create excluded directories and files
    git_dir = workspace / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]")

    node_modules = workspace / "node_modules"
    node_modules.mkdir()
    (node_modules / "express.js").write_text("module.exports = {}")

    # scanning
    results = mention_service._scan_pruned_files(workspace, 100)

    # check
    files = {name for name, _ in results}
    assert "main.py" in files
    assert "utils.py" in files
    assert "config" not in files
    assert "express.js" not in files


@pytest.mark.asyncio
async def test_scan_depth_protection(mock_sandbox_paths):
    workspace = mock_sandbox_paths["workspace"]

    # Create extremely deep file tree paths: more than 15 levels
    deep_dir = workspace
    for i in range(18):
        deep_dir = deep_dir / f"dir_{i}"

    deep_dir.mkdir(parents=True, exist_ok=True)
    (deep_dir / "deep_file.py").write_text("deep")

    # scanning
    results = mention_service._scan_pruned_files(workspace, 100)
    files = {name for name, _ in results}

    # Depth limit should successfully prune and intercept the ultra-deep file
    assert "deep_file.py" not in files


@pytest.mark.asyncio
async def test_scan_width_limit(mock_sandbox_paths):
    workspace = mock_sandbox_paths["workspace"]

    # Create 600 small flat files
    for i in range(600):
        (workspace / f"file_{i}.py").write_text(str(i))

    # Scan, set max_entries = 1000 (see if the single directory width limit of 500 works)
    results = mention_service._scan_pruned_files(workspace, 1000)

    # Limit single directory MAX_ENTRIES_PER_DIR = 500 fuse
    assert len(results) == 500


@pytest.mark.asyncio
async def test_mention_cache_lifecycle_with_ormsgpack(mock_sandbox_paths, fake_redis):
    workspace = mock_sandbox_paths["workspace"]
    uploads = mock_sandbox_paths["uploads"]

    (workspace / "main.py").write_text("main")
    (uploads / "data.csv").write_text("csv")

    # 1. First query: build cache and store it in Redis
    index_1 = await mention_service.get_or_build_file_index("thread_1", "user_1")
    assert len(index_1) == 2

    # Verify that Redis has been cached separately by workspace/thread
    workspace_redis_key = f"{mention_service.WORKSPACE_CACHE_PREFIX}user_1"
    thread_redis_key = f"{mention_service.THREAD_CACHE_PREFIX}thread_1"
    cached_workspace = fake_redis.data.get(workspace_redis_key)
    cached_thread = fake_redis.data.get(thread_redis_key)
    assert cached_workspace is not None
    assert cached_thread is not None

    # Deserialization verification
    workspace_entries = ormsgpack.unpackb(base64.b64decode(cached_workspace))
    thread_entries = ormsgpack.unpackb(base64.b64decode(cached_thread))
    assert len(workspace_entries) == 1
    assert len(thread_entries) == 1

    # 2. Modify the disk file, but the Redis cache should still be used within the TTL, and the content will not be updated.
    (workspace / "new_file.py").write_text("new")
    index_2 = await mention_service.get_or_build_file_index("thread_1", "user_1")
    assert len(index_2) == 2  # Still hitting the cache and not scanning out new_file.py

    # 3. Clear the workspace cache and read it again. The disk scan content should be successfully updated.
    await mention_service.invalidate_workspace_mention_cache("user_1")
    assert fake_redis.data.get(workspace_redis_key) is None

    index_3 = await mention_service.get_or_build_file_index("thread_1", "user_1")
    assert len(index_3) == 3
    assert any(name == "new_file.py" for name, _, source in index_3 if source == "workspace")


@pytest.mark.asyncio
async def test_search_workspace_without_thread_id(mock_sandbox_paths, fake_redis):
    workspace = mock_sandbox_paths["workspace"]
    uploads = mock_sandbox_paths["uploads"]
    (workspace / "guide.md").write_text("workspace")
    (uploads / "guide.csv").write_text("thread")

    results = await mention_service.search_mention_files_in_index(None, "user_1", "guide")

    assert len(results) == 1
    assert results[0]["name"] == "guide.md"
    assert results[0]["path"] == "/home/gem/user-data/workspace/guide.md"
    assert results[0]["source"] == "workspace"


@pytest.mark.asyncio
async def test_search_thread_source_before_workspace(mock_sandbox_paths, fake_redis):
    workspace = mock_sandbox_paths["workspace"]
    uploads = mock_sandbox_paths["uploads"]
    (workspace / "report.md").write_text("workspace")
    (uploads / "report.md").write_text("thread")

    results = await mention_service.search_mention_files_in_index("thread_1", "user_1", "report")

    assert len(results) == 2
    assert results[0]["path"] == "/home/gem/user-data/uploads/report.md"
    assert results[0]["source"] == "thread"
    assert results[1]["path"] == "/home/gem/user-data/workspace/report.md"
    assert results[1]["source"] == "workspace"


@pytest.mark.asyncio
async def test_search_mention_files_in_index(mock_sandbox_paths, fake_redis):
    workspace = mock_sandbox_paths["workspace"]
    (workspace / "agent_config.json").write_text("config")
    (workspace / "main.py").write_text("main")

    # Search match test
    results = await mention_service.search_mention_files_in_index("thread_1", "user_1", "config")
    assert len(results) == 1
    assert results[0]["name"] == "agent_config.json"
    assert results[0]["path"] == "/home/gem/user-data/workspace/agent_config.json"
    assert results[0]["is_dir"] is False
    assert results[0]["source"] == "workspace"

    # Case-insensitive matching
    results_case = await mention_service.search_mention_files_in_index("thread_1", "user_1", "MAIN")
    assert len(results_case) == 1
    assert results_case[0]["name"] == "main.py"


@pytest.mark.asyncio
async def test_search_mention_directories_and_weighted_ranking(mock_sandbox_paths, fake_redis):
    workspace = mock_sandbox_paths["workspace"]

    # 1. Create qualified subdirectory "test"
    test_dir = workspace / "test"
    test_dir.mkdir(exist_ok=True)

    # 2. Create some files containing keywords in the subdirectory
    (test_dir / "test_auth.py").write_text("auth")
    (test_dir / "conftest.py").write_text("conf")  # The file name does not contain test, but the path contains test

    # 3. Search for "@test"
    results = await mention_service.search_mention_files_in_index("thread_1", "user_1", "test")

    # 4. Verification results
    # Must contain 3 items: directory "test/", file "test_auth.py", file "conftest.py" (path matching)
    assert len(results) == 3

    # 5. Verify top sorting and is_dir attribute
    # Since the directory name "test" is 100% identical to the search term "test", it has the highest score (1000 points) and must be ranked first.
    assert results[0]["name"] == "test"
    assert results[0]["is_dir"] is True
    assert results[0]["path"] == "/home/gem/user-data/workspace/test/"

    # "test_auth.py" file name starts with "test", which is a prefix match (500 points) and must be ranked 2nd
    assert results[1]["name"] == "test_auth.py"
    assert results[1]["is_dir"] is False

    # The "conftest.py" file name does not contain test, which is a pure path matching guarantee (10 points) and must be ranked last.
    assert results[2]["name"] == "conftest.py"
    assert results[2]["is_dir"] is False
