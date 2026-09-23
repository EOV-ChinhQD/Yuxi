TRƯỜNG [TÊN TRƯỜNG]

KHOA/VIỆN [TÊN KHOA HOẶC VIỆN]

---

[HỌ VÀ TÊN SINH VIÊN]

NGHIÊN CỨU, THIẾT KẾ VÀ PHÁT TRIỂN NỀN TẢNG HỎI–ĐÁP THÔNG MINH VÀ HỆ TÁC TỬ TRI THỨC ĐA PHƯƠNG THỨC TRÊN NGỮ LIỆU TIẾNG VIỆT

YUXI AGENTIC MULTIMODAL RAG PLATFORM

ĐỒ ÁN TỐT NGHIỆP/KHÓA LUẬN TỐT NGHIỆP  

Ngành: [TÊN NGÀNH]  

Mã ngành: [MÃ NGÀNH]

Giảng viên hướng dẫn: [HỌ VÀ TÊN]  

Sinh viên thực hiện: [HỌ VÀ TÊN]  

Mã số sinh viên: [MSSV]  

Lớp: [LỚP]

[ĐỊA ĐIỂM], [NĂM]

---

&gt; **Ghi chú biên tập — xóa trước khi nộp:** Đây là bản thảo theo cấu trúc luận văn chuẩn. Mọi nội dung trong ngoặc vuông `[CẦN BỔ SUNG]` phải được hoàn thiện. Không chuyển trạng thái `Missing`, `Blocked` hoặc `Estimated` thành kết quả chính thức nếu chưa có artifact thực nghiệm tương ứng.

LỜI CAM ĐOAN

Tôi cam đoan đồ án này là kết quả nghiên cứu và triển khai của cá nhân tôi dưới sự hướng dẫn của [HỌ VÀ TÊN GIẢNG VIÊN]. Các nội dung tham khảo đều được trích dẫn và ghi nguồn đầy đủ. Các số liệu, kết quả thực nghiệm và kết luận trình bày trong đồ án là trung thực, có thể truy nguyên về cấu hình, mã nguồn và artifact thực nghiệm tương ứng. Tôi hoàn toàn chịu trách nhiệm về nội dung của đồ án.

[ĐỊA ĐIỂM], ngày ... tháng ... năm ...  

Sinh viên thực hiện  

[KÝ VÀ GHI RÕ HỌ TÊN]

LỜI CẢM ƠN

[Viết từ 150–250 từ, cảm ơn giảng viên hướng dẫn, khoa/viện, đơn vị hỗ trợ và các cá nhân liên quan. Tránh dùng lời lẽ quảng bá hoặc đánh giá chủ quan về chất lượng đồ án.]

TÓM TẮT

Các mô hình ngôn ngữ lớn có khả năng sinh văn bản tự nhiên nhưng còn hạn chế khi xử lý tri thức chuyên biệt, dữ liệu nội bộ và thông tin cần đối chiếu nguồn. Đồ án này nghiên cứu và xây dựng Yuxi, một nền tảng hỏi–đáp tăng cường truy xuất trên ngữ liệu tiếng Việt, hỗ trợ tài liệu văn bản, PDF và ảnh. Hệ thống kết hợp truy xuất từ khóa, truy xuất vector, đồ thị tri thức, tái xếp hạng kết quả và cơ chế kiểm chứng dựa trên suy luận ngôn ngữ tự nhiên. Luồng xử lý được điều phối bằng đồ thị trạng thái nhằm hỗ trợ lựa chọn công cụ, truy xuất nhiều bước và hiệu chỉnh câu trả lời.

Đồ án đề xuất một khung đánh giá gồm các tầng: chất lượng trích xuất tài liệu, hiệu năng truy xuất, chất lượng trả lời đầu cuối, khả năng gọi công cụ của tác tử, mức độ nhất quán với nguồn, độ trễ và chi phí. Các thí nghiệm được thiết kế theo nguyên tắc tách tập hiệu chỉnh và tập đánh giá, lưu cấu hình và artifact để bảo đảm khả năng tái lập. Tại thời điểm hoàn thiện bản thảo, một số bộ đánh giá thực tế cho OCR, NLI và agent tool-calling vẫn đang được xây dựng; do đó, báo cáo chỉ công bố những kết quả có bằng chứng thực nghiệm đầy đủ.

Từ khóa: truy xuất tăng cường tạo sinh, RAG, tác tử trí tuệ nhân tạo, truy xuất thông tin, đồ thị tri thức, OCR, NLI, tiếng Việt.

ABSTRACT

Large language models can generate fluent natural-language responses but remain limited when handling domain-specific knowledge, private data, and claims that require source verification. This thesis presents Yuxi, a retrieval-augmented question-answering platform for Vietnamese documents, including text, PDF, and image inputs. The system combines lexical retrieval, dense retrieval, knowledge-graph expansion, reranking, and natural-language-inference-based verification. A state-graph workflow coordinates tool selection, multi-step retrieval, and answer correction.

The thesis also proposes a layered evaluation framework covering document extraction, retrieval effectiveness, end-to-end answer quality, agent tool use, factual grounding, latency, and cost. Experiments are designed with separate calibration and evaluation splits, versioned configurations, and reproducible artifacts. At the time of this draft, several real-world evaluation sets for OCR, NLI, and agent tool calling are still under construction; therefore, only results supported by verifiable experimental artifacts are intended for final publication.

Keywords: retrieval-augmented generation, RAG, AI agent, information retrieval, knowledge graph, OCR, natural language inference, Vietnamese.

DANH MỤC TỪ VIẾT TẮT

Viết tắt	Thuật ngữ tiếng Anh	Ý nghĩa tiếng Việt

API	Application Programming Interface	Giao diện lập trình ứng dụng

BM25	Best Matching 25	Thuật toán xếp hạng từ khóa

CER	Character Error Rate	Tỷ lệ lỗi ký tự

EM	Exact Match	Độ khớp chính xác

HNSW	Hierarchical Navigable Small World	Cấu trúc chỉ mục vector xấp xỉ

KG	Knowledge Graph	Đồ thị tri thức

LLM	Large Language Model	Mô hình ngôn ngữ lớn

MRR	Mean Reciprocal Rank	Trung bình nghịch đảo thứ hạng

nDCG	Normalized Discounted Cumulative Gain	Độ lợi tích lũy chiết khấu chuẩn hóa

NLI	Natural Language Inference	Suy luận ngôn ngữ tự nhiên

OCR	Optical Character Recognition	Nhận dạng ký tự quang học

PPR	Personalized PageRank	PageRank cá nhân hóa

RAG	Retrieval-Augmented Generation	Sinh tăng cường truy xuất

RRF	Reciprocal Rank Fusion	Dung hợp theo nghịch đảo thứ hạng

TTFT	Time to First Token	Thời gian tới token đầu tiên

WER	Word Error Rate	Tỷ lệ lỗi từ

DANH MỤC HÌNH

[Tạo tự động sau khi hoàn tất định dạng luận văn.]

DANH MỤC BẢNG

[Tạo tự động sau khi hoàn tất định dạng luận văn.]

