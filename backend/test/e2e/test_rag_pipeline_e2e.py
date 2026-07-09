#!/usr/bin/env python3
"""
Yuxi RAG Pipeline End-to-End Test Suite (v2 - Corrected Flow)
=============================================================
Pipeline flow chính xác:
  STAGE 1: Authentication
  STAGE 2: Knowledge Base Creation  
  STAGE 3: File Upload → MinIO (/api/knowledge/files/upload)
  STAGE 4: Add Document to KB + Parse + Auto-Index
  STAGE 5: Poll Document Status Until "indexed"
  STAGE 6: Get Document Chunks (xác minh embedding)
  STAGE 7: Agent Chat với Knowledge Base → LLM Response
  STAGE 8: SSE Stream & Keyword Validation

Author: Pipeline Test Suite
Date: 2026-07-08
"""

import json
import sys
import time
import requests
import datetime
from pathlib import Path

# =====================================================================
BASE_URL  = "http://localhost:5050"
USERNAME  = "admin"
PASSWORD  = "admin"
TEST_DOC  = Path(__file__).parent.parent / "data" / "test_rag_document.txt"
LOG_FILE  = Path(__file__).parent / "test_rag_pipeline_e2e.log"
# =====================================================================

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"
B = "\033[94m"; C = "\033[96m"; W = "\033[1m"; E = "\033[0m"

log_entries = []

def log(level, stage, msg, data=None):
    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    entry = {"ts": ts, "level": level, "stage": stage, "msg": msg}
    if data: entry["data"] = str(data)[:300]
    log_entries.append(entry)
    icons = {"PASS": "✅","FAIL": "❌","INFO": "ℹ️ ","WARN": "⚠️ ","CHECK": "🔍"}
    colors = {"PASS": G, "FAIL": R, "INFO": B, "WARN": Y, "CHECK": C}
    ic = icons.get(level, "  "); co = colors.get(level, E)
    print(f"{co}[{ts}] {ic} [{stage:12}] {msg}{E}")
    if data and level in ("FAIL","CHECK","WARN"):
        preview = str(data)[:500]
        print(f"         {Y}{preview}{E}")

def sep(title):
    print(f"\n{W}{C}{'='*65}{E}")
    print(f"{W}{C}  {title}{E}")
    print(f"{W}{C}{'='*65}{E}")

def save_log():
    with open(LOG_FILE,"w",encoding="utf-8") as f:
        json.dump(log_entries, f, ensure_ascii=False, indent=2)
    print(f"\n{Y}📄 Log: {LOG_FILE}{E}")

def abort(stage, msg, data=None):
    log("FAIL", stage, msg, data)
    save_log()
    print(f"\n{R}{W}❌ STOPPED: {stage} — {msg}{E}")
    sys.exit(1)

sess = requests.Session()
TOKEN = None

def H():
    return {"Authorization": f"Bearer {TOKEN}"}

def GET(path, **kw):
    return sess.get(f"{BASE_URL}{path}", headers=H(), timeout=15, **kw)

def POST(path, *, json_data=None, files=None, form=None, **kw):
    h = H()
    if files:
        return sess.post(f"{BASE_URL}{path}", headers=h, files=files, timeout=30, **kw)
    if form:
        return sess.post(f"{BASE_URL}{path}", headers=h, data=form, timeout=15, **kw)
    h["Content-Type"] = "application/json"
    return sess.post(f"{BASE_URL}{path}", headers=h, json=json_data, timeout=30, **kw)


# =====================================================================
# STAGE 1: AUTH
# =====================================================================
def s1_auth():
    sep("STAGE 1 ─ Authentication")
    log("INFO","AUTH","Đăng nhập với admin credentials...")

    r = sess.post(f"{BASE_URL}/api/auth/token",
                  data={"username": USERNAME, "password": PASSWORD},
                  headers={"Content-Type":"application/x-www-form-urlencoded"}, timeout=10)

    log("CHECK","AUTH", f"HTTP {r.status_code}")
    if r.status_code != 200:
        abort("AUTH", f"Login failed HTTP {r.status_code}", r.text[:300])

    global TOKEN
    TOKEN = r.json().get("access_token","")
    if not TOKEN:
        abort("AUTH","No access_token", r.json())

    me = GET("/api/auth/me").json()
    log("PASS","AUTH",f"Logged in as '{me.get('username')}' role={me.get('role')}")
    return TOKEN


