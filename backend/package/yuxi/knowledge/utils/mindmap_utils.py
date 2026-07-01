"""Mind mapping tool function."""

import copy
import json
import textwrap
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException

from yuxi import config, knowledge_base
from yuxi.models import select_model
from yuxi.repositories.knowledge_base_repository import KnowledgeBaseRepository
from yuxi.utils import logger

MINDMAP_FILE_PAGE_SIZE = 500
MINDMAP_GENERATION_FILE_LIMIT = 200

MINDMAP_SYSTEM_PROMPT = """Bạn là một trợ lý sắp xếp kiến thức chuyên nghiệp.

Your task is to analyze the list of files provided by the user and generate a hierarchical mind map structure.

**Core rule: Each file name may appear only once! No duplicates allowed!**

Require:
1. Mind maps should have a clear hierarchical structure (2-4 levels)
2. The root node is Knowledge base name
3. The first layer is the main category (like: technical document, chapter system, data resources, etc.)
4. The second layer is a sub-category
5. **Leaf nodes must be specific file names**
6. **Each file name can only appear once in the entire mind map and cannot be repeated!**
7. If one file may belong to multiple categories, only select the most suitable category to place.
8. Use appropriate emoji tags to enhance readability
9. Returns JSON format, following the following structure:

```json
{
  "content": "Knowledge base name",
  "children": [
    {
      "content": "🎯 Main category 1",
      "children": [
        {
          "content": "Subcategory 1.1",
          "children": [
            {"content": "File name 1.txt", "children": []},
            {"content": "File name 2.pdf", "children": []}
          ]
        }
      ]
    },
    {
      "content": "💻 Main category 2",
      "children": [
        {"content": "File name 3.docx", "children": []},
        {"content": "File name 4.md", "children": []}
      ]
    }
  ]
}
```

**Important constraints:**
- Each file name can only appear once in the entire JSON
- Do not classify files by multiple dimensions resulting in duplication of files
- Choose the most important and appropriate classification dimension
- The children of each leaf node must be an empty array[]
- Category names should be concise and clear
- Use emoji to enhance visual effects
"""

MINDMAP_INCREMENTAL_SYSTEM_PROMPT = """Bạn là một trợ lý sắp xếp kiến thức chuyên nghiệp.

Your task is to integrate the new document into the existing mind map structure.

**Core rules:**
1. Keep the existing category structure unchanged.
2. It is most suitable to add the new document to the existing category.
3. If the new document does not belong to any existing category, you can create a new category node.
4. Each individual file name can only appear once, no repetitions are allowed.
5. If the existing category name needs to be fine-tuned to accommodate the new document, it can be adjusted appropriately.
6. Return the complete mind map JSON (including the original structure + new document)

The returned JSON Format is the same as the standard mind map structure.
"""


def build_database_file_list(files: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "file_id": file_id,
            "filename": file_info.get("filename", ""),
            "type": file_info.get("type", ""),
            "status": file_info.get("status", ""),
            "created_at": file_info.get("created_at", ""),
        }
        for file_id, file_info in files.items()
    ]


def _file_record_to_mindmap_file(record: Any) -> dict[str, Any]:
    created_at = getattr(record, "created_at", None)
    return {
        "file_id": getattr(record, "file_id"),
        "filename": getattr(record, "filename", None) or "",
        "type": getattr(record, "file_type", None) or "",
        "status": getattr(record, "status", None) or "",
        "created_at": created_at.isoformat() if created_at else "",
    }


async def _list_mindmap_files_page(
    kb_id: str, *, page_size: int = MINDMAP_FILE_PAGE_SIZE
) -> tuple[dict[str, dict], int]:
    from yuxi.repositories.knowledge_file_repository import KnowledgeFileRepository

    records, total = await KnowledgeFileRepository().list_documents(
        kb_id=kb_id,
        page=1,
        page_size=page_size,
        files_only=True,
    )
    return {record.file_id: _file_record_to_mindmap_file(record) for record in records}, total


