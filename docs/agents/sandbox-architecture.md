# Yuxi Mô tả kiến trúc hộp cát

::: tip info
Tài liệu này được sản xuất bởi Codex Đồng tác giả，Đánh giá của nhà phát triển，Dù đã được chỉnh sửa nhiều lần，Tuy nhiên, vẫn có thể có những mô tả không chính xác hoặc lỗi thời。Nếu bạn tìm thấy bất kỳ vấn đề，Các bài nộp đều được chào đón issue hoặc PR để giúp chúng tôi cải thiện tài liệu của mình。
:::

chúng tôi là Yuxi Giới thiệu hộp cát，Không để làm cho kiến trúc nhiều hơn“nặng nề”，Nhưng bởi vì Agent Khi bạn chuyển từ cuộc trò chuyện bằng văn bản đơn giản sang cuộc trò chuyện thực sự，Bạn chắc chắn sẽ gặp phải một tập hợp yêu cầu thời gian chạy rất cụ thể.：thực hiện lệnh、Đọc và ghi tập tin、Xử lý tệp đính kèm do người dùng tải lên、Tạo kết quả có thể tải xuống，Và giữ các tập tin tiến trình trung gian trong thư mục được kiểm soát。Nếu bạn đặt những khả năng này trực tiếp vào API quá trình tự nó，ranh giới cho phép、Cách ly người thuê nhà、Tính nhất quán về môi trường và chi phí vận hành và bảo trì tiếp theo sẽ nhanh chóng xấu đi。

Từ góc độ mục tiêu thiết kế，Lớp hộp cát chủ yếu giải quyết ba việc:。đầu tiên，cho Agent một thứ có thể ghi được、Có thể thực thi、Không gian hoạt động độc lập có thể tái chế，Thay vì để nó trực tiếp vận hành tiến trình ứng dụng chính。thứ hai，Sắp xếp hệ thống tệp hiển thị mô hình vào một không gian tên ổn định，Ví dụ `/home/gem/user-data` và `/home/gem/skills`，Lối này prompt、Công cụ、viewer và artifact Giao diện tải xuống có thể chia sẻ cùng một bộ ngữ nghĩa đường dẫn。thứ ba，Hãy để bộ khả năng này có sẵn tại địa phương Docker Làm việc ổn định trong môi trường phát triển，Bạn cũng có thể cắt nó khi cần thiết Kubernetes Loại phương pháp lưu trữ này phù hợp hơn cho việc triển khai nhiều phiên bản.。

Tài liệu này mô tả dự án hiện tại“hộp cát”Chính xác thì lớp này là gì?、Tại sao tôi có thể nhìn thấy nó cùng một lúc? Docker và Kubernetes、Chế độ nào thực sự được kích hoạt trong môi trường phát triển mặc định?，và cách hộp cát hoạt động với `skills`、Phụ kiện、Hệ thống tệp không gian làm việc hoạt động cùng nhau。Nội dung tùy thuộc vào việc thực hiện kho hiện tại.，Chúng tôi tập trung vào việc giải thích chuỗi cuộc gọi thực sự、Mục cấu hình、Ngữ nghĩa đường dẫn và ranh giới hoạt động，Thay vì giới thiệu công nghệ container một cách trừu tượng。

## một、Hãy làm rõ trước：Docker và K8s Mối quan hệ ở đây là gì?

Docker và Kubernetes Không phải là mối quan hệ loại trừ lẫn nhau。Docker Giải pháp là“Đặt một quy trình vào một thùng chứa và chạy nó”câu hỏi này，Kubernetes Giải pháp là“Cách lập lịch hàng loạt trên một nhóm máy、bị lộ、Xây dựng lại và quản lý các container này”câu hỏi này。có thể đặt Docker Được hiểu là thời gian chạy vùng chứa và phương thức phân phối hình ảnh，đặt Kubernetes Được hiểu là nền tảng điều phối vùng chứa。

đưa vào Yuxi bên trong，Mối quan hệ này cụ thể hơn。Yuxi bản thân nó không trực tiếp quyết định“Hộp cát phải đang chạy Docker Vẫn phải chạy K8s trên”，Nó chỉ yêu cầu phần phụ trợ để có được địa chỉ hộp cát có thể truy cập，sau đó vượt qua `agent-sandbox` của HTTP API để thực hiện lệnh、Đọc và ghi tập tin。Điều thực sự chịu trách nhiệm tạo và tái chế các phiên bản sandbox là `sandbox-provisioner` dịch vụ riêng biệt này。Tức là nói，Yuxi Lớp ứng dụng chỉ phụ thuộc vào “provisioner”，Và provisioner Phần phụ trợ có thể chọn sử dụng bản địa Docker Loại bỏ thùng chứa，Bạn cũng có thể chọn Kubernetes Tạo cụm Pod và Service。

Vì vậy, khái niệm nhìn thấy trong dự án thực sự được chia thành hai cấp độ。Lớp đầu tiên là lớp ứng dụng `SANDBOX_PROVIDER`，Mã hiện tại chỉ hỗ trợ `provisioner`。Lớp thứ hai là provisioner nội bộ `SANDBOX_PROVISIONER_BACKEND`，Nó xác định việc triển khai cơ bản nào sẽ được sử dụng để tạo hộp cát。Điều mà thế giới bên ngoài thực sự cần hiểu và định hình hiện nay là `docker`、`kubernetes`，Có thể sử dụng các kịch bản kiểm tra hoặc giữ chỗ `memory`。

## hai、Chuỗi cuộc gọi sandbox thực sự của dự án hiện tại

