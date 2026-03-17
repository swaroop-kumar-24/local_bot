"""
app.py
------
Flask web UI for JSON RAG Agent (main_json.py logic).
Run: python app.py  →  http://localhost:5000
"""

import os, sys, json, re, uuid, shutil
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
import secrets

from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

# ─── Config ──────────────────────────────────────────────────────────────────

CHAT_MODEL   = "qwen2.5:7b"
JSON_DIR     = "knowledge_base_json"
MAX_RESULTS  = 10
MAX_HISTORY  = 10

PRONOUNS = {"it","its","this","that","these","those","they","their",
            "them","he","she","his","her"}

# ─── Prompt ──────────────────────────────────────────────────────────────────

QA_PROMPT = """\
You are a data reporting assistant. Your only job is to read the RECORDS below and present them.

TASK:
- The user asked about: {question}
- The matching records are listed below under RECORDS.
- Present each record as a clean, readable summary listing every field and its value.
- Do not skip any fields. Do not add anything not in the records.
- Do not say "I cannot find" or "not in the records" — the records ARE the answer.
# - Format each record like this:
#     Field Name: value
#     Field Name: value

RECORDS:
{records}

CONVERSATION HISTORY (only to understand pronouns like "it", "that"):
{history}

Now present the records above as the answer to: {question}

ANSWER:"""

# ─── JSON store ──────────────────────────────────────────────────────────────

_store: dict = {}

def reload_store():
    global _store
    _store = {}
    if not os.path.exists(JSON_DIR):
        os.makedirs(JSON_DIR)
        return
    for fname in os.listdir(JSON_DIR):
        if fname.endswith(".json"):
            try:
                with open(os.path.join(JSON_DIR, fname), encoding="utf-8") as f:
                    _store[fname] = json.load(f)
            except Exception as e:
                print(f"[WARN] Could not load {fname}: {e}")

reload_store()

# ─── Search ──────────────────────────────────────────────────────────────────

def search(query: str) -> list:
    tokens      = [t.lower() for t in re.findall(r'[A-Za-z0-9]+', query) if len(t) >= 2]
    query_lower = query.strip().lower()
    scored = []
    for fname, records in _store.items():
        for rec in records:
            field_vals = [str(v).strip().lower() for v in rec.values() if str(v).strip()]
            score = 0
            if query_lower in field_vals:
                score += 100
            for tok in tokens:
                if tok in field_vals:
                    score += 10
            if score > 0:
                scored.append((score, fname, rec))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:MAX_RESULTS]


def is_followup(query: str) -> bool:
    tokens = set(re.findall(r'[A-Za-z0-9]+', query.lower()))
    return bool(tokens & PRONOUNS) or len(tokens) <= 3


def extract_last_entity(history: list) -> str:
    for human, _ in reversed(history):
        codes = re.findall(r'\b[A-Z]{1,4}\d{2,}\w*\b', human)
        if codes:
            return codes[0]
    return ""


def enrich_query(query: str, history: list) -> str:
    if not is_followup(query):
        return query
    entity = extract_last_entity(history)
    return f"{entity} {query}" if entity else query


def fmt_records(scored: list) -> str:
    if not scored:
        return "(no matching records found)"
    lines = []
    for i, (score, fname, rec) in enumerate(scored, 1):
        fields = "\n".join(f"  {k}: {v}" for k, v in rec.items() if str(v).strip())
        lines.append(f"Record {i} [source: {fname}]:\n{fields}")
    return "\n\n".join(lines)


def fmt_history(h: list) -> str:
    return "\n".join(f"Human: {q}\nAssistant: {a}" for q, a in h) if h else "None"

# ─── LLM ─────────────────────────────────────────────────────────────────────

llm      = OllamaLLM(model=CHAT_MODEL)
qa_chain = PromptTemplate.from_template(QA_PROMPT) | llm | StrOutputParser()

# ─── In-memory chat sessions ──────────────────────────────────────────────────
# { session_id: { "title": str, "history": [(q,a)], "created": str } }
_chats: dict = {}

def get_chats():
    return _chats

def new_chat():
    cid = str(uuid.uuid4())[:8]
    _chats[cid] = {
        "title":   f"Chat {len(_chats)+1}",
        "history": [],
        "created": datetime.now().strftime("%H:%M")
    }
    return cid

# ─── Flask app ────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)


