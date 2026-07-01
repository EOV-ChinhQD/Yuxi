# Skills hệ thống quản lý

Skills Có Yuxi hệ thống mở rộng Agent cơ chế quan trọng của khả năng。Vượt qua Skills，Nhà phát triển có thể thêm các công cụ cụ thể、Các mẫu từ gợi ý hoặc kiến ​​thức miền được đóng gói thành các gói kỹ năng có thể sử dụng lại，hãy để Agent Khả năng sử dụng những khả năng bổ sung này trong các cuộc trò chuyện。

## tại sao cần thiết Skills

Trong các tình huống kinh doanh thực tế，Chúng tôi thường gặp một số nhu cầu cụ thể：Chẳng hạn như cần Agent Khả năng truy vấn cụ thể API、Gọi dịch vụ bên ngoài、Hoặc sử dụng các mẫu lời nhắc cụ thể để hoàn thành các nhiệm vụ cụ thể。Cách tiếp cận truyền thống là mã hóa cứng các chức năng này trong mã，Nhưng điều này sẽ khiến hệ thống ngày càng trở nên cồng kềnh，và khó tái sử dụng。

Skills Ý tưởng thiết kế của hệ thống là kết hợp loại"có thể cắm được"Khả năng được đóng gói thành các gói kỹ năng độc lập。mỗi Skill Chứa các tệp và siêu dữ liệu triển khai hoàn chỉnh，Agent Các kỹ năng cần thiết có thể được tải động dựa trên cấu hình，Cho phép kết hợp linh hoạt các khả năng。

## thiết kế kiến trúc

Skills Áp dụng hệ thống「Nội dung lưu trữ hệ thống tập tin，Chỉ mục kiểm kê dữ liệu」kiến trúc tách biệt：

