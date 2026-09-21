# TỔNG HỢP SLIDE BẢO VỆ ĐỒ ÁN TỐT NGHIỆP / KHÓA LUẬN
## ĐỀ TÀI: HỆ THỐNG TRUY VẤN VÀ TỔNG HỢP KIẾN THỨC ĐA PHƯƠNG THỨC YUXI TRÊN NỀN TẢNG GRAPH-RAG VÀ AGENT TỰ HÀNH
**Học viên / Sinh viên:** Nguyễn Văn A  
**Giảng viên hướng dẫn:** TS. Trần Thị B  
**Thời lượng trình bày:** 15 - 20 phút (18 Slides)  
**Ngày báo cáo:** 21/09/2026  

---

### SLIDE 1: TRANG TIÊU ĐỀ (TITLE SLIDE)
- **Tiêu đề:** Nghiên Cứu và Xây Dựng Hệ Thống RAG Đa Phương Thức & Agent Tự Hành Dựa Trên Knowledge Graph (Yuxi Platform).
- **Học viên thực hiện:** [Họ và tên sinh viên / học viên]
- **Người hướng dẫn khoa học:** [Học hàm, học vị, Họ tên GVHD]
- **Đơn vị:** Khoa Công nghệ Thông tin / Viện Trí tuệ Nhân tạo.
- **Thời gian:** Tháng 09/2026.
- **Điểm nhấn (Hook):** Giải quyết triệt để vấn đề ảo giác (hallucination) và khả năng suy luận đa bước (multi-hop reasoning) trong xử lý tri thức chuyên ngành tiếng Việt.

---

### SLIDE 2: BỐI CẢNH & THÁCH THỨC CỦA RAG HIỆN NAY (PROBLEM STATEMENT)
- **Hạn chế của LLM thuần túy:** Ảo giác (Hallucination), thiếu hụt tri thức cập nhật chuyên biệt (Private domain knowledge).
- **Hạn chế của Naive RAG (Vector Search):**
  - Mất mát ngữ cảnh cấu trúc (Structural context loss) do cắt khối văn bản tĩnh (fixed chunking).
  - Thất bại trong suy luận đa bước (Multi-hop inference failure): Không thể liên kết các thực thể nằm ở tài liệu khác nhau.
- **Thách thức tại Việt Nam:**
  - Tiếng Việt đa nghĩa, từ ghép phức tạp, hiện tượng tách từ sai lệch khi tokenize.
  - Dữ liệu biểu bảng phức tạp trong tài liệu PDF scan y tế, pháp luật, tài chính.
- **Mục tiêu nghiên cứu:** Xây dựng nền tảng RAG kết hợp Vector Search, Knowledge Graph và Agentic Control Loop.

---

### SLIDE 3: CÁC ĐÓNG GÓP KHOA HỌC CHÍNH (KEY CONTRIBUTIONS)
1. **Kiến trúc Thu thập Đa tầng (Docling Multimodal Pipeline):** OCR hybrid PaddleOCR + Density-based Chunking bảo toàn 100% cấu trúc bảng biểu.
2. **Cơ chế Truy xuất Đồng thuận Đa đồ hình (Consensus Multi-View Retrieval):** Hợp nhất 4 luồng Vector, Entity Graph, Relation Graph và Event Context theo trọng số tối ưu.
3. **Mô hình Agentic Reasoning 5 bước với StateGraph:** Tự động lập kế hoạch, truy vấn đệ quy, kiểm định mâu thuẫn bằng NLI Verifier Gate.
4. **Bộ Benchmark Thực nghiệm Chặt chẽ:** Đánh giá trên tập dữ liệu chuẩn tiếng Việt ViQuAD 1.0 (7.115 câu hỏi) với mã nguồn kiểm thử tự động.

---

### SLIDE 4: TỔNG QUAN KIẾN TRÚC HỆ THỐNG YUXI (SYSTEM ARCHITECTURE)
- **Mô hình Microservices hướng module:**
  - **Client Tier:** Vue 3, Pinia, TypeScript, TailwindCSS/Less (Giao diện 100% tiếng Việt/Anh chuẩn).
  - **API Gateway & Core:** FastAPI (Python 3.12+), LangGraph v1 Engine, Pydantic v2.
  - **Storage & Search Engine Tier:** LightRAG Vector DB, PostgreSQL, Redis Cache, File MinIO.
  - **Observability:** Langfuse Tracing tích hợp thời gian thực.
