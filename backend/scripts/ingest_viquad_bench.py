#!/usr/bin/env python3
"""Ingest the ViQuAD bench corpus into KB BENCH_VIQUAD (T2b).

Host-side requests driver (mirrors backend/test/e2e/test_rag_pipeline_e2e.py):
  login -> create/reuse KB -> upload passages -> batched add_documents
  (auto_index) -> poll to indexed -> file_id -> passage map.

Resume-safe: `ingest_progress.json` caches MinIO object names and the KB's own
document list is the source of truth for what is already ingested, so a re-run
never re-uploads or re-indexes a passage.

Chunk->passage mapping is file-level (`file_passage_map.json`): every retrieved
chunk carries `metadata.file_id` (see MilvusKB._build_chunk_from_hit), so a single
document-list pass replaces 9959 per-document content calls.

Credentials are read from the environment (BENCH_ADMIN_UID / BENCH_ADMIN_PASSWORD,
falling back to the E2E_USERNAME / TEST_USERNAME pairs used by backend/test) and are
never hardcoded here.

Run on HOST:  python3 backend/scripts/ingest_viquad_bench.py
State lives in /mnt/new-volume/yuxi-eval/bench/.
"""

from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE = "http://localhost:5050"
BENCH = Path("/mnt/new-volume/yuxi-eval/bench")
CORPUS = BENCH / "corpus"
PROGRESS = BENCH / "ingest_progress.json"
FILEMAP = BENCH / "file_passage_map.json"
KB_NAME = "BENCH_VIQUAD"
KB_DESCRIPTION = "ViQuAD benchmark corpus (9959 passages) for retrieval ablation and E2E evaluation."
EMBEDDING_SPEC = "gemini_compatible:text-embedding-004"
LLM_SPEC = "gemini_compatible:gemini-2.5-flash"
UPLOAD_WORKERS = 8
ADD_BATCH = 100
POLL_SECONDS = 30
BATCH_TIMEOUT_SECONDS = 7200
FAILED_KICK_LIMIT = 3
PASSAGES_EXPECTED = 9959

SESS = requests.Session()
TOKEN = ""
BASE = DEFAULT_BASE