async def _load_mindmap_current_files(kb_id: str, tracked_file_ids: list[str]) -> tuple[dict[str, dict], int]:
    from yuxi.repositories.knowledge_file_repository import KnowledgeFileRepository

    current_files, total = await _list_mindmap_files_page(kb_id)
    tracked_ids = [file_id for file_id in tracked_file_ids if file_id]
    if not tracked_ids:
        return current_files, total

    tracked_records = await KnowledgeFileRepository().list_by_file_ids(tracked_ids)
    for record in tracked_records:
        if record.kb_id == kb_id and not record.is_folder:
            current_files[record.file_id] = _file_record_to_mindmap_file(record)
    return current_files, total


def collect_mindmap_files(all_files: dict[str, dict[str, Any]], file_ids: list[str]) -> list[dict[str, str]]:
    return [
        {
            "filename": all_files[file_id].get("filename", ""),
            "type": all_files[file_id].get("type", ""),
        }
        for file_id in file_ids
        if file_id in all_files
    ]


def build_mindmap_user_message(db_name: str, files_info: list[dict[str, str]], user_prompt: str = "") -> str:
    files_text = "\n".join([f"- {file_info['filename']} ({file_info['type']})" for file_info in files_info])
    return textwrap.dedent(f"""Please generate a mind map structure for the knowledge base "{db_name}".

        Document list (total {len(files_info)} files):
        {files_text}

        {f"Additional user instructions:{user_prompt}" if user_prompt else ""}

        **Important reminder:**
        1. This knowledge base has {len(files_info)} files
        2. Each individual file name can only appear once in the mind map.
        3. Do not let the same file appear under multiple categories
        4. Select the most appropriate category for each file

        Please generate a reasonable mind map structure. """)


def build_mindmap_incremental_user_message(
    db_name: str, mindmap_data: dict[str, Any], added_files: list[dict[str, str]], user_prompt: str = ""
) -> str:
    existing_structure = json.dumps(mindmap_data, ensure_ascii=False, indent=2)
    files_text = "\n".join([f"- {f['filename']} ({f['type']})" for f in added_files])
    return textwrap.dedent(f"""Please integrate the following new documents into the existing mind map of the knowledge base "{db_name}".

        Existing mind map structure:
        {existing_structure}

        Added file list (total {len(added_files)} files):
        {files_text}

        {f"Additional user instructions:{user_prompt}" if user_prompt else ""}

        **Important reminder:**
        1. Keep the existing category structure, and it is most suitable to add the new document to the existing category.
        2. If the new document does not fit any existing category, create a new category node
        3. Each individual file name can only appear once.
        4. Return the complete mind map JSON (including the original structure + new document)

        Please integrate the new document into the existing structure. """)


def parse_mindmap_content(content: str) -> dict[str, Any]:
    if "```json" in content:
        json_start = content.find("```json") + 7
        json_end = content.find("```", json_start)
        content = content[json_start:json_end].strip()
    elif "```" in content:
        json_start = content.find("```") + 3
        json_end = content.find("```", json_start)
        content = content[json_start:json_end].strip()

    mindmap_data = json.loads(content)
    if not isinstance(mindmap_data, dict) or "content" not in mindmap_data:
        raise ValueError("Cấu trúc sơ đồ tư duy không chính xác")
    return mindmap_data


