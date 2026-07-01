/**
 * APItập tin chỉ mục mô-đun
 * Xuất tất cảAPImô-đun，Giới thiệu thuận tiện và thống nhất
 */

// Xuất khẩuAPImô-đun
export * from './system_api' // Quản lý hệ thốngAPI
export * from './knowledge_api' // Quản lý cơ sở tri thứcAPI
export * from './graph_api' // tập bản đồAPI
export * from './agent_api' // đại lýAPI
export * from './tasker' // quản lý công việcAPI
export * from './department_api' // Quản lý bộ phậnAPI
export * from './mcp_api' // MCP API
export * from './skill_api' // Skills API
export * from './tool_api' // Công cụ API
export * from './mention_api' // đề cập đến tìm kiếm API
export * from './user_api' // Tài nguyên người dùng API

// Xuất các chức năng công cụ cơ bản
export {
  apiGet,
  apiPost,
  apiPut,
  apiDelete,
  apiAdminGet,
  apiAdminPost,
  apiAdminPut,
  apiAdminDelete,
  apiSuperAdminGet,
  apiSuperAdminPost,
  apiSuperAdminPut,
  apiSuperAdminDelete
} from './base'

/**
 * APIMô tả mô-đun:
 *
 * 1. system_api.js: Quản lý hệ thốngAPI
 *    - kiểm tra sức khỏe、Quản lý cấu hình、quản lý thông tin、OCRdịch vụ
 *    - Yêu cầu về quyền: Công khai một phần，Một số yêu cầu quyền quản trị viên
 *
 * 2. knowledge_api.js: Quản lý cơ sở tri thứcAPI
 *    - Quản lý cơ sở dữ liệu、Quản lý tài liệu、Giao diện truy vấn、Quản lý tập tin
 *    - Yêu cầu về quyền: Quyền quản trị viên
 *
 *
 * 4. graph_api.js: tập bản đồAPI
 *    - Các hàm liên quan đến đồ thị tri thức
 *
 * 5. tools.js: Công cụAPI
 *    - Thu thập thông tin công cụ
 *
 * 6. agent.js: đại lýAPI
 *    - Quản lý đại lý、trò chuyện、Cấu hình và các chức năng khác
 *
 * Lưu ý：APIMô-đun đã xử lý các tiêu đề xác minh quyền và yêu cầu，Không cần thêm tiêu đề xác thực theo cách thủ công khi sử dụng
 */
