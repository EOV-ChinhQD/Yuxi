import re
from typing import Any
from yuxi.knowledge.chunking.base import BaseChunker, ChunkResult, ChunkMetadata
from yuxi.knowledge.chunking.ragflow_like.nlp import count_tokens


class DocumentNode:
    def __init__(self, text: str, level: int, node_type: str, metadata: dict = None):
        self.text = text
        self.level = level
        self.node_type = node_type  # 'heading', 'text', 'image', 'table', 'root', 'code', 'equation'
        self.metadata = metadata or {}
        self.children: list[DocumentNode] = []
        self.token_count = 0

    def add_child(self, node: "DocumentNode"):
        self.children.append(node)


class StructuralChunker(BaseChunker):
    """
    Style-based Depth-First Search Chunker.
    Respects document structure (Headings) and semantically groups content.
    Strictly follows token limits and binds context.
    """

    def __init__(self, target_chunk_size=1024):
        self.target_size = target_chunk_size

    def chunk(self, markdown: str, config: dict[str, Any] | None = None) -> list[ChunkResult]:
        config = config or {}
        target_size = int(config.get("chunk_token_num", self.target_size) or self.target_size)
        self.target_size = target_size

        # 1. Parse markdown to blocks
        blocks = self._parse_markdown_to_blocks(markdown)
        if not blocks:
            return []

        # 2. Build Tree (Heading Hierarchy)
        root = self._build_tree(blocks)

        # 3. Traverse and Chunk
        chunks: list[ChunkResult] = []
        accum: list[DocumentNode] = []
        context_stack: list[str] = []

        self._dfs_traverse(root, context_stack, accum, chunks)

        # Final flush
        if accum:
            self._finalize_chunk(accum, chunks, context_stack)

        return chunks

    def _parse_markdown_to_blocks(self, markdown: str) -> list[dict]:
        lines = (markdown or "").splitlines()
        blocks = []

        in_code_block = False
        code_block_lines = []

        in_table = False
        table_lines = []

        for line in lines:
            stripped = line.strip()

            # Check code block
            if stripped.startswith("```"):
                if in_code_block:
                    in_code_block = False
                    blocks.append({"type": "code", "text": "\n".join(code_block_lines)})
                    code_block_lines = []
                else:
                    in_code_block = True
                    if in_table:
                        blocks.append({"type": "table", "text": "\n".join(table_lines)})
                        in_table = False
                        table_lines = []
                continue

            if in_code_block:
                code_block_lines.append(line)
                continue

            # Check heading
            if stripped.startswith("#"):
                if in_table:
                    blocks.append({"type": "table", "text": "\n".join(table_lines)})
                    in_table = False
                    table_lines = []
                level = len(stripped) - len(stripped.lstrip("#"))
                heading_text = stripped.lstrip("#").strip()
                blocks.append({"type": "heading", "text": heading_text, "level": level})
                continue

            # Check table
            if stripped.startswith("|") or (in_table and stripped.startswith("|")):
                if not in_table:
                    in_table = True
                table_lines.append(line)
                continue
            elif in_table:
                blocks.append({"type": "table", "text": "\n".join(table_lines)})
                in_table = False
                table_lines = []

            # Other text block
            if stripped:
                blocks.append({"type": "paragraph", "text": stripped})

        # Flush remaining
        if in_code_block and code_block_lines:
            blocks.append({"type": "code", "text": "\n".join(code_block_lines)})
        if in_table and table_lines:
            blocks.append({"type": "table", "text": "\n".join(table_lines)})

        # Post-process latex
        latex_pattern = re.compile(r"(\$\$[\s\S]*?\$\$)|(\\\([\s\S]*?\\\))")
        # Let's search for $$ or $ in paragraph blocks
        for block in blocks:
            if block.get("type") == "paragraph":
                text = block.get("text", "")
                if "$$" in text or "$" in text:
                    block["type"] = "equation"

        return blocks

    def _build_tree(self, blocks: list[dict]) -> DocumentNode:
        root = DocumentNode("ROOT", 0, "root")
        stack = [root]

        for block in blocks:
            b_type = block.get("type", "paragraph")
            b_text = block.get("text", "") or ""

            # Map specific types to generic categories
            if b_type == "paragraph":
                b_type = "text"

            metadata = block.copy()
            metadata.pop("text", None)

            if b_type == "heading":
                level = block.get("level", 1)
                node = DocumentNode(b_text, level, "heading", metadata)
                node.token_count = count_tokens(b_text)

                # Pop stack until we find a parent with level < node.level
                while len(stack) > 1 and stack[-1].level >= level:
                    stack.pop()

                parent = stack[-1]
                parent.add_child(node)
                stack.append(node)
            else:
                node = DocumentNode(b_text, 999, b_type, metadata)
                if b_type == "image":
                    caption_text = str(metadata.get("image_caption") or "")
                    node.token_count = count_tokens(b_text + caption_text) + 100
                elif b_type == "table":
                    node.token_count = count_tokens(b_text) + 50
                elif b_type == "equation":
                    node.token_count = count_tokens(b_text) + 20
                else:
                    node.token_count = count_tokens(b_text)

                stack[-1].add_child(node)

        return root

    def _dfs_traverse(
        self, node: DocumentNode, context_stack: list[str], accum: list[DocumentNode], chunks: list[ChunkResult]
    ):
        if node.node_type == "heading":
            if accum:
                self._finalize_chunk(accum, chunks, context_stack)
                accum.clear()
            context_stack.append(node.text)

        for child in node.children:
            if child.node_type == "heading":
                self._dfs_traverse(child, context_stack, accum, chunks)
            else:
                self._add_content_to_chunk(child, accum, chunks, context_stack)

        if node.node_type == "heading":
            if accum:
                self._finalize_chunk(accum, chunks, context_stack)
                accum.clear()
            context_stack.pop()

    def _add_content_to_chunk(
        self, node: DocumentNode, accum: list[DocumentNode], chunks: list[ChunkResult], context_stack: list[str]
    ):
        current_tokens = sum(n.token_count for n in accum)

        if current_tokens + node.token_count > self.target_size:
            lead_in_node = None
            if node.node_type in ["image", "table"] and accum:
                last = accum[-1]
                if last.node_type == "text" and last.token_count < 60:
                    lead_in_node = accum.pop()

            self._finalize_chunk(accum, chunks, context_stack)
            accum.clear()

            if lead_in_node:
                accum.append(lead_in_node)
            accum.append(node)
        else:
            accum.append(node)

    def _finalize_chunk(self, accum: list[DocumentNode], chunks: list[ChunkResult], context_stack: list[str]):
        if not accum:
            return

        content_parts = []
        dominant_type = "text"
        type_counts = {}

        for node in accum:
            type_counts[node.node_type] = type_counts.get(node.node_type, 0) + 1

            if node.node_type == "text":
                content_parts.append(node.text)
            elif node.node_type == "image":
                path = node.metadata.get("img_path", "")
                caption = node.metadata.get("image_caption", "") or ""
                if isinstance(caption, list):
                    caption = " ".join(caption)
                content_parts.append(f"\n[IMAGE_REF: {path}]\nDescription: {caption}")
            elif node.node_type == "table":
                caption = node.metadata.get("table_caption", "") or ""
                if isinstance(caption, list):
                    caption = " ".join(caption)
                content_parts.append(f"\n[TABLE_DATA]\n{node.text}\nCaption: {caption}")
            elif node.node_type == "equation":
                content_parts.append(f"\n[EQUATION]\n{node.text}\n")
            else:
                content_parts.append(node.text)

        if type_counts:
            dominant_type = max(type_counts, key=type_counts.get)

        full_content = "\n\n".join(content_parts).strip()
        if not full_content:
            return

        clean_context = [c for c in context_stack if c != "ROOT"]

        meta = ChunkMetadata(heading_path=clean_context, section_type=dominant_type, depth=len(clean_context))

        tokens = count_tokens(full_content)
        chunks.append(ChunkResult(content=full_content, metadata=meta, token_count=tokens))