Tại kho hiện tại，Phần phụ trợ chỉ hỗ trợ `SANDBOX_PROVIDER=provisioner`。Khi một chuỗi hội thoại cần thực hiện thao tác tệp hoặc thực thi lệnh lần đầu tiên，Phần phụ trợ sẽ dựa trên luồng tệp và skills Tạo chủ đề ổn định `sandbox_id`，sau đó yêu cầu `sandbox-provisioner` Tạo hoặc sử dụng lại hộp cát tương ứng；Bình thường Agent chủ đề tập tin và skills Tất cả các chủ đề đều rơi trở lại hiện tại `thread_id`。Lớp ứng dụng được trả về `sandbox_url` sau，sẽ thực sự vượt qua `agent-sandbox` Máy khách gọi tệp sandbox từ xa API và shell API。

Chuỗi cuộc gọi có thể được tóm tắt là：Web/API Yêu cầu nhập Yuxi phụ trợ，Cấu trúc phụ trợ `ProvisionerSandboxBackend`，qua lại `ProvisionerClient` gọi `sandbox-provisioner` của `/api/sandboxes` giao diện。`sandbox-provisioner` Theo `SANDBOX_PROVISIONER_BACKEND` Chọn triển khai dấu chân bộ nhớ、Docker triển khai vùng chứa hoặc Kubernetes nhận ra。Sau khi hộp cát thực sự được bắt đầu，Đưa một người ra thế giới bên ngoài HTTP địa chỉ，Yuxi Sau đó sử dụng địa chỉ này để hoàn thành lệnh thực thi、Tải tập tin lên、Tải tập tin xuống、Duyệt thư mục và các hoạt động khác。

Cấu hình mặc định và môi trường phát triển mặc định của kho hiện tại nên được hiểu là `docker`。Chạy trong điều kiện bình thường provisioner Việc kiểm tra sức khỏe sẽ trở lại `backend=docker`。Điều này có nghĩa là chúng tôi sử dụng `docker compose up -d` Khi bắt đầu một dự án，Ứng dụng không chạy code trực tiếp trên máy chủ，nhưng thông qua `sandbox-provisioner` Sử dụng nó một lần nữa Docker Bắt đầu một thùng chứa hộp cát thực sự。

## ba、`memory`、`docker`、`kubernetes` sự khác biệt là gì

Trong thực hiện hiện tại，`memory`、`docker`、`kubernetes` Có ba ngữ nghĩa cần được phân biệt。

`memory` Là một triển khai đăng ký bộ nhớ thuần túy。Nó không thực sự tạo ra vùng chứa，Nó cũng sẽ không cung cấp sự cô lập thực sự，Chủ yếu thích hợp để thử nghiệm hoặc các tình huống giữ chỗ cực kỳ nhẹ。nó chỉ ghi lại một `sandbox_id -> sandbox_url` lập bản đồ，Vì vậy nó không thể được hiểu là một hộp cát sẵn sàng cho sản xuất。

`docker` Là chương trình phụ trợ vùng chứa gốc mặc định và được đề xuất hiện tại。`sandbox-provisioner` Sẽ sử dụng `LocalContainerProvisionerBackend` thông qua máy chủ Docker daemon Tự động tạo các thùng chứa hộp cát。

`kubernetes` là một con đường thực hiện khác。Nó sẽ không gọi máy cục bộ nữa Docker thùng chứa，Thay vào đó hãy sử dụng Kubernetes API trong việc chỉ định namespace Tạo một cái trong Pod và một NodePort Service，sau đó đặt cái này Service Địa chỉ có thể truy cập tương ứng được chuyển trở lại Yuxi phụ trợ。

Vì thế，Nếu trong giao diện、Xem nó trong tài liệu hoặc các biến môi trường “docker / k8s” những từ này，Sự hiểu biết chính xác nhất phải là：Yuxi Chỉ có một lớp ứng dụng provider，Đó là `provisioner`；provisioner Có rất nhiều loại backend；Trong số đó `docker` Là địa phương mặc định Docker phụ trợ，`kubernetes` Là một phụ trợ cụm từ xa khác。

## bốn、Chế độ phát triển mặc định là gì?

Chế độ phát triển mặc định là Docker Compose Bắt đầu toàn bộ dự án，Sau đó bởi `sandbox-provisioner` nhấn `docker` Phần phụ trợ để tạo vùng chứa hộp cát。Tức là nói，Dự án tự chạy trên Compose bên trong，Hộp cát cũng chạy trong Docker bên trong，Nhưng hộp cát thì không Compose dịch vụ dài hạn được khai báo tĩnh，đúng hơn provisioner Các thùng chứa có tuổi thọ ngắn được kéo lên và tái chế linh hoạt theo yêu cầu。

Đây là lý do tại sao `docker-compose.yml` có thể được nhìn thấy trong `api`、`worker`、`sandbox-provisioner` Một dịch vụ lâu dài như vậy，Có thể nhìn thấy lại `sandbox-provisioner` Đã gắn kết `/var/run/docker.sock`。Đây không phải là một thiết kế lặp đi lặp lại，nhưng để cho provisioner Khả năng tiếp tục gọi máy chủ Docker daemon để tạo mới“Vùng chứa hộp cát trên mỗi luồng”。

Nói cách khác，Dự án hiện tại không có riêng biệt “vật chủ thuần khiết local chế độ”。Phát triển riêng và triển khai độc lập nên được sử dụng rõ ràng `docker` phụ trợ。

Ở đây chúng ta vẫn cần đặt Compose Các biến môi trường được xem ở hai cấp độ。`api` và `worker` Tập trung vào các biến lớp ứng dụng，Ví dụ `SANDBOX_PROVIDER`、`SANDBOX_PROVISIONER_URL`、`SANDBOX_VIRTUAL_PATH_PREFIX`、`SANDBOX_EXEC_TIMEOUT_SECONDS`、`SANDBOX_MAX_OUTPUT_BYTES`。`sandbox-provisioner` chính nó có một tập hợp các biến khác，Chịu trách nhiệm quyết định cách tạo phiên bản hộp cát。Không trộn lẫn hai lớp.，Nếu không, rất dễ nhầm tưởng rằng nó đã bị thay đổi. API Biến môi trường có thể chuyển đổi chế độ lưu trữ cơ bản。

