# Lộ trình phát triển

Lộ trình có thể thay đổi thường xuyên，Nếu bạn có đề xuất mạnh mẽ，Có thể tìm thấy ở [issue](https://github.com/xerrors/Yuxi/issues) trung ti。

Thông số bổ sung nhật ký（For Agent）:


### Kanban

**cơ sở tri thức**
- [ ] Công cụ cơ sở kiến thức mới query_keywords Công cụ，Được thiết kế đặc biệt để xếp hạng dựa trên lượt truy cập từ khóa <Badge text="v0.7.1" />
- [ ] Nghiên cứu tính khả thi của việc ánh xạ cơ sở tri thức hiện tại vào hệ thống tệp ảo，Đầu tiên làm rõ bản đồ cây tập tin、ranh giới cho phép、Đọc nội dung và Agent Biểu mẫu gọi công cụ，Sau đó quyết định có nên thực hiện nó hay không
- [ ] Nâng cao trải nghiệm tìm kiếm cơ sở kiến thức：nâng cao metadata、Thẻ, v.v.
- [ ] Thêm mới dựa trên PaddleOCR người phân tích cú pháp：Truy cập PaddleOCR-VL-1.6、PP-OCRv6、PP-StructureV3，Và các lớp cơ sở được chia sẻ trừu tượng để sử dụng lại các lệnh gọi tập lệnh tương tự、Thu thập sản phẩm và xử lý cấu hình
- [ ] Không gian làm việc cá nhân tăng khả năng tìm kiếm（Nhưng không có vector hóa） <Badge text="v0.7.1" />


**đại lý**
- [x] Đại lý phụ thiếu cơ chế không đồng bộ <Badge text="v0.7.1" /> <Badge type="warning" text="Đang được phát triển" />
- [ ] Thiếu đại lý phụ steer cơ chế <Badge text="v0.7.1" />
- [ ] Giao tiếp hai chiều của các đại lý phụ，mất tích ask_for_main_agent cơ chế
- [ ] Cơ chế giao tiếp giữa đại lý phụ và đại lý phụ
- [ ] Tối ưu hóa Agent `read_file` Công cụ：Căn chỉnh ít nhất DeepAgents đọc hành vi
- [ ] Skill Hiển thị nâng cao khả năng ràng buộc trên trang chi tiết：Tích hợp sẵn Skill Các công cụ chỉ đọc cũng phải được hiển thị rõ ràng/MCP/Skill Mô tả phụ thuộc
- [x] thêm Agent Giao diện gọi độc lập，Thuận tiện cho việc đánh giá và sử dụng tiếp theo
- [ ] hàng đợi nhiệm vụ <Badge text="v0.7.2" />
- [x] Truy cập phản hồi vào Langfuse

**Khác**
- [x] Khả năng tìm kiếm mới cho các cuộc hội thoại lịch sử（[#790](https://github.com/xerrors/Yuxi/issues/790)）
- [x] Thêm nút sao chép nhanh vào khối mã trong tin nhắn（[#790](https://github.com/xerrors/Yuxi/issues/790)）
- [ ] Tích hợp Memory，Dựa trên deepagents Triển khai phụ trợ tệp，Cần cân nhắc việc định vị
- [x] Tối ưu hóa Task Định vị mô-đun：Phân biệt giữa các thực thể tác vụ nền thực và các công cụ quản lý thanh tiến trình，Xác định lại trung tâm truyền giáo/Tasker Ranh giới trách nhiệm
- [x] Các loại hình nhà cung cấp kiểu mẫu tiếp tục bổ sung cho các nhà cung cấp không OpenAI Thích ứng tương thích，và dọn dẹp những thứ không còn được hỗ trợ provider type lời nói <Badge text="v0.7.1" />
- [ ] Tối ưu hóa Agent Hỏi người dùng về tương tác：Hỗ trợ nhập câu trả lời văn bản dài hơn，và luôn cập nhật khu vực trò chuyện trong khi phát trực tiếp đầu ra（[#753](https://github.com/xerrors/Yuxi/issues/753)）

**Chỉ cần tưởng tượng**
- [ ] Yuxi CLI Thêm lệnh quản lý，Sẽ được triển khai ở các phiên bản tiếp theo（Không giống như một trợ lý lập trình，Đó là một công cụ nền tảng quản lý，Đợi từng người router Sau khi tối ưu hóa giao diện）


### Bugs
- [ ] Hình ảnh trong cơ sở kiến ​​thức hiện tại có nguy cơ bị truy cập công khai
- [ ] Khi nhấp vào một cuộc trò chuyện, bạn cần có khả năng tự động định vị cuộc trò chuyện đó ở cuối.，thay vì sự khởi đầu。

---

Hồ sơ phát hành phiên bản lịch sử đã được di chuyển sang [Lịch sử thay đổi phiên bản](./changelog.md)。

Hướng dẫn bảo trì：
- roadmap Chỉ giữ lại những kế hoạch tương lai（Kanban/Bugs/hướng cột mốc）。
- Nội dung phát hành phiên bản cụ thể được duy trì thống nhất trong changelog。