@app.route("/")
def index():
    if "active_chat" not in session or session["active_chat"] not in _chats:
        session["active_chat"] = new_chat()
    total = sum(len(v) for v in _store.values())
    return render_template("index.html", model=CHAT_MODEL, total_records=total)


@app.route("/chat", methods=["POST"])
def chat():
    data    = request.json
    query   = data.get("message","").strip()
    debug   = data.get("debug", False)
    chat_id = session.get("active_chat")

    if not query or not chat_id or chat_id not in _chats:
        return jsonify({"error": "Invalid request"}), 400

    history = _chats[chat_id]["history"]

    # Enrich + search
    search_q = enrich_query(query, history)
    hits     = search(search_q)
    records  = fmt_records(hits)

    debug_info = None
    if debug:
        debug_info = {
            "search_query": search_q,
            "hits": len(hits),
            "records_preview": records[:800]
        }

    # Answer
    answer = qa_chain.invoke({
        "records":  records,
        "history":  fmt_history(history),
        "question": query,
    })

    # Update history + auto-title first message
    history.append((query, answer))
    if len(history) > MAX_HISTORY:
        _chats[chat_id]["history"] = history[-MAX_HISTORY:]
    if len(history) == 1:
        _chats[chat_id]["title"] = query[:35] + ("…" if len(query) > 35 else "")

    return jsonify({
        "answer":     answer,
        "hits":       len(hits),
        "debug":      debug_info,
        "chat_title": _chats[chat_id]["title"]
    })


@app.route("/chats", methods=["GET"])
def list_chats():
    active = session.get("active_chat")
    result = []
    for cid, c in _chats.items():
        result.append({
            "id":      cid,
            "title":   c["title"],
            "created": c["created"],
            "active":  cid == active,
            "count":   len(c["history"])
        })
    return jsonify(result)


@app.route("/chats/new", methods=["POST"])
def create_chat():
    cid = new_chat()
    session["active_chat"] = cid
    return jsonify({"id": cid, "title": _chats[cid]["title"]})


@app.route("/chats/<cid>/switch", methods=["POST"])
def switch_chat(cid):
    if cid not in _chats:
        return jsonify({"error": "Not found"}), 404
    session["active_chat"] = cid
    history = _chats[cid]["history"]
    return jsonify({
        "id":      cid,
        "title":   _chats[cid]["title"],
        "history": [{"role":"user","text":q} if i%2==0 else {"role":"bot","text":a}
                    for q,a in history for i in range(2)]
    })


@app.route("/chats/<cid>/delete", methods=["POST"])
def delete_chat(cid):
    if cid in _chats:
        del _chats[cid]
    if session.get("active_chat") == cid:
        if _chats:
            session["active_chat"] = list(_chats.keys())[-1]
        else:
            session["active_chat"] = new_chat()
    return jsonify({"status": "ok", "active": session["active_chat"]})


# ─── Knowledge base file management ──────────────────────────────────────────

@app.route("/kb/files", methods=["GET"])
def kb_files():
    files = []
    if os.path.exists(JSON_DIR):
        for f in os.listdir(JSON_DIR):
            if f.endswith(".json"):
                path  = os.path.join(JSON_DIR, f)
                count = 0
                try:
                    with open(path, encoding="utf-8") as fp:
                        count = len(json.load(fp))
                except:
                    pass
                files.append({"name": f, "records": count})
    return jsonify(files)


@app.route("/kb/upload", methods=["POST"])
def kb_upload():
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400
    f    = request.files["file"]
    name = f.filename
    if not name.endswith(".json"):
        return jsonify({"error": "Only .json files allowed"}), 400
    os.makedirs(JSON_DIR, exist_ok=True)
    f.save(os.path.join(JSON_DIR, name))
    reload_store()
    count = len(_store.get(name, []))
    return jsonify({"name": name, "records": count})


@app.route("/kb/delete/<filename>", methods=["POST"])
def kb_delete(filename):
    path = os.path.join(JSON_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
    reload_store()
    return jsonify({"status": "ok"})


@app.route("/status")
def status():
    total = sum(len(v) for v in _store.values())
    return jsonify({
        "model":   CHAT_MODEL,
        "records": total,
        "files":   len(_store)
    })


if __name__ == "__main__":
    import webbrowser
    print(f"[INFO] Starting RAG UI at http://localhost:5000")
    webbrowser.open("http://localhost:5000")
    app.run(debug=False, port=5000)

app.config["TEMPLATES_AUTO_RELOAD"] = True
app.run(debug=False, port=5000)