def login() -> None:
    """Authenticate as the bench admin and keep the bearer token in memory."""
    global TOKEN
    uid, password = _credentials()
    response = SESS.post(
        f"{BASE}/api/auth/token",
        data={"username": uid, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=20,
    )
    response.raise_for_status()
    TOKEN = response.json()["access_token"]
    print(f"auth ok as {uid}", flush=True)


def ensure_kb() -> str:
    """Return the bench KB id, creating the KB on first run."""
    payload = _request("GET", "/api/knowledge/databases").json()
    databases = payload if isinstance(payload, list) else payload.get("databases") or payload.get("items") or []
    hit = next((db for db in databases if db.get("name") == KB_NAME), None)
    if hit:
        kb_id = hit.get("kb_id") or hit.get("id")
        if hit.get("embedding_model_spec") != EMBEDDING_SPEC:
            print(f"Deleting outdated KB {KB_NAME} ({kb_id}) with model {hit.get('embedding_model_spec')}", flush=True)
            _request("DELETE", f"/api/knowledge/databases/{kb_id}")
            hit = None
        else:
            print(f"reuse KB {KB_NAME} ({kb_id})", flush=True)
            return kb_id

    body = _request(
        "POST",
        "/api/knowledge/databases",
        json={
            "database_name": KB_NAME,
            "description": KB_DESCRIPTION,
            "kb_type": "milvus",
            "embedding_model_spec": EMBEDDING_SPEC,
            "llm_model_spec": LLM_SPEC,
        },
        timeout=300,
    ).json()
    kb_id = body.get("kb_id") or body.get("id")
    if not kb_id:
        raise SystemExit(f"create KB returned no kb_id: {body}")
    print(f"created KB {KB_NAME} ({kb_id})", flush=True)
    return kb_id


def list_documents(kb_id: str, status: str | None = None) -> list[dict[str, Any]]:
    """Return every document record of the KB (paged, 500 per request)."""
    items: list[dict[str, Any]] = []
    page = 1
    while True:
        params: dict[str, Any] = {"page": page, "page_size": 500}
        if status:
            params["status"] = status
        body = _request("GET", f"/api/knowledge/databases/{kb_id}/documents", params=params).json()
        batch = body.get("items", []) if isinstance(body, dict) else body
        items.extend(batch)
        total = int(body.get("total", len(items))) if isinstance(body, dict) else len(items)
        if not batch or len(items) >= total:
            return items
        page += 1


def count_documents(kb_id: str, status: str | None = None) -> int:
    """Count document records of the KB without transferring them."""
    params: dict[str, Any] = {"page": 1, "page_size": 1}
    if status:
        params["status"] = status
    body = _request("GET", f"/api/knowledge/databases/{kb_id}/documents", params=params).json()
    return int(body.get("total", 0)) if isinstance(body, dict) else len(body)



def main() -> int:
    global BASE
    BASE = os.getenv("TEST_BASE_URL", DEFAULT_BASE).rstrip("/")

    login()
    kb_id = ensure_kb()

    progress = _load_progress()
    progress["kb_id"] = kb_id
    uploaded: dict[str, dict[str, str]] = progress.setdefault("uploaded", {})

    corpus = sorted(CORPUS.glob("*.txt"))
    if len(corpus) != PASSAGES_EXPECTED:
        raise SystemExit(f"corpus drift: {len(corpus)} files, expected {PASSAGES_EXPECTED}")

    existing = {doc["filename"]: doc for doc in list_documents(kb_id)}
    print(f"corpus={len(corpus)} in_kb={len(existing)} cached_uploads={len(uploaded)}", flush=True)

    _upload_missing(corpus, existing, uploaded, progress)
    _add_missing_documents(kb_id, uploaded, existing)
    _wait_for_indexed(kb_id)
    _write_file_passage_map(kb_id, corpus)
    print("T2b OK", flush=True)
    return 0


def _upload_missing(
    corpus: list[Path],
    existing: dict[str, dict[str, Any]],
    uploaded: dict[str, dict[str, str]],
    progress: dict[str, Any],
) -> None:
    """Upload every passage that is neither already in the KB nor cached locally."""
    todo = [path for path in corpus if path.name not in existing and path.name not in uploaded]
    print(f"uploading {len(todo)} passages with {UPLOAD_WORKERS} workers", flush=True)
    if not todo:
        return

    failures: list[tuple[str, str]] = []
    with ThreadPoolExecutor(max_workers=UPLOAD_WORKERS) as pool:
        for done, (name, meta, error) in enumerate(pool.map(_upload_one, todo), 1):
            if meta:
                uploaded[name] = meta
            else:
                failures.append((name, str(error)))
            if done % 200 == 0:
                _save_progress(progress)
                print(f"uploaded {done}/{len(todo)}", flush=True)
    _save_progress(progress)
    if failures:
        raise SystemExit(f"{len(failures)} uploads failed, e.g. {failures[:3]}")
    print(f"uploads complete: {len(uploaded)} cached", flush=True)


def _add_missing_documents(
    kb_id: str,
    uploaded: dict[str, dict[str, str]],
    existing: dict[str, dict[str, Any]],
) -> None:
    """Submit add_documents batches for cached uploads that are not in the KB yet."""
    missing = [name for name in sorted(uploaded) if name not in existing]
    batches = [missing[index : index + ADD_BATCH] for index in range(0, len(missing), ADD_BATCH)]
    print(f"adding {len(missing)} documents in {len(batches)} batches", flush=True)
    for index, batch in enumerate(batches, 1):
        items = [uploaded[name]["object_name"] for name in batch]
        hashes = {uploaded[name]["object_name"]: uploaded[name]["content_hash"] for name in batch}
        task_id = _request(
            "POST",
            f"/api/knowledge/databases/{kb_id}/documents",
            json={
                "items": items,
                "params": {"content_type": "file", "auto_index": True, "content_hashes": hashes},
            },
            timeout=300,
        ).json().get("task_id")
        print(f"add batch {index}/{len(batches)} ({len(batch)} files) -> task {task_id}", flush=True)


def _wait_for_indexed(kb_id: str) -> None:
    """Block until the whole corpus is indexed, re-driving documents a service restart left pending."""
    deadline = time.time() + BATCH_TIMEOUT_SECONDS
    last_state = (-1, -1)
    failed_at_last_kick = -1
    stuck_kicks = 0

    while True:
        documents = count_documents(kb_id)
        indexed = count_documents(kb_id, "indexed")
        failed = count_documents(kb_id, "error_indexing")
        if (documents, indexed) != last_state:
            print(f"indexed {indexed}/{PASSAGES_EXPECTED} documents={documents} failed={failed}", flush=True)
            last_state = (documents, indexed)
            stuck_kicks = 0

        if indexed >= PASSAGES_EXPECTED:
            return
        if time.time() > deadline:
            raise SystemExit(f"timeout: {indexed}/{PASSAGES_EXPECTED} indexed, {failed} failed; re-run to resume")

        # Re-trigger indexing on pending or transiently failed files
        _kick_pending(kb_id)
        failed_at_last_kick = failed
        time.sleep(POLL_SECONDS)


def _kick_pending(kb_id: str) -> None:
    """Re-submit documents left in a pending or failed state by the platform's own pipeline triggers."""
    for action in ("parse-pending", "index-pending"):
        response = SESS.post(
            f"{BASE}/api/knowledge/databases/{kb_id}/documents/{action}",
            headers={"Authorization": f"Bearer {TOKEN}"},
            timeout=300,
        )
        body = response.json() if response.ok else {}
        print(f"{action}: {body.get('message', response.status_code)}", flush=True)


def _describe_failures(kb_id: str, limit: int = 3) -> list[dict[str, Any]]:
    """Fetch the stored error message of the first failing documents."""
    described = []
    for doc in list_documents(kb_id, status="error_indexing")[:limit]:
        response = SESS.get(
            f"{BASE}/api/knowledge/databases/{kb_id}/documents/{doc['file_id']}/basic",
            headers={"Authorization": f"Bearer {TOKEN}"},
            timeout=120,
        )
        meta = response.json().get("meta", {}) if response.ok else {}
        described.append({"filename": doc.get("filename"), "error": meta.get("error_message") or meta.get("error")})
    return described


def _write_file_passage_map(kb_id: str, corpus: list[Path]) -> None:
    """Persist file_id -> passage_id so evaluation results can be scored at passage level."""
    mapping = {doc["file_id"]: Path(doc["filename"]).stem for doc in list_documents(kb_id)}
    FILEMAP.write_text(json.dumps(mapping, ensure_ascii=False), encoding="utf-8")

    covered = set(mapping.values())
    expected = {path.stem for path in corpus}
    if covered != expected:
        raise SystemExit(f"map coverage {len(covered)}/{len(expected)} passages")
    print(f"file->passage map: {len(mapping)} documents, {len(covered)} passages", flush=True)


def _upload_one(path: Path) -> tuple[str, dict[str, str] | None, str | None]:
    """Upload one passage; object_name is the MinIO URL that add_documents expects."""
    try:
        with open(path, "rb") as handle:
            response = SESS.post(
                f"{BASE}/api/knowledge/files/upload",
                headers={"Authorization": f"Bearer {TOKEN}"},
                files={"file": (path.name, handle, "text/plain")},
                timeout=120,
            )
        if response.status_code != 200:
            return path.name, None, f"HTTP {response.status_code}: {response.text[:200]}"
        body = response.json()
        return path.name, {"object_name": body["minio_path"], "content_hash": body["content_hash"]}, None
    except requests.RequestException as exc:
        return path.name, None, f"{type(exc).__name__}: {exc}"


def _request(method: str, path: str, **kwargs: Any) -> requests.Response:
    timeout = kwargs.pop("timeout", 120)
    response: requests.Response | None = None
    for attempt in range(3):
        try:
            response = SESS.request(
                method,
                f"{BASE}{path}",
                headers={"Authorization": f"Bearer {TOKEN}"},
                timeout=timeout,
                **kwargs,
            )
            break
        except requests.RequestException as exc:
            # The API can be slow to respond while it is busy ingesting; retry instead of dying.
            if attempt == 2:
                raise
            print(f"{method} {path} -> {type(exc).__name__}, retrying in 15s ({attempt + 1}/2)", flush=True)
            time.sleep(15)
    assert response is not None
    if response.status_code != 200:
        raise SystemExit(f"{method} {path} -> HTTP {response.status_code}: {response.text[:300]}")
    return response


def _credentials() -> tuple[str, str]:
    load_dotenv(BENCH / "bench_creds.env", override=False)
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    load_dotenv(PROJECT_ROOT / "backend/test/.env.test", override=False)
    uid = os.getenv("BENCH_ADMIN_UID") or os.getenv("E2E_USERNAME") or os.getenv("TEST_USERNAME")
    password = os.getenv("BENCH_ADMIN_PASSWORD") or os.getenv("E2E_PASSWORD") or os.getenv("TEST_PASSWORD")
    if not uid or not password:
        raise SystemExit(
            "Missing bench credentials: export BENCH_ADMIN_UID / BENCH_ADMIN_PASSWORD "
            "(or E2E_USERNAME / E2E_PASSWORD, TEST_USERNAME / TEST_PASSWORD)."
        )
    return uid, password


def _load_progress() -> dict[str, Any]:
    if PROGRESS.exists():
        return json.loads(PROGRESS.read_text(encoding="utf-8"))
    return {"kb_id": None, "uploaded": {}}


def _save_progress(progress: dict[str, Any]) -> None:
    PROGRESS.write_text(json.dumps(progress, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())