CHƯƠNG 1. TỔNG QUAN ĐỀ TÀI

1.1. Bối cảnh nghiên cứu

Mô hình ngôn ngữ lớn đã đạt được nhiều tiến bộ trong hiểu và sinh ngôn ngữ tự nhiên. Tuy nhiên, khi được triển khai trong các hệ thống hỏi–đáp chuyên ngành, mô hình vẫn đối mặt với ba hạn chế chính. Thứ nhất, mô hình có thể tạo ra nội dung nghe hợp lý nhưng không được hỗ trợ bởi nguồn dữ liệu, thường được gọi là hiện tượng ảo giác. Thứ hai, tri thức trong tham số mô hình không bảo đảm cập nhật và không bao gồm dữ liệu nội bộ của tổ chức. Thứ ba, việc đưa toàn bộ tài liệu vào cửa sổ ngữ cảnh làm tăng chi phí, độ trễ và nguy cơ bỏ sót thông tin quan trọng.

Retrieval-Augmented Generation (RAG) giải quyết một phần các hạn chế trên bằng cách truy xuất các đoạn thông tin liên quan trước khi yêu cầu mô hình sinh câu trả lời. Tuy vậy, một pipeline chỉ sử dụng phân đoạn cố định và tìm kiếm vector thường gặp khó khăn với truy vấn chứa mã hiệu, thuật ngữ hiếm, quan hệ nhiều bước, bảng biểu hoặc tài liệu quét. Đối với tiếng Việt, tách từ, từ ghép, dấu thanh, cách viết tên riêng và cấu trúc văn bản hành chính làm tăng thêm độ khó cho cả truy xuất từ khóa và đánh giá câu trả lời.

Từ bối cảnh đó, đồ án tập trung nghiên cứu Yuxi, một nền tảng RAG có điều phối tác tử, kết hợp nhiều tín hiệu truy xuất và có tầng kiểm chứng câu trả lời. Trọng tâm của nghiên cứu không chỉ là xây dựng hệ thống hoạt động được mà còn là thiết lập một quy trình đánh giá có thể tái lập và phản ánh đúng giới hạn của hệ thống.

1.2. Phát biểu bài toán

Cho tập tài liệu tiếng Việt (D={d_1,d_2,\ldots,d_n}) và câu hỏi người dùng (q), hệ thống cần:

Trích xuất và chuẩn hóa nội dung từ tài liệu văn bản, PDF hoặc ảnh.

Truy xuất tập chứng cứ (C_q\subset D) có liên quan đến câu hỏi.

Sinh câu trả lời (a) dựa trên chứng cứ đã truy xuất.

Cung cấp trích dẫn có thể kiểm tra.

Từ chối hoặc cảnh báo khi chứng cứ không đủ.

Kiểm soát độ trễ, chi phí và lỗi gọi công cụ trong giới hạn vận hành xác định.

Đồ án không xem một câu trả lời trôi chảy là đủ. Câu trả lời cần vừa phù hợp với câu hỏi, vừa được hỗ trợ bởi tài liệu nguồn và được tạo ra bằng một quy trình có thể quan sát, đo lường và tái lập.

1.3. Mục tiêu nghiên cứu

1.3.1. Mục tiêu tổng quát

Thiết kế, triển khai và đánh giá một nền tảng hỏi–đáp RAG trên ngữ liệu tiếng Việt, hỗ trợ tài liệu đa định dạng, truy xuất kết hợp, điều phối tác tử và kiểm chứng mức độ bám nguồn.

1.3.2. Mục tiêu cụ thể

Mã	Mục tiêu	Thí nghiệm đối chứng

O1	Xây dựng pipeline tiếp nhận, trích xuất và phân đoạn tài liệu	EXP-OCR-01

O2	So sánh BM25, dense, hybrid và consensus retrieval	EXP-RET-01

O3	Xác định trọng số dung hợp trên tập hiệu chỉnh độc lập	EXP-RET-02

O4	Đánh giá chất lượng trả lời đầu cuối và trích dẫn	EXP-E2E-01

O5	Đánh giá lựa chọn công cụ, đối số và phục hồi lỗi của tác tử	EXP-AGT-01

O6	Đánh giá khả năng phát hiện mệnh đề không được hỗ trợ	EXP-NLI-01

O7	Định lượng đánh đổi giữa chất lượng, độ trễ và chi phí	EXP-SYS-01

1.4. Câu hỏi nghiên cứu

RQ1: Việc kết hợp truy xuất từ khóa, truy xuất vector và tín hiệu đồ thị cải thiện Recall@K, MRR và nDCG@K đến mức nào so với từng phương pháp riêng lẻ?

RQ2: Cơ chế điều phối tác tử và kiểm chứng NLI ảnh hưởng như thế nào đến EM, F1, độ chính xác trích dẫn và tỷ lệ câu trả lời không được hỗ trợ?

RQ3: Tác tử lựa chọn công cụ, truyền đối số và phục hồi lỗi với độ chính xác như thế nào trên bộ tác vụ có nhãn chuẩn?

RQ4: Những cải thiện về chất lượng phải đánh đổi bao nhiêu độ trễ và chi phí suy luận?

1.5. Phạm vi nghiên cứu

Đồ án tập trung vào tài liệu tiếng Việt dạng văn bản, PDF và ảnh; các tác vụ hỏi–đáp dựa trên tri thức trong tài liệu; và pipeline triển khai bằng API cùng các dịch vụ lưu trữ hỗ trợ. Đồ án không thực hiện huấn luyện một LLM nền tảng từ đầu, không đánh giá mọi lĩnh vực tiếng Việt và không đưa ra bảo đảm loại bỏ hoàn toàn ảo giác. Khả năng mở rộng ở quy mô doanh nghiệp, phân quyền đa người thuê và triển khai sẵn sàng cao được xem là hướng phát triển nếu chưa có thử nghiệm tải tương ứng.

1.6. Đóng góp của đồ án

Các đóng góp dự kiến gồm:

Một kiến trúc tham chiếu cho hệ thống RAG tiếng Việt có ingestion, retrieval, agent workflow và verification.

Một cơ chế dung hợp nhiều tín hiệu truy xuất, có thể hiệu chỉnh trọng số trên validation set.

Một quy trình kiểm chứng câu trả lời ở mức mệnh đề bằng NLI và chính sách xử lý theo từng nhãn.

Một bộ khung đánh giá nhiều tầng, lưu cấu hình, dự đoán thô và artifact để tái lập.

Phân tích lỗi và đánh đổi giữa chất lượng, độ trễ và chi phí.

Mọi đóng góp định lượng trong bản cuối phải trỏ tới kết quả `Measured` tại Chương 4.

1.7. Bố cục luận văn

Chương 1 trình bày bối cảnh, bài toán, mục tiêu và câu hỏi nghiên cứu. Chương 2 tổng hợp cơ sở lý thuyết và công trình liên quan. Chương 3 mô tả phương pháp và kiến trúc hệ thống. Chương 4 trình bày thiết kế thực nghiệm, kết quả và phân tích lỗi. Chương 5 tổng kết kết quả, giới hạn và hướng phát triển.