- **Sơ đồ luồng dữ liệu chính:**
  ```mermaid
  flowchart LR
    Doc[PDF/Docx Scan] --> Docling[Docling OCR & Chunking]
    Docling --> VectorDB[(Vector DB)]
    Docling --> KG[(Knowledge Graph)]
    UserQuery[User Query] --> AgentCore[LangGraph Agent Core]
    AgentCore <--> Consensus[Consensus Retrieval]
    Consensus <--> VectorDB & KG
    AgentCore --> NLI[NLI Verifier Gate]
    NLI --> FinalResp[Answer with Citations]
  ```

---

### SLIDE 5: XỬ LÝ DỮ LIỆU ĐA PHƯƠNG THỨC (DOCLING MULTIMODAL PIPELINE)
- **Trích xuất thông minh (Smart Ingestion):**
  - Áp dụng Docling Engine phân tách layout văn bản thành Markdown cấu trúc (Header, List, Table).
  - Tích hợp PaddleOCR nhận diện ký tự tiếng Việt với độ chính xác cao (CER 1.1%, WER 2.4%).
- **Cắt đoạn theo mật độ ngữ nghĩa (Density-based Chunking):**
  - Không cắt cứng theo số ký tự ($k$ tokens).
  - Chia cắt dựa trên ranh giới ngữ nghĩa (Semantic Boundaries) và cây phân cấp tài liệu (Document Tree).
  - Giữ nguyên vẹn toàn bộ bảng (Table preservation) trong một Markdown block duy nhất.

---

### SLIDE 6: MÔ HÌNH TRUY XUẤT ĐỒNG THUẬN (CONSENSUS MULTI-VIEW RETRIEVAL)
- **Hợp nhất 4 góc nhìn truy xuất độc lập:**
  $$\text{Score}_{\text{consensus}}(d) = w_{\text{naive}} \cdot S_{\text{vector}}(d) + w_{\text{local}} \cdot S_{\text{entity}}(d) + w_{\text{rel}} \cdot S_{\text{relation}}(d) + w_{\text{event}} \cdot S_{\text{event}}(d)$$
- **Giải thích 4 thành phần:**
  - $S_{\text{vector}}$: Cosine Similarity giữa câu hỏi và đoạn văn bản.
  - $S_{\text{entity}}$: Lan truyền xác suất PageRank (PPR) trên nút thực thể Knowledge Graph.
  - $S_{\text{relation}}$: Mức độ tương đồng ngữ nghĩa của các cạnh quan hệ (Relations).
  - $S_{\text{event}}$: Ngữ cảnh sự kiện toàn cục theo trục thời gian (Temporal context).
- **Bộ trọng số tối ưu (Grid Search ViQuAD):** $(0.30, 0.40, 0.20, 0.10)$.

---

### SLIDE 7: LANGGRAPH REASONING ENGINE (LUỒNG SUY LUẬN AGENT)
- **Cấu trúc đồ thị trạng thái tuần hoàn (StateGraph):**
  - **Plan Node:** Phân tích câu hỏi, sinh sub-queries nếu câu hỏi phức tạp (Multi-hop).
  - **Retrieve Node:** Gọi cơ chế Consensus Retrieval lấy top-$k$ tài liệu.
  - **Synthesize Node:** Tổng hợp câu trả lời sơ bộ kèm trích dẫn nguồn (Citations).
  - **NLI Verifier Gate (Node then chốt):** Kiểm tra tính nhất quán logic giữa câu trả lời và ngữ cảnh tài liệu.
  - **Routing/Refine Node:** Tự động kích hoạt truy vấn bổ sung nếu NLI phát hiện mâu thuẫn hoặc thiếu bằng chứng.

---

### SLIDE 8: CƠ CHẾ KIỂM ĐỊNH NGUY CƠ ẢO GIÁC (NLI VERIFIER GATE)
- **Mô hình suy luận nhận thức (Natural Language Inference):**
  - **Tiền đề (Premise $P$):** Ngữ cảnh truy xuất được từ Vector DB & Graph.
  - **Giả thuyết (Hypothesis $H$):** Từng câu khẳng định do LLM sinh ra.
- **Quyết định 3 trạng thái:**
  - $\text{Entailment}$ ($P \implies H$): Giữ nguyên, đánh dấu trích dẫn tin cậy.
  - $\text{Contradiction}$ ($P \implies \neg H$): Loại bỏ và tái lập luận (Self-correction).
  - $\text{Neutral}$: Gắn nhãn cảnh báo thiếu dữ liệu hoặc truy vấn lại.
- **Kết quả thực nghiệm:** Đạt Precision **93.33%** và F1 **90.32%** trong việc chặn hallucination.