## năm、Docker Cách hoạt động của chương trình phụ trợ gốc

Khi nào `SANDBOX_PROVISIONER_BACKEND=docker` thời gian，`sandbox-provisioner` sẽ vào `LocalContainerProvisionerBackend`。nó sẽ kiểm tra Docker Nó có sẵn không，Phân tích cú pháp trong vùng chứa riêng của nó `/app/saves` Đường dẫn thực sự của điểm gắn kết này trên máy chủ，Và lấy được thư mục dữ liệu luồng tương ứng。Sau đó, nó xâu chuỗi cho từng bộ tệp với skills Chủ đề chuẩn bị ổn định `sandbox_id`，Đặt tên cho vùng chứa giống như `yuxi-sandbox-<id>` hình thức，Và trong Docker Khởi chạy hình ảnh hộp cát thực trên mạng。

Hình ảnh hộp cát này mặc định từ `SANDBOX_IMAGE`，Cổng nghe mặc định bên trong container là `8080`。provisioner Khi khởi động thùng chứa，Cổng này sẽ được ánh xạ ngẫu nhiên tới một cổng có sẵn trên máy chủ.，tái sử dụng `DOCKER_SANDBOX_HOST` đánh vần một cái gì đó như `http://host.docker.internal:<random_port>` địa chỉ truy cập。Yuxi Những gì chương trình phụ trợ nhận được là địa chỉ này。

Docker Khi khởi động hộp cát, phần phụ trợ，Ba thư mục chính sẽ được gắn kết。Danh mục đầu tiên là cấp độ người dùng workspace，Gắn vào thùng chứa `/home/gem/user-data/workspace`。Danh mục thứ hai là cấp độ luồng tệp uploads/outputs，Gắn vào `/home/gem/user-data/uploads` và `/home/gem/user-data/outputs`。Loại thứ ba là skills Chủ đề hiển thị skills Thư mục，gắn kết với `/home/gem/skills`，Và nó là một mount chỉ đọc。Ngoài ra，thùng chứa `/home/gem` Nó cũng sẽ treo thêm một cái nữa `tmpfs`，Lý do là hình ảnh hộp cát hiện tại yêu cầu `/home/gem` có thể ghi được，Nhưng Yuxi Chỉ những người hy vọng thực sự bền bỉ `user-data` nội dung bên dưới。

Để tránh các hộp cát nhàn rỗi lâu dài chiếm tài nguyên，provisioner Tôi cũng mang theo một cái idle reaper。Nó ghi lại lần cuối cùng mỗi hộp cát được touch thời gian，vượt quá `SANDBOX_IDLE_TIMEOUT_SECONDS` Tự động xóa sau đó。Thời gian chờ không hoạt động mặc định hiện tại là 120 giây，Nhưng nếu giá trị này nhỏ hơn thời gian chờ thực hiện lệnh，Hệ thống sẽ tự động tăng lên“Hết thời gian lệnh + 30 giây”，Để ngăn chặn các tác vụ đang được thực thi vô tình bị tái chế。

tương ứng với `docker-compose.yml` và `docker-compose.prod.yml`，hiện tại `sandbox-provisioner` Sẽ thực sự đọc Docker Các biến liên quan đến phụ trợ chủ yếu là những：

- Biến phổ quát：`PROVISIONER_BACKEND`、`SANDBOX_IMAGE`、`SANDBOX_CONTAINER_PORT`、`SANDBOX_HEALTH_TIMEOUT_SECONDS`、`SANDBOX_IDLE_TIMEOUT_SECONDS`、`SANDBOX_IDLE_CHECK_INTERVAL_SECONDS`、`SANDBOX_EXEC_TIMEOUT_SECONDS`、`MEMORY_SANDBOX_URL_TEMPLATE`
- Docker biến phụ trợ：`DOCKER_NETWORK`、`DOCKER_THREADS_HOST_PATH`、`DOCKER_SANDBOX_PREFIX`、`DOCKER_SANDBOX_HOST`
- Biến proxy vùng chứa：`HTTP_PROXY`、`HTTPS_PROXY`、`NO_PROXY`

Trong số đó `DOCKER_SANDBOX_HOST` chỉ trong Docker Được sử dụng dưới phần phụ trợ để ghép nối và quay lại API của `sandbox_url`。`DOCKER_THREADS_HOST_PATH` Ngoài ra Docker Chỉ phụ trợ；Nếu không được thông qua một cách rõ ràng，provisioner Sẽ cố gắng lấy đường dẫn máy chủ dựa trên giá đỡ vùng chứa của chính nó。

## sáu、Kubernetes Phần phụ trợ hoạt động như thế nào

Khi nào `SANDBOX_PROVISIONER_BACKEND=kubernetes` thời gian，`sandbox-provisioner` Sẽ sử dụng thay thế Kubernetes Python khách hàng。nó sẽ tải đầu tiên kubeconfig Hoặc cấu hình trong cụm，Sau đó trong quy định namespace Tạo hộp cát trong Pod，Tạo một cái khác có cùng tên NodePort Service，đặt cái này Service của `nodePort` tiếp xúc với Yuxi Sử dụng phụ trợ。

