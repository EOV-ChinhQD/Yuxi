import pytest
from yuxi.knowledge.chunking.naive_chunker import NaiveChunker
from yuxi.knowledge.chunking.structural_chunker import StructuralChunker

def test_naive_chunker_basic():
    chunker = NaiveChunker()
    markdown = "Dòng 1\n\nDòng 2\n\nDòng 3"
    results = chunker.chunk(markdown, {"chunk_token_num": 512})
    assert len(results) > 0
    for r in results:
        assert r.content is not None
        assert r.token_count > 0
        assert r.metadata.heading_path == []

def test_structural_chunker_heading_tree():
    chunker = StructuralChunker(target_chunk_size=100)
    markdown = """# Chương 1
Nội dung chương 1.
## Mục 1.1
Mô tả chi tiết của mục 1.1.
# Chương 2
Nội dung chương 2.
"""
    results = chunker.chunk(markdown)
    assert len(results) >= 2
    
    # Check that headings are parsed into metadata
    heading_paths = [r.metadata.heading_path for r in results]
    assert ["Chương 1"] in heading_paths or ["Chương 1", "Mục 1.1"] in heading_paths
    assert ["Chương 2"] in heading_paths

def test_structural_chunker_table_and_code():
    chunker = StructuralChunker(target_chunk_size=500)
    markdown = """# Chương Bảng
Đây là đoạn văn bản.

| Cột A | Cột B |
|---|---|
| Giá trị 1 | Giá trị 2 |

```python
def hello():
    print("world")
```
"""
    results = chunker.chunk(markdown)
    assert len(results) > 0
    # Code block and table should be preserved in content
    content_joined = "\n\n".join([r.content for r in results])
    assert "| Cột A | Cột B |" in content_joined
    assert "def hello():" in content_joined