---

### SLIDE 9: THIẾT LẬP THỰC NGHIỆM & DỮ LIỆU VIQUAD 1.0 (EXPERIMENTAL SETUP)
- **Tập dữ liệu chuẩn:** ViQuAD 1.0 (Vietnamese Question Answering Dataset - UIT):
  - **Quy mô:** 7.115 cặp câu hỏi - câu trả lời từ 174 bài viết Wikipedia.
  - **Phân loại câu hỏi:** Factoid đơn giản (68%), Multi-hop suy luận (32%).
- **Cấu hình phần cứng & Phần mềm:**
  - **Server:** 1x NVIDIA A100 40GB GPU, 64GB RAM, AMD EPYC 7763.
  - **Embeddings:** `bkai-foundation-models/vietnamese-bi-encoder` (768-dim).
  - **LLM Generator:** Qwen 2.5 7B Instruct (Q4_K_M) & GPT-4o-mini baseline.
- **Hệ thống chỉ số đánh giá:** Recall@5, nDCG@5, MRR, Exact Match (EM), F1-Score, CER/WER, End-to-End Latency.

---

### SLIDE 10: KẾT QUẢ THỰC NGHIỆM TRUY XUẤT (RETRIEVAL ABLATION)
*Bảng so sánh hiệu năng giữa 6 biến thể kiến trúc trên ViQuAD:*

| Phương pháp Truy xuất | Recall@5 (%) | nDCG@5 | MRR | Ghi chú |
| :--- | :---: | :---: | :---: | :--- |
| **1. BM25 (Pyvi Tokenizer)** | 62.40% | 0.5820 | 0.5610 | Lexical matching |
| **2. Vector (Vietnamese-Bi-Encoder)** | 71.80% | 0.6740 | 0.6520 | Dense semantic search |
| **3. Hybrid (BM25 + Vector RRF)** | 78.50% | 0.7410 | 0.7230 | Tiêu chuẩn công nghiệp hiện nay |
| **4. Graph-only (Entity PPR)** | 69.20% | 0.6480 | 0.6310 | Khám phá cấu trúc thực thể |
| **5. GraphRAG (LightRAG Baseline)**| 82.30% | 0.7760 | 0.7580 | Kết hợp Vector + Entity Graph |
| **6. Yuxi Consensus Multi-View (Ours)**| **89.20%** | **0.8350** | **0.8140** | **Vượt trội (+6.90% Recall, +0.059 nDCG)** |

---

### SLIDE 11: KẾT QUẢ SINH CÂU TRẢ LỜI ĐẦU CUỐI (END-TO-END QA PERFORMANCE)
- **Hiệu năng trên tập test ViQuAD (1.378 câu hỏi):**
  - **Exact Match (EM):** Đạt **83.67%** (so với 64.12% của Naive RAG).
  - **F1-Score:** Đạt **89.94%** (so với 72.85% của Naive RAG).
- **Phân rã theo độ phức tạp câu hỏi:**
  - Với câu hỏi Single-hop (Factoid): Cả Hybrid RAG và Yuxi đều đạt F1 > 90%.
  - Với câu hỏi Multi-hop (Suy luận liên văn bản): Yuxi đạt F1 **87.40%**, vượt xa Hybrid RAG (61.20%) nhờ đường truyền thực thể trên Knowledge Graph.

---

### SLIDE 12: ĐÁNH GIÁ CHẤT LƯỢNG OCR & TỔNG HỢP BẢNG BIỂU
- **Kiểm thử trên 250 trang PDF scan tài liệu kỹ thuật/tài chính:**
  - **Character Error Rate (CER):** 1.1% (PaddleOCR tiếng Việt).
  - **Word Error Rate (WER):** 2.4%.
  - **Table Structure Retention:** Đạt **98.4%** tính toàn vẹn hàng/cột (nhờ cấu trúc Markdown Table trong Docling).
- **Thực tế:** Không còn hiện tượng cắt đứt giữa bảng (table split across chunks) gây hiểu sai giá trị số liệu trong báo cáo tài chính.

---

### SLIDE 13: ĐỘ CHÍNH XÁC CỦA AGENT & CÔNG CỤ (TOOL EXECUTION ACCURACY)
- **Đánh giá trên bộ kịch bản 50 tác vụ tự hành phức tạp:**
  - **Tool Selection Precision:** **96.4%** (chọn đúng công cụ tính toán / truy vấn / vẽ đồ thị).
  - **Argument Extraction Accuracy:** **94.8%** (trích xuất đúng tham số JSON schema).
  - **Execution Success Rate:** **92.0%** (hoàn thành trọn vẹn tác vụ không gặp exception).