CHƯƠNG 2. CƠ SỞ LÝ THUYẾT VÀ CÔNG TRÌNH LIÊN QUAN

2.1. Mô hình ngôn ngữ lớn và hệ tác tử

LLM dựa trên kiến trúc Transformer mô hình hóa phân phối xác suất của chuỗi token. Trong ứng dụng RAG, LLM đảm nhiệm tổng hợp câu trả lời từ câu hỏi và ngữ cảnh truy xuất. Một tác tử mở rộng LLM bằng vòng lặp quan sát–lập luận–hành động, trong đó mô hình có thể lựa chọn công cụ, nhận kết quả và quyết định bước tiếp theo. Các thành phần thường gặp gồm bộ lập kế hoạch, registry công cụ, bộ nhớ trạng thái, điều kiện dừng và cơ chế phục hồi lỗi.

Trong đồ án, LangGraph được sử dụng để biểu diễn workflow dưới dạng đồ thị trạng thái. Mỗi node thực hiện một chức năng xác định; edge biểu diễn điều kiện chuyển tiếp. Cách tổ chức này hỗ trợ giới hạn số vòng lặp, ghi lại trajectory và kiểm soát các nhánh xử lý tốt hơn một vòng lặp agent không cấu trúc.

2.2. Retrieval-Augmented Generation

Pipeline RAG cơ bản gồm hai pha. Pha indexing chuyển tài liệu thành các đoạn, metadata và biểu diễn phục vụ tìm kiếm. Pha online nhận câu hỏi, truy xuất ngữ cảnh và yêu cầu LLM sinh câu trả lời. Advanced RAG bổ sung query rewriting, hybrid retrieval, reranking và context compression. Agentic RAG cho phép tác tử quyết định khi nào cần truy xuất, công cụ nào phù hợp và có cần truy vấn bổ sung hay không.

RAG không tự động bảo đảm tính đúng đắn. Lỗi có thể xuất hiện ở mọi tầng: trích xuất sai, chunking làm mất ngữ cảnh, truy xuất thiếu chứng cứ, reranker xếp hạng sai hoặc LLM suy diễn vượt quá nguồn. Vì vậy, đánh giá cần tách retrieval quality khỏi generation quality.

2.3. Truy xuất từ khóa bằng BM25

Với truy vấn (q) và tài liệu (d), điểm BM25 được tính bởi:

[

\operatorname{BM25}(q,d)=\sum_{t\in q}\operatorname{IDF}(t)

\frac{f(t,d)(k_1+1)}{f(t,d)+k_1\left(1-b+b\frac{|d|}{\operatorname{avgdl}}\right)}.

]

Trong đó, (f(t,d)) là tần suất thuật ngữ (t) trong (d), (|d|) là độ dài tài liệu, (\operatorname{avgdl}) là độ dài trung bình, còn (k_1) và (b) điều khiển độ bão hòa tần suất và chuẩn hóa độ dài. Đối với tiếng Việt, chất lượng tách từ có thể ảnh hưởng mạnh tới BM25; vì vậy đồ án so sánh baseline theo khoảng trắng với tokenizer tiếng Việt.

2.4. Truy xuất vector và HNSW

Bi-encoder ánh xạ câu hỏi và đoạn văn thành các vector trong cùng không gian. Độ tương đồng cosine được xác định bởi:

[

\operatorname{cos}(\mathbf q,\mathbf d)=

\frac{\mathbf q^\top\mathbf d}{|\mathbf q|_2|\mathbf d|_2}.

]

HNSW tổ chức vector thành đồ thị nhiều tầng để tìm kiếm láng giềng gần đúng. Các tham số chỉ mục và truy vấn như (M), `efConstruction` và `efSearch` tạo ra đánh đổi giữa bộ nhớ, tốc độ và recall. Bản cuối phải ghi rõ các tham số thực tế được sử dụng.

2.5. Hybrid retrieval và dung hợp thứ hạng

Do điểm BM25, cosine và graph score có thang đo khác nhau, hệ thống cần cơ chế dung hợp. Với chuẩn hóa min–max, điểm tổng hợp có thể được biểu diễn:

[

S(d,q)=\sum_{i=1}^{m}w_i\widehat{S_i}(d,q),

\qquad w_i\geq0,\quad\sum_{i=1}^{m}w_i=1.

]

Một lựa chọn khác là Reciprocal Rank Fusion:

[

\operatorname{RRF}(d)=\sum_{r\in R}\frac{1}{k+\operatorname{rank}_r(d)}.

]

Đồ án phải nêu rõ cơ chế nào được dùng trong hệ thống thực tế. Nếu trọng số được lựa chọn bằng grid search, việc lựa chọn chỉ được thực hiện trên validation set.

2.6. Đồ thị tri thức và Personalized PageRank

Đồ thị tri thức được mô hình hóa bởi (G=(V,E)), trong đó (V) là tập thực thể và (E) là tập quan hệ. Với vector khởi tạo (\mathbf s) từ các thực thể trong câu hỏi, Personalized PageRank có dạng:

[

\mathbf p_{t+1}=\alpha P^\top\mathbf p_t+(1-\alpha)\mathbf s.

]

Kết quả lan truyền được sử dụng để tìm các thực thể và đoạn văn liên quan gián tiếp. Để bảo đảm truy nguyên, mỗi node và cạnh cần lưu provenance về tài liệu hoặc chunk nguồn.

2.7. Tái xếp hạng

Cross-encoder nhận đồng thời câu hỏi và đoạn văn để ước lượng mức độ liên quan. So với bi-encoder, cross-encoder thường chính xác hơn nhưng có chi phí tính toán lớn hơn. Do đó, nó được áp dụng trên một tập ứng viên nhỏ sau retrieval thay vì toàn bộ corpus.

2.8. NLI và kiểm chứng bám nguồn

NLI phân loại quan hệ giữa tiền đề (p) và giả thuyết (h) thành `entailment`, `neutral` hoặc `contradiction`. Trong hệ thống, tiền đề là các đoạn chứng cứ và giả thuyết là mệnh đề nguyên tử được tách từ câu trả lời. Quyết định không chỉ phụ thuộc nhãn có xác suất cao nhất mà còn phụ thuộc ngưỡng và chính sách hệ thống.

NLI không thể thay thế hoàn toàn kiểm tra sự thật. Nếu retriever không cung cấp đúng chứng cứ, một mệnh đề đúng có thể bị đánh giá là neutral. Ngược lại, overlap từ vựng có thể làm mô hình đánh giá sai một mệnh đề. Vì vậy cần đánh giá trên tập claim có nhãn gold.

2.9. Công trình liên quan

Phần này cần so sánh Yuxi với các nhóm hệ thống, không chỉ liệt kê tính năng sản phẩm.

Nhóm	Đại diện	Điểm mạnh	Khoảng trống liên quan đến đề tài

RAG nền tảng	Lewis và cộng sự	Kết hợp retrieval và generation	Chưa tập trung workflow agent và tài liệu doanh nghiệp

Dense retrieval	DPR	Truy xuất ngữ nghĩa hiệu quả	Có thể yếu với mã hiệu và từ hiếm

