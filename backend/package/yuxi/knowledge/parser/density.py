import fitz  # PyMuPDF
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple

logger = logging.getLogger("pdf_density_analyzer")


class PDFDensityAnalyzer:
    """Bộ phân tích mật độ văn bản PDF để tự động phân loại trang (text/scan/lai) và đưa ra quyết định OCR."""

    def __init__(
        self,
        min_chars_threshold: int = 100,      # Ngưỡng ký tự tối thiểu để coi là có text layer
        target_chars_page: int = 1000,       # Số ký tự kỳ vọng cho 1 trang A4 chuẩn
        min_unique_chars: int = 40,          # Số ký tự độc bản kỳ vọng (độ đa dạng)
        garbled_ratio_limit: float = 0.02,   # Tỷ lệ ký tự lỗi cho phép (, \x00, v.v.)
        density_weight: float = 0.4,
        diversity_weight: float = 0.3,
        garbled_weight: float = 0.3,
        quality_score_threshold: float = 0.4 # Điểm chất lượng tối thiểu để bỏ qua OCR
    ):
        self.min_chars_threshold = min_chars_threshold
        self.target_chars_page = target_chars_page
        self.min_unique_chars = min_unique_chars
        self.garbled_ratio_limit = garbled_ratio_limit
        self.density_weight = density_weight
        self.diversity_weight = diversity_weight
        self.garbled_weight = garbled_weight
        self.quality_score_threshold = quality_score_threshold

    def analyze_page(self, page: fitz.Page) -> Tuple[str, Dict[str, Any]]:
        """Phân tích một trang PDF và trả về nhãn loại trang (text, scan, lai) cùng thông số chi tiết."""
        text = page.get_text("text") or ""
        clean_text = text.strip()
        chars_count = len(clean_text)

        # 1. Đo lường Density Score
        density_score = min(chars_count / self.target_chars_page, 1.0)

        # 2. Đo lường Diversity Score (Độ đa dạng ký tự)
        unique_chars = len(set(clean_text))
        diversity_score = min(unique_chars / self.min_unique_chars, 1.0)

        # 3. Đo lường Garbled Score (Nhận diện lỗi font/ký tự lạ)
        invalid_chars = clean_text.count("\x00") + clean_text.count("\ufffd")
        garbled_ratio = invalid_chars / max(chars_count, 1)
        garbled_score = 1.0 - min(garbled_ratio / max(self.garbled_ratio_limit, 0.001), 1.0)

        # Tổng hợp điểm chất lượng
        quality_score = (
            density_score * self.density_weight
            + diversity_score * self.diversity_weight
            + garbled_score * self.garbled_weight
        )

        # Bounding box kiểm tra ảnh vs text (Diện tích vùng ảnh)
        images = page.get_images()
        has_images = len(images) > 0
        
        # Nhãn mặc định
        if chars_count < self.min_chars_threshold:
            page_type = "scan" # Không có text layer hoặc quá ít ký tự -> Scan
        elif quality_score < self.quality_score_threshold:
            page_type = "scan" # Nhiều chữ nhưng bị lỗi font/garbled -> Xem như Scan để OCR lại
        elif has_images and chars_count > self.min_chars_threshold:
            page_type = "hybrid" # Có cả text layer tốt và hình ảnh -> Trang lai
        else:
            page_type = "text" # Text layer sạch hoàn toàn

        metrics = {
            "chars_count": chars_count,
            "unique_chars": unique_chars,
            "invalid_chars": invalid_chars,
            "garbled_ratio": garbled_ratio,
            "quality_score": quality_score,
            "has_images": has_images,
            "images_count": len(images),
        }

        return page_type, metrics

    def analyze_document(self, file_path: str | Path) -> Dict[str, Any]:
        """Phân tích toàn bộ file PDF để đề xuất cấu hình OCR tối ưu."""
        if isinstance(file_path, str):
            file_path = Path(file_path)

        doc = fitz.open(str(file_path))
        num_pages = len(doc)
        
        scan_pages = []
        hybrid_pages = []
        text_pages = []
        pages_detail = {}

        for page_idx in range(num_pages):
            page = doc[page_idx]
            page_type, metrics = self.analyze_page(page)
            pages_detail[page_idx] = {
                "page_type": page_type,
                **metrics
            }
            if page_type == "scan":
                scan_pages.append(page_idx)
            elif page_type == "hybrid":
                hybrid_pages.append(page_idx)
            else:
                text_pages.append(page_idx)

        # Đề xuất cấu hình tối ưu
        # Nếu > 80% số trang là text layer tốt -> Đề xuất "disable" OCR (tiết kiệm chi phí)
        # Nếu có trang scan hoặc trang lai -> Đề xuất chạy OCR
        total_non_text_pages = len(scan_pages) + len(hybrid_pages)
        if total_non_text_pages == 0:
            recommended_ocr = "disable"
        elif len(scan_pages) == num_pages:
            recommended_ocr = "force" # Bắt buộc chạy OCR toàn tập
        else:
            recommended_ocr = "hybrid" # Chạy kết hợp hoặc thông minh

        return {
            "total_pages": num_pages,
            "scan_pages": scan_pages,
            "hybrid_pages": hybrid_pages,
            "text_pages": text_pages,
            "recommended_ocr": recommended_ocr,
            "pages_detail": pages_detail,
        }
