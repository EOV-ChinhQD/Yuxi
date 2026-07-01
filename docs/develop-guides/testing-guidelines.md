# Kiểm tra thông số kỹ thuật và quy trình làm việc

Tài liệu này nhằm mục đích hướng dẫn Yuxi Cách tạo file test sau、Sửa đổi tập tin thử nghiệm，và cách xác minh chức năng của dự án。Mục tiêu là thực dụng、ổn định、Có thể thực thi，Đừng theo đuổi thiết kế quá mức。

## 1. Kiểm tra lớp

Thử nghiệm hiện tại được chia thành ba lớp：

- `backend/test/unit`
  - Kiểm tra đơn vị thuần túy
  - Không phụ thuộc vào việc chạy Docker dịch vụ
  - ưu tiên sử dụng `monkeypatch`、fake repo、stub、`tmp_path`

- `backend/test/integration`
  - đúng API Kiểm tra tích hợp
  - phụ thuộc vào `docker compose up -d` Môi trường hoạt động cuối cùng
  - đoàn kết thông qua sự thật HTTP Xác thực xác minh giao diện、Quyền、Các thông số và tác dụng phụ

- `backend/test/e2e`
  - Kiểm tra toàn diện các liên kết quan trọng
  - Bìa run、viewer、Phụ kiện、Toàn bộ quá trình đặt tập tin vào đĩa
  - Số lượng mặc định là nhỏ、Thực hiện chậm hơn

## 2. Cách chọn thư mục khi thêm bài kiểm tra mới

Đánh giá trước khi thêm bài kiểm tra：

1. Chỉ kiểm tra Python logic，Không cần dịch vụ thực sự
   đưa vào `unit`

2. Cần yêu cầu giao diện thật
   đưa vào `integration/api`

3. Cần xác minh liên kết đầy đủ từ đầu vào đến kết quả cuối cùng
   đưa vào `e2e`

Đừng mặc định ném các bài kiểm tra trực tiếp vào `backend/test/` thư mục gốc。

## 3. Quy ước đặt tên và tập tin

tên tập tin：

- sử dụng `test_<domain>_<target>.py`
- Một tập tin chỉ kiểm tra một chủ đề rõ ràng

tên hàm：

- sử dụng `test_<hành vi>_<kết quả mong đợi>`
- Tên trực tiếp thể hiện ngữ nghĩa kinh doanh

Ví dụ：

- `test_create_agent_run_commits_before_enqueue`
- `test_viewer_download_returns_attachment_response`
- `test_agent_bubble_sort_run_creates_expected_artifacts`

## 4. Yêu cầu cơ bản khi viết bài kiểm tra

Cố gắng giữ mỗi bài kiểm tra trong ba giai đoạn：

1. Arrange：Chuẩn bị dữ liệu、đóng cọc、Tạo tài nguyên
2. Act：Gọi hành vi đang được kiểm tra
3. Assert：Khẳng định kết quả

yêu cầu：

- Đừng chỉ khẳng định `status_code == 200`
- Để khẳng định lĩnh vực kinh doanh trọng điểm và tác dụng phụ
- Thông tin lỗi sẽ giúp xác định vấn đề

## 5. fixture quy phạm

nguyên tắc：

- Tái sử dụng trong cùng một tập tin，Ưu tiên viết địa phương helper
- Tái sử dụng nhiều tập tin，Sau đó giải nén đến mức tương ứng `conftest.py`
- gốc `backend/test/conftest.py` Chỉ giữ chung marker，Không bị ràng buộc với môi trường thực tế

thỏa thuận hiện tại：

- `backend/test/integration/conftest.py`
  - quản lý `test_client`、`admin_headers`、`standard_user`、`knowledge_database`

- `backend/test/e2e/conftest.py`
  - quản lý `e2e_client`、`e2e_headers`、`e2e_agent_context`

## 6. Được phép và bị cấm

cho phép：

- Được sử dụng trong các bài kiểm tra đơn vị `monkeypatch`
- Đã vượt qua bài kiểm tra tích hợp fixture Tạo tài nguyên thử nghiệm
- trong E2E Sử dụng bỏ phiếu để chờ trạng thái cuối cùng

bị cấm：

