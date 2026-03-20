"""
app.py
------
Local RAG — PDF-only, unstructured data.
PDFs are embedded into ChromaDB via mxbai-embed-large.
Three query modes: Local LLM (Ollama) | Direct (raw chunks) | API (Claude/Gemini/OpenAI)

Run: python app.py → http://localhost:5000
"""

import os, uuid, secrets, tempfile, json, subprocess, sys, time
from datetime import datetime
from collections import defaultdict
from flask import Flask, render_template, request, jsonify, session

from langchain_ollama import OllamaLLM, OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from api_providers import PROVIDERS, PROVIDER_INFO

# ── Persistent API key storage ────────────────────────────────────────────────
KEYS_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".api_keys.json")
CHATS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".chats.json")

def load_api_keys():
    """Load saved API keys and model selections from disk."""
    if os.path.exists(KEYS_FILE):
        try:
            with open(KEYS_FILE, "r") as f:
                data = json.load(f)
            return data.get("keys", {}), data.get("models", {})
        except Exception:
            pass
    return {}, {}

def save_api_keys(keys: dict, models: dict):
    """Save API keys and model selections to disk."""
    try:
        with open(KEYS_FILE, "w") as f:
            json.dump({"keys": keys, "models": models}, f, indent=2)
    except Exception as e:
        print(f"[WARN] Could not save API keys: {e}")

