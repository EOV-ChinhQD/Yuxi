# Thông số thiết kế giao diện

Tài liệu này định nghĩa Yuxi Thông số thiết kế cơ bản cho giao diện front-end，Áp dụng cho `web/src` trang mới bên dưới、Các thành phần mới và hiện có UI điều chỉnh。Nó nhắm đến cả các nhà phát triển con người và AI coding agent：Đọc trang này trước khi sửa đổi giao diện，Ưu tiên tái sử dụng các thành phần hiện có、CSS Các biến và chế độ tương tác。

## 1. khí chất thị giác

Yuxi là một cơ sở kiến thức、Sơ đồ tri thức và Agent Nền tảng phát triển，Giao diện nên được hạn chế、rõ ràng、Kỹ thuật。Được thiết kế để đọc nhiều giờ、Cấu hình、Gỡ lỗi và quản lý dữ liệu，Không trang trí trang tiếp thị。

nguyên tắc cốt lõi：

- Chức năng đầu tiên：Hệ thống phân cấp trực quan giúp người dùng hiểu nhiệm vụ、Trạng thái và các bước tiếp theo，Đừng hy sinh mật độ thông tin để trang trí。
- ưu tiên nhất trí：Các chức năng tương tự sử dụng cùng một bố cục、Màu sắc、Phản hồi trạng thái và tương tác。
- Nhẹ đầu tiên：Sử dụng nền、biên giới、Cỡ chữ và khoảng trắng tạo nên thứ bậc，tránh bóng tối nặng nề、Độ dốc quá mức và hình ảnh động không có chức năng。
- Bảo trì đầu tiên：Phong cách mới phải dựa trên phong cách hiện có token và mẫu thành phần，Không giới thiệu một hệ thống thiết kế mới cho một yêu cầu duy nhất。

## 2. Màu sắc và Token

Màu sắc phải được sử dụng đầu tiên `web/src/assets/css/base.css` và `web/src/assets/css/base.dark.css` được định nghĩa trong CSS biến。Không tùy tiện thêm các giá trị màu hardcode vào thành phần；Khi bạn thực sự cần thêm giá trị màu chung，Bổ sung đầu tiên token và giải thích công dụng。

### màu chủ đạo

`--main-*` và `--main-color` Được sử dụng cho màu sắc chính của thương hiệu và các tương tác chính：

| Token | kịch bản sử dụng |
| --- | --- |
| `--main-color` | nút chính、Trạng thái đã chọn、Liên kết chính、biểu tượng chìa khóa |
| `--main-700` / `--main-600` / `--main-500` | Văn bản màu chính、hover、active、Nhấn mạnh vào trạng thái |
| `--main-50` / `--main-30` / `--main-10` | Nền sáng màu chủ đạo、Nền hàng đã chọn、Nền nhắc nhở nhẹ |

Màu sắc chủ đạo chỉ dùng để biểu đạt“Lựa chọn hiện tại、Hoạt động chính、lối vào chính”。Không sử dụng màu chủ đạo làm màu trang trí thông thường trên thiệp hoặc nền có diện tích lớn。

### màu sắc trung tính

`--gray-*` Là bộ khung giao diện mặc định，cho nền、văn bản、Biên giới và đường phân chia：

| Token | kịch bản sử dụng |
| --- | --- |
| `--gray-0` | Nền chính của trang và thẻ |
| `--gray-10` / `--gray-25` / `--gray-50` | bối cảnh thứ cấp、hover nền、Nền phân vùng yếu |
| `--gray-100` / `--gray-150` / `--gray-200` | đường phân chia、Đường viền hộp nhập liệu、biên giới thẻ |
| `--gray-900` / `--gray-1000` | Tiêu đề và văn bản chính |
| `--gray-600` / `--gray-500` / `--gray-400` | Hướng dẫn phụ trợ、văn bản giữ chỗ、Tắt văn bản |

Văn bản cũng có thể được sử dụng Ant Design Tương thích với các biến ngữ nghĩa：`--color-text`、`--color-text-secondary`、`--color-text-tertiary`。Thích các biến ngữ nghĩa trong các thành phần；Sử dụng nó khi bạn cần một mức độ chi tiết hơn `--gray-*`。

### màu sắc ngữ nghĩa

Màu ngữ nghĩa chỉ được sử dụng cho trạng thái và phản hồi，Không dùng để trang trí：