Agent reasoning	ReAct	Đan xen suy luận và hành động	Cần kiểm soát trajectory và lỗi công cụ

Self-corrective RAG	Self-RAG, CRAG	Phản tư hoặc điều chỉnh retrieval	Tăng chi phí và cần benchmark riêng

Graph-based RAG	GraphRAG và các biến thể	Hỗ trợ quan hệ và tổng hợp nhiều nguồn	Phụ thuộc chất lượng xây dựng đồ thị

Document parsing	Docling và OCR engines	Trích xuất cấu trúc tài liệu	Cần đánh giá trên tài liệu tiếng Việt thực tế

CHƯƠNG 3. PHƯƠNG PHÁP VÀ THIẾT KẾ HỆ THỐNG

3.1. Yêu cầu hệ thống

3.1.1. Yêu cầu chức năng

Hệ thống cần cho phép người dùng tải tài liệu, theo dõi trạng thái xử lý, đặt câu hỏi, nhận câu trả lời có trích dẫn và mở lại tài liệu nguồn. Quản trị viên cần có khả năng quản lý kho tri thức và quan sát lỗi ingestion hoặc truy xuất.

3.1.2. Yêu cầu phi chức năng

Các yêu cầu phi chức năng gồm khả năng truy nguyên, giới hạn vòng lặp tác tử, cô lập thực thi mã, bảo vệ dữ liệu, quan sát độ trễ và khả năng tái lập benchmark. Các tuyên bố về sẵn sàng cao hoặc mở rộng ngang chỉ được đưa vào bản cuối khi có thiết kế và thử nghiệm tương ứng.

3.2. Kiến trúc tổng thể

```mermaid

flowchart TD

    U["Web/SDK Client"] --&gt; A["FastAPI Gateway"]

    A --&gt; W["Agent Workflow"]

    A --&gt; I["Ingestion Worker"]

    I --&gt; O["Object Storage"]

    I --&gt; V["Vector Index"]

    I --&gt; G["Knowledge Graph"]

    W --&gt; R["Hybrid Retrieval"]

    R --&gt; V

    R --&gt; G

    W --&gt; N["NLI Verifier"]

    W --&gt; S["Sandbox"]

```

Thành phần	Công nghệ dự kiến	Vai trò

API Gateway	FastAPI	Xác thực, nhận yêu cầu và trả kết quả

Workflow	LangGraph	Điều phối trạng thái, công cụ và vòng lặp

Worker	Celery/worker tương đương	Xử lý ingestion bất đồng bộ

Metadata store	PostgreSQL	Lưu tài liệu, trạng thái và metadata

Queue/cache	Redis	Hàng đợi, cache và trạng thái tạm thời

Vector store	Milvus	Lưu embedding và tìm kiếm ANN

Graph store	Neo4j	Lưu thực thể, quan hệ và provenance

Object store	MinIO/S3	Lưu tệp gốc và artifact

Parser/OCR	Docling và OCR engine	Trích xuất nội dung, layout và bảng

Sandbox	Container cô lập	Thực thi mã có giới hạn tài nguyên

Các thành phần logic chỉ được gọi là microservice khi có process, contract và vòng đời triển khai độc lập.

3.3. Pipeline ingestion

Pipeline ingestion gồm các bước:

Kiểm tra định dạng, kích thước và mã băm của tệp.

Lưu tệp gốc vào object storage.

Phân loại PDF có text layer hay tài liệu quét.

Chọn parser hoặc OCR engine.

Chuẩn hóa văn bản và cấu trúc bảng.

Phân đoạn theo tiêu đề, đoạn và giới hạn token.

Sinh embedding và cập nhật vector index.

Trích xuất thực thể, quan hệ và cập nhật graph.

Lưu provenance từ chunk về tài liệu và số trang.

Các giá trị chunk size, overlap và ngưỡng chọn OCR phải được lấy từ cấu hình thực tế và ghi trong Phụ lục B.

3.4. Xây dựng đồ thị tri thức

Mỗi thực thể được lưu cùng loại, tên chuẩn hóa, aliases và provenance. Quan hệ phải có nguồn chứng cứ và confidence nếu được trích xuất tự động. Quy trình entity resolution gồm chuẩn hóa chuỗi, đối sánh alias và kiểm tra tương đồng embedding. Khi tài liệu bị xóa, các node hoặc cạnh không còn provenance hợp lệ cũng phải được cập nhật.

[CẦN BỔ SUNG: graph schema thực tế, mô hình/rule trích xuất, thuật toán entity resolution và ví dụ Cypher.]

3.5. Consensus retrieval

Với câu hỏi đầu vào, router xác định loại truy vấn và lựa chọn các retriever phù hợp. Các retriever trả về danh sách ứng viên cùng điểm hoặc thứ hạng. Hệ thống chuẩn hóa hoặc dung hợp kết quả, sau đó cross-encoder tái xếp hạng top ứng viên. Trọng số mặc định là tham số hệ thống; chỉ được gọi là “tối ưu” khi được lựa chọn trên validation set và kiểm tra độc lập trên test set.

```text

Input query

  → intent routing/query rewriting

  → BM25 + dense + graph retrieval

  → score/rank fusion

  → cross-encoder reranking

  → context assembly

```

3.6. Workflow tác tử

Trạng thái tối thiểu của workflow gồm lịch sử thông điệp, kế hoạch hiện tại, tập chunk chứng cứ, công cụ đã gọi, số vòng lặp, grounding score và nguyên nhân kết thúc. Workflow phải có giới hạn số bước và cơ chế phát hiện lặp.

Các node chính gồm:

Input guard và chuẩn hóa câu hỏi.

Router xác định loại tác vụ.

Planner quyết định truy xuất hoặc gọi công cụ.

Tool executor thực hiện lời gọi có schema.

Evidence aggregator tổng hợp chứng cứ.

Generator tạo câu trả lời có trích dẫn.

Verifier đánh giá các mệnh đề.

Correction hoặc abstention khi chứng cứ không đủ.

Nếu hệ thống thực tế chỉ có một workflow trung tâm sử dụng nhiều công cụ, thuật ngữ chính xác là agentic RAG. Chỉ sử dụng multi-agent khi có nhiều agent với vai trò, handoff và trạng thái phối hợp được định nghĩa rõ.

3.7. NLI verifier và self-correction

Câu trả lời được tách thành các mệnh đề nguyên tử (c_1,\ldots,c_m). Với mỗi mệnh đề, hệ thống lấy các đoạn chứng cứ liên quan và tính xác suất NLI. Chính sách dự kiến:

Phán quyết	Điều kiện	Hành động

Entailment	Xác suất vượt ngưỡng và có citation hợp lệ	Giữ mệnh đề

Neutral	Không đủ bằng chứng	Loại bỏ, cảnh báo hoặc yêu cầu truy xuất bổ sung

Contradiction	Mâu thuẫn với chứng cứ vượt ngưỡng	Chặn mệnh đề và kích hoạt correction

Ngưỡng cuối cùng phải được hiệu chỉnh trên calibration set, không chọn trực tiếp từ test set.

3.8. An toàn và quan sát hệ thống