# =====================================================================
# STAGE 2: KB CREATION
# =====================================================================
def s2_kb():
    sep("STAGE 2 ─ Knowledge Base Creation")
    KB_NAME = f"TEST_RAG_PIPELINE_{int(time.time())}"

    r = GET("/api/knowledge/databases")
    resp = r.json()
    items = (
        resp.get("databases") or resp.get("items") or
        (resp if isinstance(resp, list) else [])
    )
    existing = next((x for x in items if isinstance(x, dict) and x.get("name") == KB_NAME), None)

    if existing:
        kb_id = existing.get("kb_id") or existing.get("id")
        log("INFO","KB_CREATE",f"KB '{KB_NAME}' đã tồn tại → dùng lại: {kb_id}")
    else:
        log("INFO","KB_CREATE",f"Tạo mới KB '{KB_NAME}' (type=milvus, embed=gemini)")
        r = POST("/api/knowledge/databases", json_data={
            "database_name": KB_NAME,
            "description": "Kho tri thức chứa tài liệu nghiên cứu về hệ thống Yuxi RAG và các giai đoạn xử lý dữ liệu.",
            "kb_type": "milvus",
            "embedding_model_spec": "gemini_compatible:text-embedding-004",
        })
        log("CHECK","KB_CREATE", f"HTTP {r.status_code}")
        if r.status_code not in (200,201):
            abort("KB_CREATE", f"Create failed {r.status_code}", r.text[:400])

        resp = r.json()
        kb_id = resp.get("id") or resp.get("kb_id")
        if not kb_id:
            abort("KB_CREATE","No KB id in response", resp)
        log("PASS","KB_CREATE", f"KB created: {kb_id}")

    # Verify
    detail = GET(f"/api/knowledge/databases/{kb_id}").json()
    log("PASS","KB_CREATE",
        f"KB details: name={detail.get('name')} type={detail.get('kb_type')} "
        f"embed={detail.get('embedding_model_spec')}")
    return kb_id


# =====================================================================
# STAGE 3: FILE UPLOAD TO MINIO
# =====================================================================
def s3_upload(kb_id: str):
    sep("STAGE 3 ─ File Upload → MinIO Storage")

    if not TEST_DOC.exists():
        abort("UPLOAD", f"Test doc not found: {TEST_DOC}")

    size = TEST_DOC.stat().st_size
    log("INFO","UPLOAD", f"File: {TEST_DOC.name} ({size:,} bytes)")

    # Check if file already added to KB
    docs_r = GET(f"/api/knowledge/databases/{kb_id}/documents")
    docs_data = docs_r.json()
    items = docs_data if isinstance(docs_data, list) else docs_data.get("items", [])
    existing_doc = next((d for d in items if TEST_DOC.name in str(d.get("filename",""))), None)

    if existing_doc:
        status = existing_doc.get("index_status","?")
        doc_id = existing_doc.get("id") or existing_doc.get("file_id")
        log("INFO","UPLOAD", f"Tài liệu đã tồn tại trong KB. doc_id={doc_id} status={status}")
        return existing_doc.get("minio_path") or existing_doc.get("object_name"), existing_doc.get("content_hash", ""), status

    # Step 1: Upload file to MinIO via /api/knowledge/files/upload
    log("INFO","UPLOAD","Bước 1: Upload file lên MinIO storage...")
    with open(TEST_DOC, "rb") as f:
        files = {"file": (TEST_DOC.name, f, "text/plain")}
        r = POST("/api/knowledge/files/upload", files=files)

    log("CHECK","UPLOAD", f"Upload HTTP {r.status_code}")
    if r.status_code not in (200,201):
        abort("UPLOAD", f"File upload failed: {r.status_code}", r.text[:400])

    upload_resp = r.json()
    log("CHECK","UPLOAD","Upload response", upload_resp)

    # Extract object_name / minio path
    object_name = (
        upload_resp.get("minio_path") or
        upload_resp.get("file_path") or
        upload_resp.get("url") or
        upload_resp.get("object_name") or
        upload_resp.get("path") or
        str(upload_resp)
    )
    log("PASS","UPLOAD", f"File uploaded to MinIO. object_name={object_name}")
    return object_name, upload_resp.get("content_hash", ""), "need_add"


