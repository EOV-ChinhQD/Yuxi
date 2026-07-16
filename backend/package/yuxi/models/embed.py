import asyncio
import os
import time
import random
from abc import ABC, abstractmethod

import httpx
import numpy as np
import requests

from yuxi.models.providers.cache import model_cache
from yuxi.utils import get_docker_safe_url, hashstr, logger

EMBEDDING_RATE_LIMIT_MAX_RETRIES = 5
EMBEDDING_TRANSIENT_MAX_RETRIES = 2
EMBEDDING_RETRY_MAX_DELAY_SECONDS = 10.0
EMBEDDING_RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


class BaseEmbeddingModel(ABC):
    def __init__(
        self,
        model=None,
        name=None,
        dimension=None,
        url=None,
        base_url=None,
        api_key=None,
        model_id=None,
        batch_size=40,
        provider="unknown",
    ):
        base_url = base_url or url
        self.model = model or name or model_id
        self.dimension = dimension
        self.base_url = get_docker_safe_url(base_url)
        self.api_key = os.getenv(api_key, api_key)
        self.batch_size = int(batch_size or 40)
        self.embed_state = {}
        self.provider = provider

        concurrency = int(os.getenv("EMBED_MAX_CONCURRENCY", "5"))
        self._semaphore = asyncio.Semaphore(concurrency)

    @staticmethod
    def _retry_delay_seconds(retry_index: int, retry_after: str | None = None) -> float:
        if retry_after:
            try:
                return min(float(retry_after), EMBEDDING_RETRY_MAX_DELAY_SECONDS)
            except ValueError:
                pass
        base_delay = 2 ** (retry_index - 1)
        # Random jitter +/- 20%
        jitter = base_delay * 0.2 * (random.random() * 2 - 1)
        return min(float(base_delay + jitter), EMBEDDING_RETRY_MAX_DELAY_SECONDS)

    def _prepare_retry(
        self,
        message: list[str] | str,
        *,
        retry_index: int,
        response=None,
        error: Exception | None = None,
    ) -> tuple[int, float] | None:
        status_code = getattr(response, "status_code", None)
        response_text = str(getattr(response, "text", "") or "")
        messages = [message] if isinstance(message, str) else message

        # Fast-fail for specific client errors
        if status_code in (400, 401, 403, 404):
            if status_code == 400 and response is not None:
                logger.warning(
                    "Embedding request returned 400 Bad Request: "
                    f"model={self.model}, base_url={self.base_url}, input_count={len(messages)}, "
                    f"body={response_text[:2000]}"
                )
            return None

        if status_code == 429:
            max_retries = EMBEDDING_RATE_LIMIT_MAX_RETRIES
        elif status_code in EMBEDDING_RETRYABLE_STATUS_CODES or status_code is None:
            max_retries = EMBEDDING_TRANSIENT_MAX_RETRIES
        else:
            max_retries = 0

        if retry_index >= max_retries:
            return None

        next_retry_index = retry_index + 1
        retry_after = (
            response.headers.get("Retry-After") if response is not None and hasattr(response, "headers") else None
        )
        delay = self._retry_delay_seconds(next_retry_index, retry_after)
        reason = f"status={status_code}" if status_code is not None else f"error={type(error).__name__}"

        logger.warning(
            "Retrying embedding request: "
            f"attempt={next_retry_index}, delay={delay:.1f}s, {reason}, "
            f"model={self.model}, provider={self.provider}, input_count={len(messages)}"
        )
        return next_retry_index, delay

    @abstractmethod
    def _request(self, message: list[str] | str) -> list[list[float]]:
        raise NotImplementedError("Subclasses must implement this method")

    @abstractmethod
    async def _arequest(self, message: list[str] | str) -> list[list[float]]:
        raise NotImplementedError("Subclasses must implement this method")

    def encode(self, message: list[str] | str) -> list[list[float]]:
        retry_index = 0
        while True:
            try:
                return self._request(message)
            except Exception as e:
                response = getattr(e, "response", None)
                retry = self._prepare_retry(message, retry_index=retry_index, response=response, error=e)
                if retry:
                    retry_index, delay = retry
                    time.sleep(delay)
                    continue
                raise ValueError(f"Embedding request failed: {e}")

    async def aencode(self, message: list[str] | str) -> list[list[float]]:
        retry_index = 0
        while True:
            try:
                async with self._semaphore:
                    return await self._arequest(message)
            except Exception as e:
                response = getattr(e, "response", None)
                retry = self._prepare_retry(message, retry_index=retry_index, response=response, error=e)
                if retry:
                    retry_index, delay = retry
                    await asyncio.sleep(delay)
                    continue
                raise ValueError(f"Embedding async request failed: {e}")

    def encode_queries(self, queries: list[str] | str) -> list[list[float]]:
        return self.encode(queries)

    async def aencode_queries(self, queries: list[str] | str) -> list[list[float]]:
        return await self.aencode(queries)

    def batch_encode(self, messages: list[str], batch_size: int | None = None) -> list[list[float]]:
        batch_size = batch_size or self.batch_size
        data = []
        task_id = None
        if len(messages) > batch_size:
            task_id = hashstr(messages)
            self.embed_state[task_id] = {"status": "in-progress", "total": len(messages), "progress": 0}

        for i in range(0, len(messages), batch_size):
            group_msg = messages[i : i + batch_size]
            logger.info(f"Encoding [{i}/{len(messages)}] messages (bsz={batch_size})")
            response = self.encode(group_msg)
            data.extend(response)
            if task_id:
                self.embed_state[task_id]["progress"] = i + len(group_msg)

        if task_id:
            self.embed_state[task_id]["status"] = "completed"

        return data

    async def abatch_encode(self, messages: list[str], batch_size: int | None = None) -> list[list[float]]:
        batch_size = batch_size or self.batch_size
        data = []
        task_id = None
        if len(messages) > batch_size:
            task_id = hashstr(messages)
            self.embed_state[task_id] = {"status": "in-progress", "total": len(messages), "progress": 0}

        for i in range(0, len(messages), batch_size):
            group_msg = messages[i : i + batch_size]
            logger.info(f"Async encoding [{i}/{len(messages)}] messages (bsz={batch_size})")
            res = await self.aencode(group_msg)
            data.extend(res)
            if task_id:
                self.embed_state[task_id]["progress"] = i + len(group_msg)

        if task_id:
            self.embed_state[task_id]["status"] = "completed"

        return data

    async def test_connection(self) -> tuple[bool, str]:
        try:
            embeddings = await self.aencode(["Hello world"])
            if self.dimension not in (None, ""):
                actual_dimension = len(embeddings[0]) if embeddings else 0
                expected_dimension = int(self.dimension)
                if actual_dimension != expected_dimension:
                    return (
                        False,
                        f"Embedding Inconsistent dimensions: Configuration {expected_dimension},actual {actual_dimension}",
                    )
            return True, "The connection is normal"
        except Exception as e:
            error_msg = str(e)
            error_msg += f", maybe you can check the `{self.base_url}` end with /embeddings as examples."
            logger.error(error_msg)
            return False, error_msg