Sandbox cần giới hạn CPU, RAM, thời gian chạy, filesystem và network; đồng thời áp dụng nguyên tắc đặc quyền tối thiểu. Hệ thống cần ghi trace cho mỗi request gồm model, prompt version, retriever configuration, tool calls, latency từng chặng và trạng thái kết thúc. Log không được chứa khóa bí mật hoặc nội dung nhạy cảm ngoài chính sách lưu trữ.

CHƯƠNG 4. THIẾT KẾ THỰC NGHIỆM VÀ KẾT QUẢ

4.1. Nguyên tắc đánh giá

Đồ án tuân theo các nguyên tắc: tách validation và test; chỉ chọn hyperparameter trên validation; cố định corpus giữa các retrieval arms; lưu prediction thô; ghi model version, prompt version, seed và commit; và không công bố số liệu không có artifact. Mỗi kết quả được gắn một trong các trạng thái `Measured`, `Estimated`, `Missing`, `Blocked` hoặc `Deferred` trong giai đoạn hoàn thiện. Các nhãn này được loại bỏ khỏi bản nộp cuối sau khi toàn bộ bảng kết quả đã được chốt.

4.2. Bộ dữ liệu và cách chia tập

4.2.1. Retrieval và E2E QA

UIT-ViQuAD được sử dụng làm nguồn cho benchmark đọc hiểu tiếng Việt. Khi chuyển thành retrieval benchmark, cần mô tả rõ cách xây dựng corpus, cách xác định relevant passage, cách tạo negative passages và cách loại bỏ duplicate giữa các split.

Số liệu đã khóa cho đồ án (trạng thái `Measured`, chi tiết tại §4.6 và §4.8): nguồn phụ cho retrieval là `mteb/VieQuADRetrieval` revision `f956535e` (validation: 2.048 queries, 2.490 passages, 4.096 qrels); nguồn chính cho E2E và abstention là `taidng/UIT-ViQuAD2.0` revision `406f09a4` (validation: 3.814 dòng gồm 2.653 answerable và 1.161 impossible), từ đó trích mẫu E2E 150 câu (100 answerable + 50 impossible, seed 42) trên corpus 557 passages deduplicated. Nguồn `checken9x/vietnamese-rag-benchmark-1k` (revision `cd979a55`) chỉ dùng tham khảo vì toàn bộ 1.000 ô `ground_truth` đều là placeholder, không tính được EM/F1 (xem `source-lock.json`, mục `vn-rag-1k`, trạng thái `reference_only`).

4.2.2. OCR

Bộ OCR phải gồm tài liệu tiếng Việt có ground-truth transcription và đa dạng về text layer, scan, nhiều cột, bảng, ảnh chụp và chất lượng thấp. Tài liệu synthetic chỉ được dùng cho smoke test, không thay thế bộ đánh giá thực tế.

4.2.3. NLI

Bộ NLI gồm các mệnh đề nguyên tử được gán nhãn `entailment`, `neutral` và `contradiction` dựa trên chứng cứ. Cần có annotation guideline; nếu có từ hai người gán nhãn, báo cáo mức độ đồng thuận.

4.2.4. Agent tool-calling

Mỗi task phải có câu hỏi, tool kỳ vọng, arguments kỳ vọng, tool không được phép gọi, outcome kỳ vọng và loại lỗi nếu là bài kiểm tra recovery.

Số liệu đã khóa (trạng thái `Measured`, chi tiết tại §4.10): kiểm định contract đạt 2.899/2.899 records Vietnamese Function Calling và 3.652/3.652 records When2Call hợp lệ, 0 lỗi (`agent_contract_validation.json`); đo mô hình trên 100 task VN-FC (tool match 98%, exact match 93%) và 60 quyết định When2Call phân tầng (accuracy 66,67%).

4.3. Experiment registry

Exp ID	Nội dung	Dữ liệu	Chỉ số chính	Trạng thái hiện tại

EXP-OCR-01	OCR trên tài liệu in thực tế	[CẦN BỔ SUNG]	CER, WER, table score, latency	`Deferred` (raw OCR trống, engine chưa kiểm chứng; xem §4.9)

EXP-RET-01	Retrieval ablation	UIT-ViQuAD converted corpus	Recall@K, MRR, nDCG@5	`Measured` một phần (arm BM25 whitespace full 2.048 queries; dense/hybrid `Blocked` vì không có embedding key)

EXP-RET-02	Consensus weight search	Validation split	nDCG@5	`Blocked` (cần dense arm trước)

EXP-E2E-01	End-to-end QA	Test split	EM, F1, citation, abstention	`Measured` (150 mẫu UIT-ViQuAD 2.0: extractive + standard RAG)

EXP-AGT-01	Agent trajectory	Tool-calling suite	Task success, tool/argument accuracy	`Measured` (VN-FC 100 + When2Call 60)

EXP-NLI-01	Claim grounding	Gold claim set	Precision, Recall, F1, confusion matrix	Chưa đo (full 2.091 bị gián đoạn do tắt máy; chỉ smoke pipeline 6 mẫu; chạy lại trên GPU)

EXP-SYS-01	Latency và chi phí	Request traces	p50, p95, p99, cost/query	`Measured` một phần (latency từ run E2E/agent/NLI; chi phí `Estimated` vì dùng free trial)

&gt; Trạng thái trên phản ánh bản thảo hiện tại. Chỉ cập nhật thành `Measured` khi có command, config, raw predictions, metrics, commit SHA và ngày chạy.

4.4. Chỉ số đánh giá

4.4.1. Retrieval

Với tập tài liệu liên quan (Rel(q)) và top-(K) kết quả (Ret_K(q)):

[

\operatorname{Recall@K}=\frac{|Rel(q)\cap Ret_K(q)|}{|Rel(q)|}.

]

MRR sử dụng nghịch đảo thứ hạng của kết quả liên quan đầu tiên:

[

\operatorname{MRR}=\frac{1}{|Q|}\sum_{q\in Q}\frac{1}{\operatorname{rank}_q}.

]

Với graded relevance, nDCG@K được tính từ DCG đã chuẩn hóa bởi thứ hạng lý tưởng.

4.4.2. OCR

[

\operatorname{CER}=\frac{S_c+D_c+I_c}{N_c},\qquad

\operatorname{WER}=\frac{S_w+D_w+I_w}{N_w}.

]

Trong đó (S), (D), (I) lần lượt là số phép thay thế, xóa và chèn.

4.4.3. Generation

EM bằng 1 khi câu trả lời dự đoán sau chuẩn hóa khớp hoàn toàn với đáp án. Token F1 là trung bình điều hòa giữa precision và recall trên token. Báo cáo phải ghi quy tắc chuẩn hóa tiếng Việt, dấu câu và chữ hoa/thường.

4.4.4. NLI và agent

NLI được đánh giá bằng confusion matrix, precision, recall và F1 theo từng lớp, đặc biệt là recall của lớp contradiction. Agent được đánh giá bằng task success, tool selection accuracy, argument validity, số lời gọi thừa, trajectory length và recovery rate.

4.5. Giao thức thực nghiệm

Mỗi thí nghiệm `Measured` phải có khối tái lập:

```text

Exp ID      :

Command     :

Dataset     :

Split       :

N           :

Model       :

Prompt ver. :

Config      :

Seed        :

Hardware    :

Artifact    :

Commit SHA  :

Run date    :

```

4.6. Retrieval ablation

Các cấu hình tối thiểu:

BM25 theo khoảng trắng.

BM25 với tokenizer tiếng Việt.

Dense retrieval.

BM25 + dense.

Hybrid + query rewriting.

Consensus retrieval + reranking.

Cấu hình	Recall@1	Recall@5	Recall@10	MRR	nDCG@5	p50	p95	Trạng thái

BM25 whitespace	58,06%	85,74%	91,80%	0,7010	0,4919	32,7ms	56,0ms	`Measured` (N=2.048, corpus 2.490; `viequad_bm25_validation.json`)

BM25 tiếng Việt	—	—	—	—	—	—	—	`Missing` (chưa chạy arm pyvi)

Dense	—	—	—	—	—	—	—	`Blocked` (không có embedding key khả dụng: Gemini/OpenRouter hết hạn, NVIDIA chỉ có chat, SiliconFlow/DashScope không có key)

Hybrid	—	—	—	—	—	—	—	`Blocked` (phụ thuộc dense)

Hybrid + rewrite	—	—	—	—	—	—	—	`Blocked` (phụ thuộc dense)

Consensus + reranker	—	—	—	—	—	—	—	`Blocked` (phụ thuộc dense + weight search)

[Sau khi chạy: báo cáo bootstrap 95% confidence interval và chênh lệch theo điểm phần trăm; không dùng “tăng X%” nếu thực chất là X percentage points.]

4.7. Tìm kiếm trọng số consensus

Trọng số được lựa chọn trên validation set theo nDCG@5. Sau khi chọn, cấu hình được khóa và đánh giá một lần trên test set. Cần công bố toàn bộ search space, normalization method và tiêu chí xử lý tie.

Bộ trọng số	(w_{BM25})	(w_{dense})	(w_{graph})	(w_{event})	Validation nDCG@5	Test nDCG@5	Trạng thái

[Cấu hình]	—	—	—	—	—	—	`Missing`

4.8. Đánh giá đầu cuối

Phương pháp	EM	Token F1	Citation accuracy	Abstention F1	Unsupported claim rate	Trạng thái

Direct retrieval/extractive	0,67% (95% CI [0,12; 3,68])	17,57%	—	— (P=0, R=0)	—	`Measured` (N=150, hit@1 77,33%; `uit-viquad-2_e2e_150.json`)

Standard RAG	45,33% (95% CI [37,58; 53,32])	66,94%	—	P=79,49%, R=62,00%	—	`Measured` (N=150, DeepSeek V4.1 Flash qua NVIDIA, temp=0, max_tokens=4096, top_k=5, 150 calls/2 lỗi; cùng file trên)

Agentic RAG không NLI	—	—	—	—	—	`Missing` (cần KB populated + LangGraph path)

Agentic RAG + NLI	—	—	—	—	—	`Missing` (phụ thuộc arm trên + NLI gate)

Các arms phải sử dụng cùng test queries và cùng LLM nếu mục tiêu là đo đóng góp của retrieval/agent/NLI.

4.9. Đánh giá OCR

Engine	Loại tài liệu	N trang	CER	WER	Table score	Giây/trang	Trạng thái

Docling/parser	—	—	—	—	—	—	`Deferred` (kỳ này không đo; `benchmarks/raw` không có file OCR nào trên máy đo, engine trong container chưa kiểm chứng)

OCR engine 1	—	—	—	—	—	—	`Deferred` (như trên)

OCR engine 2	—	—	—	—	—	—	`Deferred` (như trên)

Parser PDF và OCR chỉ được so sánh trực tiếp trên cùng tập đầu vào và cùng ground truth.

4.10. Đánh giá agent

Nhóm tác vụ	N	Task success	Tool precision	Tool recall	Argument validity	Calls thừa/task	Trạng thái

VN Function Calling (tool match / EM)	100	—	98,00% (95% CI [93,00; 99,45])	—	93,00% (95% CI [86,25; 96,57])	~0,3	`Measured` (DeepSeek V4.1 Flash qua NVIDIA, temp=0, max_tokens=1024; `vietnamese_function_calling_nvidia_deepseek_100.json`; usage: 105 calls tracked cho 80 mẫu sau + ~25 calls cho 20 mẫu smoke trước tracker)

When2Call decision (accuracy)	60 (20/class)	66,67% (95% CI [54,06; 77,27])	—	—	—	—	`Measured` (cannot 60%, request 55%, tool_call 90%; `when2call_nvidia_deepseek_stratified60.json`; chạy trước tracker nên quota tính tay ~60 calls)

Knowledge retrieval	—	—	—	—	—	—	`Missing` (cần task manifest + trajectory log trên KB populated)

Document navigation	—	—	—	—	—	—	`Missing` (như trên)

Multi-step	—	—	—	—	—	—	`Missing` (như trên)

Error recovery	—	—	—	—	—	—	`Missing` (recovery chưa định nghĩa + đo chính thức)

Recovery phải được định nghĩa trước, ví dụ: tác vụ hoàn tất đúng trong tối đa (n) bước sau khi công cụ trả timeout, empty result hoặc structured error.

4.11. Đánh giá NLI

Gold \ Predicted	Entailment	Neutral	Contradiction

Entailment	—	—	—

Neutral	—	—	—

Contradiction	—	—	—

Chỉ số	Giá trị	Trạng thái

Macro F1	—	`Missing`

Contradiction precision	—	`Missing`

Contradiction recall	—	`Missing`

False-negative rate	—	`Missing`

Hallucination rate trước correction	—	`Missing`

Hallucination rate sau correction	—	`Missing`

Số lượng nhãn do mô hình dự đoán không được dùng thay cho accuracy hoặc confusion matrix.

4.12. Độ trễ và chi phí

Độ trễ E2E phải được đo trực tiếp trên từng request. Không suy ra E2E p95 bằng tổng p95 của các thành phần.

Thành phần	p50	p95	p99	Cache state	N	Trạng thái

Router	—	—	—	—	—	`Missing`

Retrieval (BM25 standalone, VieQuAD 2.490 docs)	32,7ms	56,0ms	—	không cache	2.048	`Measured` (`viequad_bm25_validation.json`)

Retrieval (BM25, E2E corpus 557 docs)	0,3ms	—	—	không cache	150	`Measured` (trong `uit-viquad-2_e2e_150.json`, arm extractive)

Reranker	—	—	—	—	—	`Missing` (chưa có reranker key/model)

LLM TTFT	—	—	—	—	—	`Missing` (adapter không tách TTFT)

Generation (DeepSeek V4.1 Flash, reasoning)	11,7s	—	—	không cache	150	`Measured` (mean 23,1s p50 11,7s; `uit-viquad-2_e2e_150.json`)

NLI	—	—	—	—	—	Đang chạy (2.091 cặp × 2 cấu hình, CPU)

E2E trực tiếp	11,7s	—	—	không cache	150	`Measured` (standard_rag; p95 tính sau khi chốt mẫu, không cộng dồn phân vị thành phần)