Kubernetes Dưới phần phụ trợ，Sandbox vẫn là bộ ảnh như cũ，Vẫn lộ diện như cũ HTTP API，Nhưng phương pháp lưu trữ và phơi nhiễm đã thay đổi。Nó không phụ thuộc vào máy chủ Docker bind mount，Thay vào đó, nó yêu cầu một tệp có thể ghi PVC。Những gì thực sự được sử dụng trong việc thực hiện hiện tại là `THREAD_PVC`，Pod Bộ nhớ dùng chung này sẽ được đính kèm vào `/mnt/shared-data`，Sau đó sử dụng `subPath` cách để đặt `threads/shared/<uid>/workspace` Treo lên `/home/gem/user-data/workspace`，đặt `threads/<file_thread_id>/user-data/uploads` với `threads/<file_thread_id>/user-data/outputs` Treo tương ứng uploads/outputs，đặt `threads/<skills_thread_id>/skills` Treo lên `/home/gem/skills`。Ưu điểm của việc này là cấu trúc thư mục vẫn có thể được Docker Mẫu vẫn nhất quán，Đồng thời cho phép các tổng đài viên con chia sẻ tệp hội thoại gốc nhưng tách biệt nó skills。

Điều cần giải thích đặc biệt là，Mặc dù nó được đọc trong mã `SKILLS_PVC` Biến môi trường này，Nhưng hiện tại Pod Đặc điểm kỹ thuật không thực sự sử dụng một skills PVC，Nhưng thống nhất từ `THREAD_PVC` cắt trung tâm `threads/<thread_id>/skills` đường dẫn phụ này。Vì thế，Nếu bạn thấy cả hai xuất hiện trong các biến môi trường `SKILLS_PVC` và `THREAD_PVC`，nên `THREAD_PVC` Ngữ nghĩa gắn kết thực tế của，`SKILLS_PVC` Hiện tại giống như một trường dành riêng。

Kubernetes Phần phụ trợ cũng cần một `NODE_HOST`。Điều này là do việc triển khai hiện tại sử dụng NodePort Service，thay vì Ingress，cũng không ClusterIP。provisioner Đã tạo Service sau，Địa chỉ truy cập cuối cùng sẽ được đánh vần thành `http://<NODE_HOST>:<nodePort>` quay trở lại Yuxi phụ trợ。Vì vậy `NODE_HOST` phải là Yuxi Có thể truy cập được bởi phần phụ trợ Kubernetes Địa chỉ nút、Địa chỉ hoặc cặp cân bằng tải NodePort Tên miền bên ngoài bị lộ。

hiện tại Compose trung hòa Kubernetes Các biến tương ứng với phần phụ trợ chủ yếu là：

- `K8S_NAMESPACE`
- `KUBECONFIG_PATH`
- `NODE_HOST`
- `THREAD_PVC`
- `SKILLS_PVC`

Điều thực sự quyết định việc gắn kết thời gian chạy là `THREAD_PVC`。`SKILLS_PVC` Hiện chỉ dành riêng cho các trường đọc lớp mã，chưa nhập thực tế Pod gắn kết。

## bảy、Nếu bạn muốn sử dụng“từ xa K8s”，Tôi nên trả lời thế nào

Điểm dễ hiểu lầm nhất ở đây là，cái gọi là“Chọn điều khiển từ xa K8s”，Không có trong Yuxi Bấm vào một công tắc trên trang，Sau đó hệ thống tự động phát hiện một cụm。Việc triển khai hiện tại không có bộ chọn cụm tích hợp，Không có giao diện quản lý đa cụm。Cách thức hoạt động rất đơn giản：chúng tôi đặt `sandbox-provisioner` được cấu hình như `kubernetes` phụ trợ，Và để nó lấy cụm mục tiêu kubeconfig Hoặc chỉ chạy nó trong một cụm。Có provisioner Hãy nói chuyện，miễn là Kubernetes Client có thể kết nối API Server，Cụm này chính là mục đích hoạt động của nó“từ xa K8s”。

nếu Yuxi Đã triển khai ở Docker Compose bên trong，Và Kubernetes Cụm này nằm trên một máy khác hoặc môi trường lưu trữ của nhà cung cấp dịch vụ đám mây，Vì vậy cách tiếp cận phổ biến nhất là đặt địa phương kubeconfig Tập tin được gắn vào `sandbox-provisioner` thùng chứa，Sau đó đặt `KUBECONFIG_PATH`。cùng lúc `SANDBOX_NODE_HOST` Thay đổi thành một từ `api` Nút mạng công cộng mà container cũng có thể truy cập IP、Tên miền cân bằng tải，Hoặc một địa chỉ đã được ủy quyền ngược。

một điển hình Compose Cấu hình ghi đè sẽ trông như thế này：

```yaml
services:
  sandbox-provisioner:
    environment:
      - PROVISIONER_BACKEND=kubernetes
      - K8S_NAMESPACE=yuxi-know
      - KUBECONFIG_PATH=/root/.kube/config
      - THREAD_PVC=yuxi-thread
      - SKILLS_PVC=yuxi-skills
      - NODE_HOST=203.0.113.10
    volumes:
      - ~/.kube/config:/root/.kube/config:ro
```

Cấu hình này không có nghĩa“Di chuyển toàn bộ ứng dụng sang K8s”，đúng hơn“vẫn sử dụng Compose chạy Yuxi dịch vụ chính，Nhưng phiên bản hộp cát được thay đổi thành điều khiển từ xa Kubernetes Lưu trữ cụm”。Đây là phương pháp triển khai kết hợp tự nhiên nhất cho mã hiện tại。

nếu `sandbox-provisioner` chính nó chạy tiếp Kubernetes Bên trong cụm，thì thường không cần phải cung cấp rõ ràng `KUBECONFIG_PATH`。nó sẽ thử trước `incluster_config`，Tức là sử dụng Pod Quyền tài khoản dịch vụ để truy cập trực tiếp Kubernetes API。Điều cần quan tâm hơn lúc này là namespace、PVC và NodePort khả năng tiếp cận，thay vì kubeconfig chính tập tin。

## tám、Hệ thống tệp sandbox của dự án hiện tại được thiết kế như thế nào?

