"""Đã loại bỏ 2 test cũ cho KnowledgeBaseManager.aquery(caller_uid=...).

API này không còn tồn tại sau khi port kiến trúc mới từ auth/Yuxi:
- Kiểm soát truy cập KB được thực thi ở tầng router qua permission dependencies
  (require_knowledge_base_read/manage) và qua danh sách KB hiển thị của phiên agent
  (_resolve_visible_knowledge_bases_for_query).
- Phạm vi test tương ứng: test_evaluation_resource_permission.py, test_kbs_tools.py.
"""
