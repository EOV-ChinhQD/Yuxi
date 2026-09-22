# Weighted Hybrid và Retrieval Ablation

## Mục tiêu

Tối ưu weighted hybrid một cách có kiểm soát, sau đó chạy đủ các nhánh retrieval còn thiếu bằng cùng một corpus, qrels, top-k và quy trình đo.

## Kế hoạch

- [ ] Chuẩn hóa runner full retrieval: nạp embedding một lần, dùng production search path, lưu config, latency, failures và ranking artifact.
- [ ] Tách VieQuAD validation thành tuning cố định 512 query và holdout 1.536 query; không dùng holdout để chọn weight.
- [ ] Chạy coarse grid weighted hybrid với `vector_weight` từ `0.0` đến `1.0`, bước `0.1`, `bm25_weight = 1 - vector_weight`; chọn theo thứ tự `nDCG@10`, `MRR@10`, `Recall@10`.
- [ ] Chạy fine grid quanh winner với bước `0.05`, đánh giá winner duy nhất trên holdout; so sánh với BM25, keyword, vector và RRF.
- [ ] Chạy full RRF (`k=60`) trên toàn bộ 2.048 query; không dùng RRF score để chọn weighted winner.
- [ ] Chạy query-rewrite smoke 20 query bằng model đã cấu hình; nếu provider lỗi hoặc rate-limit thì ghi blocked artifact, không suy diễn điểm.
- [ ] Kiểm tra model reranker và graph readiness của benchmark KB; chỉ chạy reranker/consensus khi có model và graph index thực sự sẵn sàng.
- [ ] Chạy RAG E2E smoke 20 mẫu sau khi chốt retrieval; nếu ổn, chạy full 300 mẫu với EM, F1, answerability và refusal metrics.
- [ ] Review artifact, `git diff --check`, compile/lint phạm vi thay đổi và Docker health; cập nhật báo cáo/changelog.

## Artifact dự kiến

- `benchmarks/results/viequad_weight_grid_tuning.json`
- `benchmarks/results/viequad_weight_grid_holdout.json`
- `benchmarks/results/viequad_yuxi_full_nvidia_rrf.json`
- `benchmarks/results/viequad_query_rewrite_smoke.json`
- `benchmarks/results/viequad_reranker_smoke.json`
- `benchmarks/results/viequad_rag_e2e_smoke.json`
- `benchmarks/results/viequad_rag_e2e_full.json`

## Điều kiện hoàn thành

- Weight được chọn trên tuning và được xác nhận độc lập trên holdout.
- Có bảng so sánh tất cả nhánh đã chạy; nhánh chưa chạy có lý do và artifact trạng thái.
- Không gọi `0.3/0.7` là tối ưu nếu fine grid không xác nhận điều đó.
- RAG chỉ được đánh dấu hoàn thành khi có kết quả generation full và metric artifact reproducible.