| Token nhóm | kịch bản sử dụng |
| --- | --- |
| `--color-success-*` | sự thành công、Đã hoàn thành、Kết nối vẫn bình thường |
| `--color-error-*` | Lỗi、Hoạt động nguy hiểm、Xóa、thất bại |
| `--color-warning-*` | cảnh báo、Đang chờ xử lý、Cần chú ý nhưng không thất bại |
| `--color-info-*` | Lời nhắc thông tin、trạng thái mô tả |
| `--color-accent-*` | Một lượng nhỏ sự nhấn mạnh phụ trợ，Không thể thay thế màu chính |

Nên sử dụng nền sáng cho nhãn trạng thái + văn bản sâu，Ví dụ `background: var(--color-success-50); color: var(--color-success-700);`。Đừng chỉ dựa vào màu sắc để truyền đạt trạng thái，Sử dụng văn bản hoặc biểu tượng khi cần thiết。

### màu biểu đồ

Ưu tiên biểu đồ và trực quan hóa thống kê `--chart-palette-*`。Đừng sử dụng lại màu sai、Màu cảnh báo để phân loại biểu đồ chung，Tránh nhầm lẫn với phản hồi trạng thái。

### chế độ tối

Yuxi Vượt qua `:root.dark` Ghi đè cùng tên token。Mới UI Phải sử dụng CSS Giá trị ánh sáng thay đổi thay vì cố định，và kiểm tra màu sáng、Hai bộ màu tối。

Khi thêm một thành phần, hãy kiểm tra ít nhất：

- nền、thẻ、Hộp đầu vào không xuất hiện với màu tối do mã hóa cứng màu trắng tinh.。
- Văn bản và đường viền vẫn có đủ độ tương phản ở chế độ tối。
- hover、focus、disabled、selected、error v.v. các trạng thái hiển thị ở chế độ tối。
- biểu đồ、Các khối mã và thành phần của bên thứ ba cần được chuyển vào một cách rõ ràng theme thời gian，sử dụng `useThemeStore()` mô hình hiện có。

## 3. Phông chữ và cấp độ văn bản

Ngăn xếp phông chữ chung được xác định trong `web/src/assets/css/main.css`，Khi thêm thành phần mới, không giới thiệu phông chữ mới một cách riêng tư。mã、lệnh、Đường mòn và dấu hiệu kỹ thuật có sẵn monospace，Ưu tiên tái sử dụng những gì hiện có `@mono-font` hoặc hệ thống monospace chồng。

Mức độ đề xuất：

| vai trò | Kiểu được đề xuất | kịch bản sử dụng |
| --- | --- | --- |
| Tiêu đề trang | 20-24px，600 | Tiêu đề chính của trang、Tiêu đề chính của cửa sổ bật lên |
| Tiêu đề nhóm | 16-18px，600 | tiêu đề thẻ、Tiêu đề nhóm biểu mẫu |
| văn bản | 14-15px，400 | Hướng dẫn chung、Liệt kê nội dung |
| Hướng dẫn phụ trợ | 12-13px，400 | helper text、Thông tin meta、thời gian、Mô tả thống kê |
| nhãn/Trạng thái | 12px，500 | tag、chip、biểu tượng trạng thái |
| mã/con đường | 12-14px，monospace | đường dẫn tập tin、lệnh、đoạn mã |

đặc tả văn bản：

- Giữ tiêu đề ngắn gọn，Ưu tiên mô tả đối tượng，Đừng viết khẩu hiệu tiếp thị。
- Sử dụng các hành động rõ ràng trong bản sao nút，Chẳng hạn như“Lưu cấu hình”“Kiểm tra lại”“Xóa tập tin”。
- Những hoạt động nguy hiểm phải cho phép người viết quảng cáo trực tiếp bày tỏ hậu quả，Chẳng hạn như“Xóa cơ sở kiến thức”。
- Không được sử dụng placeholder hình thức thay thế label；placeholder Ví dụ đầu vào duy nhất。
- Không sử dụng phông chữ kerning âm hoặc tỷ lệ cho chiều rộng khung nhìn，Tránh bố cục không kiểm soát được ở màn hình rộng và nhỏ。

## 4. Kiểu thành phần

### Hạn chế về ngăn xếp công nghệ

- Trình quản lý gói：`pnpm`
- Thư viện biểu tượng：ưu tiên sử dụng `lucide-vue-next`
- phong cách ngôn ngữ：LESS
- biến màu：sử dụng `base.css` / `base.dark.css` trong CSS biến
- UI Khái niệm cơ bản：Tái sử dụng Ant Design Vue và dự án các mẫu thành phần hiện có，Tránh đóng gói các hệ thống thành phần mới cho các nhu cầu đơn lẻ

### nút

Các nút phải được phân biệt theo mức độ ưu tiên hành động：