class GeminiEmbedding(BaseEmbeddingModel):
    def __init__(self, **kwargs):
        kwargs["provider"] = "gemini"
        super().__init__(**kwargs)

    def build_payload(self, messages: list[str]) -> dict:
        is_legacy = self.model == "text-embedding-004"
        m_id = "gemini-embedding-2" if is_legacy else self.model
        req_list = []
        for m in messages:
            req = {"model": f"models/{m_id}", "content": {"parts": [{"text": m}]}}
            if is_legacy:
                req["outputDimensionality"] = 768
            req_list.append(req)
        return {"requests": req_list}

    def _get_url(self):
        m_id = "gemini-embedding-2" if self.model == "text-embedding-004" else self.model
        return f"{self.base_url}/models/{m_id}:batchEmbedContents?key={self.api_key}"

    def _request(self, message: list[str] | str) -> list[list[float]]:
        messages = [message] if isinstance(message, str) else message
        payload = self.build_payload(messages)
        headers = {"Content-Type": "application/json"}
        response = requests.post(self._get_url(), json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        if "embeddings" not in data:
            raise ValueError(f"Gemini embedding failed: {data}")
        return [item["values"] for item in data["embeddings"]]

    async def _arequest(self, message: list[str] | str) -> list[list[float]]:
        messages = [message] if isinstance(message, str) else message
        payload = self.build_payload(messages)
        headers = {"Content-Type": "application/json"}
        async with httpx.AsyncClient() as client:
            response = await client.post(self._get_url(), json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            data = response.json()
            if "embeddings" not in data:
                raise ValueError(f"Gemini embedding failed: {data}")
            return [item["values"] for item in data["embeddings"]]


class OtherEmbedding(BaseEmbeddingModel):
    def __init__(self, **kwargs) -> None:
        kwargs["provider"] = kwargs.get("provider", "other")
        super().__init__(**kwargs)
        self.headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def build_payload(self, message: list[str] | str) -> dict:
        return {"model": self.model, "input": message}

    @staticmethod
    def _extract_embeddings(result: dict) -> list[list[float]]:
        if not isinstance(result, dict) or "data" not in result:
            raise ValueError(f"Embedding failed: Invalid response format {result}")
        return [item["embedding"] for item in result["data"]]

    def _request(self, message: list[str] | str) -> list[list[float]]:
        payload = self.build_payload(message)
        response = requests.post(self.base_url, json=payload, headers=self.headers, timeout=60)
        response.raise_for_status()
        return self._extract_embeddings(response.json())

    async def _arequest(self, message: list[str] | str) -> list[list[float]]:
        payload = self.build_payload(message)
        async with httpx.AsyncClient() as client:
            response = await client.post(self.base_url, json=payload, headers=self.headers, timeout=60)
            response.raise_for_status()
            return self._extract_embeddings(response.json())


def get_embedding_model_info_by_id(model_id: str) -> dict:
    info = model_cache.get_model_info(model_id)
    if not info:
        raise ValueError(f"Unknown embedding model spec: {model_id}")
    if info.model_type != "embedding":
        raise ValueError(f"Model {model_id} is not an embedding model (type={info.model_type})")

    logger.info(f"Loaded embedding model info for {model_id}")
    return {
        "name": info.model_id,
        "display_name": info.display_name,
        "dimension": info.dimension,
        "base_url": info.base_url,
        "api_key": info.api_key,
        "model_id": info.spec,
        "batch_size": info.batch_size,
    }


def select_embedding_model(model_id: str):
    info = model_cache.get_model_info(model_id)
    if not info:
        raise ValueError(f"Unknown embedding model spec: {model_id}")

    if info.model_type != "embedding":
        raise ValueError(f"Model {model_id} is not an embedding model (type={info.model_type})")

    logger.info(f"Selecting embedding model: {model_id} (provider_type={info.provider_type})")

    if info.provider_type == "gemini":
        return GeminiEmbedding(
            model=info.model_id,
            base_url=info.base_url,
            api_key=info.api_key,
            dimension=info.dimension,
            batch_size=info.batch_size,
            provider="gemini",
        )

    return OtherEmbedding(
        model=info.model_id,
        base_url=info.base_url,
        api_key=info.api_key,
        dimension=info.dimension,
        batch_size=info.batch_size,
        provider=info.provider_type,
    )


async def test_embedding_model_status_by_spec(spec: str) -> dict:
    try:
        model = select_embedding_model(spec)
        success, message = await model.test_connection()
        return {
            "spec": spec,
            "status": "available" if success else "unavailable",
            "message": "The connection is normal" if success else message,
        }
    except Exception as e:
        logger.warning(f"Testing Embedding model status failed {spec}: {e}")
        return {"spec": spec, "status": "error", "message": str(e)}
