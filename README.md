# 🧠 Local RAG Agent — JSON + Vector Knowledge Base

A fully **offline** Retrieval-Augmented Generation (RAG) system.
Your data never leaves your machine. No API keys. No cloud.

---

## 📁 Project Structure

```
files/
├── app.py                        ← Flask web UI (localhost:5000)
├── main.py                       ← Terminal chat (PDF/DOCX/TXT vector search)
├── main_json.py                  ← Terminal chat (Excel/CSV JSON exact lookup)
├── vector.py                     ← Ingestion logic: Excel→JSON, PDF→ChromaDB
├── ingest.py                     ← Run to ingest knowledge_base/ files
├── pdf_to_json.py                ← Manually convert PDF tables to JSON
├── debug_json.py                 ← Debug: inspect JSON records and search hits
├── debug_search.py               ← Debug: test keyword search in isolation
├── debug_db.py                   ← Debug: inspect ChromaDB contents
├── requirements.txt
│
├── knowledge_base/               ← DROP YOUR FILES HERE
│   ├── *.xlsx / *.csv            →  converted to JSON (exact lookup)
│   ├── *.pdf / *.docx / *.txt    →  embedded into ChromaDB (semantic search)
│   └── *.md
│
├── knowledge_base_json/          ← Auto-created: Excel/CSV → JSON records
├── chroma_db/                    ← Auto-created: vector embeddings for PDF/DOCX
└── templates/
    └── index.html                ← Web UI template
```

---

## ⚙️ How It Works

### Two retrieval paths

| File type | Pipeline | Query method |
|-----------|----------|-------------|
| `.xlsx` `.xls` `.csv` | `pandas` → `knowledge_base_json/*.json` | Exact token match — no embeddings |
| `.pdf` `.docx` `.txt` `.md` | `pdfplumber` / LangChain → ChromaDB | Semantic MMR search |

### JSON search scoring
- **+100** — full query string exactly equals a field value (`AR76 == AR76`)
- **+10** — a query token exactly equals a field value
- **0** — substring matches are excluded (`AR76` inside `AR764` = no match)

### Conversation memory
- Stores last 5–10 exchanges as `(human, assistant)` tuples
- Follow-up detection: queries with pronouns (`it`, `its`, `this`, `that`) or ≤3 tokens are enriched with the last known entity from history
- Search always uses enriched raw query — no LLM rewriting that could poison retrieval

---

## 🚀 Setup (Step by Step)

### Step 1 — Install Ollama
Download from https://ollama.com and run:
```bash
ollama pull qwen2.5:7b          # main chat model (recommended)
ollama pull mxbai-embed-large   # embedding model (for PDF/DOCX vector search)
```

> **GTX 1650 (4GB VRAM) note:**
> `qwen2.5:7b` needs ~4.4GB. If it crashes, run before starting:
> ```powershell
> $env:OLLAMA_NUM_GPU=20
> python app.py
> ```

