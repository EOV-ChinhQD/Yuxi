import asyncio
import time
import os
from pathlib import Path
from typing import Any
import pandas as pd

from yuxi.knowledge.parser.factory import DocumentProcessorFactory
from yuxi.knowledge.parser.unified import _get_docling_converter

# Tạm thời giả lập hàm tính metrics
def calculate_cer_wer(reference_text: str, predicted_text: str) -> dict[str, float]:
    """Calculate Character Error Rate (CER) and Word Error Rate (WER)"""
    # Placeholder: Cần thư viện như JiWER để tính chính xác
    return {"CER": 0.0, "WER": 0.0}

def evaluate_layout(markdown_output: str) -> dict[str, float]:
    """Evaluate Table and Heading detection in Markdown"""
    heading_count = markdown_output.count("\n#")
    table_count = markdown_output.count("\n|") // 3  # Ước lượng thô
    return {"heading_count": heading_count, "table_count": table_count}

def evaluate_structure(markdown_output: str) -> dict[str, Any]:
    """Evaluate structural tree from markdown"""
    from yuxi.knowledge.chunking.structural_chunker import StructuralChunker
    chunker = StructuralChunker(target_chunk_size=1024)
    # Tạm thời gọi hàm nội bộ để build tree và lấy metadata
    blocks = chunker._parse_markdown_to_blocks(markdown_output)
    if not blocks:
         return {"tree_depth": 0, "orphan_text_ratio": 1.0}
    
    root = chunker._build_tree(blocks)
    
    # Tính depth (độ sâu) lớn nhất và tỷ lệ text mồ côi (orphan)
    max_depth = 0
    orphan_tokens = 0
    total_tokens = 0
    
    def traverse(node, depth):
        nonlocal max_depth, orphan_tokens, total_tokens
        if depth > max_depth:
            max_depth = depth
            
        total_tokens += getattr(node, "token_count", 0)
        
        # Nếu là text và nằm ở depth <= 1 (ngay dưới ROOT) thì có thể coi là orphan
        if node.node_type == "text" and depth <= 1:
            orphan_tokens += getattr(node, "token_count", 0)
            
        for child in node.children:
            traverse(child, depth + 1)
            
    traverse(root, 0)
    orphan_ratio = (orphan_tokens / max(total_tokens, 1))
    
    return {
        "tree_depth": max_depth,
        "orphan_text_ratio": orphan_ratio
    }

async def run_engine(engine_name: str, file_path: str) -> tuple[str, float]:
    start_time = time.time()
    try:
        if engine_name == "docling":
            converter = _get_docling_converter()
            result = converter.convert(file_path)
            if result.status.name != "SUCCESS":
                 raise RuntimeError(f"Docling failed: {result.status}")
            output = result.document.export_to_markdown()
        else:
            output = DocumentProcessorFactory.process_file(engine_name, file_path, params={})
            
        latency = time.time() - start_time
        return output, latency
    except Exception as e:
        print(f"Error running {engine_name} on {file_path}: {e}")
        return "", time.time() - start_time

async def main():
    test_docs_dir = Path("test_docs") # Thư mục chứa file PDF benchmark
    if not test_docs_dir.exists():
        test_docs_dir.mkdir()
        print(f"Created {test_docs_dir}. Please place sample PDFs there and run again.")
        return

    pdf_files = list(test_docs_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDFs found in {test_docs_dir}.")
        return

    engines = ["docling", "pp_structure_v3_ocr", "paddleocr_vl_1_6"]
    results = []

    for pdf_file in pdf_files:
        print(f"Processing {pdf_file.name}...")
        for engine in engines:
            print(f"  Running {engine}...")
            markdown_output, latency = await run_engine(engine, str(pdf_file))
            
            if not markdown_output:
                continue
                
            # Đánh giá các metrics
            layout_metrics = evaluate_layout(markdown_output)
            structure_metrics = evaluate_structure(markdown_output)
            
            results.append({
                "document": pdf_file.name,
                "engine": engine,
                "latency": latency,
                "heading_count": layout_metrics["heading_count"],
                "table_count": layout_metrics["table_count"],
                "tree_depth": structure_metrics["tree_depth"],
                "orphan_text_ratio": structure_metrics["orphan_text_ratio"]
            })

    if results:
        df = pd.DataFrame(results)
        print("\n--- Benchmark Results ---")
        print(df.to_string())
        df.to_csv("benchmark_results.csv", index=False)
        print("Saved to benchmark_results.csv")

if __name__ == "__main__":
    asyncio.run(main())
