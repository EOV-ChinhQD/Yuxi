#!/usr/bin/env python3
import json
import sys
import time
import requests
import datetime
from pathlib import Path

BASE_URL  = "http://localhost:5050"
USERNAME  = "admin"
PASSWORD  = "admin123456"
TEST_DOC  = Path("/home/chinh303/code/rag/data/2606.20603v1.pdf")

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"
B = "\033[94m"; C = "\033[96m"; W = "\033[1m"; E = "\033[0m"

sess = requests.Session()
TOKEN = None

def H():
    return {"Authorization": f"Bearer {TOKEN}"}

def GET(path, **kw):
    for attempt in range(5):
        try:
            return sess.get(f"{BASE_URL}{path}", headers=H(), timeout=60, **kw)
        except requests.exceptions.ConnectionError:
            print(f"{Y}ConnectionError on {path}, retrying {attempt+1}/5...{E}")
            time.sleep(10)
    return sess.get(f"{BASE_URL}{path}", headers=H(), timeout=60, **kw)

def POST(path, *, json_data=None, files=None, form=None, **kw):
    h = H()
    if files:
        return sess.post(f"{BASE_URL}{path}", headers=h, files=files, timeout=60, **kw)
    if form:
        return sess.post(f"{BASE_URL}{path}", headers=h, data=form, timeout=15, **kw)
    h["Content-Type"] = "application/json"
    return sess.post(f"{BASE_URL}{path}", headers=h, json=json_data, timeout=60, **kw)

def DELETE(path, **kw):
    return sess.delete(f"{BASE_URL}{path}", headers=H(), timeout=60, **kw)

def print_step(msg):
    print(f"\n{W}{C}=== {msg} ==={E}")