```
┌─────────────────────────────────────────────────────────────┐
│                      Skills Kiến trúc lưu trữ                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   /app/saves/skills/          chỉ mục cơ sở dữ liệu                    │
│   ├── skill-a/               ┌──────────────┐              │
│   │   ├── SKILL.md           │ skills bàn    │              │
│   │   ├── tools/             │ - slug       │              │
│   │   └── prompts/           │ - name       │              │
│   └── skill-b/               │ - description│              │
│       ├── SKILL.md           │ - dir_path   │              │
│       └── ...                │ - source_type│              │
│                              │ - share_config              │
│                              │ - enabled     │              │
│                              │ - deps...     │              │
│                              └──────────────┘              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### cấu trúc lưu trữ

- **hệ thống tập tin**：`/app/saves/skills` dưới thư mục，mỗi Skill chiếm một thư mục con
- **chỉ mục cơ sở dữ liệu**：`skills` Siêu dữ liệu lưu trữ bảng（slug、name、description、Nguồn、Phạm vi chia sẻ、Trạng thái đã bật、Sự phụ thuộc, v.v.）
- **cơ chế liên kết**：Vượt qua `dir_path` Các trường liên kết thư mục hệ thống tệp với các bản ghi cơ sở dữ liệu

::: tip Không thể tạo trực tiếp trong hệ thống tập tin
do Skills Siêu dữ liệu cần được ghi vào cơ sở dữ liệu，Vì vậy nó không thể được tạo trực tiếp trong hệ thống tập tin Skill。Việc này phải được thực hiện thông qua chức năng nhập hoặc cài đặt của hệ thống，Hệ thống tự động xử lý việc tạo hồ sơ cơ sở dữ liệu。
:::

## Cách tạo

Hệ thống cung cấp các phương pháp sau để tạo hoặc cài đặt Skills：

1. **Được đề xuất Skill Cài đặt**：trong Skills Đề xuất click nhóm trên trang quản lý `+`，Hệ thống sẽ kéo nguồn remote tương ứng và tạo ra bản nháp cài đặt
2. **ZIP / SKILL.md tải lên**：Sau khi tải lên, đầu tiên nó được phân tích thành bản nháp cài đặt.，Xác nhận phạm vi chia sẻ trước khi viết bài chính thức Skills Lưu trữ và cơ sở dữ liệu
3. **Lắp đặt kho từ xa**：điền vào skills Địa chỉ kho、ModelScope Skill Địa chỉ hoặc địa chỉ nhận hàng，Cuộc gọi phụ trợ `npx skills` Tải xuống và phân tích dưới dạng bản nháp cài đặt，Sau khi xác nhận thì import vào hệ thống
4. **Chỉnh sửa trực tuyến**：hiện có và có thể quản lý được Skill Tạo danh mục trực tuyến、Chỉnh sửa tập tin và duy trì sự phụ thuộc
5. **Agent Cài đặt bên trong**：Đại lý chính có thể vượt qua `install_skill` Công cụ，từ đường dẫn hộp cát hoặc Git Nguồn cài đặt người dùng hiện tại riêng tư Skill；Tác nhân con vô hiệu hóa công cụ

Không nên trực tiếp vận hành cơ sở dữ liệu hoặc nhập hệ thống tệp Skill。Viết tập tin trực tiếp sẽ không tự động tạo ra `skills` bảng ghi，Cũng không thể tham gia vào quyền、Phụ thuộc và gắn hộp cát。

## Skills Nguồn

Skills Về cơ bản là một gói các từ và công cụ nhắc nhở，Sau đây là một số để tham khảo Skills nhận ra：

- **Anthropic chính thức Tools**：https://github.com/anthropics/skills Bạn có thể tham khảo nó skills Cách tổ chức và thiết kế lời nhắc
- **ModelScope Skill thị trường**：https://modelscope.cn/skills Hỗ trợ đơn Skill địa chỉ，Nó cũng hỗ trợ kéo hàng loạt địa chỉ bộ sưu tập.
- **MiniMax-AI CLI**：https://github.com/MiniMax-AI/cli văn bản、hình ảnh、video、Tạo lời nói và âm nhạc + Web Tìm kiếm（Có thể vượt qua `MiniMax-AI/cli` Cài đặt từ xa）
- **cộng đồng Skills**：Được chia sẻ bởi nhiều nền tảng khác nhau Agent mẫu lời nhắc
- **Phát triển tùy chỉnh**：Tự phát triển theo nhu cầu kinh doanh

## bắt đầu nhanh

### Tạo đầu tiên của bạn Skill

một tiêu chuẩn Skill Cấu trúc thư mục như sau：

```
my-awesome-skill/
├── SKILL.md              # Bắt buộc，Skill tập tin định nghĩa cốt lõi
├── tools/                # Tùy chọn，Tập lệnh công cụ liên quan
│   └── helper.py
└── prompts/              # Tùy chọn，mẫu lời nhắc
    └── system.md
```

Trong số đó `SKILL.md` là mọi Skill Các tập tin cốt lõi phải được bao gồm，nó sử dụng Markdown + Frontmatter định dạng：

```markdown
---
name: My Awesome Skill
slug: my-awesome-skill
description: Đây là một kỹ năng được sử dụng để xử lý một nhiệm vụ cụ thể
---

# Skill Hướng dẫn sử dụng

Dưới đây là tài liệu sử dụng chi tiết của kỹ năng，Agent Sẽ đọc phần này để tìm hiểu cách sử dụng kỹ năng này。

## Danh sách tính năng

1. Chức năng một：xxx
2. Chức năng hai：yyy

## Ví dụ sử dụng

