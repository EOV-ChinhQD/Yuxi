---
name: knowledge-base
slug: knowledge-base
description: "Use the Yuxi knowledge base to search, open documents, locate within documents, and view mind maps. Use this skill when users need to answer questions, verify information, or quote document content based on the configured knowledge base."
---

#Knowledge base skills

Use this skill when users require answers to questions based on content related to the project knowledge base, internal data, uploaded documents, or knowledge graphs.

## Available tools

- `list_kbs`: Lists the enabled knowledge bases accessible to the current session.
- `query_kb`: Retrieve content in the specified knowledge base by `kb_id`, returning `file_id` and related fragments.
- `query_keywords`: Search for exact keywords (error codes, abbreviations, document IDs) in the knowledge base using BM25.
- `open_kb_document`: Press `kb_id` and `file_id` to open the original document window, suitable for viewing more complete context.
- `find_kb_document`: Use keywords or regular expressions to locate paragraphs in known documents.
- `get_mindmap`: View the knowledge base mind map structure.
- `search_file`: Search files in the knowledge base based on file name keywords, support specified knowledge bases or cross-knowledge bases, and return file lists and paging information.

## Operation process

1. You need to first confirm which knowledge bases are available for the current session; call `list_kbs` when you are not sure.
2. Select the most relevant knowledge base for user questions and use `query_kb` to search.
3. If retrieving the fragment is not enough to answer, call `open_kb_document` with the returned `file_id` to see the context.
4. If the user requires locating a term, index, chapter or original text evidence, use `find_kb_document` to search within the candidate document.
5. Use `get_mindmap` when the user cares about the knowledge base structure, document classification or knowledge framework.

## Key constraints

- Only knowledge bases allowed by the current session configuration and user permissions can be accessed.
- Don't make up `kb_id` or `file_id`; get them from the results returned by `list_kbs` and `query_kb` instead.
- When the answer needs to be traceable, it should indicate which knowledge base, file or retrieval fragment the basis comes from.
- External read-only knowledge bases such as Dify may only support retrieval, and may not necessarily support opening full text or searching within documents; when encountering restrictions returned by tools, users should be truthfully informed.