def main():
    global TOKEN
    print_step("1. Login")
    r = sess.post(f"{BASE_URL}/api/auth/token", data={"username": USERNAME, "password": PASSWORD}, headers={"Content-Type":"application/x-www-form-urlencoded"})
    TOKEN = r.json().get("access_token")
    print(f"{G}Logged in!{E}")

    print_step("2. Create Knowledge Base")
    KB_NAME = f"PDF_TEST_{int(time.time())}"
    r = POST("/api/knowledge/databases", json_data={
        "database_name": KB_NAME,
        "description": "Test PDF ingestion with Structural Chunker",
        "kb_type": "milvus",
        "embedding_model_spec": "gemini_compatible:text-embedding-004",
    })
    kb_id = r.json().get("id") or r.json().get("kb_id")
    print(f"{G}KB Created: {kb_id}{E}")

    print_step("3. Upload PDF File")
    with open(TEST_DOC, "rb") as f:
        files = {"file": (TEST_DOC.name, f, "application/pdf")}
        r = POST("/api/knowledge/files/upload", files=files)
    upload_resp = r.json()
    object_name = upload_resp.get("minio_path") or upload_resp.get("object_name") or upload_resp.get("file_path")
    content_hash = upload_resp.get("content_hash", "")
    print(f"{G}Uploaded to MinIO: {object_name}{E}")

    print_step("4. Add to KB and Auto Index (OCR + Chunker + Embed)")
    r = POST(f"/api/knowledge/databases/{kb_id}/documents", json_data={
        "items": [object_name],
        "params": {
            "content_type": "file",
            "auto_index": True,
            "content_hashes": {object_name: content_hash}
        }
    })
    add_resp = r.json()
    items = add_resp if isinstance(add_resp, list) else add_resp.get("items", add_resp.get("results", []))
    doc_id = items[0].get("file_id") or items[0].get("id") if items else add_resp.get("task_id") or add_resp.get("id")
    print(f"{G}Document Added! ID: {doc_id}. Polling status...{E}")

    print_step("5. Polling Status")
    for _ in range(60):
        time.sleep(5)
        docs_r = GET(f"/api/knowledge/databases/{kb_id}/documents")
        items = docs_r.json() if isinstance(docs_r.json(), list) else docs_r.json().get("items", [])
        doc = next((d for d in items if TEST_DOC.name in d.get("filename", "")), None)
        if doc:
            doc_id = doc.get("id") or doc.get("file_id")
            status = doc.get("status", "?")
            print(f"Status: {status} (Chunks: {doc.get('chunk_count', 0)})")
            if status == "indexed":
                print(f"{G}✅ Indexing complete! Total chunks: {doc.get('chunk_count', 0)}{E}")
                break
            if "error" in status.lower():
                print(f"{R}❌ Error indexing: {status}{E}")
                sys.exit(1)

    print_step("6. Verify Structural Chunker Metadata")
    r = GET(f"/api/knowledge/databases/{kb_id}/documents/{doc_id}/content")
    chunks = r.json() if isinstance(r.json(), list) else r.json().get("lines", r.json().get("items", r.json().get("chunks", [])))
    print(f"Retrieved {len(chunks)} chunks from DB.")
    for i, chunk in enumerate(chunks):
        text = str(chunk.get("content") or chunk.get("text") or "")[:80].replace('\n', ' ')
        metadata = {"heading_path": chunk.get("heading_path"), "section_type": chunk.get("section_type")}
        print(f"  Chunk {i+1}: {text}...")
        print(f"    Metadata: {metadata}")

    print_step("7. RAG Chat QA")
    sys.exit(0)
    # Create temporary agent with target KB
    agent_name = f"QA_Agent_{int(time.time())}"
    agent_resp = POST("/api/agent", json_data={
        "name": agent_name,
        "backend_id": "ChatbotAgent",
        "config_json": {
            "context": {
                "knowledges": [kb_id],
                "tools": ["query_kb"]
            }
        }
    })
    if agent_resp.status_code != 200:
        print(f"{R}Failed to create temporary agent: {agent_resp.text}{E}")
        return
    agent_id = agent_resp.json().get("agent", {}).get("slug") or agent_resp.json().get("agent", {}).get("id")
    print(f"{G}Created temporary Agent: {agent_id} bound to KB {kb_id}{E}")
    
    questions = [
        "What are the three critical dimensions proposed in the analytical framework of the paper?",
        "What datasets are recommended for Passive Assessment from Natural Language according to the paper?"
    ]

    try:
        for q in questions:
            print(f"\n{B}Question: {q}{E}")
            # Create thread
            thread_id = POST("/api/chat/thread", json_data={"title": "PDF QA", "agent_id": agent_id}).json().get("id")
            
            run_r = POST("/api/agent/runs", json_data={
                "query": q,
                "agent_slug": agent_id,
                "thread_id": thread_id,
                "model_spec": "gemini_compatible:gemini-2.5-flash",
                "meta": {"knowledge_base_ids": [kb_id]}
            })
            run_id = run_r.json().get("id") or run_r.json().get("run_id")
            
            # Poll result instead of SSE for simplicity
            for _ in range(30):
                time.sleep(3)
                r = GET(f"/api/agent/runs/{run_id}/result")
                if r.status_code == 200:
                    st = r.json().get("status", "")
                    if st in ("completed", "done", "success", "finished"):
                        ans = r.json().get("output") or r.json().get("answer") or str(r.json().get("messages",[""])[-1])
                        print(f"{G}Answer:{E}\n{ans}\n")
                        break
                    elif st in ("failed", "error", "cancelled"):
                        print(f"{R}Failed to get answer{E}")
                        break
    finally:
        # Delete temporary agent
        del_r = DELETE(f"/api/agent/{agent_id}")
        if del_r.status_code == 200:
            print(f"{G}Deleted temporary Agent {agent_id}{E}")
        else:
            print(f"{R}Failed to delete temporary Agent {agent_id}: {del_r.text}{E}")

if __name__ == "__main__":
    main()
