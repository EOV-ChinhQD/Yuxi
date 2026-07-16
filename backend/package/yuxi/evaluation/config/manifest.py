from __future__ import annotations
import datetime
import yaml
from pydantic import BaseModel, Field


class EmbeddingConfig(BaseModel):
    provider: str = Field(..., description="Nhà cung cấp embedding (ví dụ: openai, huggingface, local)")
    model: str = Field(..., description="Tên model embedding sử dụng")
    revision: str | None = Field(default=None, description="Phiên bản hoặc revision cụ thể (nhằm chống drift)")


class EvaluationManifest(BaseModel):
    experiment_id: str = Field(..., description="Mã định danh duy nhất cho cuộc thực nghiệm")
    dataset: str = Field(..., description="Tên tập dữ liệu snapshot được sử dụng")
    embedding: EmbeddingConfig = Field(..., description="Cấu hình mô hình nhúng (Embedding)")
    chunker: str = Field(..., description="Tên phương pháp/cấu hình phân đoạn văn bản (Chunking)")
    retriever: str = Field(..., description="Tên phương pháp/cấu hình truy xuất (Retrieval)")
    reranker: str | None = Field(default=None, description="Tên bộ xếp hạng lại (Reranker) nếu có")
    llm: str = Field(..., description="Tên mô hình ngôn ngữ lớn (LLM) để sinh phản hồi hoặc đánh giá")
    prompt_version: str | None = Field(default=None, description="Phiên bản system prompt sử dụng")
    nli_version: str | None = Field(default=None, description="Phiên bản NLI verifier sử dụng")
    date: datetime.date | str | None = Field(default=None, description="Ngày thực hiện thực nghiệm")

    @classmethod
    def from_yaml(cls, yaml_content: str) -> EvaluationManifest:
        """
        Nạp cấu hình từ chuỗi nội dung YAML.
        """
        try:
            data = yaml.safe_load(yaml_content)
            if not isinstance(data, dict):
                raise ValueError("Nội dung YAML phải trả về một dictionary")
            return cls(**data)
        except Exception as e:
            raise ValueError(f"Lỗi cú pháp hoặc xác thực Manifest YAML: {e}")

    @classmethod
    def from_file(cls, file_path: str) -> EvaluationManifest:
        """
        Nạp cấu hình từ đường dẫn tệp tin YAML.
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
            return cls.from_yaml(content)
        except Exception as e:
            raise ValueError(f"Không thể nạp tệp cấu hình Manifest từ {file_path}: {e}")
