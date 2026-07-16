import logging
import re
import asyncio
from typing import Any

logger = logging.getLogger("nli_verifier")

# Singleton for the NLI Pipeline
_nli_pipeline = None
_nli_lock = asyncio.Lock()
_nli_semaphore: asyncio.Semaphore | None = None


def get_nli_semaphore():
    global _nli_semaphore
    if _nli_semaphore is None:
        from yuxi.config import config

        concurrency = getattr(config, "nli_max_concurrency", 3)
        _nli_semaphore = asyncio.Semaphore(concurrency)
    return _nli_semaphore


def get_nli_pipeline():
    global _nli_pipeline
    if _nli_pipeline is None:
        from transformers import pipeline

        # Load MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7
        model_name = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"
        logger.info(f"Loading NLI model {model_name}...")
        _nli_pipeline = pipeline(
            "zero-shot-classification",
            model=model_name,
            device=-1,  # CPU by default, can be customized
        )
        logger.info("NLI model loaded successfully.")
    return _nli_pipeline


class NLIVerifier:
    @staticmethod
    def split_into_claims(text: str) -> list[str]:
        """Tách câu trả lời thành các claims nguyên tử."""
        if not text:
            return []

        # 1. Clean markdown
        text = re.sub(r"#+\s*", "", text)  # Headings
        text = re.sub(r"[*_`~]+", "", text)  # Bold, italics, code, strikethrough
        text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)  # Links -> Text
        text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)  # List bullets

        # 2. Tách theo dấu câu tiếng Việt cơ bản (. ! ? \n)
        sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
        claims = []
        for s in sentences:
            s_clean = s.strip()

            # Reject rules
            if not s_clean or len(s_clean) < 15:
                continue
            if s_clean.endswith("?") or s_clean.endswith("!"):
                continue

            lower_s = s_clean.lower()
            if any(greet in lower_s for greet in ["chào", "cảm ơn", "ok", "hello", "xin lỗi"]):
                continue

            if re.match(r"^(nguồn|tóm tắt|kết luận|điểm nhấn|lưu ý|tổng kết)[:\s-]", lower_s):
                continue
            if "bạn có muốn" in lower_s or "dưới đây là" in lower_s or "như sau:" in lower_s:
                continue

            if not re.search(r"[a-zA-Z0-9\u00C0-\u1EF9]", s_clean):
                continue

            claims.append(s_clean)
        return claims

    @staticmethod
    def score_claim_importance(claim: str) -> float:
        """Tính điểm tầm quan trọng của claim để ưu tiên verify."""
        score = 0.0

        # 1. Chứa số liệu (ngày tháng, số lượng, phần trăm...)
        if re.search(r"\d+", claim):
            score += 3.0

        # 2. Chứa năm cụ thể hoặc định dạng ngày tháng
        if re.search(r"\b(19|20)\d{2}\b|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", claim):
            score += 2.0

        # 3. Chứa trích dẫn tài liệu kiểu [1], [Nguồn]
        if re.search(r"\[\d+\]|\[[a-zA-Z\s]+\]", claim):
            score += 2.0

        # 4. Chứa từ viết hoa (tên riêng, tên viết tắt, điều khoản...) - bỏ từ đầu tiên
        words = claim.split()
        if len(words) > 1:
            capitalized_words = [w for w in words[1:] if w and w[0].isupper()]
            score += len(capitalized_words) * 0.5

        # 5. Chứa các từ khóa mang tính chất khẳng định thực tế pháp lý/kinh doanh
        factual_keywords = [
            "luật",
            "quy định",
            "nghị định",
            "thông tư",
            "hợp đồng",
            "doanh thu",
            "chi phí",
            "hiệu lực",
            "ngày",
            "tháng",
            "năm",
            "yêu cầu",
            "bắt buộc",
            "điều kiện",
            "tiêu chuẩn",
            "quy trình",
        ]
        claim_lower = claim.lower()
        for kw in factual_keywords:
            if kw in claim_lower:
                score += 1.0

        # Phạt các câu quá ngắn
        if len(words) < 5:
            score -= 2.0

        return score

    @classmethod
    async def verify_claims(cls, claims: list[str], chunks: list[str], timeout: float = 15.0) -> list[dict[str, Any]]:
        """Verify each claim against the retrieved chunks using NLI in batch."""
        if not claims or not chunks:
            return [{"claim": c, "score": 0.0, "label": "contradiction"} for c in claims]

        from yuxi.config import config

        # 1. Smart Filtering & Ranking claims
        scored_claims = [(c, cls.score_claim_importance(c)) for c in claims]
        scored_claims.sort(key=lambda x: x[1], reverse=True)

        max_claims = getattr(config, "max_nli_claims", 8)

        claims_to_verify = [c for c, score in scored_claims[:max_claims]]
        claims_skipped = [c for c, score in scored_claims[max_claims:]]

        logger.info(
            f"[NLI] Claims extracted: {len(claims)} | "
            f"High priority: {len(claims_to_verify)} | "
            f"Verified: {len(claims_to_verify)} | "
            f"Skipped: {len(claims_skipped)}"
        )

        context = "\n".join(chunks)
        verified_results = []

        if claims_to_verify:

            async def _run_inference():
                return await asyncio.to_thread(cls._run_batch_nli, claims_to_verify, context)

            try:
                semaphore = get_nli_semaphore()
                async with semaphore:
                    verified_results = await asyncio.wait_for(_run_inference(), timeout=timeout)
            except TimeoutError:
                logger.warning("NLI Verification timed out.")
                try:
                    from yuxi.agents.backends.sandbox import sandbox_metrics

                    sandbox_metrics.record_event("nli_timeout")
                except Exception:
                    pass
                verified_results = [
                    {"claim": c, "score": 0.5, "label": "timeout", "error": "timeout"} for c in claims_to_verify
                ]
            except Exception as e:
                logger.error(f"NLI Verification error: {e}")
                verified_results = [
                    {"claim": c, "score": 0.5, "label": "error", "error": str(e)} for c in claims_to_verify
                ]

        # Map back results to original order
        verified_map = {res["claim"]: res for res in verified_results}
        for c in claims_skipped:
            verified_map[c] = {"claim": c, "score": 0.5, "label": "skipped"}

        final_results = []
        for c in claims:
            res = verified_map.get(c)
            if res and res.get("label") == "contradiction":
                try:
                    from yuxi.agents.backends.sandbox import sandbox_metrics

                    sandbox_metrics.record_event("hallucination_detected")
                except Exception:
                    pass
            final_results.append(res)

        return final_results

    @classmethod
    def _run_batch_nli(cls, claims: list[str], context: str) -> list[dict[str, Any]]:
        async_pipeline = get_nli_pipeline()

        # Sử dụng multi_label=True để tính điểm độc lập cho từng claim
        output = async_pipeline(
            sequences=context,
            candidate_labels=claims,
            hypothesis_template="This text implies that: {}",
            multi_label=True,
        )

        labels = output.get("labels", [])
        scores = output.get("scores", [])
        label_to_score = dict(zip(labels, scores))

        results = []
        for claim in claims:
            score = label_to_score.get(claim, 0.0)
            # Phân nhãn dựa trên điểm số độc lập
            label = "entailment" if score > 0.6 else ("neutral" if score > 0.3 else "contradiction")
            results.append({"claim": claim, "score": float(score), "label": label})

        return results