- Mã hóa mật khẩu tài khoản thực trong tệp thử nghiệm
- Yêu cầu sự thật trong các bài kiểm tra đơn vị HTTP dịch vụ
- ở gốc `conftest.py` Tiếp tục thêm các phần phụ thuộc môi trường nặng vào đây
- viết `if __name__ == "__main__":` Là một lối vào thử nghiệm
- sử dụng `print` như đã thông qua/Phán xét thất bại có nghĩa là
- Vì trong hệ thống không có dữ liệu mặc định nên chỉ `skip`

## 7. skip Quy tắc sử dụng

Chỉ được phép trong hai trường hợp sau: `pytest.skip`：

1. Khả năng tùy chọn bên ngoài không có sẵn
   Ví dụ OCR dịch vụ、Dịch vụ mô hình bên ngoài chưa được bắt đầu

2. E2E Biến môi trường không được cấu hình
   Ví dụ: không có tài khoản thử nghiệm chuyên dụng nào được định cấu hình

không được phép“Không có trong hệ thống agent / config / Dữ liệu đặt trước”Hãy coi nó như bình thường skip Điều kiện。
Trong những trường hợp như vậy, nên thay đổi mức độ ưu tiên thành fixture Chuẩn bị nguồn lực rõ ràng，Hoặc trực tiếp fail tiếp xúc với các vấn đề môi trường。

## 8. Quy tắc sửa đổi tệp thử nghiệm

Nếu là sửa chữa bug：

1. Hãy tạo ra một cái đầu tiên để có thể tái tạo nó một cách ổn định bug kiểm tra
2. Sửa lại mã
3. Trước tiên hãy chạy bộ thử nghiệm tối thiểu có liên quan
4. Chạy lại hồi quy mức liên quan

Nếu bạn đang thay đổi một chức năng hiện có：

- hành vi đã thay đổi，Khẳng định về việc cập nhật
- Trách nhiệm tài liệu khó hiểu，Chỉ cần chia nhỏ hoặc di chuyển thư mục một cách dễ dàng
- Các thử nghiệm dựa trên trạng thái hệ thống hiện có，Ưu tiên thay đổi fixture Xây dựng tài nguyên

## 9. Chế độ hoạt động

Bắt đầu môi trường：

```bash
docker compose up -d
docker ps
docker logs api-dev --tail 100
```

Chạy thử nghiệm đơn vị：

```bash
docker compose exec api uv run --group test pytest test/unit -m "not slow"
```

Chạy thử nghiệm tích hợp：

```bash
docker compose exec api uv run --group test pytest test/integration
```

chạy E2E：

```bash
docker compose exec api uv run --group test pytest test/e2e -m e2e
```

Chạy tất cả các bài kiểm tra：

```bash
docker compose exec api uv run --group test pytest test
```

Cũng có thể được sử dụng：

```bash
backend/test/run_tests.sh unit
backend/test/run_tests.sh integration
backend/test/run_tests.sh e2e
backend/test/run_tests.sh all
```

## 10. Quy trình phát triển hàng ngày được đề xuất

Thứ tự đề xuất：

1. Thay đổi mã cục bộ
2. Trước tiên hãy chạy thử nghiệm đơn vị có liên quan
3. Chạy thử nghiệm tích hợp có liên quan khi có liên quan đến giao diện
4. Phản ứng bù đắp khi có liên quan đến các liên kết chính quan trọng E2E
5. Hoàn thành trước khi gửi ít nhất“Kiểm tra -> kiểm tra -> Lint”

## 11. Nguyên tắc thực hiện hiện hành

Mục đích của bộ thông số kỹ thuật này không phải là viết lại tất cả các bài kiểm tra cũ trong một lần.，đúng hơn：

- Các bài kiểm tra mới phải được đặt trong thư mục mới
- Dễ dàng di chuyển khi thay đổi sang các bài kiểm tra cũ
- Ưu tiên giữ cho các bài kiểm tra có thể thực thi được và đáng tin cậy
- Ưu tiên giảm sự kết hợp sai màu xanh lá cây và môi trường

đến hiện tại Yuxi Hãy nói chuyện，Đây là cách thực dụng nhất、Đây cũng là tiêu chuẩn thử nghiệm dễ dàng nhất để thực hiện liên tục.。