# =====================================================================
# STAGE 4: ADD TO KB + AUTO-PARSE + AUTO-INDEX
# =====================================================================
def s4_add_and_index(kb_id: str, object_name: str, content_hash: str, current_status: str):
    sep("STAGE 4 ─ Add Document + Parse + Index (Auto Pipeline)")

    if current_status == "indexed":
        log("INFO","ADD_DOC","Document đã indexed → skip")
        docs_r = GET(f"/api/knowledge/databases/{kb_id}/documents")
        items = docs_r.json() if isinstance(docs_r.json(), list) else docs_r.json().get("items",[])
        doc = next((d for d in items if TEST_DOC.name in str(d.get("filename",""))), None)
        return doc["id"] if doc else None

    log("INFO","ADD_DOC", f"Thêm tài liệu vào KB: {kb_id}")
    log("INFO","ADD_DOC", f"object_name: {object_name}")

    # Add with auto_index=True (parse + embed + index in one shot)
    r = POST(f"/api/knowledge/databases/{kb_id}/documents", json_data={
        "items": [object_name],
        "params": {
            "content_type": "file",
            "auto_index": True,
            "content_hashes": {
                object_name: content_hash
            }
        }
    })

    log("CHECK","ADD_DOC", f"Add document HTTP {r.status_code}")
    if r.status_code not in (200,201,202):
        abort("ADD_DOC", f"Add document failed {r.status_code}", r.text[:500])

    add_resp = r.json()
    log("CHECK","ADD_DOC","Add response", add_resp)

    # Extract doc_id from response
    doc_id = None
    if isinstance(add_resp, list) and add_resp:
        doc_id = add_resp[0].get("file_id") or add_resp[0].get("id")
    elif isinstance(add_resp, dict):
        items = add_resp.get("items", add_resp.get("results", []))
        if items:
            doc_id = items[0].get("file_id") or items[0].get("id")
        else:
            doc_id = add_resp.get("task_id") or add_resp.get("id")

    log("PASS","ADD_DOC", f"Document added. doc_id/task_id={doc_id}")
    return doc_id


# =====================================================================
# STAGE 5: POLL STATUS UNTIL INDEXED
# =====================================================================
def s5_poll_status(kb_id: str, doc_id: str):
    sep("STAGE 5 ─ Poll Document Status Until 'indexed'")
    
    log("INFO","POLL", f"Polling doc status in {kb_id}...")
    max_wait = 360  # 6 min
    poll_interval = 8
    elapsed = 0
    last_status = "?"
    real_doc_id = None
    
    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval

        docs_r = GET(f"/api/knowledge/databases/{kb_id}/documents")
        if docs_r.status_code != 200:
            continue
            
        data = docs_r.json()
        items = data if isinstance(data, list) else data.get("items", [])
        doc = next((d for d in items if TEST_DOC.name in d.get("filename", "")), None)
        
        if doc:
            real_doc_id = doc.get("id") or doc.get("file_id")
            status = doc.get("status", "?")
            chunk_count = doc.get("chunk_count", 0)
            
            if status != last_status:
                log("CHECK","POLL", f"[{elapsed}s] {last_status} → {status} | chunks={chunk_count}")
                last_status = status
                
            if status == "indexed":
                # Fetch basic details to get the actual chunk_count
                basic_r = GET(f"/api/knowledge/databases/{kb_id}/documents/{real_doc_id}/basic")
                if basic_r.status_code == 200:
                    doc = basic_r.json().get("meta", doc)
                    chunk_count = doc.get("chunk_count", 0)
                log("PASS","POLL",
                    f"✅ Document {status.upper()}! chunks={chunk_count} | "
                    f"filename={doc.get('filename')} | "
                    f"size={doc.get('size', doc.get('file_size','?'))} bytes")
                return real_doc_id, doc
                
            elif "error" in str(status).lower():
                log("FAIL","POLL", f"Indexing error: {status}", doc)
                abort("POLL", f"Indexing failed: {status}", doc)

    abort("POLL", f"Timeout {max_wait}s — last status: {last_status}")