Phần chi phí được đặt tên là Cost–Quality Trade-off. Chỉ sử dụng thuật ngữ ROI nếu đã định lượng lợi ích kinh tế.

4.13. Phân tích lỗi

Mỗi lỗi phải có `sample_id`, loại lỗi, tầng gây lỗi, đầu ra dự đoán, gold answer, chứng cứ và hướng khắc phục. Taxonomy tối thiểu gồm extraction, chunking, retrieval, reranking, graph, generation, citation, NLI và tool execution.

Nhóm lỗi	Số ca	Tỷ lệ	Ví dụ sample_id	Hướng xử lý

Over-trigger tool_call (gọi tool khi nên từ chối/hỏi thêm)	15/20 lỗi When2Call	75%	`5ce19067…`, `ca90b386…`	Tăng tách cannot/request khỏi tool_call trong prompt; hiệu chỉnh ngưỡng

Parse error (reasoning text lẫn trước JSON)	4/20 lỗi When2Call	20%	`a0bc455a…`	Parser chịu được thinking prefix hoặc yêu cầu JSON-first

Under-trigger (bỏ tool đúng)	1/20 lỗi When2Call	5%	`f95f23f9…`	Bổ sung vào tập regression khi đổi prompt

Extraction/OCR	—	—	—	`Deferred` theo OCR

Retrieval miss (E2E: hit@1 đúng nhưng abstain / EM sai)	—	—	—	Phân tích sau khi chốt NLI (xem §4.8: hit@1 77,33% nhưng EM 45,33%)

Unsupported generation	—	—	—	Chờ NLI dual-config

Tool/argument error (VN-FC: 7/100 EM sai)	7	7%	—	Phân tích chi tiết sau (tách lỗi gold-chuẩn-hóa khỏi lỗi slot)

4.14. Đe dọa đối với tính hợp lệ

Internal validity: sai lệch có thể đến từ thay đổi model API, cache, prompt hoặc phiên bản index.

Construct validity: EM/F1 không phản ánh đầy đủ tính hữu ích và mức độ bám nguồn.

External validity: UIT-ViQuAD và tập synthetic không đại diện toàn bộ tài liệu doanh nghiệp tiếng Việt.

Conclusion validity: tập đánh giá nhỏ có thể tạo ra chênh lệch không ổn định; cần confidence interval và kiểm định phù hợp.

CHƯƠNG 5. KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN

5.1. Kết luận

Đồ án đã xác định kiến trúc và phương pháp đánh giá cho một nền tảng hỏi–đáp RAG tiếng Việt có hỗ trợ tài liệu đa định dạng, hybrid retrieval, đồ thị tri thức, workflow tác tử và kiểm chứng NLI. Thiết kế nhấn mạnh khả năng truy nguyên và tách riêng các tầng đánh giá thay vì chỉ sử dụng một chỉ số trả lời đầu cuối.

[CẦN CẬP NHẬT SAU THỰC NGHIỆM: viết một đoạn trả lời cho từng RQ1–RQ4, kèm số liệu và tham chiếu bảng. Không dùng “vượt trội”, “đột phá”, “chặn hoàn toàn” hoặc “production-ready” nếu dữ liệu không chứng minh.]

Trả lời sơ bộ từ số liệu đã chốt (cập nhật tiếp sau NLI):

RQ1 (retrieval): mới chỉ đo arm BM25 whitespace trên VieQuAD (R@10 91,80%, MRR@10 0,7010, N=2.048) và BM25 trên corpus E2E 557 docs (hit@1 77,33%). Chưa đủ cơ sở so sánh với dense/hybrid/consensus (`Blocked`, §4.6).

RQ2 (NLI + tác tử): E2E standard RAG đạt EM 45,33% (95% CI [37,58; 53,32]), F1 66,94%, abstention P 79,49% / R 62,00% trên 150 mẫu; đóng góp của NLI gate chưa tách được — confusion matrix dual-config phải chạy lại full 2.091 trên GPU (bản CPU bị gián đoạn; xem §4.11).

RQ3 (agent): VN-FC 100 mẫu tool match 98% (95% CI [93,00; 99,45]), EM 93%; When2Call 60 mẫu accuracy 66,67% (95% CI [54,06; 77,27]), lỗi tập trung ở over-trigger tool_call (15/20). Recovery chưa đo chính thức (§4.10, §4.13).

RQ4 (trade-off): E2E standard RAG p50 11,7s (reasoning model) so với retrieval thuần 0,3–32,7ms; chi phí ở mức `Estimated` vì dùng free trial — cần bảng giá công khai hoặc đo spend thật trước khi kết luận (§4.12).

5.2. Hạn chế

Tại thời điểm của bản thảo, bộ OCR tài liệu in thực tế, tập NLI có nhãn gold và agent task suite chưa hoàn thiện. Một số benchmark lớn chưa được chạy đầy đủ do hạn chế dữ liệu, hạ tầng hoặc license. Ngoài ra, benchmark đọc hiểu từ Wikipedia chưa phản ánh đầy đủ tài liệu nội bộ, bảng biểu phức tạp và truy vấn nhiều bước trong môi trường doanh nghiệp.

Bổ sung từ đợt đo 2026-09-22: E2E 150 mẫu cho thấy khoảng cách giữa retrieval (hit@1 77,33%) và generation (EM 45,33%) — trả lời sai không chỉ do miss chứng cứ; abstention recall mới 62% nghĩa là 38% câu unanswerable vẫn bị trả lời bừa; mẫu E2E 150 và agent 60–100 còn nhỏ nên khoảng tin cậy rộng (±8–15 điểm phần trăm); chi phí suy luận chưa đo bằng tiền thật; toàn bộ model calls đi qua trial rate-limit của NVIDIA nên khả năng tái lập dài hạn phụ thuộc nhà cung cấp.

NLI chỉ kiểm tra quan hệ giữa claim và context được cung cấp; nó không chứng minh chân lý tuyệt đối. Knowledge graph cũng phụ thuộc vào chất lượng trích xuất thực thể và quan hệ. Cuối cùng, Docker Compose phục vụ phát triển và tái lập cục bộ nhưng không tự chứng minh khả năng sẵn sàng cao hay mở rộng production.

5.3. Hướng phát triển

Hoàn thiện benchmark OCR tiếng Việt có ground truth và kiểm tra license.

Xây dựng tập NLI và agent tool-calling có gán nhãn độc lập.

Đánh giá retrieval trên nhiều domain và dữ liệu ngoài Wikipedia.

Cải thiện entity resolution và provenance trong knowledge graph.

Nghiên cứu adaptive retrieval để giảm số lần gọi LLM và graph.

Bổ sung phân quyền đa người thuê, audit trail và kiểm thử bảo mật.

Thực hiện load test, chaos test và đánh giá triển khai trên hạ tầng phân tán.

TÀI LIỆU THAM KHẢO

P. Lewis et al., “Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks,” Advances in Neural Information Processing Systems, 2020.

K. V. Nguyen, D.-V. Nguyen, A.-T. Nguyen, and N. L.-T. Nguyen, “A Vietnamese Dataset for Evaluating Machine Reading Comprehension,” Proceedings of COLING, 2020.