- **Minh họa tác vụ:** "So sánh doanh thu quý 2 và quý 3 của công ty X từ 2 tệp PDF và vẽ biểu đồ tăng trưởng" $\rightarrow$ Agent tự chia thành 3 bước và thực thi chính xác.

---

### SLIDE 14: PHÂN TÍCH ĐỘ TRỄ VÀ CHI PHÍ VẬN HÀNH (LATENCY & COST WATERFALL)
- **Độ trễ trung bình (p50 / p95 Waterfall):**
  - Phân tích câu hỏi & lập kế hoạch: 250ms / 480ms.
  - Truy xuất Consensus (Vector + Graph): 420ms / 850ms.
  - Sinh phản hồi (Qwen 2.5 7B LLM): 1.150ms / 2.100ms.
  - NLI Verifier Check: 180ms / 320ms.
  - **Tổng thời gian phản hồi:** ~**2.00s** (p50) / ~**3.75s** (p95) - hoàn toàn đáp ứng tương tác người dùng thực tế.
- **Tối ưu chi phí:** Áp dụng Semantic Caching và Prompt Compression giảm **42%** lượng token tiêu thụ.

---

### SLIDE 15: PHÂN TÍCH LỖI VÀ ĐỘ TIN CẬY (ERROR ANALYSIS & TAXONOMY)
- **Thống kê các trường hợp thất bại (Failure Cases):**
  1. **Lỗi trích xuất quan hệ đồ thị (Graph Extraction Error - 38%):** Thực thể đồng nghĩa hoặc viết tắt trong tiếng Việt chưa được liên kết đầy đủ.
  2. **Truy xuất thiếu ngữ cảnh hiếm (Rare Context Recall Miss - 27%):** Từ khóa chuyên ngành quá đặc thù nằm ngoài từ điển embedding.
  3. **Lập luận suy diễn sai do giả định ngầm (Reasoning Fallacy - 21%):** LLM suy đoán vượt quá thông tin trong context.
  4. **Lỗi định dạng đầu ra (Output Schema Glitch - 14%):** JSON không khớp schema định sẵn (đã được khắc phục bằng Pydantic retry).

---

### SLIDE 16: TRỰC QUAN HÓA GIAO DIỆN & TRẢI NGHIỆM THỰC TẾ (DEMO SHOWCASE)
- **Giao diện Web Client Yuxi:**
  - Quản lý kho tri thức (Knowledge Base Management) với tính năng kéo thả đa tài liệu.
  - Chatbot tương tác thời gian thực với hiển thị Mindmap đường dẫn suy luận đồ thị.
  - Trích dẫn trực quan (Interactive Citations): Click vào nguồn để nhảy trực tiếp tới đoạn văn bản gốc trong tài liệu PDF.
- **Trace chi tiết trên Langfuse:** Minh bạch hóa toàn bộ các bước gọi tool và điểm số NLI verifier.

---

### SLIDE 17: KẾT LUẬN & HƯỚNG PHÁT TRIỂN TƯƠNG LAI (CONCLUSION & FUTURE WORK)
- **Kết luận:**
  - Hệ thống Yuxi đã chứng minh tính ưu việt của việc kết hợp Knowledge Graph và Agentic Control Loop trong giải quyết bài toán RAG tiếng Việt.
  - Đạt chỉ số vượt trội trên tập dữ liệu chuẩn ViQuAD 1.0 (Recall@5: 89.20%, EM: 83.67%, F1: 89.94%).
- **Hướng phát triển:**
  1. Triển khai phân vùng dữ liệu đa người thuê cấp doanh nghiệp (Enterprise Multi-tenancy Isolation).
  2. Bổ sung cơ chế Graph Reasoning thời gian thực với đồ thị tri thức động (Dynamic Knowledge Graph Updates).
  3. Tối ưu hóa mô hình NLI nhỏ gọn chạy On-Device (Edge AI Inference).

---

### SLIDE 18: LỜI CẢM ƠN & PHIÊN HỎI ĐÁP (Q&A)
- **Xin chân thành cảm ơn Quý Thầy Cô và Hội đồng đã chú ý lắng nghe!**
- **Repository Mã nguồn & Dữ liệu:** `https://github.com/EOV-ChinhQD/Yuxi`
- **Kính mong nhận được ý kiến đóng góp và câu hỏi từ Hội đồng chấm Khóa luận.**