khi người dùng xxx thời gian，Kỹ năng này có thể được gọi...
```

**Frontmatter Mô tả trường：**

| trường | Bắt buộc | Mô tả |
|------|------|------|
| `name` | Có | Skill tên hiển thị，Một tên dễ đọc hơn có thể được sử dụng（Chẳng hạn như `Word / DOCX`） |
| `slug` | Không | Skill mã định danh duy nhất，Phải là chữ thường、con số、sự kết hợp của dấu gạch ngang，và không thể chứa dấu gạch ngang liên tiếp（Chẳng hạn như `my-skill`）。Tương thích với định dạng cũ khi không điền，Hệ thống sẽ sử dụng `name` như slug，tại thời điểm này `name` cũng phải thỏa mãn slug quy tắc |
| `description` | Có | Skill Mô tả chức năng，sẽ ở trong Agent Hiển thị trong quá trình cấu hình |

### nhập khẩu Skill

Nó có thể được nhập hoặc cài đặt thông qua Skill：

**Phương pháp một：Cài đặt từ danh sách được đề xuất**

1. thiết lập trong hệ thống「Skills quản lý」Lượt xem trang「Được đề xuất」Nhóm
2. Đề xuất chưa được cài đặt Skill Sẽ coi nó như bình thường Skill Hiển thị kiểu thẻ，Hiển thị bên phải `+`
3. Bấm vào thẻ giới thiệu hoặc `+` sau，Hệ thống sẽ sử dụng điều này Skill Kéo nội dung từ các nguồn từ xa
4. Sau khi kéo thành công, một bản nháp cài đặt sẽ bật lên.，Hoàn tất cài đặt sau khi xác nhận phạm vi chia sẻ

Đề xuất đã cài đặt Skill sẽ không còn xuất hiện trong「Được đề xuất」Trong nhóm。

**Phương pháp 2：Vượt qua ZIP gói hoặc SKILL.md tải lên**

1. sẽ Skill Thư mục được đóng gói thành ZIP tập tin（Lưu ý：ZIP Thư mục gốc là Skill Thư mục）
2. thiết lập trong hệ thống「Skills quản lý」Trang，nhấp chuột「tải lên Skill」
3. tải lên ZIP tập tin hoặc đơn `SKILL.md`
4. Hệ thống phân tích nội dung tải lên và trả về bản nháp cài đặt
5. Hoàn tất cài đặt sau khi xác nhận phạm vi chia sẻ；Bạn cũng có thể loại bỏ bản nháp

Hệ thống sẽ tự động：
- Xác minh ZIP Bảo mật nội dung và đường dẫn
- Kiểm tra slug xung đột（Nếu có xung đột, nó sẽ được thêm tự động. `-v2` v.v. hậu tố）
- phân tích cú pháp SKILL.md của frontmatter và lưu trữ trong cơ sở dữ liệu
- Xác minh phạm vi chia sẻ có thể lựa chọn dựa trên vai trò người dùng hiện tại

**Phương pháp ba：Cài đặt từ nguồn từ xa**

1. trong Skills Bấm vào trang quản lý「Cài đặt từ xa」
2. trong“Kéo theo kho”Điền nguồn，Ví dụ：
   - `anthropics/skills`
   - `https://github.com/anthropics/skills`
   - `https://modelscope.cn/skills/@anthropics/pdf`
   - `https://modelscope.cn/collections/MiniMax/MiniMax-Office-skills`
3. nhấp chuột“Kỹ năng kéo”Có thể được khám phá trong nguồn này Skills danh sách
4. độc thân Skill Địa chỉ thường được chọn tự động；Bạn có thể kiểm tra một hoặc nhiều địa chỉ kho hoặc địa chỉ nhận hàng trong danh sách Skills
5. nhấp chuột“Phân tích và xác nhận”，Hệ thống quay về bản nháp cài đặt，Sau khi xác nhận phạm vi chia sẻ, quá trình cài đặt được chính thức hóa.

Bạn cũng có thể chuyển sang“Khám phá tìm kiếm toàn cầu”，Nhập từ khóa tìm kiếm skills.sh Nguồn mở trên Skills，Sau đó chọn kết quả để cài đặt。

Hệ thống sẽ ở chế độ phụ trợ：
- gọi `npx skills add <source> --list` Xác minh nguồn và tìm có thể cài đặt skills
- Sử dụng cách ly tạm thời `HOME` thi hành `npx skills add <source> --skill <name> -g -y --copy`
- Trích xuất thư từ thư mục tạm thời skill，Sau đó tạo bản nháp theo quy trình nhập hiện có；Viết sau khi xác nhận `/app/saves/skills` với cơ sở dữ liệu