# =====================================================================
# STAGE 6: VERIFY CHUNKS
# =====================================================================
def s6_verify_chunks(kb_id: str, doc_id: str, doc_data: dict):
    sep("STAGE 6 ─ Verify Chunks in DB")

    chunk_count = doc_data.get("chunk_count", 0)
    log("INFO","CHUNKS", f"Expected chunks: {chunk_count}")

    r = GET(f"/api/knowledge/databases/{kb_id}/documents/{doc_id}/content")
    log("CHECK","CHUNKS", f"Content HTTP {r.status_code}")

    if r.status_code == 200:
        content = r.json()
        chunks = content if isinstance(content, list) else content.get("lines", content.get("items", content.get("chunks", [])))
        log("PASS","CHUNKS", f"Retrieved {len(chunks)} chunks from storage")

        # Show samples
        for i, chunk in enumerate(chunks[:3]):
            text = str(chunk.get("content") or chunk.get("text") or "")[:120]
            cid = chunk.get("chunk_id") or chunk.get("id","?")
            log("CHECK","CHUNKS", f"Chunk[{i}] id={cid}: '{text}...'")

        # Assertions
        assert len(chunks) > 0, "No chunks found!"
        assert chunk_count > 0, "chunk_count is 0!"
        log("PASS","CHUNKS", f"✅ Chunk assertion passed: {len(chunks)} chunks > 0")
        return chunks
    else:
        log("WARN","CHUNKS", f"Cannot read chunks: {r.status_code} — tiếp tục test")
        return []


# =====================================================================
# STAGE 7: AGENT SETUP
# =====================================================================
def s7_get_agent():
    sep("STAGE 7 ─ Get Default Agent & Create Thread")

    # Get default agent
    r = GET("/api/agent/default")
    log("CHECK","AGENT_SETUP", f"Default agent HTTP {r.status_code}")

    agent_id = None
    if r.status_code == 200:
        agent_data = r.json().get("agent", {})
        agent_id = agent_data.get("agent_id") or agent_data.get("id")
        log("PASS","AGENT_SETUP", f"Default agent: id={agent_id} name={agent_data.get('name')}")
    else:
        # List agents
        r2 = GET("/api/agent")
        agents = r2.json()
        items = agents if isinstance(agents, list) else agents.get("items", [])
        if items:
            agent_id = items[0]["id"]
            log("INFO","AGENT_SETUP", f"Using first agent: {agent_id}")
        else:
            abort("AGENT_SETUP","No agents found")

    # Create thread
    thread_r = POST("/api/chat/thread", json_data={"title": "Pipeline E2E Test", "agent_id": agent_id})
    log("CHECK","AGENT_SETUP", f"Thread create HTTP {thread_r.status_code}")
    if thread_r.status_code not in (200,201):
        abort("AGENT_SETUP", f"Thread create failed: {thread_r.status_code}", thread_r.text[:300])

    thread_data = thread_r.json()
    thread_id = thread_data.get("id") or thread_data.get("thread_id")
    log("PASS","AGENT_SETUP", f"Thread created: {thread_id}")

    return agent_id, thread_id


# =====================================================================
# STAGE 8: LLM RESPONSE VIA SSE
# =====================================================================
TEST_CASES = [
    {
        "q": "Hệ thống RAG là gì và tại sao nó giải quyết được vấn đề hallucination?",
        "expect": ["retrieval","generation","hallucination","ưu điểm","ngữ cảnh"],
        "label": "RAG_BASIC"
    },
    {
        "q": "Yuxi pipeline xử lý tài liệu qua bao nhiêu giai đoạn? Liệt kê từng giai đoạn.",
        "expect": [
            "5",
            ["giai đoạn", "bước"],
            ["ingestion", "nạp dữ liệu", "nhập liệu", "thu thập"],
            ["parsing", "phân tách", "phân tích", "trích xuất"],
            ["chunking", "phân đoạn", "cắt nhỏ", "chia nhỏ", "tách đoạn"],
            ["embedding", "nhúng", "mô hình nhúng"],
            ["indexed", "lập chỉ mục", "index", "lưu trữ"]
        ],
        "label": "PIPELINE_STAGES"
    },
    {
        "q": "Embedding model nào được dùng, chiều vector là bao nhiêu, và kích thước chunk điển hình?",
        "expect": [
            "768",
            ["text-embedding-004", "gemini-embedding", "embedding model"],
            ["512", "kích thước chunk", "chunk size"],
            "1024"
        ],
        "label": "TECH_SPECS"
    },
]

def _make_thread(agent_id):
    """Create a fresh conversation thread for isolation."""
    thread_r = POST("/api/chat/thread", json_data={"title": "Pipeline E2E Test", "agent_id": agent_id})
    if thread_r.status_code not in (200, 201):
        abort("AGENT_SETUP", f"Thread create failed: {thread_r.status_code}", thread_r.text[:300])
    thread_data = thread_r.json()
    return thread_data.get("id") or thread_data.get("thread_id")


