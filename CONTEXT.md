# CONTEXT.md — Project Shared Language (Yuxi Integration)

One term per row. Agents and humans use these words verbatim in code, tests, and docs.

| Term | Means | Does NOT mean |
|---|---|---|
| ProjectWorkdir | Specialized linked-only directory bound per conversation thread with symlink guard | Temporary sandbox directory |
| AgentRunRequest | Per-thread FIFO queue request ensuring transaction safety before ARQ dispatch | Simple background async job |
| ConsensusRetriever | Unified multi-source retriever combining Milvus dense vectors + Vietnamese BM25 | Pure single-vector similarity search |
| NLIVerifier | Natural language inference module validating factual grounding against citations | Standard LLM reranking |
| ShareConfig | RBAC v2 resource permission mechanism for sharing KB/Agent/Skill across users/depts | Raw API secret management |