::: tip ModelScope Bộ sưu tập phù hợp cho việc cài đặt hàng loạt
ModelScope Địa chỉ bộ sưu tập có thể được điền vào dưới dạng nguồn từ xa，Ví dụ `https://modelscope.cn/collections/MiniMax/MiniMax-Office-skills`。Sau khi kéo, kiểm tra những cái cần thiết trong danh sách Skills，Sau đó thống nhất phân tích thành dự thảo lắp đặt。
:::

**Phương pháp bốn：Chỉnh sửa trực tuyến đã tồn tại Skill**

trong Skills Trang quản lý，bạn có thể：
- Tạo một thư mục hoặc tập tin mới
- Chỉnh sửa tập tin văn bản trực tuyến（hỗ trợ .md、.py、.js、.json định dạng vv）
- Sửa đổi trực tiếp trên trang web SKILL.md nội dung

Chỉ khi bạn có `can_manage` Chỉ những người dùng có quyền được ủy quyền mới có thể chỉnh sửa tệp.、phụ thuộc vào、Phạm vi chia sẻ và trạng thái kích hoạt。

::: tip Cài đặt từ xa sẽ không ~/.agents/skills Là bộ lưu trữ chính của hệ thống
Chỉ cài đặt từ xa `skills.sh` CLI như“Trình tải xuống”sử dụng。Yuxi Vẫn với `/app/saves/skills + skills bàn` là nguồn chính thức，Điều này sẽ cho phép các quyền hiện có được、Khả năng hiển thị luồng và cơ chế gắn hộp cát vẫn nhất quán。
:::

## Phụ thuộc vào hệ thống

Skills Sự phụ thuộc có thể được thiết lập giữa，Hình thành một mạng lưới kỹ năng gắn kết lỏng lẻo。

### loại phụ thuộc

mỗi Skill Ba loại phụ thuộc có thể được khai báo：

| loại phụ thuộc | Mô tả | Thời gian tải |
|----------|------|----------|
| `tool_dependencies` | Các công cụ tích hợp cần thiết | Tải theo yêu cầu sau khi kích hoạt |
| `mcp_dependencies` | cần thiết MCP dịch vụ | Tải theo yêu cầu sau khi kích hoạt |
| `skill_dependencies` | Phụ thuộc vào người khác Skill | Có hiệu lực ngay khi phiên bắt đầu |

### Cơ chế tải lũy tiến

Hệ thống áp dụng chiến lược tải lũy tiến ba cấp độ，Đảm bảo sử dụng hiệu quả các nguồn lực：

**Giai đoạn một：bắt đầu phiên**

Khi nào Agent Khi phiên bắt đầu，Hệ thống sẽ：
1. Tạo Graph Đọc đã lọc `context.skills` danh sách
2. Mở rộng đệ quy `skill_dependencies`，bắt nguồn từ `_prompt_skills` và `_readable_skills`
3. sẽ `_prompt_skills` Mô tả kỹ năng tương ứng được đưa vào từ nhắc nhở của hệ thống

điều này có nghĩa：Miễn là nhất định Skill，sự phụ thuộc của nó Skill Bạn sẽ nhập ngay từ nhắc và sandbox `/home/gem/skills` phạm vi chỉ đọc。

**Giai đoạn 2：Kích hoạt kỹ năng**

Khi nào Agent Vượt qua `read_file` đọc công cụ `/home/gem/skills/<slug>/SKILL.md` thời gian，coi là"kích hoạt"kỹ năng。Hệ thống sẽ：
1. Xác minh rằng kỹ năng có trong danh sách hiển thị
2. thêm nó vào `activated_skills` danh sách
3. Các cuộc gọi mô hình tiếp theo sẽ sử dụng danh sách kích hoạt để tải các phần phụ thuộc

**Giai đoạn ba：Tải theo yêu cầu**

mỗi khi mô hình được gọi，Hệ thống sẽ：
1. Kiểm tra `activated_skills` kỹ năng trong
2. Thu thập những kỹ năng này `tool_dependencies` và `mcp_dependencies`
3. Động lực sẽ yêu cầu các công cụ và MCP Dịch vụ được thêm vào bộ công cụ có sẵn

