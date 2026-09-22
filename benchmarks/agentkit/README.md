# Yuxi AgentKit tool contract

`tool-suite.json` is generated from Yuxi's registered tool registry. It keeps
the selected production tool names, descriptions, JSON Schemas, and the first
smoke tasks under version control.

The trace-first executor is `scripts/eval/agentkit_executor.py`. It currently
supports one model decision and at most one tool call per task. It validates
the selected tool and required arguments, binds an explicit handler, captures
the result or error, and records latency.

The following are intentionally deferred to the model-scoring phase:

- binding runtime-dependent Yuxi handlers with authenticated context;
- model provider selection and tool-call generation;
- multi-tool sequences and recovery retries;
- accuracy and argument scoring against the task gold labels.

Regenerate the contract with:

```bash
PYTHONPATH=backend/package uv run python scripts/eval/prepare_agentkit_tool_suite.py \
  --output benchmarks/agentkit/tool-suite.json
```