Từ quan điểm của việc gọi mô hình và công cụ，Yuxi Chủ yếu để Agent Hiển thị hai loại đường dẫn：`/home/gem/user-data` và `/home/gem/skills`。Trong số đó `user-data` Là không gian làm việc của người dùng có thể ghi，`skills` Đây là một thư mục kỹ năng chỉ đọc。Cơ sở kiến thức không còn được ánh xạ tới đường dẫn hệ thống tệp hộp cát，Các mô hình nên truy xuất và mở tài liệu thông qua các công cụ cơ sở tri thức。

Về phía chủ nhà，Dữ liệu liên quan đến chủ đề chủ yếu được đặt trong `saves` dưới thư mục。Cấu trúc thư mục có thể đọc được hiện tại có thể được tóm tắt như sau：

```text
saves/
├── skills/
│   ├── <skill-slug>/
│   └── ...
├── threads/
│   ├── <thread_id>/
│   │   ├── user-data/
│   │   │   ├── uploads/
│   │   │   ├── outputs/
│   │   │   └── ...
│   │   └── skills/
│   │       ├── <skill-slug>/
│   │       └── ...
│   ├── shared/
│   │   └── <uid>/
│   │       └── workspace/
│   └── ...
```

Điều quan trọng là phải hiểu ở đây `workspace` và `uploads/outputs` Sự khác biệt。Phân tích logic theo đường dẫn máy chủ hiện tại，`workspace` được định nghĩa là thư mục chia sẻ cấp người dùng，Vị trí là `saves/threads/shared/<uid>/workspace`；Và `uploads` và `outputs` Thuộc về thư mục chủ đề tập tin，Các địa điểm là `saves/threads/<file_thread_id>/user-data/uploads` và `saves/threads/<file_thread_id>/user-data/outputs`。Bình thường Agent của `file_thread_id` Đó là cuộc trò chuyện hiện tại `thread_id`，Khi tác nhân con chạy, nó sử dụng đoạn hội thoại cha mẹ làm `file_thread_id`，Vì vậy, bạn có thể đọc tệp đính kèm cuộc trò chuyện của phụ huynh và viết lại sản phẩm cho cuộc trò chuyện của phụ huynh outputs。

Đồng thời，thời gian chạy provisioner Tạo Docker thùng chứa hoặc Kubernetes Pod thời gian，cấp độ người dùng `saves/threads/shared/<uid>/workspace` treo một mình `/home/gem/user-data/workspace`，Sau đó xâu chuỗi tập tin `uploads/outputs` Treo tương ứng `/home/gem/user-data/uploads` và `/home/gem/user-data/outputs`。Vì vậy khi khắc phục sự cố về file，Tiền đề cần được làm rõ trước：Cả hai đều tồn tại trong dự án hiện tại“Tổ chức thư mục phía máy chủ”và“Thống nhất các đường dẫn ảo trong vùng chứa”khái niệm hai tầng。giao diện bên ngoài và viewer Ngữ nghĩa hiện đã nhất quán với việc triển khai gắn kết cơ bản，workspace Đó là không gian chia sẻ của người dùng，Và uploads/outputs Theo dõi cách ly hoặc chia sẻ luồng tập tin。

## chín、Các quy tắc tiếp xúc với đường dẫn là gì?

Yuxi không mở toàn bộ hệ thống tập tin vùng chứa để Agent hoặc viewer。hiện tại viewer Thư mục gốc sẽ chỉ liệt kê một vài mục không gian tên，không bộc lộ trực tiếp `/` cây tập tin thực sự của。Điều này được thực hiện để tránh kích hoạt khởi động nguội hộp cát bằng cách chỉ nhìn vào cây tệp.，Ngoài ra để làm cho ranh giới quyền ổn định hơn。

`/home/gem/user-data` là khu vực làm việc chính。Nó cho phép các mô hình và công cụ viết，Nhưng ngữ nghĩa đề xuất không giống nhau。Tích hợp sẵn prompt đã được nêu rõ ràng trong，`workspace` Nên đặt các tập tin trung gian，`outputs` Sản phẩm cuối cùng nên được đặt，`uploads` Là nơi người dùng upload file。để nói chuyện bình thường Agent，Copywriting thậm chí còn gợi ý“Đừng viết trừ khi cần thiết workspace，và viết đầu tiên outputs”。

`/home/gem/skills` là một thư mục chỉ đọc。Nó không chỉ đơn giản là đặt `saves/skills` Toàn bộ sự việc được phơi bày，Thay vào đó, nó đầu tiên dựa trên thời gian chạy hiện tại `_readable_skills`，Đặt những kỹ năng này vào quan điểm skills Thư mục gốc được sao chép đồng bộ vào `saves/threads/<skills_thread_id>/skills`，đặt lại cái này skills Thư mục chủ đề ở chế độ chỉ đọc và được treo trong hộp cát。Kết quả của việc này là，Chủ sở hữu khác nhau/con trai Agent nhìn thấy skill Bộ có thể khác nhau，Và mô hình không bao giờ có thể được sửa đổi khi chạy skills nội dung。

Quyền truy cập cơ sở kiến ​​thức không thuộc quy tắc hiển thị hệ thống tệp hộp cát。hiện tại Agent Có thể thấy, cơ sở tri thức vẫn được kiểm soát bởi sự cho phép của người dùng và Agent Cấu hình cùng nhau quyết định，nhưng chỉ thông qua `query_kb`、`open_kb_document` Công cụ truy cập，Phép chiếu thư mục hộp cát không được cung cấp。

## mười、skills、cơ sở tri thức、Các tệp đính kèm được kết hợp với hộp cát như thế nào?

