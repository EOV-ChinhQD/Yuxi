# Handoff: phiên đo 2026-09-22/23 — E2E, NLI, Agent trên NVIDIA

Ngày: 2026-09-23 (UTC). Branch: `phase2-viquad-benchmark`. Commits đã push:
`bc2cb62d` (runners) → `11f9b019` (thesis) → `87fa2af8` (artifacts + results).

## ĐÃ XONG (có artifact, đã push)

| Thí nghiệm | Kết quả (kèm 95% CI) | Artifact trong `benchmarks/results/` |
|---|---|---|
| E2E standard RAG, UIT-ViQuAD2 sample 150 | EM 45.33% [37.58, 53.32], F1 66.94%, abstention P 79.49% / R 62.00%, hit@1 77.33% | `uit-viquad-2_e2e_150.json` |
| E2E extractive baseline, cùng 150 mẫu | EM 0.67%, F1 17.57% | cùng file trên |
| VN Function Calling 100 mẫu, DeepSeek V4.1 Flash | tool 98% [93.00, 99.45], EM 93% [86.25, 96.57] | `vietnamese_function_calling_nvidia_deepseek_100.json` |
| When2Call stratified 60 (20/class) | accuracy **66.67%** [54.06, 77.27]; cannot 60%, request 55%, tool_call 90% | `when2call_nvidia_deepseek_stratified60.json` |
| VieQuAD BM25 full 2048 | R@10 91.80%, MRR@10 0.7010 | `viequad_bm25_validation.json` (giữ nguyên) |
| Contract validation | 2899 + 3652 records hợp lệ, 0 lỗi | `agent_contract_validation.json` (giữ nguyên) |

Đính chính: số When2Call 68.3% báo miệng giữa phiên là file trung gian; file cuối
trên disk là 66.67% — thesis và bảng trên dùng số cuối.

Thesis đã điền số thật: `docs/thesis/template_thesis.md` (§4.2, §4.3, §4.6, §4.8,
§4.10, §4.11, §4.12, §4.13, §5.1–5.2, Phụ lục A/B/C). NLI full đã được chạy lại trên GPU.

## CHƯA XONG

1. **VN-FC failure review 7/100**, **E2E retrieval-vs-generation decomposition** —
   có đủ per-sample data, chưa viết phân tích.
3. **OCR, dense/hybrid/consensus arms, weight search, BFCL, production retrieval,
   reranker, agentic E2E arms** — `Blocked`/`Deferred` có lý do trong thesis
   (kẹt embedding key; raw OCR trống; cần KB populated).

## Chạy tiếp trên máy GPU

```bash
git pull origin phase2-viquad-benchmark
# raw/ không push — tải lại theo revision trong benchmarks/source-lock.json,
# artifact chuẩn hóa đã push sẵn trong benchmarks/artifacts/ nên có thể bỏ qua prep.
# NLI full trên GPU (đã chạy, dùng lệnh sau để tái lập):
docker exec api-dev python /app/project-scripts/eval/run_nli_viwikifc.py \
  --input /app/benchmarks/artifacts/nli/viwikifc/test.jsonl \
  --output /app/benchmarks/results/viwikifc_nli_dual_2091.json
# Đã cập nhật thesis; các mục còn lại vẫn là OCR, dense/hybrid và production retrieval.
```

## Lưu ý quota & hạ tầng

- Model duy nhất dùng được với key hiện tại: `nvidia:deepseek-ai/deepseek-v4.1-flash`
  (reasoning model — bắt buộc `max_tokens>=1024` agent / `4096` E2E, xem Phụ lục B).
  sea-lion, mistral-7b/nemo, gemma, granite đều 404 entitlement.
- Tổng ~372 calls phiên này, 0 lần 429. Mọi run mới log vào
  `benchmarks/results/usage_log.jsonl` và tôn trọng `--max-calls`.
- NVIDIA đã bỏ credit, chỉ còn trial rate-limit — không query balance bằng API được.
- `.env` (chứa key) không push — tự cấu hình lại trên máy GPU.
- `uit-viquad-2` mirror không công bố license: local-only, không redistribute.
