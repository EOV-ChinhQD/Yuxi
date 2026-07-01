---
name: deep-research
description: "In-depth research orchestration methodology: clarifying scope, dismantling planning, parallel scheduling sub-agent investigation, adversarial verification, and synthesis into a structured report with references. Use this skill when the task requires in-depth research with multiple sources, traceability, and fact-checking."
---

# Deep research skills

When the task goal is to produce in-depth research conclusions with multiple sources, traceability, and verification (scientific research review, industry/competitive product research, technology selection, thematic analysis, etc.), use this skill to organize the entire research process. The core of this skill is **Orchestration**: You are responsible for the overall control and sub-agent scheduling, dispatch the heavy retrieval and verification work, and focus on planning and synthesis yourself.

## Available subagents

Scheduling through the `task` tool (multiple tasks can be started in parallel, and subtasks that are independent of each other are dispatched at the same time):

- `research-explorer` (research explorer): performs multiple rounds of web/knowledge base searches around a clear sub-question and returns structured findings organized by key points and cited with `<cite>`. **This is the main force, and can be opened in parallel according to sub-issues. **
- `fact-verifier` (fact checker): conduct adversarial verification of given key assertions, provide support / doubt / refutation + source + confidence level one by one, and mark conflicts.

## Orchestration process

### 1. Clarify the scope
When the question is unclear, first use `ask_user_question` to supplement 2-3 key questions (research objectives, audience, scope boundaries, region/timeliness, output language and format), and then start work after aligning the acceptance criteria. Do not ask repeated questions about tasks that are already clear.

### 2. Planning for dismantling
Use `write_todos` to split the research goal into sub-questions that can be independently investigated. Each sub-question states the output standard (what to answer, what type of evidence is required). Sub-problems should be orthogonal and fully covered to avoid overlapping or missing key angles.

### 3. Parallel distribution survey
- Use multiple `task` calls to dispatch independent sub-problems to `research-explorer` in parallel.
- Write clearly in `description` for each dispatch: sub-problem goal, known context, expected output format (key points + `<cite source="$URL" type="url">$INDEX</cite>` citation + reference source list).
- When to dispatch vs. Direct checking by yourself: Sub-agents are always dispatched when the sub-problem is complex, requires multiple rounds of retrieval, can isolate context, and can be parallelized; only when clarifying the scope, filling in one or two scattered facts, or quickly correcting the direction, do a small amount of direct retrieval by yourself.
- When there are dependencies between sub-problems, the preceding sub-problems are dispatched first, and the follow-up sub-problems are dispatched after the results are obtained.

### 4. Verify key conclusions
Dispatch `fact-verifier` for adversarial verification of key assertions, numbers, and conflicts between sub-agents that affect the final conclusion. Ask them to default to "mark doubtful if there is insufficient evidence." Conclusions that fail to pass the verification should not be written into the text, or must be clearly marked for downgrade.

### 5. Comprehensive draft
After the evidence is sufficient, it is up to you to synthesize it into a structured report. **Do not** simply splice the original text returned by the sub-agent. Organizational sequence: problem definition → evidence collection → analysis and comparison → conclusions and recommendations → sources. Focusing on "argument" rather than "data accumulation", every conclusion must be supported by evidence.

### 6. Stopping Criteria
Stop when the information is saturated or it is confirmed that no more valid information can be obtained. Clearly mark evidence gaps and uncertainties, and do not make assumptions or fabricate sources.

## Reference specification

- Key conclusions, data, and opinions in the report must be bound to sources.
- Follow the `<cite source="$URL" type="url">$INDEX</cite>` annotation, $INDEX increases from 1, and the quotation follows the conclusion and is not on a separate line.
- List the "Source" chapter separately at the end of the article, and list the title and URL one by one; indicate the file name or path when citing user attachments/knowledge bases.

## Output constraints

- The final delivery is a report that can be directly used, rather than "how do I plan to study it".
- Do not leak the intermediate reasoning process and original search logs, and do not output the to-do list as it is.
- The language of the report is consistent with the language of the user's questions, and uses formal, restrained, and reviewable written expressions.