skills Phương pháp kết hợp được chia thành hai lớp。Lớp đầu tiên là lớp từ nhắc，`prepare_agent_runtime_context` đầu tiên sẽ dựa trên hiện tại Agent được cấu hình `context.skills` Mở rộng việc đóng cửa phụ thuộc，`SkillsMiddleware` một lần nữa `_prompt_skills` Đưa vào dấu nhắc hệ thống，Hãy cho người mẫu biết điều gì skill tồn tại、Các tập tin nhập của họ thường ở dạng `/home/gem/skills/<slug>/SKILL.md`。Lớp thứ hai là lớp hệ thống tập tin，Sẽ được gọi khi chạy `sync_thread_readable_skills`，đặt `_readable_skills` tương ứng skill Thư mục được sao chép sang hiện tại `skills_thread_id` của `saves/threads/<skills_thread_id>/skills` xuống，Sau đó hộp cát được gắn ở chế độ chỉ đọc vào `/home/gem/skills`。Tức là nói，skill cả hai prompt Mô tả các khả năng trong，Cũng là một thư mục kiến thức chỉ đọc trong hệ thống tập tin。

Cách kết hợp các phụ kiện có xu hướng thiên về“Đặt đầu tiên，Sau đó cho người mẫu biết đường dẫn”。Sau khi người dùng tải file lên，Đầu tiên hệ thống sẽ ghi file gốc `saves/threads/<file_thread_id>/user-data/uploads`。Nếu tập tin có thể được phân tích cú pháp，Hệ thống cũng sẽ tạo thêm Markdown sao chép，viết thư cho `saves/threads/<file_thread_id>/user-data/uploads/attachments/<name>.md`。Bình thường Agent Chuỗi tập tin là chuỗi hội thoại hiện tại；Tác nhân con kế thừa chuỗi tệp hội thoại gốc，Vì vậy, bạn có thể truy cập vào phần đính kèm cuộc trò chuyện của phụ huynh。sau đó，LangGraph state Ủy ban Trung ương sẽ lưu giữ một bản sao `uploads` danh sách，`AttachmentMiddleware` Những đường dẫn có thể đọc được này sẽ được đưa vào lời nhắc của hệ thống，Nói với mô hình để sử dụng `read_file` để đọc những con đường này。Vì thế，Tệp đính kèm không“Các khối tin nhắn nội tuyến dưới dạng tin nhắn đến mô hình”，Thay vào đó, nó được chuyển đổi thành một đối tượng đường dẫn trong hệ thống tệp hộp cát.。

Cơ sở kiến thức không còn được tích hợp với hệ thống tệp sandbox。Nó sẽ không được sao chép vào mỗi thư mục chủ đề，Sẽ không có thư mục ảo nào được tạo；Các mô hình được truy xuất thông qua các công cụ cơ sở tri thức chuyên dụng，và khi cần một bối cảnh hoàn chỉnh hơn, hãy sử dụng `open_kb_document` nhấn `resource_id` và `file_id` Mở nội dung tài liệu。

## mười một、Khuyến nghị hiện tại để sử dụng Docker hộp cát

Nếu chỉ là sự phát triển bình thường、Gỡ lỗi hoặc triển khai độc lập，Cách đơn giản nhất và mặc định hiện nay là giữ `SANDBOX_PROVIDER=provisioner`，cùng lúc `SANDBOX_PROVISIONER_BACKEND` đặt thành `docker`。Điều này sẽ cho phép toàn bộ dự án tiếp tục được điều hành bởi Docker Compose quản lý，Phiên bản hộp cát bao gồm provisioner Được tạo động。Thông thường không cần làm việc thủ công `docker run` hình ảnh hộp cát，Không cần phải ở đó Compose Khai báo tĩnh mỗi sandbox container trong file。

Cấu hình cần thiết tối thiểu thường là những mục sau:：

```env
SANDBOX_PROVIDER=provisioner
SANDBOX_PROVISIONER_URL=http://sandbox-provisioner:8002
SANDBOX_PROVISIONER_BACKEND=docker
SANDBOX_VIRTUAL_PATH_PREFIX=/home/gem/user-data
SANDBOX_DOCKER_SANDBOX_HOST=host.docker.internal
```

Sau đó chỉ cần khởi động nó theo cách thông thường：

```bash
docker compose up -d
curl http://localhost:8002/health
```

Nếu kết quả kiểm tra sức khỏe trở lại `backend: docker`，Chỉ hiển thị provisioner đã mặc định rồi Docker phụ trợ gốc。Các thùng chứa hộp cát thực sự không xuất hiện ngay lập tức khi khởi động hệ thống，Thay vào đó, nó sẽ được tạo sau khi bạn tạo luồng lần đầu tiên và kích hoạt một thao tác yêu cầu hệ thống tệp hoặc thực thi lệnh.。

Nếu chạy tiếp Linux，thay vì Docker Desktop，Sau đó `host.docker.internal` Không phải lúc nào cũng có sẵn。Lúc này cần phải `SANDBOX_DOCKER_SANDBOX_HOST` Thay đổi thành một từ `api` Địa chỉ máy chủ có thể truy cập được bằng container，Hoặc đổi sang một tên ổn định hơn trong môi trường mạng hiện tại.。Nếu không provisioner Mặc dù container có thể được khởi động thành công，Nhưng phần phụ trợ có thể nhận được một cái mà nó không thể truy cập. `sandbox_url`。

## mười hai、Làm thế nào để hiểu ranh giới quản lý tập tin và hiển thị

Từ góc độ hành vi sản phẩm，viewer hệ thống tập tin và artifact Giao diện tải xuống ưu tiên độ phân giải đường dẫn máy chủ.，Thay vì truyền nó vô điều kiện vào bên trong hộp cát。Thiết kế này có hai lợi ích trực tiếp:。đầu tiên，Duyệt qua `/` hoặc `/home/gem/user-data` Một lối vào hình cây như vậy，Không cần khởi động nguội hộp cát để xem chỉ đọc。thứ hai，Ranh giới cho phép tốt hơn，bởi vì `resolve_virtual_path` Sẽ giới hạn nghiêm ngặt các đường dẫn mà người dùng có thể nhìn thấy ở những đường dẫn được xác định trước `user-data` và `skills` trong không gian tên。