Ưu điểm của thiết kế này là：Không phải tất cả các công cụ đều được tải khi bắt đầu phiên，nhưng dựa trên Agent Việc sử dụng thực tế được tải theo yêu cầu，Tiết kiệm tài nguyên và đảm bảo tốc độ phản hồi。

### Ví dụ khai báo phụ thuộc

Giả sử chúng ta có ba Skills：

- **base-skill**：kỹ năng cơ bản，Không phụ thuộc
- **advanced-skill**：phụ thuộc vào `base-skill`
- **pro-skill**：phụ thuộc vào `advanced-skill`

dangzai Agent Chỉ chọn trong cấu hình `pro-skill` thời gian：
1. giai đoạn khởi động：`_readable_skills` = [`pro-skill`, `advanced-skill`, `base-skill`]（Tự động mở rộng chuỗi phụ thuộc）
2. Agent Lần đầu tiên bất kỳ skill thời gian：cả ba Skill Mọi người đều có thể đọc được
3. Khi nào Agent đọc `pro-skill/SKILL.md` thời gian：kích hoạt kích hoạt，công cụ và MCP Các phần phụ thuộc đã được tải

## Quản lý quyền

Skills sử dụng `source_type`、`share_config` và `enabled` nguồn điều khiển、Phạm vi chia sẻ và trạng thái kích hoạt。

| trường | Mô tả |
|------|------|
| `source_type` | `builtin`、`upload` hoặc `remote` |
| `share_config.access_level` | `global`、`department` hoặc `user` |
| `enabled` | Có được phép không Agent Cấu hình và sử dụng thời gian chạy |

Quy tắc truy cập và quản lý：

| người dùng | có thể nhìn thấy / Có sẵn | Có thể quản lý được |
|------|-------------|--------|
| siêu quản trị viên / Quản trị viên | Có thể xem có thể quản lý hoặc kích hoạt và có thể truy cập Skills | Có thể quản lý tất cả những thứ không tích hợp sẵn Skills；Tích hợp khởi động và dừng Skills |
| Người dùng thông thường | Có thể xem được kích hoạt và có thể truy cập được cho bạn Skills，Bạn cũng có thể cài đặt riêng của bạn Skill | Có thể quản lý các tập tin không tích hợp do chính bạn tạo Skills |
| Tích hợp sẵn Skills | Được chia sẻ trên toàn cầu và được bật theo mặc định | Quản trị viên có thể bắt đầu và dừng；Không được phép xóa hoặc chỉnh sửa trực tiếp các tập tin |

Giới hạn phạm vi chia sẻ：

- `global`：Có thể truy cập được cho tất cả người dùng
- `department`：Có thể truy cập được đối với người dùng ở các phòng ban được chỉ định
- `user`：Có thể truy cập được đối với người dùng được chỉ định；Người dùng thông thường chỉ có thể chọn phạm vi cá nhân khi cài đặt.

Quản trị viên và người dùng thông thường đang tạo hoặc chỉnh sửa Agent thời gian，chỉ có thể được truy cập và kích hoạt từ Skills khả năng lựa chọn。

## hành vi thời gian chạy

### Agent Cách sử dụng Skills

1. **Nhắc từ**：Tính năng tiêm động có sẵn cho hệ thống mỗi khi một mô hình được yêu cầu Skills Mô tả（Yêu cầu tiêm mức độ，tránh ô nhiễm runtime context）
2. **truy cập tập tin**：Skills Thư mục được gắn ở chế độ chỉ đọc vào `/home/gem/skills/<slug>/...`
3. **Cuộc gọi công cụ**：Khi nào Agent cần sử dụng một Skill thời gian，tương ứng SKILL.md Tìm hiểu cách sử dụng

### Hạn chế thao tác tập tin

thời gian chạy `/home/gem/skills` Đường dẫn có những hạn chế sau：
- **chỉ đọc**：Agent Chỉ có thể đọc nội dung tập tin
- **Tắt tính năng viết**：không thể tạo、Sửa đổi hoặc xóa tập tin
- **con đường an toàn**：Tất cả các đường dẫn đều được xác minh an toàn，Ngăn chặn các cuộc tấn công truyền tải thư mục

