<div align="center">
<h1>Phân tích ngôn ngữ Yuxi</h1>

<p><strong>nhiều người thuê nhà Harness + Cơ sở tri thức doanh nghiệp</strong><br/>Làm cho các đại lý có thể truy xuất được kiến thức doanh nghiệp、Lý luận và giao hàng</p>

[![](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=ffffff)](https://github.com/xerrors/Yuxi/blob/main/docker-compose.yml)
[![](https://img.shields.io/github/issues/xerrors/Yuxi?color=F48D73)](https://github.com/xerrors/Yuxi/issues)
[![License](https://img.shields.io/github/license/bitcookies/winrar-keygen.svg?logo=github)](https://github.com/xerrors/Yuxi/blob/main/LICENSE)
[![DeepWiki](https://img.shields.io/badge/DeepWiki-blue.svg)](https://deepwiki.com/xerrors/Yuxi)
[![Bilibili](https://img.shields.io/badge/Bản demo cơ sở kiến thức-00A1D6?logo=bilibili&logoColor=fff)](https://www.bilibili.com/video/BV1erE26iEgv/?share_source=copy_web&vd_source=37b0bdbf95b72ea38b2dc959cfadc4d8)


<a href="https://trendshift.io/repositories/24335" target="_blank"><img src="https://trendshift.io/api/badge/repositories/24335" alt="xerrors%2FYuxi | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>

[[Tài liệu dự án]](https://xerrors.github.io/Yuxi) · [[Đặc điểm phiên bản]](http://xhslink.com/o/5Y6QWnmjF2d) · [[🇬🇧 English README]](README.en.md)

</div>

![arch](https://xerrors.oss-cn-shanghai.aliyuncs.com/github/arch.png)

## Giới thiệu

Phân tích ngôn ngữ（Yuxi）Nó là một nền tảng phát triển tác nhân đồ thị tri thức và cơ sở tri thức thông minh dựa trên các mô hình lớn.。nó đặt **RAG Tìm kiếm**、**Milvus Sơ đồ tri thức trong cơ sở tri thức** với **LangGraph Điều phối đa tác nhân** Được tích hợp vào một bàn làm việc nhiều người thuê thống nhất：Cơ sở kiến thức cấu hình quản trị viên、Mô hình và quyền，Người dùng trong lớp ChatGPT Giao diện và có thể gắn kết Skills、MCP、Đối thoại đại lý giữa đại lý phụ và công cụ hộp cát，và lấy nguồn có trích dẫn、Lập luận về biểu đồ tri thức và các câu trả lời về sản phẩm có thể phân phối được。

Điều hướng：[Giới thiệu dự án](https://xerrors.github.io/Yuxi/) ｜ [bắt đầu nhanh](https://xerrors.github.io/Yuxi/intro/quick-start) ｜ [Lộ trình phát triển](https://xerrors.github.io/Yuxi/develop-guides/roadmap) | [0.7 Đặc điểm phiên bản](http://xhslink.com/o/5Y6QWnmjF2d)；Tin tức phát triển mới nhất，Xem chi tiết [changelog](https://xerrors.github.io/Yuxi/develop-guides/changelog)。

🩷 Nhà tài trợ

<table>
  <tr>
    <td style="width: 220px; padding: 8px 12px 8px 8px; vertical-align: middle;">
      <img 
        width="220" 
        height="64" 
        alt="7fb163d0fb02740948521dbcaf6191ea" 
        src="https://xerrors.oss-cn-shanghai.aliyuncs.com/github/image-20260623195812766.png"
      />
    </td>
    <td style="padding: 8px 8px 8px 0; vertical-align: middle;">
      <p style="margin: 0 0 4px 0;">
        Cảm ơn <a href="https://sui-xiang.com/">Những suy nghĩ ngẫu nhiênAIcửa ngõ</a > Tài trợ cho dự án này！
        Những suy nghĩ ngẫu nhiênAIcửa ngõ Đây là một công ty đáng tin cậy và hiệu quả API Nhà cung cấp dịch vụ chuyển tiếp，cung cấp Claude、Codex、Gemini dịch vụ chuyển tiếp。Một trung tâm chuyển tiếp tập trung vào quyền riêng tư·Không bán lại dữ liệu·Không có mô hình trộn với nước，Quyền riêng tư，Minh bạch，Dịch vụ hậu mãi cực kỳ nhanh chóng。Đăng ký tài khoản mới và nhận quà miễn phí nếu bạn đăng nhập mỗi ngày 0.5 Số tiền kiểm tra meta，Số tiền nạp 1:1，Không cần đăng ký，Thanh toán khi bạn đi。
      </p >
    </td>
  </tr>
</table>

![image-20260606190609377](https://xerrors.oss-cn-shanghai.aliyuncs.com/github/image-20260606235615139.png)

## ngăn xếp công nghệ

| lớp | Công nghệ |
| --- | --- |
| giao diện người dùng | Vue 3 · Vite · Pinia |
| phụ trợ | FastAPI · LangGraph · ARQ (không đồng bộ worker) |
| lưu trữ | PostgreSQL · Redis · MinIO · Milvus · Neo4j |
| Phân tích tài liệu | MinerU · PaddleX · RapidOCR |
| triển khai | Docker Compose |
## bắt đầu nhanh

**Điều kiện tiên quyết**：Đã cài đặt [Docker](https://docs.docker.com/get-docker/) với Docker Compose，và chuẩn bị ít nhất một cái tương thích OpenAI Mô hình giao diện lớn API。

**1. Sao chép mã và khởi tạo nó**

```bash
git clone --branch v0.7.0 --depth 1 https://github.com/xerrors/Yuxi.git
cd Yuxi

# Linux/macOS
./scripts/init.sh

# Windows PowerShell
.\scripts\init.ps1
```

**2. sử dụng Docker bắt đầu**

```bash
docker compose up --build
```

**3. nền tảng truy cập**

Đợi quá trình khởi động hoàn tất，Trình duyệt mở ra `http://localhost:5173`，Chỉ cần đăng nhập bằng tài khoản quản trị viên được tạo trong quá trình khởi tạo.。

> 💡 Không cần nền tảng kiến thức / Sơ đồ tri thức và các phụ thuộc nặng nề khác，Có sẵn `make up-lite` để LITE Bắt đầu ở chế độ ánh sáng，Tăng tốc độ khởi động nguội。Để biết thêm hướng dẫn triển khai, hãy xem [Tài liệu dự án](https://xerrors.github.io/Yuxi)。

## Lời cảm ơn

Dự án này đề cập đến và trích dẫn các dự án nguồn mở xuất sắc sau đây，Tôi xin gửi lời cảm ơn chân thành：

- [LightRAG](https://github.com/HKUDS/LightRAG) - Các phiên bản trước đó đã đề cập đến các ý tưởng xây dựng và truy xuất bản đồ của nó.；hiện tại Yuxi Tự nghiên cứu đã đạt được Milvus cơ sở tri thức/Liên kết đồ thị để thay thế tích hợp lịch sử，Giảm các vấn đề tương thích
- [DeepAgents](https://github.com/langchain-ai/deepagents) - Được giới thiệu trực tiếp dưới dạng khung tác nhân sâu
- [DeerFlow](https://github.com/bytedance/deer-flow) - tham khảo nó Sandbox Ý tưởng triển khai kiến trúc Agent thông minh
- [RAGflow](https://github.com/infiniflow/ragflow) - Đã tham khảo tài liệu của nó Text Chunking chiến lược phân chia
- [LangGraph](https://github.com/langchain-ai/langgraph) - Khung điều phối đa tác nhân，Nền tảng kiến trúc cốt lõi của dự án này
- [QwenPaw](https://github.com/agentscope-ai/QwenPaw) - Cấu hình mô hình tham chiếu và thiết kế vùng tệp cá nhân

## Tham gia và đóng góp

Cảm ơn tất cả những người đóng góp đã hỗ trợ！

<a href="https://github.com/xerrors/Yuxi/contributors">
  <img src="https://contrib.rocks/image?repo=xerrors/Yuxi&max=100&columns=10" />
</a>


## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=xerrors/Yuxi)](https://star-history.com/#xerrors/Yuxi)

## 📄 giấy phép

Dự án này sử dụng MIT giấy phép - Xem [LICENSE](LICENSE) Tài liệu để biết chi tiết。

---

<div align="center">

**Nếu dự án này hữu ích cho bạn，Xin đừng quên cung cấp cho chúng tôi một ⭐️**

</div>
