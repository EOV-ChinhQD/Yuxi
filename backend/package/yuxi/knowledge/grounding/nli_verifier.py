import logging
import re
import asyncio
from typing import List, Dict, Any

logger = logging.getLogger("nli_verifier")

# Singleton for the NLI Pipeline
_nli_pipeline = None
_nli_lock = asyncio.Lock()

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
            device=-1 # CPU by default, can be customized
        )
        logger.info("NLI model loaded successfully.")
    return _nli_pipeline


class NLIVerifier:
    @staticmethod
    def split_into_claims(text: str) -> List[str]:
        """Tách câu trả lời thành các claims nguyên tử."""
        if not text:
            return []
        # Tách theo dấu câu tiếng Việt cơ bản (. ! ? \n)
        sentences = re.split(r'(?<=[.!?])\s+|\n+', text)
        claims = []
        for s in sentences:
            s_clean = s.strip()
            # Bỏ qua câu quá ngắn hoặc câu chào hỏi/cảm ơn phổ biến
            if len(s_clean) > 8 and not any(greet in s_clean.lower() for greet in ["chào", "cảm ơn", "ok", "hello"]):
                claims.append(s_clean)
        return claims

    @classmethod
    async def verify_claims(cls, claims: List[str], chunks: List[str], timeout: float = 15.0) -> List[Dict[str, Any]]:
        """Verify each claim against the retrieved chunks using NLI in batch."""
        if not claims or not chunks:
            return [{"claim": c, "score": 0.0, "label": "contradiction"} for c in claims]

        # Ghép toàn bộ chunks thành một ngữ cảnh lớn
        context = "\n".join(chunks)

        async def _run_inference():
            # Chạy đồng bộ trong thread pool của asyncio để tránh block event loop
            return await asyncio.to_thread(cls._run_batch_nli, claims, context)

        try:
            return await asyncio.wait_for(_run_inference(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning("NLI Verification timed out.")
            return [{"claim": c, "score": 0.5, "label": "neutral", "error": "timeout"} for c in claims]
        except Exception as e:
            logger.error(f"NLI Verification error: {e}")
            return [{"claim": c, "score": 0.5, "label": "neutral", "error": str(e)} for c in claims]

    @classmethod
    def _run_batch_nli(cls, claims: List[str], context: str) -> List[Dict[str, Any]]:
        async_pipeline = get_nli_pipeline()
        
        # Sử dụng multi_label=True để tính điểm độc lập cho từng claim
        output = async_pipeline(
            sequences=context,
            candidate_labels=claims,
            hypothesis_template="This text implies that: {}",
            multi_label=True
        )

        labels = output.get("labels", [])
        scores = output.get("scores", [])
        label_to_score = dict(zip(labels, scores))

        results = []
        for claim in claims:
            score = label_to_score.get(claim, 0.0)
            # Phân nhãn dựa trên điểm số độc lập
            label = "entailment" if score > 0.6 else ("neutral" if score > 0.3 else "contradiction")
            results.append({
                "claim": claim,
                "score": float(score),
                "label": label
            })
            
        return results
