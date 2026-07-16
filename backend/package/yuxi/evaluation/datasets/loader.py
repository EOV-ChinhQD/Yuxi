import json
import os
from typing import Any
from pydantic import BaseModel, Field


class DatasetItem(BaseModel):
    query: str = Field(..., description="Câu hỏi hoặc truy vấn đầu vào")
    gold_chunk_ids: list[str] = Field(
        default_factory=list, description="Danh sách chunk ID đúng mẫu (Ground Truth Chunks)"
    )
    gold_answer: str | None = Field(default=None, description="Câu trả lời chuẩn (Ground Truth Answer) nếu có")
    gold_intent: str | None = Field(default=None, description="Ý định đúng mẫu của câu hỏi (Ground Truth Intent)")


class DatasetMetadata(BaseModel):
    name: str = Field(..., description="Tên của tập dữ liệu")
    description: str | None = Field(default=None, description="Mô tả chi tiết tập dữ liệu")
    corpus_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata của corpus gốc phục vụ phân nhóm lọc (ví dụ: doc_type, language, source)",
    )


class EvaluationDataset(BaseModel):
    metadata: DatasetMetadata = Field(..., description="Thông tin mô tả tập dữ liệu")
    items: list[DatasetItem] = Field(default_factory=list, description="Danh sách các câu hỏi test")


class DatasetLoader:
    @staticmethod
    def load_from_jsonl(file_path: str, metadata_path: str | None = None) -> EvaluationDataset:
        """
        Nạp tập dữ liệu (dataset) từ đường dẫn tệp JSONL cục bộ.
        Kiểm chứng cấu trúc tệp dữ liệu JSONL (phải có trường 'query').

        Args:
            file_path: Đường dẫn tuyệt đối tới tệp JSONL chứa câu hỏi.
            metadata_path: Đường dẫn tùy chọn tới tệp JSON chứa metadata của dataset.

        Returns:
            Đối tượng EvaluationDataset đã được nạp và kiểm chứng.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Không tìm thấy tệp dataset tại đường dẫn: {file_path}")

        items = []
        with open(file_path, encoding="utf-8") as f:
            for idx, line in enumerate(f, 1):
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    data = json.loads(line_str)
                    if "query" not in data:
                        raise ValueError("Thiếu trường 'query' bắt buộc")

                    item = DatasetItem(
                        query=data["query"],
                        gold_chunk_ids=data.get("gold_chunk_ids", []),
                        gold_answer=data.get("gold_answer"),
                        gold_intent=data.get("gold_intent"),
                    )
                    items.append(item)
                except Exception as e:
                    raise ValueError(f"Lỗi kiểm chứng dòng {idx} trong tệp JSONL {file_path}: {e}")

        # Tự động lấy tên mặc định từ tên file
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        meta_name = base_name
        meta_desc = f"Được nạp tự động từ tệp {file_path}"
        corpus_meta = {}

        # Nạp tệp metadata nếu được chỉ định
        target_meta_path = metadata_path
        if not target_meta_path:
            # Thử tìm file metadata.json nằm cùng thư mục
            dir_name = os.path.dirname(file_path)
            possible_meta = os.path.join(dir_name, f"{base_name}_metadata.json")
            if os.path.exists(possible_meta):
                target_meta_path = possible_meta

        if target_meta_path and os.path.exists(target_meta_path):
            try:
                with open(target_meta_path, encoding="utf-8") as f:
                    meta_data = json.load(f)
                    meta_name = meta_data.get("name", meta_name)
                    meta_desc = meta_data.get("description", meta_desc)
                    corpus_meta = meta_data.get("corpus_metadata", {})
            except Exception:
                # Ghi nhận lỗi nhưng không dừng tiến trình
                pass

        return EvaluationDataset(
            metadata=DatasetMetadata(
                name=meta_name,
                description=meta_desc,
                corpus_metadata=corpus_meta,
            ),
            items=items,
        )