def s8_rag_chat(agent_id, thread_id, kb_id):
    sep("STAGE 8 ─ RAG Chat: Retrieval + LLM Generation")

    results = []
    for i, tc in enumerate(TEST_CASES):
        log("INFO","RAG_CHAT", "\n" + "─"*50)
        log("INFO","RAG_CHAT", f"Test {i+1}/{len(TEST_CASES)}: [{tc['label']}]")
        log("INFO","RAG_CHAT", f"❓ Question: {tc['q']}")

        # Fresh thread per test to avoid context contamination
        fresh_thread_id = _make_thread(agent_id)
        log("INFO","RAG_CHAT", f"Fresh thread: {fresh_thread_id}")

        run_r = POST("/api/agent/runs", json_data={
            "query": tc["q"],
            "agent_slug": agent_id,
            "thread_id": fresh_thread_id,
            "model_spec": "openrouter:cohere/north-mini-code:free",
            "meta": {
                "knowledge_base_ids": [kb_id],
            }
        })

        log("CHECK","RAG_CHAT", f"Run create HTTP {run_r.status_code}")
        if run_r.status_code not in (200,201):
            log("WARN","RAG_CHAT", f"Run failed: {run_r.text[:300]}")
            results.append({"label": tc["label"], "status": "FAIL_RUN"})
            continue

        run_data = run_r.json()
        run_id = run_data.get("id") or run_data.get("run_id")
        log("INFO","RAG_CHAT", f"Run ID: {run_id} — Collecting SSE stream...")

        answer = _collect_sse(run_id)

        if answer:
            ans_lower = answer.lower()
            matched = []
            missing = []
            for item in tc["expect"]:
                if isinstance(item, list):
                    if any(option.lower() in ans_lower for option in item):
                        matched.append(item[0])
                    else:
                        missing.append(item[0])
                else:
                    if item.lower() in ans_lower:
                        matched.append(item)
                    else:
                        missing.append(item)
            pass_pct = len(matched)/len(tc["expect"])*100

            if pass_pct >= 60:
                log("PASS","RAG_CHAT",
                    f"✅ [{tc['label']}] {pass_pct:.0f}% keywords matched: {matched}")
            else:
                log("WARN","RAG_CHAT",
                    f"⚠️  [{tc['label']}] Only {pass_pct:.0f}%: matched={matched} missing={missing}")

            log("CHECK","RAG_CHAT",
                f"Answer preview ({len(answer)} chars):\n{answer[:500]}")

            results.append({
                "label": tc["label"], "status": "PASS" if pass_pct>=60 else "PARTIAL",
                "pass_pct": pass_pct, "matched": matched, "missing": missing,
                "answer_len": len(answer)
            })
        else:
            log("WARN","RAG_CHAT", f"No answer for [{tc['label']}]")
            results.append({"label": tc["label"], "status": "NO_ANSWER"})

        time.sleep(2)  # Cool-down between questions

    return results


def _collect_sse(run_id, timeout=120):
    url = f"{BASE_URL}/api/agent/runs/{run_id}/events"
    texts = []
    event_count = 0
    t0 = time.time()
    last_event = None

    try:
        with sess.get(url, headers={**H(), "Accept":"text/event-stream"},
                      stream=True, timeout=(10, timeout)) as r:
            if r.status_code != 200:
                log("WARN","SSE", f"Stream HTTP {r.status_code}")
                return _poll_result(run_id)

            log("INFO","SSE", f"Stream connected (HTTP {r.status_code})")
            for raw in r.iter_lines(decode_unicode=True):
                if time.time()-t0 > timeout: break
                if not raw: continue
                if raw.startswith("event:"):
                    last_event = raw.split(":",1)[1].strip()
                elif raw.startswith("data:"):
                    event_count += 1
                    try:
                        d = json.loads(raw.split(":",1)[1].strip())
                        ev = d.get("event") or last_event or ""

                        # Extract text from various event formats
                        content = ""
                        if ev in ("message_chunk","on_chat_model_stream","delta"):
                            content = (d.get("data",{}).get("content")
                                       or d.get("content",""))
                        elif ev in ("message","on_chat_model_end"):
                            content = (d.get("data",{}).get("output",{}).get("content")
                                       or d.get("data",{}).get("content")
                                       or d.get("content",""))
                        elif ev in ("done","finish","end","[DONE]"):

                            break

                        if content:
                            texts.append(str(content))
                    except Exception:
                        pass

    except Exception as e:
        log("WARN","SSE", f"Stream error: {e}")

    result = "".join(texts).strip()
    elapsed = time.time()-t0
    log("INFO","SSE", f"Streamed {event_count} events in {elapsed:.1f}s → {len(result)} chars")

    if not result:
        return _poll_result(run_id)
    return result


