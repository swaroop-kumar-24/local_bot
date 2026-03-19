# 🧠 Local RAG Agent

A fully **offline** document Q&A system with three query modes.  
Upload PDFs → ask questions → get answers from your documents.  
100% private. No data leaves your machine.

---

## 📁 Files You Need (keep these)

```
project/
├── app.py                 ← Main application — run this
├── api_providers.py       ← Claude / Gemini / Groq / OpenAI integration
├── vector.py              ← PDF ingestion via terminal (optional)
├── requirements.txt       ← Python dependencies
├── setup.bat              ← First-time setup for Windows
├── run.bat                ← Launcher shortcut
├── assets/
│   └── logo.svg           ← Brand icon
└── templates/
    └── index.html         ← Web UI
```

## 🗑 Files You Can Delete

```
main.py          ← Old terminal chat (replaced by app.py)
main_json.py     ← Old JSON-only terminal chat (no longer used)
pdf_to_json.py   ← Old PDF→JSON converter (no longer needed)
debug_db.py      ← Debug tool (optional to keep)
debug_json.py    ← Debug tool (optional to keep)
debug_search.py  ← Debug tool (optional to keep)
ingest.py        ← Terminal ingestion (PDF upload via UI replaces this)
```

---

## 🚀 Setup (First Time)

### Step 1 — Install Ollama
Download from **https://ollama.com** and install it.

### Step 2 — Run Setup
Double-click `setup.bat` — it will:
- Create a Python virtual environment
- Install all required packages
- Pull the Ollama models (`qwen2.5:7b` + `mxbai-embed-large`)
- Create a **"RAG Agent"** shortcut on your Desktop

### Step 3 — Launch
Double-click **"RAG Agent"** on your Desktop  
or run `run.bat` from the project folder.

Browser opens automatically at **http://localhost:5000**

---

## 📖 How to Use

### Upload PDFs
1. Click **"+ Add PDF"** in the left sidebar
2. Select your PDF — it gets embedded automatically
3. The sidebar shows the file with chunk count

### Ask Questions
Three modes available in the input box:

| Mode | What it does |
|------|-------------|
| **⚙ LLM** | Local `qwen2.5:7b` via Ollama — offline, private |
| **⚡ Direct** | Returns raw document excerpts — no model needed |
| **☁ API** | External AI (Groq / Claude / Gemini / OpenAI) |

### API Keys (optional — for API mode)
1. Click **🔑 API Keys** in the top bar
2. Paste your key and select a model
3. Keys are **saved automatically** — no need to re-enter after restart

### Recommended Free API: Groq
- Sign up free at **https://console.groq.com**
- No credit card needed
- 14,400 requests/day free
- Uses **Llama 3.3 70B** — much stronger than local 7B model

---

## 🤖 Models

### Local (Ollama)
| Model | Use |
|-------|-----|
| `qwen2.5:7b` | Chat — answers questions |
| `mxbai-embed-large` | Embeddings — indexes PDFs |

### API Providers
| Provider | Free? | Best Model |
|----------|-------|-----------|
| **Groq** | ✅ Free | `llama-3.3-70b-versatile` |
| **Gemini** | ✅ Free (limited) | `gemini-1.5-flash` |
| **Claude** | 💰 Paid | `claude-sonnet-4-5` |
| **OpenAI** | 💰 Paid | `gpt-4o-mini` |

---

## 🛠 Troubleshooting

| Problem | Fix |
|---------|-----|
| Browser doesn't open | Go to http://localhost:5000 manually |
| "Ollama not reachable" | App auto-starts Ollama — wait 10s and retry |
| PDF shows 0 chunks | PDF may be image-based (scanned) — needs OCR |
| Groq model decommissioned | Open 🔑 API Keys and select a different model |
| Gemini rate limit | Switch to Groq (free, 30 RPM) |
| Port 5000 in use | Edit `app.py` last line: change `port=5000` to `port=5001` |
| Slow responses | Switch from LLM mode to API mode (Groq is much faster) |

---

## 🔒 Privacy

- PDFs are embedded locally using `mxbai-embed-large`
- Embeddings stored in `chroma_db/` on your machine
- API keys stored in `.api_keys.json` locally (never sent anywhere except the chosen provider)
- In **LLM mode**: zero internet — fully offline
- In **API mode**: only the retrieved document excerpts (not full PDFs) are sent to the API

---

## 📦 Full Dependency List

```
flask, pdfplumber, pdfminer.six
langchain, langchain-core, langchain-community
langchain-ollama, langchain-chroma, langchain-text-splitters
chromadb, anthropic, google-generativeai, openai
pandas, openpyxl, docx2txt, unstructured, pypdf
python-dotenv
```

Install all: `pip install -r requirements.txt`

---

## 💻 Requirements

- Windows 10/11 (setup.bat) or Mac/Linux (run manually)
- Python 3.10+
- Ollama installed
- 8GB RAM minimum (16GB recommended for `qwen2.5:7b`)
- Internet only needed for API mode and first-time model download