# ── Persistent chat storage ───────────────────────────────────────────────────
def load_chats() -> dict:
    if os.path.exists(CHATS_FILE):
        try:
            with open(CHATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_chats():
    try:
        with open(CHATS_FILE, "w", encoding="utf-8") as f:
            json.dump(_chats, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[WARN] Could not save chats: {e}")


# ── Auto-start Ollama ─────────────────────────────────────────────────────────
def ensure_ollama_running():
    """Check if Ollama is running, start it if not."""
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
        print("[INFO] Ollama is already running.")
        return True
    except Exception:
        pass

    print("[INFO] Starting Ollama...")
    try:
        if sys.platform == "win32":
            subprocess.Popen(
                ["ollama", "serve"],
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        else:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        # Wait up to 15s for Ollama to start
        for i in range(15):
            time.sleep(1)
            try:
                urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
                print("[INFO] Ollama started successfully.")
                return True
            except Exception:
                pass
        print("[WARN] Ollama did not start in time — proceeding anyway.")
        return False
    except FileNotFoundError:
        print("[ERROR] Ollama not found. Download from https://ollama.com")
        return False

# ── Config ────────────────────────────────────────────────────────────────────
CHAT_MODEL    = "qwen2.5:7b"
EMBED_MODEL   = "mxbai-embed-large"
CHROMA_DIR    = "chroma_db"
COLLECTION    = "local_rag"
MAX_HISTORY   = 10
TOP_K         = 5
CHUNK_SIZE    = 400
CHUNK_OVERLAP = 80

PRONOUNS = {"it","its","this","that","these","those","they","their","them","he","she","his","her"}

# ── Prompt ────────────────────────────────────────────────────────────────────
QA_PROMPT = """You are a helpful assistant answering questions from document content.

Instructions:
- Answer the questions with respect to the knowledge provided in context to Indian Patent rights and its SOPs.
- The context was fetched specifically for the user query — use all relevant parts.
- Reference specific sections or pages when helpful.
- Use conversation history only to resolve pronouns like "it" or "that".
- Always use all relevant context, even if the question seems answerable without it.
- If the question is ambiguous, use the context to disambiguate and provide a more specific answer.
- If the context contains multiple relevant sections, synthesize them into a comprehensive answer.
- If no relevant information is found in the context, answer it but say specifically "I couldn't find that in the documents, but based on my general knowledge..." to ensure the user knows the answer is not grounded in the provided context.

USER QUERY:
{question}

RETRIEVED CONTEXT (passages retrieved from documents based on the query above):
{context}

CONVERSATION HISTORY (use only to resolve pronouns):
{history}

ANSWER:"""

# ── Flask ─────────────────────────────────────────────────────────────────────
app = Flask(__name__,
    template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates'),
    static_folder  =os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets'),
    static_url_path='/assets')
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.secret_key = secrets.token_hex(16)

# ── Embeddings & Vector store ─────────────────────────────────────────────────
_embeddings   = OllamaEmbeddings(model=EMBED_MODEL)
_vector_store = None

def get_vs():
    global _vector_store
    if _vector_store is not None:
        return _vector_store
    if os.path.exists(CHROMA_DIR):
        try:
            _vector_store = Chroma(
                persist_directory  =CHROMA_DIR,
                embedding_function =_embeddings,
                collection_name    =COLLECTION,
            )
            n = _vector_store._collection.count()
            print(f"[INFO] Vector store loaded — {n} chunks.")
        except Exception as e:
            print(f"[ERROR] Vector store: {e}")
    return _vector_store

def _ocr_available() -> bool:
    """Check if Tesseract OCR is installed on this system."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _extract_images_from_page(page, page_num: int, source_name: str) -> list:
    """
    Extract images from a pdfplumber page and run OCR on each.
    Returns list of Document objects with OCR text.
    """
    docs = []
    try:
        import pytesseract
        from PIL import Image
        import io

        for img_idx, img in enumerate(page.images):
            try:
                # Get image bytes from the page
                x0, top, x1, bottom = img["x0"], img["top"], img["x1"], img["bottom"]
                # Crop the image region from the page as a PIL image
                cropped = page.within_bbox((x0, top, x1, bottom)).to_image(resolution=100)
                pil_img = cropped.original

                # Run OCR
                ocr_text = pytesseract.image_to_string(pil_img, lang="eng").strip()
                if ocr_text and len(ocr_text) > 20:   # skip noise
                    docs.append(Document(
                        page_content="[Image OCR text]\n" + ocr_text,
                        metadata={"source": source_name, "page": page_num,
                                  "type": "image_ocr", "image_index": img_idx}
                    ))
            except Exception as e:
                print(f"[WARN] OCR failed for image {img_idx} on page {page_num}: {e}")
    except ImportError:
        pass
    return docs


def embed_pdf(path: str, source_name: str) -> int:
    """
    Extract text and images from a PDF and embed into ChromaDB.
    - Text pages: extracted via pdfplumber
    - Image-only pages (scanned): OCR via pytesseract if installed
    - Embedded images: OCR extracted separately
    """
    import pdfplumber
    use_ocr = _ocr_available()
    if use_ocr:
        print(f"[INFO] OCR enabled — will extract text from images in {source_name}")
    else:
        print(f"[INFO] OCR not available — install Tesseract for image text extraction")

    pages = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_num = i + 1
            text = page.extract_text()

            if text and text.strip():
                # Normal text page
                pages.append(Document(
                    page_content=text.strip(),
                    metadata={"source": source_name, "page": page_num, "type": "text"}
                ))
                # Also extract any embedded images on this page
                if use_ocr and page.images:
                    pages.extend(_extract_images_from_page(page, page_num, source_name))

            else:
                # No text found — likely a scanned/image page
                if use_ocr:
                    print(f"[INFO] Page {page_num} has no text — running OCR...")
                    try:
                        import pytesseract
                        # Render full page as image and OCR it
                        page_img = page.to_image(resolution=200)
                        pil_img  = page_img.original
                        ocr_text = pytesseract.image_to_string(pil_img, lang="eng").strip()
                        if ocr_text and len(ocr_text) > 20:
                            pages.append(Document(
                                page_content="[Scanned page OCR]\n" + ocr_text,
                                metadata={"source": source_name, "page": page_num,
                                          "type": "scanned_ocr"}
                            ))
                            print(f"[OK] OCR extracted {len(ocr_text)} chars from page {page_num}")
                        else:
                            print(f"[WARN] OCR found no readable text on page {page_num}")
                    except Exception as e:
                        print(f"[WARN] OCR failed on page {page_num}: {e}")
                else:
                    print(f"[WARN] Page {page_num} has no text and OCR is not available.")

    if not pages:
        return 0

    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    chunks   = splitter.split_documents(pages)
    global _vector_store
    if _vector_store is None:
        _vector_store = Chroma.from_documents(
            documents=chunks, embedding=_embeddings,
            persist_directory=CHROMA_DIR, collection_name=COLLECTION)
    else:
        _vector_store.add_documents(chunks)
    return len(chunks)

def search(query: str) -> str:
    vs = get_vs()
    if vs is None:
        print("[WARN] Vector store not loaded — upload a PDF first.")
        return ""
    try:
        # Try MMR first for diversity
        docs = vs.as_retriever(
            search_type="mmr",
            search_kwargs={"k": TOP_K, "fetch_k": TOP_K * 4}
        ).invoke(query)

        # Fallback to similarity search if MMR returns nothing
        if not docs:
            print("[INFO] MMR returned nothing — trying similarity search")
            docs = vs.similarity_search(query, k=TOP_K)

        if not docs:
            print(f"[WARN] No chunks found for query: {query[:60]}")
            return ""

        print(f"[INFO] Retrieved {len(docs)} chunks for: {query[:60]}")
        parts = []
        for doc in docs:
            src = os.path.basename(doc.metadata.get("source", "doc"))
            pg  = doc.metadata.get("page", "")
            parts.append(f"[{src}{' p.'+str(pg) if pg else ''}]\n{doc.page_content}")
        return "\n\n".join(parts)
    except Exception as e:
        print(f"[WARN] Search error: {e}")
        return ""

def get_sources(context: str) -> list:
    import re
    return list(dict.fromkeys(re.findall(r'\[([^\]]+)\]', context)))

# ── Helpers ───────────────────────────────────────────────────────────────────
_llm      = OllamaLLM(model=CHAT_MODEL)
_qa_chain = PromptTemplate.from_template(QA_PROMPT) | _llm | StrOutputParser()

def fmt_history(h):
    return "\n".join(f"Human: {q}\nAssistant: {a}" for q, a in h) if h else "None"

def enrich(query, history):
    tokens = set(query.lower().split())
    if not (tokens & PRONOUNS) and len(tokens) > 3:
        return query
    for q, _ in reversed(history):
        codes = __import__('re').findall(r'\b[A-Z]{1,4}\d{2,}\w*\b', q)
        if codes:
            return f"{codes[0]} {query}"
    return query

# ── Session ───────────────────────────────────────────────────────────────────
_chats: dict     = load_chats()
_api_keys, _api_models = load_api_keys()
if _api_keys:
    print(f"[INFO] Loaded saved API keys for: {', '.join(_api_keys.keys())}")

def new_chat():
    cid = str(uuid.uuid4())[:8]
    _chats[cid] = {"title": f"Chat {len(_chats)+1}",
                   "history": [], "created": datetime.now().strftime("%H:%M")}
    save_chats()
    return cid

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    if "active_chat" not in session or session["active_chat"] not in _chats:
        # Restore last chat from saved chats, or create new one
        if _chats:
            session["active_chat"] = list(_chats.keys())[-1]
        else:
            session["active_chat"] = new_chat()
    vs = get_vs()
    chunks = vs._collection.count() if vs else 0
    # list PDF source files
    files = []
    if vs:
        try:
            metas = vs._collection.get(include=["metadatas"])["metadatas"]
            src_counts = defaultdict(int)
            for m in metas:
                if m: src_counts[m.get("source","?")] += 1
            files = [{"name": k, "chunks": v} for k, v in src_counts.items()]
        except: pass
    return render_template("index.html", model=CHAT_MODEL, chunks=chunks, files=files)

@app.route("/chat", methods=["POST"])
def chat():
    data    = request.json
    query   = data.get("message","").strip()
    debug   = data.get("debug", False)
    chat_id = session.get("active_chat")
    if not query or not chat_id or chat_id not in _chats:
        return jsonify({"error": "Invalid request"}), 400
    history = _chats[chat_id]["history"]
    context = search(enrich(query, history))
    try:
        ctx_for_llm = context if context else "(No relevant passages found in documents)"
        answer = _qa_chain.invoke({"context": ctx_for_llm, "history": fmt_history(history), "question": query})
    except Exception as e:
        err = str(e).lower()
        if "connection" in err or "refused" in err:
            return jsonify({"error": "Ollama is not reachable. Is it running?"}), 500
        return jsonify({"error": "LLM error: " + str(e)[:200]}), 500
    sources = get_sources(context)
    debug_info = {"context": context[:800], "sources": sources} if debug else None
    return _finish(chat_id, query, answer, sources, {"debug": debug_info})

@app.route("/chat/direct", methods=["POST"])
def chat_direct():
    data    = request.json
    query   = data.get("message","").strip()
    chat_id = session.get("active_chat")
    if not query or not chat_id or chat_id not in _chats:
        return jsonify({"error": "Invalid request"}), 400
    history = _chats[chat_id]["history"]
    context = search(enrich(query, history))
    answer  = context if context else "No relevant passages found in the uploaded documents for this query."
    sources = get_sources(context)
    return _finish(chat_id, query, answer, sources)

@app.route("/chat/api", methods=["POST"])
def chat_api():
    data     = request.json
    query    = data.get("message","").strip()
    provider = data.get("provider","").lower()
    chat_id  = session.get("active_chat")
    if not query or not chat_id or chat_id not in _chats:
        return jsonify({"error": "Invalid request"}), 400
    if provider not in PROVIDER_INFO:
        return jsonify({"error": "Unknown provider"}), 400
    if provider not in _api_keys:
        return jsonify({"error": f"No API key set for {provider}"}), 400
    history = _chats[chat_id]["history"]
    context = search(enrich(query, history))
    try:
        model      = _api_models.get(provider, PROVIDER_INFO[provider]["default_model"])
        ctx_for_api = context if context else "(No relevant passages found in documents)"
        print(f"[API] {provider}/{model} | {len(ctx_for_api)} chars context")
        answer = PROVIDERS[provider](api_key=_api_keys[provider], context=ctx_for_api,
                                     history=history, question=query, model=model)
    except Exception as e:
        return jsonify({"error": "API error: " + str(e)[:400]}), 500
    sources = get_sources(context)
    return _finish(chat_id, query, answer, sources, {"provider": provider})

def _finish(chat_id, query, answer, sources, extra=None):
    h = _chats[chat_id]["history"]
    h.append((query, answer))
    if len(h) > MAX_HISTORY:
        _chats[chat_id]["history"] = h[-MAX_HISTORY:]
    if len(h) == 1:
        _chats[chat_id]["title"] = query[:35] + ("…" if len(query) > 35 else "")
    save_chats()
    resp = {"answer": answer, "sources": sources, "chat_title": _chats[chat_id]["title"]}
    if extra: resp.update(extra)
    return jsonify(resp)

# ── KB management ─────────────────────────────────────────────────────────────
@app.route("/kb/files")
def kb_files():
    vs = get_vs()
    if not vs:
        return jsonify([])
    try:
        metas = vs._collection.get(include=["metadatas"])["metadatas"]
        src_counts = defaultdict(int)
        for m in metas:
            if m: src_counts[m.get("source","?")] += 1
        return jsonify([{"name": k, "chunks": v, "display": f"{v} chunks"}
                        for k, v in src_counts.items()])
    except Exception as e:
        return jsonify([])

@app.route("/kb/upload", methods=["POST"])
def kb_upload():
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400
    f   = request.files["file"]
    ext = os.path.splitext(f.filename)[1].lower()
    if ext != ".pdf":
        return jsonify({"error": "Only PDF files are supported. Upload .pdf files."}), 400
    tmp = os.path.join(tempfile.gettempdir(), f.filename)
    f.save(tmp)
    try:
        chunks = embed_pdf(tmp, f.filename)
        os.remove(tmp)
        if chunks == 0:
            return jsonify({"error": "No readable text found in this PDF."}), 400
        return jsonify({"name": f.filename, "chunks": chunks,
                        "display": f"{chunks} chunks", "type": "vector"})
    except Exception as e:
        return jsonify({"error": f"Embedding failed: {str(e)}"}), 500

@app.route("/kb/delete/<path:filename>", methods=["POST"])
def kb_delete(filename):
    global _vector_store
    vs = get_vs()
    if not vs:
        return jsonify({"error": "No vector store"}), 404
    try:
        all_data   = vs._collection.get(include=["metadatas"])
        ids_to_del = [id_ for id_, m in zip(all_data["ids"], all_data["metadatas"])
                      if m and m.get("source") == filename]
        if ids_to_del:
            vs._collection.delete(ids=ids_to_del)
            return jsonify({"status": "ok", "deleted": len(ids_to_del)})
        return jsonify({"status": "not_found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Chat sessions ─────────────────────────────────────────────────────────────
@app.route("/chats")
def list_chats():
    active = session.get("active_chat")
    return jsonify([{"id": cid, "title": c["title"], "created": c["created"],
                     "active": cid == active, "count": len(c["history"])}
                    for cid, c in _chats.items()])

@app.route("/chats/new", methods=["POST"])
def create_chat():
    cid = new_chat(); session["active_chat"] = cid
    return jsonify({"id": cid, "title": _chats[cid]["title"]})

@app.route("/chats/<cid>/switch", methods=["POST"])
def switch_chat(cid):
    if cid not in _chats: return jsonify({"error": "Not found"}), 404
    session["active_chat"] = cid
    flat = []
    for q, a in _chats[cid]["history"]:
        flat += [{"role":"user","text":q}, {"role":"bot","text":a}]
    return jsonify({"id": cid, "title": _chats[cid]["title"], "history": flat})

@app.route("/chats/<cid>/delete", methods=["POST"])
def delete_chat(cid):
    if cid in _chats: del _chats[cid]
    if session.get("active_chat") == cid:
        session["active_chat"] = list(_chats.keys())[-1] if _chats else new_chat()
    save_chats()
    return jsonify({"status": "ok", "active": session["active_chat"]})

# ── API keys ──────────────────────────────────────────────────────────────────
@app.route("/apikeys")
def get_apikeys():
    return jsonify({k: {"set": k in _api_keys, "info": info,
                        "selected_model": _api_models.get(k, info["default_model"])}
                    for k, info in PROVIDER_INFO.items()})

@app.route("/apikeys/<provider>", methods=["POST"])
def set_apikey(provider):
    if provider not in PROVIDER_INFO: return jsonify({"error": "Unknown provider"}), 400
    data  = request.json
    key   = data.get("key","").strip()
    model = data.get("model","").strip()
    if key: _api_keys[provider] = key
    elif provider in _api_keys: del _api_keys[provider]; save_api_keys(_api_keys, _api_models); return jsonify({"status":"cleared"})
    if model: _api_models[provider] = model
    elif provider not in _api_models:
        _api_models[provider] = PROVIDER_INFO[provider]["default_model"]
    save_api_keys(_api_keys, _api_models)
    return jsonify({"status": "set", "model": _api_models.get(provider)})

# ── Debug ─────────────────────────────────────────────────────────────────────
@app.route("/debug/context", methods=["POST"])
def debug_context():
    query = request.json.get("query","").strip()
    if not query: return jsonify({"error": "No query"}), 400
    vs  = get_vs()
    ctx = search(query)
    return jsonify({
        "query": query, "vector_store": vs is not None,
        "vec_chunks": vs._collection.count() if vs else 0,
        "context_len": len(ctx),
        "context_preview": ctx[:800] if ctx else "(empty)",
    })

if __name__ == "__main__":
    import webbrowser
    ensure_ollama_running()
    print("[INFO] RAG UI → http://localhost:5000")
    webbrowser.open("http://localhost:5000")
    app.run(debug=False, port=5000)