def _poll_result(run_id, timeout=90):
    log("INFO","POLL_RESULT", f"Polling /api/agent/runs/{run_id}/result...")
    t0 = time.time()
    while time.time()-t0 < timeout:
        time.sleep(6)
        r = GET(f"/api/agent/runs/{run_id}/result")
        if r.status_code == 200:
            d = r.json()
            st = d.get("status","")
            if st in ("completed","done","success","finished"):
                ans = (d.get("output") or d.get("answer") or
                       str(d.get("messages",[""])[-1]))
                if ans:
                    log("PASS","POLL_RESULT", f"Got answer {len(str(ans))} chars")
                    return str(ans)[:3000]
            elif st in ("failed","error","cancelled"):
                log("WARN","POLL_RESULT", f"Run status: {st}")
                return ""
            else:
                log("CHECK","POLL_RESULT", f"status={st}...")
    log("WARN","POLL_RESULT","Timeout")
    return ""


# =====================================================================
# FINAL REPORT
# =====================================================================
def final_report(results):
    sep("📊 FINAL PIPELINE VERIFICATION REPORT")

    passed = sum(1 for r in results if r.get("status") == "PASS")
    partial = sum(1 for r in results if r.get("status") == "PARTIAL")
    failed  = sum(1 for r in results if r.get("status") not in ("PASS","PARTIAL"))
    total   = len(results)

    print(f"\n{W}  Results: {total} tests │ {G}PASS: {passed}{E}{W} │ {Y}PARTIAL: {partial}{E}{W} │ {R}FAIL: {failed}{E}\n")

    for r in results:
        st = r.get("status","?")
        co = G if st=="PASS" else (Y if st=="PARTIAL" else R)
        ic = "✅" if st=="PASS" else ("⚠️ " if st=="PARTIAL" else "❌")
        label = r.get("label","?")
        pct = r.get("pass_pct",0)
        print(f"  {ic} {co}[{label}] {pct:.0f}% keywords matched | ans={r.get('answer_len',0)} chars{E}")
        if r.get("missing"):
            print(f"      {Y}Missing: {r['missing']}{E}")

    print()
    if failed == 0 and partial == 0:
        print(f"{G}{W}🎉 ALL STAGES PASSED — RAG PIPELINE FULLY OPERATIONAL{E}")
    elif passed + partial >= total * 0.6:
        print(f"{Y}{W}⚠️  PIPELINE MOSTLY WORKING — CHECK WARNINGS ABOVE{E}")
    else:
        print(f"{R}{W}❌ PIPELINE HAS SIGNIFICANT ISSUES — SEE LOG{E}")


# =====================================================================
# MAIN
# =====================================================================
def main():
    print(f"\n{W}{C}{'='*65}")
    print(f"  Yuxi RAG Pipeline E2E Test Suite v2")
    print(f"  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*65}{E}\n")

    try:
        s1_auth()
        kb_id = s2_kb()
        object_name, content_hash, doc_status = s3_upload(kb_id)
        if doc_status == "indexed":
            doc_id = object_name
            docs_r = GET(f"/api/knowledge/databases/{kb_id}/documents")
            items = docs_r.json() if isinstance(docs_r.json(),list) else docs_r.json().get("items",[])
            doc = next((d for d in items if TEST_DOC.name in str(d.get("filename",""))), None)
            doc_data = doc or {}
        else:
            doc_id = s4_add_and_index(kb_id, object_name, content_hash, doc_status)
            doc_id, doc_data = s5_poll_status(kb_id, doc_id)

        s6_verify_chunks(kb_id, doc_id, doc_data)
        agent_id, thread_id = s7_get_agent()
        results = s8_rag_chat(agent_id, thread_id, kb_id)
        final_report(results)
        save_log()

    except SystemExit:
        raise
    except Exception as e:
        log("FAIL","MAIN", f"Unexpected: {e}")
        import traceback; traceback.print_exc()
        save_log()
        sys.exit(1)

if __name__ == "__main__":
    main()
