# 🧠 Local RAG Agent — Multi-File Knowledge Base

A fully **offline** Retrieval-Augmented Generation (RAG) system.  
Your data never leaves your machine. No API keys. No cloud.

---

## 📁 Project Structure

```
local_rag_project/
│
├── knowledge_base/        ← DROP YOUR FILES HERE (.txt, .pdf, .docx, .md)
│   └── example.txt
│
├── chroma_db/             ← Auto-created by ingest.py (vector store)
│
├── main.py                ← Chat agent (run this to talk to your KB)
├── vector.py              ← Document loading + embedding logic
├── ingest.py              ← One-time ingestion script
├── requirements.txt       ← Python dependencies
└── README.md
```

---

## ⚙️ Step-by-Step Setup

### Step 1 — Install Ollama

Download and install Ollama from: https://ollama.com

Verify it works:
```bash
ollama --version
```

---

### Step 2 — Pull the Required Models

You need TWO models:  
- **llama3** — the chat/reasoning model  
- **nomic-embed-text** — the embedding model (converts text to vectors)

```bash
ollama pull llama3
ollama pull nomic-embed-text
```

> 💡 Alternative chat models (if you have low RAM):
> - `ollama pull phi3` (~2GB, fast)
> - `ollama pull mistral` (~4GB, balanced)
> - `ollama pull llama3` (~5GB, best quality)

Verify models are downloaded:
```bash
ollama list
```

---

### Step 3 — Set Up Python Environment

```bash
# Create a virtual environment (recommended)
python -m venv venv

# Activate it
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

### Step 4 — Add Your Knowledge Base Files

Create the `knowledge_base/` folder and drop your files in:

```bash
mkdir knowledge_base
```

Supported formats:
| Format | Extension |
|--------|-----------|
| Plain text | `.txt` |
| PDF | `.pdf` |
| Word document | `.docx` |
| Markdown | `.md` |

You can add **as many files as you want** — even in subfolders:
```
knowledge_base/
├── company_policy.pdf
├── product_manual.docx
├── notes.txt
└── research/
    ├── paper1.pdf
    └── paper2.pdf
```

---

### Step 5 — Ingest the Knowledge Base

This builds the vector store (embeddings) from your files:

```bash
python ingest.py
```

You'll see output like:
```
=== Ingestion Pipeline ===
[OK]   Loaded: knowledge_base/company_policy.pdf  (12 page(s))
[OK]   Loaded: knowledge_base/notes.txt  (1 page(s))
[INFO] Split into 87 chunks.
[INFO] Vector store saved to 'chroma_db/'.
=== Ingestion Complete ===
```

> ⚠️ Re-run `python ingest.py` whenever you add or update files.  
> Use `python ingest.py --reset` to wipe and fully rebuild the vector store.

---

### Step 6 — Chat with Your Knowledge Base

```bash
python main.py
```

Example session:
```
============================================================
  Local RAG Agent  —  Model: llama3
  All processing is 100% local. Type 'exit' to quit.
============================================================

You: What is the refund policy?

Agent: According to the company policy, refunds must be requested
within 30 days of purchase and require a valid receipt...

  📚 Sources used:
     • knowledge_base/company_policy.pdf

You: exit
```

---

## 🔧 Customization

### Change the Chat Model

Edit `main.py`:
```python
CHAT_MODEL = "mistral"   # or phi3, llama3, etc.
```

### Change the Embedding Model

Edit `vector.py`:
```python
EMBED_MODEL = "nomic-embed-text"  # best default
```

### Tune Retrieval

In `main.py`, adjust how many chunks are retrieved:
```python
TOP_K = 5   # increase for broader context, decrease for precision
```

In `vector.py`, adjust chunk size:
```python
chunk_size    = 1000   # characters per chunk
chunk_overlap = 200    # overlap between chunks (preserves context)
```

---

## 🛠️ Troubleshooting

| Problem | Fix |
|---------|-----|
| `Connection refused` error | Make sure Ollama is running: `ollama serve` |
| `No vector store found` | Run `python ingest.py` first |
| Out of memory | Switch to a smaller model: `phi3` or `mistral` |
| PDF not loading | Install: `pip install pypdf` |
| DOCX not loading | Install: `pip install docx2txt` |
| Empty answers | Increase `TOP_K` or reduce `chunk_size` |

---

## 🔒 Privacy

- **Zero internet access** during inference
- All embeddings and vectors stored locally in `chroma_db/`
- Ollama models stored in `~/.ollama/` on your machine
- Nothing is sent to any server

---

## 📦 Dependencies Explained

| Package | Purpose |
|---------|---------|
| `langchain` | RAG pipeline framework |
| `langchain-community` | Document loaders, ChromaDB integration |
| `langchain-ollama` | Ollama LLM + embeddings connector |
| `chromadb` | Local vector database |
| `pypdf` | PDF file reading |
| `docx2txt` | Word document reading |
| `unstructured` | Markdown and other format parsing |