### Step 2 — Set up Python environment
```bash
python -m venv venv

# Activate
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### Step 3 — Add files to knowledge base
```
knowledge_base/
├── your_patent_list.xlsx    ← Excel sheets → JSON exact lookup
├── research_paper.pdf       ← PDFs → semantic vector search
└── notes.docx
```

### Step 4 — Ingest
```bash
python ingest.py           # first time
python ingest.py --reset   # wipe and rebuild (after adding/changing files)
```

Output example:
```
[JSON] patent_list.xlsx  →  knowledge_base_json/patent_list.json  (1810 rows)
[VEC]  research_paper.pdf  (12 pages)
[INFO] Split into 87 vector chunks.
```

### Step 5 — Run

**Web UI (recommended):**
```bash
python app.py
# Opens http://localhost:5000 automatically
```

**Terminal (JSON only):**
```bash
python main_json.py
```

**Terminal (PDF/DOCX vector search):**
```bash
python main.py
```

---

## 🖥️ Web UI Features

### Left Sidebar — Chat History
- **+ New Chat** — start a fresh conversation
- Chat list with auto-title (first question), timestamp, message count
- Click any chat to switch and restore full history
- **✕** on hover to delete a chat

### Left Sidebar — Knowledge Base
- Lists all loaded `.json` files with record counts
- **+ Add JSON file** — upload directly from browser
- **✕** next to each file to delete it and reload
- Record count updates live in status bar

### Top Bar
- **Debug toggle** — when ON, shows below each answer:
  - The actual search query used (enriched if follow-up)
  - Number of records retrieved
  - Raw records sent to the LLM
- **Record badge** — shows how many records were retrieved for last question

### Chat Area
- Animated thinking indicator while model responds
- Gold badge showing `N records retrieved` per answer
- Auto-titles each chat session from the first question

---

## 💬 Chat Commands (terminal mode)

| Command | Action |
|---------|--------|
| `clear` | Reset conversation memory |
| `history` | Print current conversation history |
| `exit` / `quit` | Quit |

---

## 🔧 Configuration

### Change model — `app.py` or `main_json.py`
```python
CHAT_MODEL = "qwen2.5:7b"        # recommended for GTX 1650
# CHAT_MODEL = "qwen2.5:3b"      # lighter, less accurate
# CHAT_MODEL = "llama3.2:3b"     # alternative
```

### Change embedding model — `vector.py`
```python
EMBED_MODEL = "mxbai-embed-large"   # default
```

### Tune retrieval — `app.py` / `main_json.py`
```python
MAX_RESULTS = 10    # max JSON records returned per query
MAX_HISTORY = 10    # conversation exchanges to remember
```

### Tune vector chunking — `vector.py`
```python
chunk_size    = 400   # chars per chunk
chunk_overlap = 50    # overlap between chunks
MAX_CHARS     = 300   # max chars before truncation
```

---

## 🐛 Debug Tools

```bash
# Check what's in ChromaDB
python debug_db.py
python debug_db.py AR76         # search for specific term

# Test JSON search in isolation
python debug_json.py AR76       # see all hits + first record columns
python debug_json.py AR7        # see all AR7x codes that exist

# Test keyword search
python debug_search.py AR76
```

---

## 🛠️ Troubleshooting

| Problem | Fix |
|---------|-----|
| `TemplateNotFound: index.html` | Create `templates/` folder next to `app.py`, put `index.html` inside |
| Old UI showing after update | Hard refresh: `Ctrl+Shift+R`, or open incognito tab |
| `ollama connection refused` | Run `ollama serve` in a separate terminal |
| CUDA OOM crash | Run `$env:OLLAMA_NUM_GPU=20` before starting, or use `qwen2.5:3b` |
| `No module named langchain.xxx` | Run `pip install -r requirements.txt` |
| AR76 returning AR764, AR765 | Already fixed — exact-only matching, no substring scoring |
| 0 chunks in ChromaDB | Previous ingest crashed — run `python ingest.py --reset` |
| LLM hallucinating | Enable Debug toggle in UI to verify records are being passed correctly |
| Excel date warning (openpyxl) | Harmless — cell has invalid date serial, treated as error, ignored |

---

## 📦 Requirements

```
flask
pandas
openpyxl
langchain
langchain-core
langchain-community
langchain-ollama
langchain-text-splitters
langchain-chroma
chromadb
pypdf
pdfplumber
docx2txt
unstructured
python-dotenv
```

---

## 🔒 Privacy

- Zero internet access during inference
- All embeddings stored locally in `chroma_db/`
- JSON records stored locally in `knowledge_base_json/`
- Ollama models stored in `~/.ollama/`
- Nothing sent to any server

---

## 🏗️ Stack

| Component | Technology |
|-----------|-----------|
| LLM | `qwen2.5:7b` via Ollama |
| Embeddings | `mxbai-embed-large` via Ollama |
| Vector DB | ChromaDB (`langchain-chroma`) |
| Framework | LangChain LCEL |
| Table extraction | `pdfplumber`, `pandas`, `openpyxl` |
| Web UI | Flask + vanilla HTML/CSS/JS |
| Python | 3.x in virtualenv |
