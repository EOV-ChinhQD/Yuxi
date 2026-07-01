from typing import Any, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from server.utils.auth_middleware import get_admin_user
from yuxi.knowledge.eval.benchmark_generation import (
    DEFAULT_BENCHMARK_GENERATION_CONCURRENCY,
    MAX_BENCHMARK_GENERATION_CONCURRENCY,
)
from yuxi.knowledge.eval.service import EvaluationService
from yuxi.storage.postgres.models_business import User
from yuxi.utils import logger


evaluation = APIRouter(prefix="/evaluation", tags=["evaluation"])


class GenerateDatasetRequest(BaseModel):
    name: str = Field(default="Tự động tạo bộ dữ liệu đánh giá", min_length=1, max_length=100)
    description: str = ""
    count: int = Field(default=10, ge=1, le=100)
    neighbors_count: int = Field(default=1, ge=0, le=10)
    concurrency_count: int = Field(
        default=DEFAULT_BENCHMARK_GENERATION_CONCURRENCY,
        ge=1,
        le=MAX_BENCHMARK_GENERATION_CONCURRENCY,
    )
    llm_model_spec: str = Field(..., min_length=1)
    generation_mode: Literal["vector", "graph_enhanced"] = "vector"
    graph_expand_top_k: int = Field(default=1, ge=1, le=3)


class RunEvaluationRequest(BaseModel):
    dataset_id: str = Field(..., min_length=1)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    retrieval_config: dict[str, Any] = Field(default_factory=dict, alias="model_config")


@evaluation.post("/databases/{kb_id}/datasets/upload")
async def upload_evaluation_dataset(
    kb_id: str,
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str = Form(""),
    current_user: User = Depends(get_admin_user),
):
    """Tải lên bộ dữ liệu đánh giá"""
    try:
        if not file.filename.endswith(".jsonl"):
            raise HTTPException(status_code=400, detail="Chỉ hỗ trợ tệp định dạng JSONL")

        service = EvaluationService()
        result = await service.upload_dataset(
            kb_id=kb_id,
            file_content=await file.read(),
            filename=file.filename,
            name=name,
            description=description,
            created_by=current_user.uid,
        )
        return {"message": "success", "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Tải lên bộ dữ liệu đánh giá thất bại: {e}")
        raise HTTPException(status_code=500, detail=f"Tải lên bộ dữ liệu đánh giá thất bại: {str(e)}")


@evaluation.get("/databases/{kb_id}/datasets")
async def list_evaluation_datasets(kb_id: str, current_user: User = Depends(get_admin_user)):
    """Lấy danh sách bộ dữ liệu đánh giá của kho kiến thức"""
    try:
        service = EvaluationService()
        datasets = await service.list_datasets(kb_id)
        return {"message": "success", "data": datasets}
    except Exception as e:
        logger.exception(f"Lấy danh sách bộ dữ liệu đánh giá thất bại: {e}")
        raise HTTPException(status_code=500, detail=f"Lấy danh sách bộ dữ liệu đánh giá thất bại: {str(e)}")


@evaluation.get("/databases/{kb_id}/datasets/{dataset_id}")
async def get_evaluation_dataset(
    kb_id: str, dataset_id: str, page: int = 1, page_size: int = 10, current_user: User = Depends(get_admin_user)
):
    """Lấy chi tiết bộ dữ liệu đánh giá"""
    try:
        if page < 1:
            raise HTTPException(status_code=400, detail="Số trang phải lớn hơn 0")
        if page_size < 1 or page_size > 100:
            raise HTTPException(status_code=400, detail="Kích thước mỗi trang phải nằm trong khoảng 1-100")

        service = EvaluationService()
        dataset = await service.get_dataset_detail(kb_id, dataset_id, page, page_size)
        return {"message": "success", "data": dataset}
    except HTTPException:
        raise
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Lấy chi tiết bộ dữ liệu đánh giá thất bại: {e}")
        raise HTTPException(status_code=500, detail=f"Lấy chi tiết bộ dữ liệu đánh giá thất bại: {str(e)}")


@evaluation.get("/datasets/{dataset_id}/download")
async def download_evaluation_dataset(dataset_id: str, current_user: User = Depends(get_admin_user)):
    """Xuất bộ dữ liệu đánh giá dưới dạng JSONL"""
    try:
        service = EvaluationService()
        export_info = await service.export_dataset_jsonl(dataset_id)
        filename = export_info["filename"]
        return Response(
            content=export_info["content"].encode("utf-8"),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
        )
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Xuất bộ dữ liệu đánh giá thất bại: {e}")
        raise HTTPException(status_code=500, detail=f"Xuất bộ dữ liệu đánh giá thất bại: {str(e)}")