| Loại | kịch bản sử dụng | quy tắc phong cách |
| --- | --- | --- |
| nút chính | Hoạt động chính của trang、Xác nhận gửi | Sử dụng nền màu chính hoặc Ant Design primary，Không đặt nhiều nút home ở cùng một khu vực |
| nút phụ | Trở lại、Hủy bỏ、Hoạt động bình thường | Sử dụng đường viền trung tính và nền sáng，hover Chỉ tăng cường đường viền hoặc nền |
| văn bản/nút liên kết | Các thao tác về hàng trong bảng、Lối vào nhẹ | Giữ nó nhẹ，Không mở rộng trọng lượng thị giác |
| nút nguy hiểm | Xóa、Hủy bỏ、Các hoạt động không thể đảo ngược như thanh toán bù trừ | sử dụng error màu sắc ngữ nghĩa，Và hợp tác với cửa sổ bật lên xác nhận hoặc bản sao rõ ràng |
| nút biểu tượng | Thanh công cụ、gấp lại、Làm mới、Sao chép | sử dụng `lucide-icon-btn` Đảm bảo biểu tượng và văn bản được căn giữa |

trạng thái tương tác：

- hover có thể thay đổi `background`、`border-color`、`color`，Không di chuyển hoặc phóng to。
- focus phải được nhìn thấy，Không thể xóa kiểu tiêu điểm bàn phím。
- disabled Sử dụng văn bản và nền yếu，Không bị ràng buộc hover phản hồi mạnh mẽ。
- loading Chiều rộng nút nên được giữ nguyên，Tránh nhảy bố cục。

### Hộp và biểu mẫu đầu vào

Các biểu mẫu cho nhiệm vụ cấu hình và quản lý，Ưu tiên khả năng đọc và phục hồi lỗi：

- Cách sử dụng nền của hộp nhập liệu `--gray-0` hoặc Ant Design Màu vùng chứa mặc định。
- Sử dụng đường viền `--gray-150` / `--gray-200`，focus Sử dụng màu chính hoặc khung mặc định focus ring。
- label Phải hiển thị ổn định，helper text Đặt nó bên dưới hộp nhập liệu。
- Sử dụng thông báo lỗi `--color-error-*`，Và ghi rõ cách khắc phục。
- Các biểu mẫu nhiều trường được nhóm lại một cách hợp lý，Tránh nhồi nhét các cài đặt không liên quan vào cùng một dòng。

### thẻ、Danh sách và bảng

Yuxi giao diện thông tin để cấu hình thẻ、Chủ yếu là danh sách và bảng，Sử dụng phân lớp nhẹ theo mặc định：

- Thẻ thông thường：`background: var(--gray-0); border: 1px solid var(--gray-150); border-radius: 8px;`
- tiểu vùng：Có sẵn `var(--gray-10)` / `var(--gray-25)` làm nền sáng。
- Bấm vào hàng danh sách：hover Chỉ thay đổi nền hoặc đường viền，Không được sử dụng `transform`。
- Giữ cho các hoạt động của hàng trong bảng được nhỏ gọn，Tránh nhiều nút có trọng số cao trên mỗi hàng。
- Trạng thái trống cần được giải thích“Không có gì vào lúc này”và“Có thể làm gì tiếp theo?”，Đừng chỉ hiển thị các biểu tượng。

Bóng chỉ được sử dụng cho lớp phủ thực，Chẳng hạn như cửa sổ bật lên、ngăn kéo、trình đơn thả xuống、tooltip。Đừng sử dụng bóng để tạo các lớp trang trí trên các tấm thiệp và danh sách thông thường。

### nhãn trạng thái

Nhãn trạng thái sử dụng nền sáng màu ngữ nghĩa + văn bản sâu：

| Trạng thái | Được đề xuất token |
| --- | --- |
| sự thành công/bình thường | `--color-success-50` + `--color-success-700` |
| thất bại/Lỗi | `--color-error-50` + `--color-error-700` |
| cảnh báo/Đang chờ xử lý | `--color-warning-50` + `--color-warning-900` |
| thông tin/Đang chạy | `--color-info-50` + `--color-info-700` |
| Bình thường/không rõ | `--gray-100` + `--gray-600` |

Thẻ có thể được sử dụng pill góc tròn，Nhưng đừng đặt pill Hình dạng trải rộng đến tất cả các nút và thẻ。

### biểu tượng