S. Robertson and H. Zaragoza, “The Probabilistic Relevance Framework: BM25 and Beyond,” Foundations and Trends in Information Retrieval, 2009.

V. Karpukhin et al., “Dense Passage Retrieval for Open-Domain Question Answering,” Proceedings of EMNLP, 2020.

Y. Malkov and D. Yashunin, “Efficient and Robust Approximate Nearest Neighbor Search Using Hierarchical Navigable Small World Graphs,” IEEE TPAMI, 2020.

G. V. Cormack, C. L. A. Clarke, and S. Buettcher, “Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods,” Proceedings of SIGIR, 2009.

S. Yao et al., “ReAct: Synergizing Reasoning and Acting in Language Models,” International Conference on Learning Representations, 2023.

A. Asai et al., “Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection,” International Conference on Learning Representations, 2024.

P. Lewis et al., “PAQ: 65 Million Probably-Asked Questions and What You Can Do With Them,” Transactions of the Association for Computational Linguistics, 2021.

A. Conneau et al., “XNLI: Evaluating Cross-lingual Sentence Representations,” Proceedings of EMNLP, 2018.

[CẦN BỔ SUNG] Tài liệu chính thức đúng phiên bản của LangGraph, Milvus, Neo4j, Docling và các model/API được sử dụng; ghi ngày truy cập.

PHỤ LỤC A. MA TRẬN TRUY NGUYÊN KẾT QUẢ

Claim ID	Tuyên bố trong luận văn	Exp ID	Bảng/Hình	Artifact	Trạng thái

C-001	BM25 whitespace đạt R@10 91,80%, MRR@10 0,7010 trên VieQuAD validation	EXP-RET-01	Bảng 4.6	`benchmarks/results/viequad_bm25_validation.json`	`Measured`

C-002	Standard RAG đạt EM 45,33%, F1 66,94%, abstention P/R 79,49%/62,00% trên 150 mẫu	EXP-E2E-01	Bảng 4.8	`benchmarks/results/uit-viquad-2_e2e_150.json`	`Measured`

C-003	VN-FC tool match 98%, EM 93% trên 100 mẫu	EXP-AGT-01	Bảng 4.10	`benchmarks/results/vietnamese_function_calling_nvidia_deepseek_100.json`	`Measured`

C-004	When2Call accuracy 66,67% trên 60 mẫu phân tầng	EXP-AGT-01	Bảng 4.10	`benchmarks/results/when2call_nvidia_deepseek_stratified60.json`	`Measured`

C-005	[NLI: chờ chạy lại full 2.091 trên GPU]	EXP-NLI-01	Bảng 4.11	`benchmarks/results/viwikifc_nli_dual_smoke6.json` (pipeline check, N=6)	Chưa đo

PHỤ LỤC B. CẤU HÌNH HỆ THỐNG

```yaml

system_version: "0.7.1b1 (Docker images YUXI_VERSION=0.7.1)"

commit_sha: "bc2cb62d (phase2-viquad-benchmark; runs dùng đúng working tree này)"

chunking:

  strategy: "[CẦN BỔ SUNG từ config thực tế]"

  chunk_size: null

  overlap: null

embedding:

  provider: "[CẦN BỔ SUNG — dense arms đang Blocked]"

  model: "[CẦN BỔ SUNG]"

  dimensions: null

retrieval:

  top_k: 5 (E2E) / 10 (VieQuAD BM25)

  fusion: "[BM25 standalone cho các run đã đo; weighted/rrf chưa chạy]"

reranker:

  model: "[CẦN BỔ SUNG — chưa chạy]"

nli:

  model: "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7 (CPU, transformers zero-shot pipeline)"

  threshold: "production path: entailment > 0.6, neutral > 0.3 (xem nli_verifier.py:226)"

agent:

  max_steps: null

llm_runs:

  model: "nvidia:deepseek-ai/deepseek-v4.1-flash (https://integrate.api.nvidia.com/v1)"

  temperature: 0

  max_tokens: "1024 (agent) / 4096 (E2E; bắt buộc vì reasoning tokens ăn budget)"

  timeout_s: 180

measurement_machine: "Intel i7-10850H 6 cores, RAM 15.6GB, CPU-only, Windows + Docker"

```

PHỤ LỤC C. ARTIFACT INDEX

Artifact	Exp ID	SHA-256	Vị trí	Mô tả

viequad_bm25_validation.json	EXP-RET-01	—	`benchmarks/results/`	BM25 full 2.048 queries (R@10 91,80%)

uit-viquad-2/queries.jsonl + corpus.jsonl + manifest.json	EXP-E2E-01	926fcf2e… / 57127d17… (xem manifest)	`benchmarks/artifacts/e2e/uit-viquad-2/`	E2E sample 150 (seed 42), corpus 557 docs

uit-viquad-2_e2e_150.json	EXP-E2E-01	—	`benchmarks/results/`	EM 45,33%, abstention P/R 79,49%/62,00%

vietnamese_function_calling_nvidia_deepseek_100.json	EXP-AGT-01	—	`benchmarks/results/`	Tool 98%, EM 93% (merge smoke20 + rows20_100)

when2call_nvidia_deepseek_stratified60.json	EXP-AGT-01	—	`benchmarks/results/`	Accuracy 66,67% (20/class)

agent_contract_validation.json	EXP-AGT-01	—	`benchmarks/results/`	2.899 + 3.652 records hợp lệ

usage_log.jsonl	EXP-SYS-01	—	`benchmarks/results/`	Calls/tokens từng run có guard (không ước tính token)

viwikifc_nli_dual_2091.json	EXP-NLI-01	—	`benchmarks/results/`	Đang chạy (dual-config × 2.091 cặp)

Ghi chú: result/artifact dưới `benchmarks/` bị gitignore theo thiết kế; tái tạo bằng command trong §4.5 + dataset revision trong `source-lock.json`.

PHỤ LỤC D. CHECKLIST TRƯỚC KHI NỘP

[ ] Đã thay toàn bộ placeholder `[CẦN BỔ SUNG]`.

[ ] Không còn bảng kết quả `Missing`, trừ nội dung được công bố là giới hạn.

[ ] Mỗi số liệu có raw artifact và command tái lập.

[ ] Grid search chỉ sử dụng validation set.

[ ] Test set chỉ dùng cho đánh giá cuối.

[ ] Mọi metric có định nghĩa và quy tắc chuẩn hóa.

[ ] NLI có gold labels và confusion matrix.

[ ] Agent suite có expected tools và arguments.

[ ] E2E p95 được đo trực tiếp.

[ ] Các tuyên bố định lượng dùng đúng điểm phần trăm và phần trăm tương đối.

[ ] Tên “multi-agent” phù hợp với kiến trúc thực tế.

[ ] Bảng, công thức, hình và trích dẫn hiển thị đúng.

[ ] Đã tạo danh mục hình, bảng và từ viết tắt.

[ ] Đã kiểm tra chính tả và tính thống nhất thuật ngữ.

[ ] PDF cuối đã được kiểm tra từng trang.