@evaluation.delete("/datasets/{dataset_id}")
async def delete_evaluation_dataset(dataset_id: str, current_user: User = Depends(get_admin_user)):
    """Xóa bộ dữ liệu đánh giá"""
    try:
        service = EvaluationService()
        await service.delete_dataset(dataset_id)
        return {"message": "success", "data": None}
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Xóa bộ dữ liệu đánh giá thất bại: {e}")
        raise HTTPException(status_code=500, detail=f"Xóa bộ dữ liệu đánh giá thất bại: {str(e)}")


@evaluation.post("/databases/{kb_id}/datasets/generate")
async def generate_evaluation_dataset(
    kb_id: str, request: GenerateDatasetRequest, current_user: User = Depends(get_admin_user)
):
    """Tự động tạo bộ dữ liệu đánh giá"""
    try:
        service = EvaluationService()
        result = await service.generate_dataset(
            kb_id=kb_id,
            name=request.name,
            description=request.description,
            count=request.count,
            neighbors_count=request.neighbors_count,
            concurrency_count=request.concurrency_count,
            llm_model_spec=request.llm_model_spec,
            generation_mode=request.generation_mode,
            graph_expand_top_k=request.graph_expand_top_k,
            created_by=current_user.uid,
        )
        return {"message": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Tạo bộ dữ liệu đánh giá thất bại: {e}")
        raise HTTPException(status_code=500, detail=f"Tạo bộ dữ liệu đánh giá thất bại: {str(e)}")


@evaluation.post("/databases/{kb_id}/runs")
async def run_evaluation(kb_id: str, request: RunEvaluationRequest, current_user: User = Depends(get_admin_user)):
    """Chạy đánh giá RAG"""
    try:
        service = EvaluationService()
        run_id = await service.run_evaluation(
            kb_id=kb_id,
            dataset_id=request.dataset_id,
            name=request.name,
            model_config=request.retrieval_config,
            created_by=current_user.uid,
        )
        return {"message": "success", "data": {"run_id": run_id}}
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Khởi động đánh giá thất bại: {e}")
        raise HTTPException(status_code=500, detail=f"Khởi động đánh giá thất bại: {str(e)}")


@evaluation.get("/databases/{kb_id}/runs")
async def list_evaluation_runs(kb_id: str, current_user: User = Depends(get_admin_user)):
    """Lấy lịch sử chạy đánh giá kho kiến thức"""
    try:
        service = EvaluationService()
        runs = await service.list_runs(kb_id)
        return {"message": "success", "data": runs}
    except Exception as e:
        logger.exception(f"Lấy lịch sử chạy đánh giá thất bại: {e}")
        raise HTTPException(status_code=500, detail=f"Lấy lịch sử chạy đánh giá thất bại: {str(e)}")


@evaluation.get("/databases/{kb_id}/runs/{run_id}")
async def get_evaluation_run_results(
    kb_id: str,
    run_id: str,
    page: int = 1,
    page_size: int = 20,
    error_only: bool = False,
    current_user: User = Depends(get_admin_user),
):
    """Lấy kết quả chạy đánh giá"""
    try:
        if page < 1:
            raise HTTPException(status_code=400, detail="Số trang phải lớn hơn 0")
        if page_size < 1 or page_size > 100:
            raise HTTPException(status_code=400, detail="Kích thước mỗi trang phải nằm trong khoảng 1-100")

        service = EvaluationService()
        results = await service.get_run_results(kb_id, run_id, page=page, page_size=page_size, error_only=error_only)
        return {"message": "success", "data": results}
    except HTTPException:
        raise
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Lấy kết quả chạy đánh giá thất bại: {e}")
        raise HTTPException(status_code=500, detail=f"Lấy kết quả chạy đánh giá thất bại: {str(e)}")


@evaluation.delete("/databases/{kb_id}/runs/{run_id}")
async def delete_evaluation_run(kb_id: str, run_id: str, current_user: User = Depends(get_admin_user)):
    """Xóa lượt chạy đánh giá"""
    try:
        service = EvaluationService()
        await service.delete_run(kb_id, run_id)
        return {"message": "success", "data": None}
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Xóa lượt chạy đánh giá thất bại: {e}")
        raise HTTPException(status_code=500, detail=f"Xóa lượt chạy đánh giá thất bại: {str(e)}")