::: tip Hạn chế của hệ thống tệp ảo
hiện tại Skills Thư mục được gắn dưới dạng hệ thống tệp ảo，**Không được hỗ trợ shell thực thi lệnh**。Skill Tập lệnh trong chỉ để tham khảo từ nhắc nhở，Agent Các tập lệnh này không thể được thực thi trực tiếp。Nếu bạn cần thực hiện một chức năng cụ thể，Đề nghị vượt qua MCP Triển khai công cụ hoặc công cụ tùy chỉnh。
:::

### cách ly phiên

mỗi Agent Các phiên độc lập Skills bộ hiển thị：
- Các phiên khác nhau có thể được cấu hình với các phiên khác nhau Skills
- Chỉnh sửa trong cùng một phiên `context.skills` Sẽ kích hoạt việc xây dựng lại ảnh chụp nhanh
- Sửa đổi nền Skills Sau nội dung，Các phiên hiện tại sẽ không được tự động làm mới

## thực tiễn tốt nhất

### Skill Quy ước đặt tên

- `slug` Sử dụng chữ thường、Số và dấu gạch ngang，Không thể có dấu gạch ngang liên tục
- `slug` nên mang tính mô tả，Chẳng hạn như `weather-query`、`sql-reporter`
- `name` để trưng bày，Có thể so sánh `slug` tự nhiên hơn，Ví dụ `Word / DOCX`
- tránh quá dài `name` và `slug`

### Lời khuyên quản lý sự phụ thuộc

- **Giữ chuỗi phụ thuộc đơn giản**：Mức độ không nên quá sâu，trung bình 1-2 lớp thích hợp
- **Tránh phụ thuộc vòng tròn**：Hệ thống phát hiện và ngăn chặn sự phụ thuộc vòng tròn
- **Làm rõ sự cần thiết của sự phụ thuộc**：Chỉ xây dựng các phần phụ thuộc khi thực sự cần khả năng chia sẻ

### SKILL.md Kỹ năng viết

```markdown
---
name: example-skill
description: Mô tả ngắn gọn chức năng kỹ năng
---

# Tên kỹ năng

Dưới đây là hướng dẫn sử dụng chi tiết...

## Khi nào nên sử dụng

Mô tả tình huống nên sử dụng kỹ năng này...

## Cách sử dụng

1. bước đầu tiên...
2. Bước 2...

## Ví dụ

```
Ví dụ sử dụng cụ thể...
```
```

## Câu hỏi thường gặp

**Q：Tại sao tôi cấu hình Skill Không hiệu quả？**

A：Vui lòng kiểm tra các điểm sau：
1. Skill của slug Nó có được cấu hình đúng không? Agent của `context.skills` trong
2. SKILL.md Liệu nó có tồn tại và frontmatter Định dạng đúng
3. Nếu phụ thuộc được sử dụng，Đảm bảo chuỗi phụ thuộc đã hoàn tất

**Q：Cách cập nhật một bản đã nhập Skill？**

A：Điều này có thể được thực hiện theo những cách sau：
1. Xuất hiện tại Skill，Nhập lại sau khi sửa đổi
2. trong Skills Chỉnh sửa file trực tuyến trên trang quản lý
3. từ một nguồn từ xa Skill Có thể được phân tích lại và xác nhận để cài đặt，Tạo kết quả nhập mới

**Q：Skill Công cụ phụ thuộc/MCP Phải làm gì nếu nó không tồn tại？**

A：Hệ thống sẽ xác minh cấu hình phụ thuộc khi lưu nó，Nếu công cụ được tham chiếu hoặc MCP không tồn tại，Sẽ báo lỗi và ngăn chặn việc lưu。

---

Vượt qua Skills cơ chế，Yuxi cho Agent cung cấp một cách linh hoạt、Khung mở rộng khả năng mở rộng。Bạn có thể sử dụng kiến thức kinh doanh tích lũy của mình、Khả năng của công cụ được gói gọn trong Skills，làm khác đi Agent Tái sử dụng những khả năng này，Cải thiện đáng kể khả năng bảo trì và tái sử dụng của hệ thống。
