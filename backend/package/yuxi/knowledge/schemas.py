from typing import Any, Literal

from pydantic import BaseModel, Field


class SearchInputSchema(BaseModel):
    kb_id: str = Field(description="ID tài nguyên kho kiến thức, tức là kb_id")
    query_text: str = Field(
        description="Từ khóa tìm kiếm, nên được trích xuất thành từ khóa hoặc cụm từ giúp truy xuất câu trả lời"
    )
    file_name: str | None = Field(
        default=None, description="Lọc từ khóa tên file tùy chọn, không sử dụng nếu không cần thiết"
    )


class SearchResultSchema(BaseModel):
    id: str = Field(description="ID kết quả tìm kiếm, thường tương ứng với chunk_id")
    kb_id: str = Field(description="ID tài nguyên kho kiến thức, tức là kb_id")
    file_id: str = Field(default="", description="ID file thuộc về kết quả, có thể dùng cho Find/Open")
    content: str = Field(description="nội dung chunk")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Thông tin bổ sung như nguồn, điểm số, chunk_index, v.v."
    )


class SearchOutputSchema(BaseModel):
    kb_id: str = Field(description="ID tài nguyên kho kiến thức, tức là kb_id")
    results: list[SearchResultSchema] = Field(default_factory=list, description="Danh sách kết quả tìm kiếm")


class FindInputSchema(BaseModel):
    kb_id: str = Field(description="ID tài nguyên kho kiến thức, tức là kb_id")
    file_id: str = Field(description="ID file cần tìm kiếm")
    patterns: list[str] = Field(description="Danh sách từ khóa hoặc regex, cung cấp ít nhất một")
    use_regex: bool = Field(default=False, description="Có xử lý patterns dưới dạng regex không")
    case_sensitive: bool = Field(default=False, description="Có phân biệt chữ hoa chữ thường không")
    max_windows: int = Field(default=5, ge=1, le=20, description="Số lượng cửa sổ ngữ cảnh tối đa trả về")
    window_size: int = Field(default=80, ge=1, le=200, description="Số dòng của mỗi cửa sổ ngữ cảnh")


class FindWindowSchema(BaseModel):
    start_line: int = Field(description="Số dòng bắt đầu cửa sổ, bắt đầu từ 1")
    end_line: int = Field(description="Số dòng kết thúc cửa sổ, bắt đầu từ 1")
    matched_lines: list[int] = Field(default_factory=list, description="Số dòng khớp trong cửa sổ này")
    content: str = Field(description="Nội dung cửa sổ có số dòng")


class FindOutputSchema(BaseModel):
    kb_id: str = Field(description="ID tài nguyên kho kiến thức, tức là kb_id")
    file_id: str = Field(description="ID file")
    semantic: bool = Field(default=False, description="Có phải tìm kiếm ngữ nghĩa không")
    match_mode: Literal["keyword", "regex"] = Field(description="Chế độ khớp")
    total_matches: int = Field(description="Số dòng khớp")
    windows: list[FindWindowSchema] = Field(default_factory=list, description="Cửa sổ ngữ cảnh")


class OpenInputSchema(BaseModel):
    kb_id: str = Field(description="ID tài nguyên kho kiến thức, tức là kb_id")
    file_id: str = Field(description="ID file cần mở")
    line: int | None = Field(default=None, ge=1, description="Tùy chọn, số dòng bắt đầu, bắt đầu từ 1")
    offset: int | None = Field(
        default=None, ge=0, description="Tùy chọn, độ lệch bắt đầu, bắt đầu từ 0; line ưu tiên hơn offset"
    )
    window_size: int = Field(default=1800, ge=1, le=2000, description="Đọc số dòng cửa sổ")


class OpenOutputSchema(BaseModel):
    kb_id: str = Field(description="ID tài nguyên kho kiến thức, tức là kb_id")
    file_id: str = Field(description="ID file")
    start_line: int = Field(description="Số dòng bắt đầu cửa sổ, bắt đầu từ 1; kết quả rỗng là 0")
    end_line: int = Field(description="Số dòng kết thúc cửa sổ, bắt đầu từ 1; kết quả rỗng là 0")
    total_lines: int = Field(description="Tổng số dòng của file")
    offset: int = Field(description="Độ lệch bắt đầu cửa sổ, bắt đầu từ 0")
    window_size: int = Field(description="Số dòng cửa sổ được yêu cầu lần này")
    has_more_before: bool = Field(description="Cửa sổ trước có nội dung không")
    has_more_after: bool = Field(description="Cửa sổ sau có nội dung không")
    next_offset: int | None = Field(
        default=None, description="offset của cửa sổ tiếp theo; null khi không còn nội dung"
    )
    content: str = Field(description="Nội dung cửa sổ có số dòng")