- Sử dụng kích thước biểu tượng thông thường 16px、18px hoặc 20px。
- Màu biểu tượng kế thừa màu văn bản theo mặc định；Sử dụng ngữ nghĩa khi cần nhấn mạnh token。
- Đã thêm nút biểu tượng `lucide-icon-btn`，Tránh căn chỉnh sai các biểu tượng và đường trung tâm của văn bản hoặc nút。
- Không trộn lẫn nhiều biểu tượng cho cùng một concept；Hoạt động tương tự vẫn nhất quán trên các trang khác nhau。

## 5. bố cục và khoảng cách

Khoảng cách là 4px / 8px như nhịp điệu cơ bản：

| bối cảnh | Giá trị đề xuất |
| --- | --- |
| Khoảng cách biểu tượng và văn bản | 6px / 8px |
| Khoảng cách nội bộ của mục biểu mẫu | 6px / 8px |
| Bên trong thẻ padding | 16px / 20px / 24px |
| khoảng cách dòng danh sách | 8px / 12px |
| Khoảng cách khối chính của trang | 24px / 32px |
| Khoảng cách vùng nội dung của cửa sổ bật lên | 16px / 24px |

Nguyên tắc bố cục：

- Các trang cấu hình duy trì mật độ thông tin vừa phải，Đừng để những khoảng trống theo phong cách tiếp thị quy mô lớn。
- Các thao tác liền kề gần với nội dung tương ứng，Các thao tác cấp trang được đặt trong khu vực tiêu đề hoặc thanh công cụ。
- Hành động chính trong một bộ nút là rõ ràng nhất，Hủy bỏ/Trở lại trạng thái hoạt động bình thường。
- Giới hạn độ dài văn bản trong màn hình rộng，Tránh chú thích kéo dài toàn bộ trang。
- Ưu tiên xếp chồng dọc trên màn hình nhỏ，Tránh việc ép buộc các bảng và trường biểu mẫu。

## 6. Độ sâu và cấp độ

Yuxi Được sử dụng theo mặc định“nền + biên giới”mức độ nhẹ：

| Hệ thống phân cấp | Phương pháp xử lý | kịch bản sử dụng |
| --- | --- | --- |
| Nền trang | `var(--gray-0)` Hoặc bố cục đã có nền | Trang chính |
| bối cảnh thứ cấp | `var(--gray-10)` / `var(--gray-25)` | Phân vùng、gợi ý yếu、danh sách hover |
| biên giới thẻ | `1px solid var(--gray-150)`，8px góc tròn | Cấu hình thẻ、khối nội dung |
| lớp nổi | Tạo bóng hoặc ánh sáng mặc định trong khung `--shadow-*` | Cửa sổ bật lên、ngăn kéo、dropdown、tooltip |
| tiêu điểm | màu chủ đạo outline / Ant Design focus ring | Điều khiển có thể truy cập bằng bàn phím |

Không sử dụng bóng đậm trên thẻ nội dung thông thường。Chỉ khi phần tử thực sự bao gồm nội dung khác、Khi cần thể hiện mối quan hệ của lớp nổi，Bóng tối chỉ được phép。

## 7. Do / Don't

### Do

- sử dụng `base.css` và `base.dark.css` trong token。
- Hoàn thành cho các tương tác mới hover、focus、disabled、loading、empty、error Đang chờ trạng thái cần thiết。
- Sử dụng nền、biên giới、Cỡ chữ、Khoảng cách tạo ra thứ bậc。
- Luôn có sẵn các chế độ sáng và tối。
- Tái sử dụng `lucide-vue-next`、Ant Design Vue Và dự án đã có chế độ thành phần。
- Giữ mô tả ngắn gọn trong các khu vực cấu hình phức tạp，Giúp người dùng hiểu tác động của cài đặt。

### Don't

- Đừng ở đây hover Sử dụng sự dịch chuyển khi、Phóng to、Trang trí như xoay transform。
- Đừng sử dụng bóng đậm để trang trí những tấm thiệp đơn giản。
- Không sử dụng độ dốc quá mức hoặc diện tích lớn có nền có độ bão hòa cao。
- Không sử dụng màu sắc ngữ nghĩa cho mục đích trang trí đơn thuần。
- Không thêm một lần helper、Hệ thống kiểu hoặc trừu tượng không có giá trị tái sử dụng。
- Không mã hóa cứng các giá trị màu của chế độ sáng khiến chế độ tối bị lỗi。
- Không đặt nhiều hoạt động chính có trọng lượng hình ảnh bằng nhau trong cùng một khu vực。

## 8. Hành vi đáp ứng

Thiết kế đáp ứng với“Không mất chức năng、Thông tin không bị ép”ưu tiên：

