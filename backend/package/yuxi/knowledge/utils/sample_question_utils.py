"""Knowledge base sample question generation tool."""

import json
import textwrap
from typing import Any

from fastapi import HTTPException

from yuxi import config, knowledge_base
from yuxi.knowledge.factory import KnowledgeBaseFactory
from yuxi.models import select_model
from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository
from yuxi.utils import logger

SAMPLE_QUESTIONS_SYSTEM_PROMPT = """Bạn là một chuyên gia kiểm tra hỏi đáp cơ sở kiến thức chuyên nghiệp.

The task of youof is to generate valuable oftestquestion based on the ofdocument column surface in the knowledge base.

Require:
1. The question should be specific and targeted. Based on the file name and type, it is estimated that the content may be
2. Questions should cover different aspects and difficulty
3. The question should be concise and clear, suitable for retrieval tests
4. Questions should be diverse, including fact inquiries, concept explanations, operational guidance, etc.
5. Question length is limited to 10-30 words
6. Directly return the JSON array Format without any other explanation.

ReturnFormat:
```json
{
  "questions": [
    "Question 1?",
    "Question 2?",
    "Question 3?"
  ]
}
```
"""


def build_sample_question_file_list(files: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "filename": file_info.get("filename", ""),
            "type": file_info.get("type") or file_info.get("file_type", ""),
        }
        for file_info in files.values()
    ]


def build_sample_questions_user_message(db_name: str, files_info: list[dict[str, str]], count: int) -> str:
    files_text = "\n".join([f"- {file_info['filename']} ({file_info['type']})" for file_info in files_info[:20]])
    file_count_text = f"(common{len(files_info)}files)" if len(files_info) > 20 else ""

    return textwrap.dedent(f"""Please contribute to the knowledge base\"{db_name}\"generate{count}indivualtestquestion。

        knowledge baseddocument column surface{file_count_text}:
        {files_text}

        Please generate{count}A valuable testing question.""")


def parse_sample_questions_content(content: str) -> list[str]:
    if "```json" in content:
        json_start = content.find("```json") + 7
        json_end = content.find("```", json_start)
        if json_end == -1:
            raise ValueError("Khối mã JSON do AI trả về không đầy đủ")
        content = content[json_start:json_end].strip()
    elif "```" in content:
        json_start = content.find("```") + 3
        json_end = content.find("```", json_start)
        if json_end == -1:
            raise ValueError("Khối mã do AI trả về không đầy đủ")
        content = content[json_start:json_end].strip()

    questions_data = json.loads(content)
    questions = questions_data.get("questions", []) if isinstance(questions_data, dict) else []
    if not questions or not isinstance(questions, list):
        raise ValueError("Định dạng câu hỏi do AI trả về không chính xác")
    return questions


async def generate_database_sample_questions(kb_id: str, count: int = 10) -> dict[str, Any]:
    db_info = await knowledge_base.get_database_info(kb_id, include_files=True)
    if not db_info:
        raise HTTPException(status_code=404, detail=f"Cơ sở kiến thức {kb_id} không tồn tại")

    kb_type = (db_info.get("kb_type") or "").lower()
    if not KnowledgeBaseFactory.get_kb_class(kb_type).supports_documents:
        raise HTTPException(status_code=400, detail=f"{db_info.get('name') or kb_type} không hỗ trợ tạo câu hỏi kiểm tra dựa trên tệp")

    db_name = db_info.get("name", "")
    all_files = db_info.get("files", {})
    if not all_files:
        raise HTTPException(status_code=400, detail="Không có file trong kho kiến thức")

    files_info = build_sample_question_file_list(all_files)
    logger.info(f"Start generating knowledge base questions, knowledge base: {db_name}, Number of files: {len(files_info)}, Number of questions: {count}")

    model = select_model(model_spec=config.default_model)
    messages = [
        {"role": "system", "content": SAMPLE_QUESTIONS_SYSTEM_PROMPT},
        {"role": "user", "content": build_sample_questions_user_message(db_name, files_info, count)},
    ]
    response = await model.call(messages, stream=False)
    content = response.content if hasattr(response, "content") else str(response)

    try:
        questions = parse_sample_questions_content(content)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"JSON parsing returned by AI failed: {e}, original content: {content}")
        raise HTTPException(status_code=500, detail=f"Lỗi định dạng trả về từ AI: {str(e)}") from e

    logger.info(f"Successfully generated{len(questions)}questions")

    try:
        await KnowledgeBaseRepository().update(kb_id, {"sample_questions": questions})
        logger.info(f"Saved successfully {len(questions)} questions to the knowledge base {kb_id}")
    except Exception as save_error:
        logger.error(f"Failed to save problem: {save_error}")

    return {
        "message": "success",
        "questions": questions,
        "count": len(questions),
        "kb_id": kb_id,
        "db_name": db_name,
    }


async def get_database_sample_questions(kb_id: str) -> dict[str, Any]:
    kb = await KnowledgeBaseRepository().get_by_kb_id(kb_id)
    if kb is None:
        raise HTTPException(status_code=404, detail=f"Cơ sở kiến thức {kb_id} không tồn tại")

    questions = kb.sample_questions or []
    return {
        "message": "success",
        "questions": questions,
        "count": len(questions),
        "kb_id": kb_id,
    }
