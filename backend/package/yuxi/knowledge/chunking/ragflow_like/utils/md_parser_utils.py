from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from .semantic_utils import semantic_chunking_with_auto_clusters


def infer_heading_level(title: str) -> int:
    """
    Infer the hierarchical level of the title text (1-6 levels).

    Logical description:
    1. Number sequence inference:
       - Matches like "1.", "1.1", "1.2.3" etc. format.
       - Determine the level based on the number of dots separated, for example "1.1" is level 2,"1.2.3" is level 3.
       - Tier limited to between 1-6.
    2. Chinese serial number inference:
       - Matches like "one,", "two." Wait for the Chinese numeral serial number.
       - Unified one is classified as a level 1 title.
    3. Default processing:
       - If the above rules are not matched, level 1 will be returned by default.
    """
    m = re.match(r"^\s*(\d+(?:\.\d+)*)[.)、]?\s*", title)
    if m:
        return max(1, min(len(m.group(1).split(".")), 6))
    m_zh = re.match(r"^\s*[One, two, three, four, five, six, seven, eight, nine, one hundred thousand]+[、.]\s*", title)
    if m_zh:
        return 1
    return 1


def get_title_path(stack: list[str]) -> str:
    """
    Generate the title path based on the title stack, use"|"Separate.
    """
    return "|".join([t for t in stack if t])


def extract_table_block(tokens: list[Any], i: int, original_lines: list[str]) -> tuple[int, str]:
    """
    Extract complete chunks ofsheet from token stream and raw text.

    Logical description:
    1. Positioning start: through the current token (i) of `map` Property gets the starting row number of the table in the original row `table_start`。
    2. Find end token: traverse subsequent tokens until found `table_close`。
    3. Determine the ending line number (`table_end`)：
       - priority use `table_close` token of `map` property.
       - If it does not exist, try to find the next one with `map` The starting row of the message token serves as the end of the current table.
       - If the above fails (like the end of the document or parseabnormal), then fall back to heuristic scanning based on the text content:
         From `table_start` start scanning down until you encounter a row that does not match Markdown table characteristics (not starting with '|' and does not contain '|').
    4. Return result: return `table_close` Index of `j` And the concatenated original string of the table.
    """
    token = tokens[i]
    table_start = token.map[0] if token.map else 0
    j = i + 1
    while j < len(tokens) and tokens[j].type != "table_close":
        j += 1
    if j < len(tokens):
        end_token = tokens[j]
        if end_token.map and end_token.map[1] is not None:
            table_end = end_token.map[1]
        else:
            table_end = None
            for k in range(j + 1, len(tokens)):
                if tokens[k].map and tokens[k].map[0] is not None:
                    table_end = tokens[k].map[0]
                    break
            if table_end is None:
                table_end = table_start + 1
                for line_idx in range(table_start, len(original_lines)):
                    line = original_lines[line_idx].strip()
                    if not line or not (line.startswith("|") or "|" in line):
                        table_end = line_idx
                        break
    else:
        table_end = table_start + 1
        for line_idx in range(table_start, len(original_lines)):
            line = original_lines[line_idx].strip()
            if not line or not (line.startswith("|") or "|" in line):
                table_end = line_idx
                break
    return j, "\n".join(original_lines[table_start:table_end])


def split_text_by_length_and_newline(
    text: str, max_length: int, embed_fn: Callable[[list[str]], Any] | None, token_count_fn: Callable[[str], int]
) -> list[str]:
    """
    Hierarchical text segmentation strategy.
    """
    chunks = []

    paragraphs = text.split("\n\n")

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        paragraph_token_count = token_count_fn(paragraph)

        # If the length of the current paragraph does not exceed the maximum number of Tokens, it will be directly put into chunks as independent chunks.
        # Otherwise continue trying to split by row
        if paragraph_token_count <= max_length:
            chunks.append(paragraph)
            continue

        # Split the paragraph into lines using line breaks
        lines = paragraph.split("\n")
        current_chunk_lines = []
        current_chunk_tokens = 0

        for line in lines:
            line = line.strip()
            if not line:  # Skip empty lines
                continue

            line_token_count = token_count_fn(line)  # Calculate the number of Tokens in the current row
            # In order to take into account the spaces between lines, you need to add 1 when calculating the number of Tokens (if the current line is not the first line, you need to add the number of Tokens with a newline character)
            added_tokens = line_token_count + (1 if current_chunk_lines else 0)
            # If the number of Tokens in the current row exceeds the maximum number of Tokens, it will be directly put into chunks as independent chunks.
            if line_token_count > max_length:
                if current_chunk_lines:
                    chunks.append("\n".join(current_chunk_lines))
                    current_chunk_lines = []
                    current_chunk_tokens = 0

                sub_chunks = semantic_chunking_with_auto_clusters(
                    line, embed_fn=embed_fn, token_count_fn=token_count_fn, max_chunk_size=max_length
                )
                chunks.extend(sub_chunks)
            # If the number of Tokens in the current row and the number of Tokens in the current chunk exceed the maximum number of Tokens, they will be directly placed into chunks as independent chunks.
            elif current_chunk_tokens + added_tokens > max_length:
                # Put the previous chunked content into chunks
                chunks.append("\n".join(current_chunk_lines))
                # Resets the current section to the contents of the current row
                current_chunk_lines = [line]
                # Update the number of Tokens in the current block
                current_chunk_tokens = line_token_count
            # If the content of the current row will not exceed the maximum number of Tokens after being added to the current block, add it directly to the current block.
            else:
                current_chunk_lines.append(line)
                current_chunk_tokens += added_tokens  # Update the number of Tokens in the current block
        # The final finishing touch is to put the last line of content into chunks
        if current_chunk_lines:
            chunks.append("\n".join(current_chunk_lines))

    return chunks
