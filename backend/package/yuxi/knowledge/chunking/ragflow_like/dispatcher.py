from __future__ import annotations

from typing import Any

from yuxi.knowledge.chunking.ragflow_like.parsers import book, general, laws, qa, semantic, separator
from yuxi.knowledge.chunking.ragflow_like.presets import map_to_internal_parser_id, normalize_chunk_preset_id


def _build_chunk_records(
    text_chunks: list[str], file_id: str, filename: str, source_text: str | None = None
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    search_from = 0

    for idx, chunk_content in enumerate(text_chunks):
        text = (chunk_content or "").strip()
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


from yuxi.core.feature_manager import FeatureManager
from yuxi.knowledge.chunking.base import ChunkResult


def _build_chunk_records_from_results(
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
                "section_type": cr.metadata.section_type,
            }
        )

    return records


def _build_chunk_records(
    text_chunks: list[str], file_id: str, filename: str, source_text: str | None = None
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    search_from = 0

    for idx, chunk_content in enumerate(text_chunks):
        text = (chunk_content or "").strip()
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
                "heading_path": [],
                "section_type": "text",
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


def chunk_markdown(
    markdown_content: str, file_id: str, filename: str, processing_params: dict[str, Any]
) -> list[dict[str, Any]]:
    params = dict(processing_params or {})
    preset_id = normalize_chunk_preset_id(params.get("chunk_preset_id"))
    parser_config = params.get("chunk_parser_config") if isinstance(params.get("chunk_parser_config"), dict) else {}

    # Nếu tính năng STRUCTURAL_CHUNKING được bật
    if FeatureManager.is_enabled(FeatureManager.STRUCTURAL_CHUNKING):
        if preset_id == "general":
            from yuxi.knowledge.chunking.structural_chunker import StructuralChunker

            chunker = StructuralChunker()
        else:
            from yuxi.knowledge.chunking.naive_chunker import NaiveChunker

            chunker = NaiveChunker()

        chunk_results = chunker.chunk(markdown_content, parser_config)
        return _build_chunk_records_from_results(chunk_results, file_id, filename, markdown_content)

    text_chunks = _dispatch_markdown_parser(preset_id, filename, markdown_content, parser_config)
    return _build_chunk_records(text_chunks, file_id, filename, markdown_content)


def chunk_file(
    file_content: str, file_id: str, filename: str, processing_params: dict[str, Any]
) -> list[dict[str, Any]]:

    return chunk_markdown(file_content, file_id, filename, processing_params)
