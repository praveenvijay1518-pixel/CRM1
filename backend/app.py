"""
IPC-iQ local backend
--------------------
A small FastAPI server that stores the app's documents in SQLite and serves the
frontend. The frontend talks to it through frontend/local-runtime.js.

Run:  python app.py        then open http://localhost:8000
"""
import json
import os
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

BASE = Path(__file__).resolve().parent
FRONTEND = BASE.parent / "frontend"
DB_PATH = Path(os.environ.get("IPC_DB", BASE / "ipc.db"))
SEED_PATH = BASE / "seed_data.json"
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")

NAME_RE = re.compile(r"^[A-Za-z0-9_\-.~:@+]{1,200}$")
_lock = threading.Lock()


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    return con


con = connect()
con.execute(
    "CREATE TABLE IF NOT EXISTS docs (col TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL, "
    "updated REAL NOT NULL, PRIMARY KEY (col, id))"
)
con.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v INTEGER NOT NULL)")
con.execute("INSERT OR IGNORE INTO meta (k, v) VALUES ('version', 0)")
con.commit()


def bump() -> None:
    con.execute("UPDATE meta SET v = v + 1 WHERE k = 'version'")


def seed_if_empty() -> None:
    (count,) = con.execute("SELECT COUNT(*) FROM docs").fetchone()
    if count or not SEED_PATH.exists():
        return
    rows = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    with _lock:
        for w in rows:
            con.execute(
                "INSERT OR REPLACE INTO docs (col, id, data, updated) VALUES (?, ?, ?, ?)",
                (w["collection"], w["doc_id"], json.dumps(w["data"]), time.time()),
            )
        bump()
        con.commit()
    print(f"Loaded {len(rows)} demo documents into {DB_PATH.name}")


def check(*names: str) -> None:
    for n in names:
        if not NAME_RE.match(n):
            raise HTTPException(400, f"Invalid name: {n!r}")


def deep_merge(base: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    """Nested objects merge recursively; anything else (arrays included) replaces."""
    out = dict(base)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


seed_if_empty()
app = FastAPI(title="IPC-iQ local backend")


@app.get("/api/version")
def version():
    (v,) = con.execute("SELECT v FROM meta WHERE k = 'version'").fetchone()
    return {"version": v}


@app.get("/api/config")
def config():
    return {"ai": bool(ANTHROPIC_KEY)}


@app.get("/api/collections/{col}")
def list_docs(col: str):
    check(col)
    rows = con.execute("SELECT id, data FROM docs WHERE col = ? ORDER BY id", (col,)).fetchall()
    return [{"id": i, "data": json.loads(d)} for i, d in rows]


@app.get("/api/collections/{col}/{doc_id}")
def get_doc(col: str, doc_id: str):
    check(col, doc_id)
    row = con.execute("SELECT data FROM docs WHERE col = ? AND id = ?", (col, doc_id)).fetchone()
    return {"exists": bool(row), "data": json.loads(row[0]) if row else None}


@app.put("/api/collections/{col}/{doc_id}")
def set_doc(col: str, doc_id: str, data: Dict[str, Any] = Body(...)):
    check(col, doc_id)
    with _lock:
        con.execute(
            "INSERT OR REPLACE INTO docs (col, id, data, updated) VALUES (?, ?, ?, ?)",
            (col, doc_id, json.dumps(data), time.time()),
        )
        bump()
        con.commit()
    return {"id": doc_id}


@app.patch("/api/collections/{col}/{doc_id}")
def update_doc(col: str, doc_id: str, data: Dict[str, Any] = Body(...)):
    check(col, doc_id)
    with _lock:
        row = con.execute("SELECT data FROM docs WHERE col = ? AND id = ?", (col, doc_id)).fetchone()
        if not row:
            raise HTTPException(404, "Document does not exist")
        merged = deep_merge(json.loads(row[0]), data)
        con.execute(
            "UPDATE docs SET data = ?, updated = ? WHERE col = ? AND id = ?",
            (json.dumps(merged), time.time(), col, doc_id),
        )
        bump()
        con.commit()
    return {"id": doc_id}


@app.post("/api/collections/{col}")
def add_doc(col: str, data: Dict[str, Any] = Body(...)):
    doc_id = uuid.uuid4().hex[:20]
    set_doc(col, doc_id, data)
    return {"id": doc_id}


@app.delete("/api/collections/{col}/{doc_id}")
def delete_doc(col: str, doc_id: str):
    check(col, doc_id)
    with _lock:
        con.execute("DELETE FROM docs WHERE col = ? AND id = ?", (col, doc_id))
        bump()
        con.commit()
    return {"ok": True}


@app.post("/api/reset-demo")
def reset_demo():
    """Wipes everything and reloads the demo data."""
    with _lock:
        con.execute("DELETE FROM docs")
        con.commit()
    seed_if_empty()
    return {"ok": True}


@app.post("/api/ask")
def ask(payload: Dict[str, Any] = Body(...)):
    """Proxies a prompt to the Anthropic API so the key never reaches the browser."""
    if not ANTHROPIC_KEY:
        raise HTTPException(503, "AI features are off. Set ANTHROPIC_API_KEY and restart.")
    prompt = str(payload.get("prompt", ""))[:200_000]
    body = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": 1500,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            out = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise HTTPException(502, f"Anthropic API error {e.code}: {e.read().decode()[:300]}")
    except urllib.error.URLError as e:
        raise HTTPException(502, f"Could not reach the Anthropic API: {e.reason}")
    text = "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text")
    return {"text": text, "truncated": out.get("stop_reason") == "max_tokens"}


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


app.mount("/", StaticFiles(directory=FRONTEND), name="frontend")

if __name__ == "__main__":
    import uvicorn

    # Local use stays on 127.0.0.1:8000. A host sets HOST/PORT (see render.yaml).
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    print(f"IPC-iQ running at http://localhost:{port}  (Ctrl+C to stop)")
    uvicorn.run(app, host=host, port=port)
