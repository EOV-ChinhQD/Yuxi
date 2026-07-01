from __future__ import annotations

import argparse
from datetime import UTC, datetime

from langfuse import Langfuse


PYTHON_TASK_ITEMS = [
    {
        "id": "py-task-001",
        "input": (
            "Vui lòng sử dụng Python Hoàn thành nhiệm vụ và đưa ra câu trả lời cuối cùng：đưa ra nums = [7, -2, 5, 11, -8, 4]，"
            "Chỉ giữ số dương，tổng sau khi bình phương。Vui lòng chỉ xuất số nguyên cuối cùng。"
        ),
        "expected_output": "211",
    },
    {
        "id": "py-task-002",
        "input": (
            "Vui lòng sử dụng Python Hoàn thành nhiệm vụ và đưa ra câu trả lời cuối cùng：văn bản đã cho 'alpha,beta;gamma delta\\nepsilon'，"
            "nhấn dấu phẩy、dấu chấm phẩy、Phân đoạn khoảng trắng và dòng mới token，thống kê token con số。Vui lòng chỉ xuất số nguyên cuối cùng。"
        ),
        "expected_output": "5",
    },
    {
        "id": "py-task-003",
        "input": (
            "Vui lòng sử dụng Python Hoàn thành nhiệm vụ và đưa ra câu trả lời cuối cùng：Tính toán 1 Đến 200 Tất cả trong đó có thể được 7 chia hết nhưng không chia hết cho 5 số nguyên chia hết。"
            "Vui lòng chỉ xuất số nguyên cuối cùng。"
        ),
        "expected_output": "23",
    },
    {
        "id": "py-task-004",
        "input": (
            "Vui lòng sử dụng Python Hoàn thành nhiệm vụ và đưa ra câu trả lời cuối cùng：đưa ra records = [('a', 3), ('b', 5), ('a', 4), ('c', 2), ('b', -1)]，"
            "nhấn key Giá trị tóm tắt，và nhấn key Đầu ra theo thứ tự bảng chữ cái trông giống như a=7,b=4,c=2 chuỗi。"
        ),
        "expected_output": "a=7,b=4,c=2",
    },
    {
        "id": "py-task-005",
        "input": (
            "Vui lòng sử dụng Python Hoàn thành nhiệm vụ và đưa ra câu trả lời cuối cùng：ma trận đã cho [[1, 2, 3], [4, 5, 6], [7, 8, 9]]，"
            "Tính tổng các đường chéo chính trừ đi tổng các đường chéo phụ。Vui lòng chỉ xuất số nguyên cuối cùng。"
        ),
        "expected_output": "0",
    },
    {
        "id": "py-task-006",
        "input": (
            "Vui lòng sử dụng Python Hoàn thành nhiệm vụ và đưa ra câu trả lời cuối cùng：đưa ra s = 'Yuxi Agent Evaluation'，"
            "Bỏ qua số liệu thống kê trường hợp cho nguyên âm a/e/i/o/u tổng số。Vui lòng chỉ xuất số nguyên cuối cùng。"
        ),
        "expected_output": "10",
    },
    {
        "id": "py-task-007",
        "input": (
            "Vui lòng sử dụng Python Hoàn thành nhiệm vụ và đưa ra câu trả lời cuối cùng：khoảng nhất định [10, 50]，Tìm tất cả các số nguyên tố và tính tổng chúng。"
            "Vui lòng chỉ xuất số nguyên cuối cùng。"
        ),
        "expected_output": "311",
    },
    {
        "id": "py-task-008",
        "input": (
            "Vui lòng sử dụng Python Hoàn thành nhiệm vụ và đưa ra câu trả lời cuối cùng：đưa ra JSON chuỗi "
            "'{\"items\":[{\"price\":12.5,\"qty\":2},{\"price\":3,\"qty\":5},{\"price\":8,\"qty\":1}]}'，"
            "Đếm tất cả price * qty tổng của。Vui lòng chỉ xuất số cuối cùng，Giữ đến một chữ số thập phân。"
        ),
        "expected_output": "48.0",
    },
    {
        "id": "py-task-009",
        "input": (
            "Vui lòng sử dụng Python Hoàn thành nhiệm vụ và đưa ra câu trả lời cuối cùng：đưa ra words = ['graph', 'rag', 'agent', 'tool', 'trace']，"
            "Sắp xếp theo độ dài từ tăng dần、Sắp xếp theo thứ tự bảng chữ cái nếu độ dài bằng nhau，Sử dụng cùng nhau '-' kết nối。"
        ),
        "expected_output": "rag-tool-agent-graph-trace",
    },
    {
        "id": "py-task-010",
        "input": (
            "Vui lòng sử dụng Python Hoàn thành nhiệm vụ và đưa ra câu trả lời cuối cùng：tạo ra Fibonacci trước trình tự 12 mục（từ 0, 1 bắt đầu），"
            "Tính tổng các số hạng chẵn。Vui lòng chỉ xuất số nguyên cuối cùng。"
        ),
        "expected_output": "44",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload a Python task dataset to Langfuse.")
    parser.add_argument(
        "--dataset-name",
        default=f"yuxi-python-tasks-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}",
        help="Langfuse dataset name. Defaults to a timestamped name.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client = Langfuse()
    client.create_dataset(
        name=args.dataset_name,
        description="Yuxi agent evaluation dataset: deterministic Python programming tasks.",
        metadata={
            "source": "scripts/eval/upload_langfuse_python_tasks_dataset.py",
            "task_type": "python_programming",
            "item_count": len(PYTHON_TASK_ITEMS),
        },
    )
    for item in PYTHON_TASK_ITEMS:
        client.create_dataset_item(
            dataset_name=args.dataset_name,
            id=item["id"],
            input={"input": item["input"]},
            expected_output=item["expected_output"],
            metadata={"category": "python_programming", "source": "yuxi_eval_smoke"},
        )
    client.flush()
    print(args.dataset_name)


if __name__ == "__main__":
    main()
