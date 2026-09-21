from __future__ import annotations

from typing import Any

from yuxi.core.feature_manager import FeatureManager
from yuxi.knowledge.chunking.base import ChunkMetadata, ChunkResult
from yuxi.knowledge.chunking.ragflow_like.parsers import book, general, laws, qa, semantic, separator
from yuxi.knowledge.chunking.ragflow_like.presets import map_to_internal_parser_id, normalize_chunk_preset_id


def _build_chunk_records(
    chunk_results: list[ChunkResult], file_id: str, filename: str, source_text: str | None = None
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    search_from = 0

    for idx, cr in enumerate(chunk_results):
        text = (cr.content or "").strip()
        if not text:
            continue

        start_char_pos = None
        end_char_pos = None
        if source_text:
            found_at = source_text.find(text, search_from)
            if found_at >= 0:
                start_char_pos = found_at
                end_char_pos = found_at + len(text)
                search_from = end_char_pos

        records.append(
            {
                "id": f"{file_id}_chunk_{idx}",
                "content": text,
                "file_id": file_id,
                "filename": filename,
                "chunk_index": idx,
                "source": filename,
                "chunk_id": f"{file_id}_chunk_{idx}",
                "start_char_pos": start_char_pos,
                "end_char_pos": end_char_pos,
                "start_token_pos": None,
                "end_token_pos": None,
                "extraction_result": None,
                "chunk_version": "v1.0",
                "status": "pending",
                "heading_path": cr.metadata.heading_path,
                "section_type": cr.metadata.section_type or "text",
                "chunk_quality": getattr(cr.metadata, "chunk_quality", "good") or "good",
            }
        )

    return records


def _dispatch_markdown_parser(
    preset_id: str, filename: str, markdown_content: str, parser_config: dict[str, Any]
) -> list[str]:
    parser_id = map_to_internal_parser_id(preset_id)

    if parser_id == "naive":
        return general.chunk_markdown(markdown_content, parser_config)
    if parser_id == "qa":
        return qa.chunk_markdown(filename, markdown_content, parser_config)
    if parser_id == "book":
        return book.chunk_markdown(markdown_content, parser_config)
    if parser_id == "laws":
        return laws.chunk_markdown(filename, markdown_content, parser_config)
    if parser_id == "semantic":
        return semantic.chunk_markdown(markdown_content, parser_config)
    if parser_id == "separator":
        return separator.chunk_markdown(markdown_content, parser_config)

    return general.chunk_markdown(markdown_content, parser_config)


def _chunk_with_base_chunker(
    markdown_content: str, filename: str, parser_config: dict[str, Any], preset_id: str
) -> list[ChunkResult]:
    from yuxi.knowledge.chunking.naive_chunker import NaiveChunker
    from yuxi.knowledge.chunking.structural_chunker import StructuralChunker

    chunker = StructuralChunker() if preset_id == "general" else NaiveChunker()
    chunking = chunker.chunk(markdown_content, parser_config)
    chunks = chunking.chunks

    if chunking.quality == "POOR":
        from yuxi.utils import logger

        logger.warning(
            f"Structural chunking quality is POOR for file {filename}. "
            f"Metrics: {chunking.metadata}. Falling back to NaiveChunker."
        )
        fallback_chunks = NaiveChunker().chunk(markdown_content, parser_config).chunks
        for chunk in fallback_chunks:
            chunk.metadata.section_type = "fallback"
            chunk.metadata.chunk_quality = "poor_structure"
        chunks = fallback_chunks

    return chunks


def chunk_markdown(
    markdown_content: str, file_id: str, filename: str, processing_params: dict[str, Any]
) -> list[dict[str, Any]]:
    params = dict(processing_params or {})
    preset_id = normalize_chunk_preset_id(params.get("chunk_preset_id"))
    parser_config = params.get("chunk_parser_config") if isinstance(params.get("chunk_parser_config"), dict) else {}

    if preset_id == "general" and FeatureManager.is_enabled(FeatureManager.STRUCTURAL_CHUNKING):
        chunks = _chunk_with_base_chunker(markdown_content, filename, parser_config, preset_id)
        return _build_chunk_records(chunks, file_id, filename, markdown_content)

    text_chunks = _dispatch_markdown_parser(preset_id, filename, markdown_content, parser_config)
    chunk_results = [ChunkResult(content=c, metadata=ChunkMetadata()) for c in text_chunks]
    return _build_chunk_records(chunk_results, file_id, filename, markdown_content)


def chunk_file(
    file_content: str, file_id: str, filename: str, processing_params: dict[str, Any]
) -> list[dict[str, Any]]:
    return chunk_markdown(file_content, file_id, filename, processing_params)
