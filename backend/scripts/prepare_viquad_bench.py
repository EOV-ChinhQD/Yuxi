#!/usr/bin/env python3
"""Prepare ViQuAD benchmark artifacts from the gated HF cache mirror.

Reads the arrow cache (cols: answer, prompt), parses the prompt wrapper into
(question, context), and emits:
  corpus/<passage_id>.txt   — 9959 unique contexts, stable first-seen order
  qrels.jsonl               — 33084 lines: query, gold_passage_id, gold_answer
  eval_sample300.jsonl      — stratified 300-line subset (answerable ratio kept)
  quarantine.jsonl          — rows that failed parsing (must stay empty)

Run on HOST (needs datasets/pyarrow, absent from the api image):
  python3 backend/scripts/prepare_viquad_bench.py
Outputs go to /mnt/new-volume/yuxi-eval/bench/ (never on /).
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import sys
from pathlib import Path

ARROW = Path(
    "/mnt/new-volume/yuxi-eval/hf_cache/NghiemAbe___viquad/default/0.0.0"
    "/b41b219c687cb851aa6967f793da68ab4789ae0d/viquad-train.arrow"
)
OUT = Path("/mnt/new-volume/yuxi-eval/bench")
SEED = 42
SAMPLE_N = 300

PROMPT_RE = re.compile(
    r'câu hỏi "(?P<q>.*?)" nằm trong ngữ cảnh sau đây\.\s*Ngữ cảnh: "(?P<ctx>.*)"\.\s*Những câu văn phù hợp là:\s*$',
    re.DOTALL,
)


def parse_row(answer: str, prompt: str) -> tuple[str, str, str] | None:
    m = PROMPT_RE.search(prompt)
    if not m:
        return None
    q, ctx = m.group("q").strip(), m.group("ctx").strip()
    if not q or not ctx:
        return None
    return q, ctx, (answer or "").strip()


def main() -> int:
    import datasets  # host-only dep; api image lacks it by design

    ds = datasets.Dataset.from_file(str(ARROW))
    print(f"rows={len(ds)} cols={ds.column_names}", flush=True)

    (OUT / "corpus").mkdir(parents=True, exist_ok=True)
    passage_of: dict[str, str] = {}  # ctx_hash -> passage_id
    qrels: list[dict] = []
    quarantine: list[dict] = []

    for i, row in enumerate(ds):
        parsed = parse_row(row["answer"], row["prompt"])
        if parsed is None:
            quarantine.append({"idx": i, "answer": row["answer"][:200], "prompt": row["prompt"][:500]})
            continue
        q, ctx, ans = parsed
        h = hashlib.sha256(ctx.encode("utf-8")).hexdigest()[:16]
        if h not in passage_of:
            pid = f"p{len(passage_of) + 1:05d}"
            passage_of[h] = pid
            (OUT / "corpus" / f"{pid}.txt").write_text(ctx, encoding="utf-8")
        qrels.append({
            "query": q,
            "gold_passage_id": passage_of[h],
            "gold_answer": ans,
            "answerable": bool(ans),
        })

    with open(OUT / "qrels.jsonl", "w", encoding="utf-8") as f:
        for r in qrels:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(OUT / "quarantine.jsonl", "w", encoding="utf-8") as f:
        for r in quarantine:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Stratified sample: keep answerable ratio, spread across passages.
    rng = random.Random(SEED)
    pos = [r for r in qrels if r["answerable"]]
    neg = [r for r in qrels if not r["answerable"]]
    n_pos = round(SAMPLE_N * len(pos) / len(qrels))
    by_pass: dict[str, list[dict]] = {}
    for r in qrels:
        by_pass.setdefault(r["gold_passage_id"], []).append(r)

    def spread(pool: list[dict], n: int) -> list[dict]:
        groups = [g for g in by_pass.values() if any(x in pool for x in g)]
        rng.shuffle(groups)
        out, seen = [], set()
        for g in groups:
            cands = [x for x in g if x in pool and id(x) not in seen]
            if cands:
                pick = rng.choice(cands)
                out.append(pick)
                seen.add(id(pick))
            if len(out) == n:
                break
        return out

    sample = spread(pos, n_pos) + spread(neg, SAMPLE_N - n_pos)
    rng.shuffle(sample)
    with open(OUT / "eval_sample300.jsonl", "w", encoding="utf-8") as f:
        for r in sample:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    ans_in_ctx = sum(1 for r in qrels if r["answerable"] and r["gold_answer"] in
                     (OUT / "corpus" / f"{r['gold_passage_id']}.txt").read_text(encoding="utf-8"))
    print(f"passages={len(passage_of)} qrels={len(qrels)} quarantine={len(quarantine)}", flush=True)
    print(f"answerable={len(pos)} unanswerable={len(neg)} sample={len(sample)} ans_in_ctx={ans_in_ctx}", flush=True)

    assert len(qrels) + len(quarantine) == len(ds), "row accounting broken"
    assert len(quarantine) == 0, f"{len(quarantine)} unparseable rows — inspect quarantine.jsonl"
    assert len(passage_of) == 9959, f"passage drift: {len(passage_of)}"
    assert len(sample) == SAMPLE_N, f"sample drift: {len(sample)}"
    print("T2a OK", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