- Sắp xếp theo chiều dọc các trường biểu mẫu trên màn hình nhỏ，Nhóm nút có thể quấn。
- thanh bên、Ngăn kéo và cửa sổ bật lên phải đảm bảo nội dung trong phạm vi chiều rộng tối thiểu có thể đọc được。
- Bảng cho phép cuộn ngang trên màn hình nhỏ；Đừng nén các trường khóa cho đến khi chúng không thể đọc được。
- Các nút biểu tượng và hành động chính cần phải là khu vực có thể nhấp vào，Kích thước mục tiêu trên thiết bị di động không được nhỏ hơn 40px。
- Khi sử dụng dấu chấm lửng cho văn bản dài，nên được cung cấp tooltip、title Hoặc vào cổng thông tin chi tiết để xem đầy đủ nội dung。
- tập bản đồ、biểu đồ、Nội dung đơn băng thông của khối mã phải duy trì các chiến lược cuộn ngang hoặc chia tỷ lệ thích ứng。

## 9. Agent Prompt Guide

AI agent sửa đổi hoặc tạo ra Yuxi UI thời gian，Ưu tiên phần này。

### Quick Reference

- Nền trang：`var(--gray-0)`
- bối cảnh thứ cấp：`var(--gray-10)` / `var(--gray-25)`
- văn bản chính：`var(--color-text)` hoặc `var(--gray-900)`
- văn bản phụ：`var(--color-text-secondary)` hoặc `var(--gray-600)`
- biên giới：`var(--gray-150)` / `var(--gray-200)`
- màu chủ đạo：`var(--main-color)`
- Thẻ được bo tròn các góc：`8px`
- Các góc bo tròn có điều khiển nhỏ：`4px` / `6px`
- nhãn trạng thái góc tròn：`999px`
- Kích thước biểu tượng thông thường：`16px` / `18px` / `20px`
- thẻ padding：`16px` / `20px` / `24px`
- Bình thường hover：Chỉ thay đổi nền、Màu đường viền hoặc văn bản

### Example Prompts

Triển khai thẻ cấu hình：

```text
thực hiện một Yuxi Thẻ cấu hình phong cách：sử dụng nền var(--gray-0)，biên giới 1px solid var(--gray-150)，góc tròn 8px，không có bóng。Cách sử dụng tiêu đề var(--color-text)，Cách sử dụng văn bản mô tả var(--color-text-secondary)。hover Chỉ thay đổi một chút đường viền hoặc nền，Không được sử dụng transform。
```

Triển khai các nút trên thanh công cụ：

```text
Triển khai nút thanh công cụ：ưu tiên sử dụng lucide-vue-next biểu tượng，kích thước biểu tượng 16px，nút thêm lucide-icon-btn。Sử dụng màu trung tính theo mặc định，hover được sử dụng khi var(--main-color) hoặc var(--main-10) Tăng cường，Không có sự dịch chuyển、Đừng phóng to。
```

Triển khai nhãn trạng thái：

```text
Triển khai nhãn trạng thái：sử dụng thành công var(--color-success-50) nền và var(--color-success-700) văn bản；sử dụng không đúng cách var(--color-error-50) nền và var(--color-error-700) văn bản；Cảnh báo sử dụng var(--color-warning-50) nền và var(--color-warning-900) văn bản。Sử dụng các góc bo tròn 999px，Văn bản vẫn còn 12px。
```

### Danh sách kiểm tra thực hiện

- Sử dụng hiện có CSS biến，Không có giá trị màu mã hóa cứng tùy ý mới。
- Đã kiểm tra cả chế độ sáng và tối。
- hover、focus、disabled、loading、empty、error Trạng thái phù hợp với kịch bản。
- không được sử dụng hover Sự dịch chuyển、Phóng to、Hoạt hình xoay hoặc trang trí。
- Thẻ thông thường không sử dụng bóng đậm。
- biểu tượng từ `lucide-vue-next`，Kích thước và căn chỉnh phù hợp với lược đồ hiện có。
- API giao diện、Vị trí thành phần、Ngôn ngữ phong cách tuân thủ các thông số kỹ thuật phát triển front-end。

## Tài liệu tham khảo

- `web/src/assets/css/base.css`：chế độ ánh sáng token
- `web/src/assets/css/base.dark.css`：chế độ tối token
- `web/src/assets/css/main.css`：phông chữ toàn cầu、Bố cục kiểu cơ bản và `lucide-icon-btn`
- [Awesome DESIGN.md](https://github.com/VoltAgent/awesome-design-md)：cho AI agent của `DESIGN.md` Bộ sưu tập mẫu