Từ góc độ kỹ thuật，Việc thực hiện hiện tại giống như“Hệ thống tập tin hai lớp”。Có Agent Về mặt thực hiện，Điều thực sự hiệu quả là các tệp được hiển thị bởi quy trình hộp cát từ xa API；Có viewer、Tải xuống tệp đính kèm và một phần artifact Xem nó，Đầu tiên hệ thống sẽ giải quyết đường dẫn ảo ở phía máy chủ.，Sau đó sử dụng các tệp cục bộ để đọc hoặc chỉ đọc backend Tải nội dung xuống。Đây là lý do tại sao bạn thấy cả hai `ProvisionerSandboxBackend`，một lần nữa `viewer_filesystem_service`、`SelectedSkillsReadonlyBackend` Việc hỗ trợ thực hiện như vậy。

## Mười ba、Cấu hình biến môi trường và chuỗi phân phối

sandbox-provisioner điểm chuyển biến môi trường**hai tầng**，cần được hiểu riêng：

### tầng một：Lớp ứng dụng → sandbox-provisioner

`api` và `worker` Dịch vụ đã được thông qua `SANDBOX_*` Biến môi trường có tiền tố cho phần phụ trợ biết cách kết nối provisioner。Các biến này được xác định trong `docker-compose.yml` của `x-api-worker-env` trong mỏ neo：

| tên biến | Mô tả | Giá trị mặc định |
|--------|------|--------|
| `SANDBOX_PROVIDER` | loại nhà cung cấp，cố định vào `provisioner` | `provisioner` |
| `SANDBOX_PROVISIONER_URL` | provisioner Địa chỉ dịch vụ | `http://sandbox-provisioner:8002` |
| `SANDBOX_VIRTUAL_PATH_PREFIX` | tiền tố đường dẫn ảo | `/home/gem/user-data` |
| `SANDBOX_EXEC_TIMEOUT_SECONDS` | Hết thời gian thực hiện lệnh | `180` |
| `SANDBOX_MAX_OUTPUT_BYTES` | Số byte đầu ra tối đa | `262144` |

### tầng hai：sandbox-provisioner Cấu hình bên trong

`sandbox-provisioner` Bản thân dịch vụ sẽ đọc một bộ biến môi trường khác，Quyết định cách tạo vùng chứa hộp cát。Các biến này được viết trực tiếp trong `docker-compose.yml` của `sandbox-provisioner.environment` trong：

**Cấu hình chung：**

| tên biến | Mô tả | Giá trị mặc định |
|--------|------|--------|
| `PROVISIONER_BACKEND` | loại phụ trợ cơ bản，`docker` hoặc `kubernetes` | `docker` |
| `SANDBOX_IMAGE` | Hình ảnh thùng chứa hộp cát | Xem chi tiết compose tập tin |
| `SANDBOX_CONTAINER_PORT` | Cổng nội bộ của hộp cát | `8080` |
| `SANDBOX_IDLE_TIMEOUT_SECONDS` | thời gian phục hồi nhàn rỗi | `120` |
| `SANDBOX_HEALTH_TIMEOUT_SECONDS` | Hết thời gian kiểm tra sức khỏe | `300` |

**Docker Chỉ phụ trợ：**

| tên biến | Mô tả | Giá trị mặc định |
|--------|------|--------|
| `DOCKER_NETWORK` | Docker tên mạng | `yuxi-know_app-network` |
| `DOCKER_SANDBOX_PREFIX` | Tiền tố tên vùng chứa hộp cát | `yuxi-sandbox` |
| `DOCKER_SANDBOX_HOST` | Địa chỉ truy cập máy chủ | `host.docker.internal` |
| `DOCKER_THREADS_HOST_PATH` | Đường dẫn máy chủ dữ liệu chủ đề | suy luận tự động |

**Kubernetes Chỉ phụ trợ：**

| tên biến | Mô tả | Giá trị mặc định |
|--------|------|--------|
| `K8S_NAMESPACE` | Kubernetes namespace | `yuxi-know` |
| `NODE_HOST` | Kubernetes Địa chỉ nút | `host.docker.internal` |
| `KUBECONFIG_PATH` | kubeconfig đường dẫn tập tin | trống rỗng（sử dụng incluster Cấu hình） |
| `THREAD_PVC` | Khối lượng lưu trữ dữ liệu chủ đề | `yuxi-thread` |
| `SKILLS_PVC` | Khối lượng kiên trì danh mục kỹ năng（dành riêng） | `yuxi-skills` |

### Chuỗi phân phối biến môi trường

```
Máy chủ .env / Biến môi trường hệ thống
         ↓
    docker-compose.yml
         ↓
    ┌────────────────────────────────┐
    │  api/worker dịch vụ               │  Biến lớp ứng dụng (SANDBOX_*)
    │    SANDBOX_PROVISIONER_URL     │
    └────────────┬───────────────────┘
                 ↓  HTTP gọi
    ┌────────────────────────────────┐
    │  sandbox-provisioner dịch vụ       │  Biến lớp hộp cát (PROVISIONER_BACKEND, DOCKER_*, K8S_*)
    │    PROVISIONER_BACKEND         │
    └────────────┬───────────────────┘
                 ↓  Docker API / K8s API
    ┌────────────────────────────────┐
    │  Vùng chứa hộp cát được tạo động              │
    └────────────────────────────────┘
```

Đừng trộn lẫn hai cấp độ biến。Đã thay đổi `api/worker` của `SANDBOX_PROVISIONER_URL` Chỉ cần thay đổi phần phụ trợ để tìm provisioner địa chỉ；Đã thay đổi `sandbox-provisioner` của `PROVISIONER_BACKEND` Đó là điều đã thay đổi provisioner Cách tự tạo hộp cát。

