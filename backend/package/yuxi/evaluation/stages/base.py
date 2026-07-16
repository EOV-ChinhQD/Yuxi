import random
from typing import Any, Protocol, runtime_checkable
from pydantic import BaseModel, Field


class ReportSchema(BaseModel):
    metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Chỉ số chất lượng đánh giá (ví dụ: Recall, NDCG, Accuracy, Groundedness...)",
    )
    performance: dict[str, Any] = Field(
        default_factory=dict,
        description="Chỉ số hiệu năng (ví dụ: Latency, Indexing Time, Throughput...)",
    )
    cost: dict[str, Any] = Field(
        default_factory=dict,
        description="Chỉ số chi phí (ví dụ: Token cost, API cost...)",
    )
    reliability: dict[str, Any] = Field(
        default_factory=dict,
        description="Chỉ số độ tin cậy (ví dụ: Retry rate, Timeout, Fallback count...)",
    )
    regression: dict[str, Any] = Field(
        default_factory=dict,
        description="Chỉ số so sánh tương đối (phần trăm thay đổi/cải thiện) so với Baseline",
    )


@runtime_checkable
class EvaluationStage(Protocol):
    def prepare(self, dataset_path: str, manifest: dict[str, Any]) -> None:
        """
        Chuẩn bị dữ liệu và tài nguyên cho Stage.

        Args:
            dataset_path: Đường dẫn tới tệp dữ liệu dataset / corpus.
            manifest: Cấu hình manifest của thực nghiệm hiện tại dưới dạng dictionary.
        """
        ...

    async def run(self) -> None:
        """
        Chạy thực thi tác vụ đánh giá (như thực hiện search, sinh câu trả lời, parse tài liệu).
        """
        ...

    async def evaluate(self) -> dict[str, Any]:
        """
        Tính toán các chỉ số metrics dựa trên kết quả đã chạy.

        Returns:
            Dict chứa các kết quả chấm điểm thô hoặc tổng hợp của stage.
        """
        ...

    def report(self) -> ReportSchema:
        """
        Trả về báo cáo chi tiết tuân thủ cấu trúc chuẩn ReportSchema.

        Returns:
            Đối tượng ReportSchema chứa đầy đủ thông tin báo cáo.
        """
        ...


def calculate_bootstrap_ci(
    scores: list[float], n_bootstrap: int = 1000, ci_level: float = 0.95
) -> tuple[float, float, float]:
    """
    Tính toán Mean, Lower Bound và Upper Bound của Confidence Interval sử dụng phương pháp Bootstrap.

    Args:
        scores: Danh sách các điểm số thu được.
        n_bootstrap: Số lượng lượt lấy mẫu lại (resampling).
        ci_level: Độ tin cậy (mặc định 95%).

    Returns:
        Tuple chứa (mean_value, lower_bound, upper_bound).
    """
    if not scores:
        return 0.0, 0.0, 0.0

    n = len(scores)
    means = []
    # Cài đặt cố định seed để kết quả ổn định và lặp lại được trong test
    rng = random.Random(42)

    for _ in range(n_bootstrap):
        sample = rng.choices(scores, k=n)
        means.append(sum(sample) / n)

    means.sort()

    mean_val = sum(scores) / n
    alpha = 1.0 - ci_level
    lower_idx = int(n_bootstrap * (alpha / 2))
    upper_idx = int(n_bootstrap * (1.0 - alpha / 2))

    lower_idx = max(0, min(lower_idx, n_bootstrap - 1))
    upper_idx = max(0, min(upper_idx, n_bootstrap - 1))

    return mean_val, means[lower_idx], means[upper_idx]