def detect_mindmap_changes(
    mindmap_data: dict[str, Any] | None,
    mindmap_file_ids: dict[str, str] | None,
    current_files: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Compare the files tracked by the mind map with the current files in the knowledge base and return the change information."""
    # Compatible with old data: if a mind map exists but the tracked file_ids are missing, reconstruct the mapping backwards through the leaf nodes
    if mindmap_data and not mindmap_file_ids:
        leaf_filenames = _collect_leaf_filenames(mindmap_data)
        mindmap_file_ids = {
            fid: info.get("filename", "")
            for fid, info in current_files.items()
            if info.get("filename", "") in leaf_filenames
        }

    if not mindmap_data or not mindmap_file_ids:
        added_files = [
            {"file_id": fid, "filename": info.get("filename", ""), "type": info.get("type", "")}
            for fid, info in current_files.items()
        ]
        return {
            "has_mindmap": mindmap_data is not None,
            "tracked_files": list(mindmap_file_ids.keys()) if mindmap_file_ids else [],
            "current_files": list(current_files.keys()),
            "added_files": added_files,
            "removed_file_ids": [],
            "unchanged_count": 0,
            "needs_update": len(added_files) > 0,
        }

    tracked_ids = set(mindmap_file_ids.keys())
    current_ids = set(current_files.keys())

    removed_file_ids = list(tracked_ids - current_ids)
    added_file_ids = current_ids - tracked_ids
    added_files = [
        {"file_id": fid, "filename": current_files[fid].get("filename", ""), "type": current_files[fid].get("type", "")}
        for fid in sorted(added_file_ids)
        if fid in current_files
    ]
    unchanged_count = len(tracked_ids & current_ids)

    return {
        "has_mindmap": True,
        "tracked_files": list(tracked_ids),
        "current_files": list(current_ids),
        "added_files": added_files,
        "removed_file_ids": removed_file_ids,
        "unchanged_count": unchanged_count,
        "needs_update": len(added_files) > 0 or len(removed_file_ids) > 0,
    }


def _prune_mindmap_node(node: dict[str, Any], removed_filenames: set[str], root_name: str) -> dict[str, Any] | None:
    """Recursively prune mind map nodes and remove leaf nodes with specified file names."""
    content = node.get("content", "")
    children = node.get("children", [])

    if not children:
        if content in removed_filenames:
            return None
        return node

    pruned_children = []
    for child in children:
        result = _prune_mindmap_node(child, removed_filenames, root_name)
        if result is not None:
            pruned_children.append(result)

    if not pruned_children:
        if content == root_name:
            node["children"] = []
            return node
        return None

    node["children"] = pruned_children
    return node


def remove_files_from_mindmap(mindmap_data: dict[str, Any], removed_filenames: set[str]) -> dict[str, Any]:
    """Removes the leaf node of the specified file name from the mind map tree without AI call."""
    if not removed_filenames:
        return mindmap_data

    mindmap_copy = copy.deepcopy(mindmap_data)
    root_name = mindmap_copy.get("content", "")
    result = _prune_mindmap_node(mindmap_copy, removed_filenames, root_name)
    return result if result is not None else {"content": root_name, "children": []}


async def get_mindmap_database_files(kb_id: str) -> dict[str, Any]:
    kb = await KnowledgeBaseRepository().get_by_kb_id(kb_id)
    if kb is None:
        raise HTTPException(status_code=404, detail=f"Cơ sở kiến thức {kb_id} không tồn tại")

    current_files, total = await _list_mindmap_files_page(kb_id)
    return {
        "message": "success",
        "kb_id": kb_id,
        "slug": kb_id,
        "db_name": kb.name,
        "files": build_database_file_list(current_files),
        "total": total,
        "truncated": total > len(current_files),
    }


async def get_mindmap_diff(kb_id: str) -> dict[str, Any]:
    """Get mind map change detection results."""
    kb = await KnowledgeBaseRepository().get_by_kb_id(kb_id)
    if kb is None:
        raise HTTPException(status_code=404, detail=f"Cơ sở kiến thức {kb_id} không tồn tại")

    current_files, total = await _load_mindmap_current_files(kb_id, list((kb.mindmap_file_ids or {}).keys()))

    changes = detect_mindmap_changes(kb.mindmap, kb.mindmap_file_ids, current_files)
    changes["current_total"] = total
    changes["current_files_truncated"] = total > len(current_files)
    changes["kb_id"] = kb_id
    changes["slug"] = kb_id
    changes["message"] = "success"
    return changes


async def update_mindmap_incremental(kb_id: str, user_prompt: str = "") -> dict[str, Any]:
    """Incremental mind map update: pure deletion of scenes does not require AI, and AI integration is called when new ones are added."""
    kb = await KnowledgeBaseRepository().get_by_kb_id(kb_id)
    if kb is None or not kb.mindmap:
        raise HTTPException(status_code=400, detail="Kho kiến thức không có sơ đồ tư duy hiện tại, vui lòng tạo toàn bộ")

    current_files, total = await _load_mindmap_current_files(kb_id, list((kb.mindmap_file_ids or {}).keys()))
    db_name = kb.name or "knowledge base"

    changes = detect_mindmap_changes(kb.mindmap, kb.mindmap_file_ids, current_files)
    changes["current_files_truncated"] = total > len(current_files)

    if not changes["needs_update"]:
        return {
            "message": "success",
            "mindmap": kb.mindmap,
            "kb_id": kb_id,
            "slug": kb_id,
            "db_name": db_name,
            "no_ai_needed": True,
            "no_changes": True,
        }

    mindmap_data = kb.mindmap
    if kb.mindmap_file_ids:
        updated_file_ids = dict(kb.mindmap_file_ids)
    else:
        leaf_filenames = _collect_leaf_filenames(mindmap_data)
        updated_file_ids = {
            fid: info.get("filename", "")
            for fid, info in current_files.items()
            if info.get("filename", "") in leaf_filenames
        }

    if changes["removed_file_ids"]:
        removed_filenames = {updated_file_ids[fid] for fid in changes["removed_file_ids"] if fid in updated_file_ids}
        mindmap_data = remove_files_from_mindmap(mindmap_data, removed_filenames)
        for fid in changes["removed_file_ids"]:
            updated_file_ids.pop(fid, None)

    if changes["added_files"]:
        added_files_info = collect_mindmap_files(current_files, [f["file_id"] for f in changes["added_files"]])
        if added_files_info:
            model = select_model(model_spec=config.default_model)
            messages = [
                {"role": "system", "content": MINDMAP_INCREMENTAL_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_mindmap_incremental_user_message(
                        db_name, mindmap_data, added_files_info, user_prompt
                    ),
                },
            ]
            response = await model.call(messages, stream=False)
            content = response.content if hasattr(response, "content") else str(response)

            try:
                mindmap_data = parse_mindmap_content(content)
            except ValueError as e:
                logger.error(f"JSON parsing returned by incremental AI failed: {e}, original content: {content}")
                raise HTTPException(status_code=500, detail=f"Lỗi định dạng trả về từ AI: {str(e)}") from e

        for f in changes["added_files"]:
            updated_file_ids[f["file_id"]] = f["filename"]

    now = datetime.now(UTC).isoformat()
    metadata = {
        "generated_at": now,
        "file_count": len(updated_file_ids),
        "incremental": True,
    }

    try:
        await KnowledgeBaseRepository().update(
            kb_id,
            {
                "mindmap": mindmap_data,
                "mindmap_file_ids": updated_file_ids,
                "mindmap_metadata": metadata,
            },
        )
        logger.info(f"Mind map incremental update successful: {kb_id}")
    except Exception as save_error:
        logger.error(f"Failed to save mind map: {save_error}")

    no_ai = not changes["added_files"]
    return {
        "message": "success",
        "mindmap": mindmap_data,
        "kb_id": kb_id,
        "slug": kb_id,
        "db_name": db_name,
        "no_ai_needed": no_ai,
    }


async def generate_database_mindmap(
    kb_id: str, file_ids: list[str] | None = None, user_prompt: str = "", incremental: bool = False
) -> dict[str, Any]:
    if incremental:
        return await update_mindmap_incremental(kb_id, user_prompt)

    kb = await KnowledgeBaseRepository().get_by_kb_id(kb_id)
    if kb is None:
        raise HTTPException(status_code=404, detail=f"Cơ sở kiến thức {kb_id} không tồn tại")

    db_name = kb.name or "knowledge base"
    from yuxi.repositories.knowledge_file_repository import KnowledgeFileRepository

    file_repo = KnowledgeFileRepository()
    if file_ids:
        original_count = len(file_ids)
        selected_file_ids = list(file_ids[:MINDMAP_GENERATION_FILE_LIMIT])
        if len(file_ids) > MINDMAP_GENERATION_FILE_LIMIT:
            logger.info(
                f"The number of files exceeds the limit and has been removed from{original_count}before selecting files{MINDMAP_GENERATION_FILE_LIMIT}Generate mind map from file"
            )
        records = await file_repo.list_by_file_ids(selected_file_ids)
        all_files = {
            record.file_id: _file_record_to_mindmap_file(record)
            for record in records
            if record.kb_id == kb_id and not record.is_folder
        }
    else:
        all_files, original_count = await _list_mindmap_files_page(kb_id, page_size=MINDMAP_GENERATION_FILE_LIMIT)
        selected_file_ids = list(all_files.keys())

    if not selected_file_ids:
        raise HTTPException(status_code=400, detail="Không có file trong kho kiến thức")

    files_info = collect_mindmap_files(all_files, selected_file_ids)
    if not files_info:
        raise HTTPException(status_code=400, detail="File đã chọn không tồn tại")

    logger.info(f"Start generating mind maps and knowledge bases: {db_name}, Number of files: {len(files_info)}")

    model = select_model(model_spec=config.default_model)
    messages = [
        {"role": "system", "content": MINDMAP_SYSTEM_PROMPT},
        {"role": "user", "content": build_mindmap_user_message(db_name, files_info, user_prompt)},
    ]
    response = await model.call(messages, stream=False)
    content = response.content if hasattr(response, "content") else str(response)

    try:
        mindmap_data = parse_mindmap_content(content)
    except ValueError as e:
        logger.error(f"JSON parsing returned by AI failed: {e}, original content: {content}")
        raise HTTPException(status_code=500, detail=f"Lỗi định dạng trả về từ AI: {str(e)}") from e

    logger.info("Mind map generated successfully")

    now = datetime.now(UTC).isoformat()
    mindmap_file_ids = {fid: all_files[fid].get("filename", "") for fid in selected_file_ids if fid in all_files}
    mindmap_metadata = {
        "generated_at": now,
        "file_count": len(files_info),
        "incremental": False,
    }

    try:
        await KnowledgeBaseRepository().update(
            kb_id,
            {
                "mindmap": mindmap_data,
                "mindmap_file_ids": mindmap_file_ids,
                "mindmap_metadata": mindmap_metadata,
            },
        )
        logger.info(f"The mind map has been saved to the knowledge base: {kb_id}")
    except Exception as save_error:
        logger.error(f"Failed to save mind map: {save_error}")

    return {
        "message": "success",
        "mindmap": mindmap_data,
        "kb_id": kb_id,
        "slug": kb_id,
        "db_name": db_name,
        "file_count": len(files_info),
        "original_file_count": original_count,
        "truncated": len(files_info) < original_count,
    }


async def get_mindmap_databases_overview(uid: str) -> dict[str, Any]:
    from yuxi.repositories.knowledge_file_repository import KnowledgeFileRepository

    file_repo = KnowledgeFileRepository()
    databases = await knowledge_base.get_databases_by_uid(uid)
    db_list = []
    for db_info in databases.get("databases", []):
        kb_id = db_info.get("kb_id") or db_info.get("slug")
        if not kb_id:
            continue

        file_count = (await file_repo.get_kb_file_stats(kb_id))["file_count"]
        db_list.append(
            {
                "kb_id": kb_id,
                "slug": kb_id,
                "name": db_info.get("name", ""),
                "description": db_info.get("description", ""),
                "kb_type": db_info.get("kb_type", ""),
                "file_count": file_count,
            }
        )

    return {"message": "success", "databases": db_list, "total": len(db_list)}


async def get_database_mindmap_data(kb_id: str) -> dict[str, Any]:
    kb = await KnowledgeBaseRepository().get_by_kb_id(kb_id)
    if kb is None:
        raise HTTPException(status_code=404, detail=f"Cơ sở kiến thức {kb_id} không tồn tại")

    return {
        "message": "success",
        "mindmap": kb.mindmap,
        "kb_id": kb_id,
        "slug": kb_id,
        "db_name": kb.name,
        "mindmap_file_ids": kb.mindmap_file_ids,
        "mindmap_metadata": kb.mindmap_metadata,
    }


def _collect_leaf_filenames(node: dict[str, Any]) -> set[str]:
    """Recursively collect the file names of all leaf nodes in the mind map."""
    children = node.get("children", [])
    if not children:
        return {node.get("content", "")}
    result: set[str] = set()
    for child in children:
        result |= _collect_leaf_filenames(child)
    return result


async def remove_file_from_mindmap(kb_id: str, file_id: str, filename: str | None = None) -> None:
    """Remove and Delete files of leaf nodes from the mind guide picture (pure tree surgery, no AI calls).

    Args:
        kb_id: knowledge base ID
        file_id: Delete filesof ID
        filename: The file name of the deleted file (optional, for old data compatibility)
    """
    kb = await KnowledgeBaseRepository().get_by_kb_id(kb_id)
    if not kb or not kb.mindmap:
        return

    removed_filename: str | None = None

    if kb.mindmap_file_ids and file_id in kb.mindmap_file_ids:
        removed_filename = kb.mindmap_file_ids[file_id]
    elif filename:
        leaf_filenames = _collect_leaf_filenames(kb.mindmap)
        if filename in leaf_filenames:
            removed_filename = filename

    if not removed_filename:
        return

    updated_mindmap = remove_files_from_mindmap(kb.mindmap, {removed_filename})
    updated_file_ids = (
        {fid: name for fid, name in kb.mindmap_file_ids.items() if fid != file_id} if kb.mindmap_file_ids else None
    )

    try:
        await KnowledgeBaseRepository().update(
            kb_id,
            {
                "mindmap": updated_mindmap,
                "mindmap_file_ids": updated_file_ids,
            },
        )
        logger.info(f"File removed from mind map: {removed_filename}")
    except Exception as e:
        logger.error(f"Failed to remove file from mind map: {e}")


async def batch_remove_files_from_mindmap(kb_id: str, removals: list[tuple[str, str]]) -> None:
    """Remove and Delete files of leaf nodes from mind guidance pictures in batches (single DB read and write, no AI call).

    Args:
        kb_id: knowledge base ID
        removals: [(file_id, filename), ...] List of files to be removed
    """
    if not removals:
        return

    kb = await KnowledgeBaseRepository().get_by_kb_id(kb_id)
    if not kb or not kb.mindmap:
        return

    stale_filenames: set[str] = set()
    stale_file_ids: set[str] = set()

    for file_id, filename in removals:
        if kb.mindmap_file_ids and file_id in kb.mindmap_file_ids:
            stale_filenames.add(kb.mindmap_file_ids[file_id])
            stale_file_ids.add(file_id)
        elif filename:
            stale_filenames.add(filename)
            stale_file_ids.add(file_id)

    if not stale_filenames:
        return

    updated_mindmap = remove_files_from_mindmap(kb.mindmap, stale_filenames)
    updated_file_ids = (
        {fid: name for fid, name in kb.mindmap_file_ids.items() if fid not in stale_file_ids}
        if kb.mindmap_file_ids
        else None
    )

    try:
        await KnowledgeBaseRepository().update(
            kb_id,
            {
                "mindmap": updated_mindmap,
                "mindmap_file_ids": updated_file_ids,
            },
        )
        logger.info(f"Mind map batch cleaning completed: {kb_id}, Remove {len(stale_filenames)} files")
    except Exception as e:
        logger.error(f"Batch removal of files from mind map failed: {e}")