### sandbox.env vai trò đặc biệt

`docker/sandbox_provisioner/sandbox.env` Mục đích của tệp khác với hai cấp độ biến trên.。nó trôi qua volume gắn kết với provisioner thùng chứa bên trong (`/app/sandbox.env`)，sau đó bởi `LocalContainerProvisionerBackend` Đọc khi tạo vùng chứa hộp cát，Các cặp khóa-giá trị được phân tích cú pháp sẽ là**Các biến môi trường được đưa vào từng vùng chứa hộp cát được tạo động**trong。

```yaml
# docker-compose.yml trong sandbox-provisioner gắn kết
sandbox-provisioner:
  volumes:
    - ./docker/sandbox_provisioner/sandbox.env:/app/sandbox.env:ro
```

Tức là nói，`sandbox.env` Các biến môi trường hiển thị bên trong vùng chứa hộp cát đã được định cấu hình.，thay vì provisioner cấu hình riêng。Nội dung hiện tại của tập tin này là：

```env
CHECK_YUXI_SANDBOX_ENV_EXISTS=True
```

Nếu bạn cần đưa các biến môi trường bổ sung vào tất cả các vùng chứa hộp cát（Chẳng hạn như cấu hình proxy、Thông tin chứng nhận, v.v.），có thể được thêm vào `sandbox.env` trong tập tin。

### Tóm tắt các phương pháp cấu hình

| Định cấu hình mục tiêu | Vị trí cấu hình | Biến ví dụ |
|----------|----------|----------|
| Kết nối lớp ứng dụng provisioner | `.env` hoặc compose môi trường | `SANDBOX_PROVISIONER_URL` |
| provisioner hành vi của chính mình | `.env` hoặc compose môi trường | `PROVISIONER_BACKEND`, `DOCKER_*` |
| Môi trường bên trong hộp cát | `sandbox.env` tập tin | đại lý、Xác thực và các biến thời gian chạy khác |

## mười bốn、So với phiên bản cũ của tài liệu，Cách quan trọng nhất để hiểu ngày nay

Mục hiện tại không còn được nhấn nữa“Ứng dụng trực tiếp quản lý một địa phương tồn tại lâu dài sandbox dịch vụ”để hiểu。Cần có sự hiểu biết chính xác hơn：Yuxi Chỉ quản lý chủ đề và bối cảnh；provisioner Chịu trách nhiệm tạo các phiên bản hộp cát tương ứng với các luồng；Hệ thống tập tin không chỉ hiển thị thư mục gốc của vùng chứa，Thay vào đó, hãy đặt không gian làm việc có thể ghi、chỉ đọc skills kết hợp thành một không gian tên được kiểm soát（Cơ sở kiến thức không còn được ánh xạ dưới dạng thư mục hộp cát，Thay đổi thành `query_kb`/`open_kb_document` Công cụ truy cập）。

Vì thế，khi bạn đang ở trên giao diện“Bật hộp cát”Hoặc trong tài liệu“chọn K8s”thời gian，Về cơ bản, những gì chúng tôi đang làm không phải là chuyển đổi một phần logic kinh doanh.，Nhưng chuyển đổi provisioner Phương thức lưu trữ phiên bản cơ bản。chọn `docker` thời gian，Hộp cát bao gồm Docker daemon Được tạo động；chọn `kubernetes` thời gian，hộp cát theo mục tiêu K8s Tạo động cụm。Yuxi Tôi luôn phải đối mặt với chỉ một provisioner Địa chỉ dịch vụ。

## mười lăm、Những điều nên xem xét đầu tiên khi khắc phục sự cố là gì?

Nếu sự nghi ngờ là provisioner câu hỏi cấp độ，Nhìn đầu tiên `http://localhost:8002/health`，Xác nhận backend gõ và idle timeout Liệu nó có đáp ứng được mong đợi không?。Mặc định Docker Bạn sẽ thấy nó ở đây đang được triển khai `backend=docker`。Đọc tiếp `docker logs sandbox-provisioner --tail 200`，Vì các bạn có thể trực tiếp nhìn thấy quá trình tạo container tại đây、Sử dụng lại phiên bản cũ、kiểm tra sức khỏe không thành công và idle reaper Nhật ký đã xóa。

Nếu sự nghi ngờ là Docker Địa chỉ không thể truy cập được，Kiểm tra chính `SANDBOX_DOCKER_SANDBOX_HOST` và liệu cổng được ánh xạ ngẫu nhiên có phải là từ `api` Có thể truy cập vùng chứa。Có thể tìm thấy ở `api` trực tiếp trong container `curl` provisioner trả lại `sandbox_url`。Nếu sự nghi ngờ là Kubernetes Địa chỉ không thể truy cập được，Kiểm tra chính `NODE_HOST` và NodePort kết nối bên ngoài，Vì việc triển khai hiện tại không thông qua cluster nội bộ Service liên kết ngược tên。

Nếu bạn nghi ngờ rằng tập tin có thể được nhìn thấy nhưng mô hình không thể đọc được，Hoặc mô hình được viết nhưng viewer không thể nhìn thấy，Ưu tiên chia vấn đề thành hai cấp độ：Một lớp là liệu đường dẫn máy chủ có tồn tại trong `saves/...` xuống，Một lớp khác là liệu đường dẫn có thực sự được gắn kết và hiển thị bởi hộp cát luồng hiện tại hay không `/home/gem/user-data` hoặc `/home/gem/skills`。Chỉ cần làm rõ trước“Ngữ nghĩa của tệp phía máy chủ”và“Ngữ nghĩa gắn kết thời gian chạy phía hộp cát”，Vấn đề định vị thường nhanh hơn nhiều。
