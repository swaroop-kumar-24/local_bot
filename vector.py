"""
vector.py
---------
- Excel files (.xlsx, .xls, .csv) → JSON records (exact lookup)
- PDF, DOCX, TXT, MD              → ChromaDB vector store (semantic search)
"""

import os
import json
import pdfplumber

from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    Docx2txtLoader,
    UnstructuredMarkdownLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

# ─── Config ──────────────────────────────────────────────────────────────────

KNOWLEDGE_BASE_DIR = "knowledge_base"
CHROMA_DB_DIR      = "chroma_db"
JSON_OUTPUT_DIR    = "knowledge_base_json"
EMBED_MODEL        = "mxbai-embed-large"
COLLECTION_NAME    = "local_rag"
MAX_CHARS          = 300

# ─── Excel / CSV → JSON ──────────────────────────────────────────────────────

def convert_excel_to_json(filepath: str) -> str:
    """Convert an Excel or CSV file to a JSON file. Returns output path."""
    import pandas as pd

    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".csv":
        df = pd.read_csv(filepath, dtype=str).fillna("")
    else:
        df = pd.read_excel(filepath, dtype=str).fillna("")

    records  = df.to_dict(orient="records")
    os.makedirs(JSON_OUTPUT_DIR, exist_ok=True)
    out_name = os.path.splitext(os.path.basename(filepath))[0] + ".json"
    out_path = os.path.join(JSON_OUTPUT_DIR, out_name)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    return out_path


# ─── PDF → Documents (text-aware) ────────────────────────────────────────────

def load_pdf(filepath: str) -> list:
    """Load a PDF as text chunks using pdfplumber (better than PyPDFLoader for layout)."""
    docs = []
    try:
        with pdfplumber.open(filepath) as pdf:
            for page_num, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text and text.strip():
                    docs.append(Document(
                        page_content=text.strip(),
                        metadata={"source": filepath, "page": page_num + 1}
                    ))
        if not docs:
            # Fallback
            loader = PyPDFLoader(filepath)
            docs   = loader.load()
    except Exception as e:
        print(f"[WARN] pdfplumber failed for {filepath}: {e}. Using PyPDFLoader.")
        loader = PyPDFLoader(filepath)
        docs   = loader.load()
    return docs


# ─── Main ingestion ───────────────────────────────────────────────────────────

VECTOR_LOADERS = {
    ".txt":  TextLoader,
    ".md":   UnstructuredMarkdownLoader,
    ".docx": Docx2txtLoader,
}

EXCEL_EXTS = {".xlsx", ".xls", ".csv"}
PDF_EXT    = ".pdf"


def ingest():
    print("\n=== Ingestion Pipeline ===")
    os.makedirs(JSON_OUTPUT_DIR, exist_ok=True)

    vector_docs  = []   # goes to ChromaDB
    json_count   = 0    # files converted to JSON

    for root, _, files in os.walk(KNOWLEDGE_BASE_DIR):
        for filename in files:
            ext      = os.path.splitext(filename)[1].lower()
            filepath = os.path.join(root, filename)

            # ── Excel/CSV → JSON ──────────────────────────────────────────
            if ext in EXCEL_EXTS:
                try:
                    out_path = convert_excel_to_json(filepath)
                    with open(out_path, encoding="utf-8") as f:
                        count = len(json.load(f))
                    print(f"[JSON] {filename}  →  {out_path}  ({count} rows)")
                    json_count += 1
                except Exception as e:
                    print(f"[ERROR] Excel→JSON failed for {filename}: {e}")

            # ── PDF → vector docs ─────────────────────────────────────────
            elif ext == PDF_EXT:
                try:
                    docs = load_pdf(filepath)
                    vector_docs.extend(docs)
                    print(f"[VEC]  {filename}  ({len(docs)} pages)")
                except Exception as e:
                    print(f"[ERROR] PDF load failed for {filename}: {e}")

            # ── Other text files → vector docs ────────────────────────────
            elif ext in VECTOR_LOADERS:
                try:
                    loader = VECTOR_LOADERS[ext](filepath)
                    docs   = loader.load()
                    for d in docs:
                        d.metadata["source"] = filepath
                    vector_docs.extend(docs)
                    print(f"[VEC]  {filename}  ({len(docs)} section(s))")
                except Exception as e:
                    print(f"[ERROR] Load failed for {filename}: {e}")

            else:
                print(f"[SKIP] {filename}")

    print(f"\n[INFO] JSON conversions: {json_count} file(s)")
    print(f"[INFO] Vector documents: {len(vector_docs)} page(s)/section(s)")

    # ── Build vector store ────────────────────────────────────────────────
    if vector_docs:
        chunks = _split(vector_docs)
        _build_vector_store(chunks)
    else:
        print("[INFO] No text documents to embed — skipping vector store.")

    print("=== Ingestion Complete ===\n")


def _split(docs: list) -> list:
    splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=50)
    chunks   = splitter.split_documents(docs)
    # Truncate oversized chunks
    for c in chunks:
        if len(c.page_content) > MAX_CHARS * 4:
            c.page_content = c.page_content[:MAX_CHARS * 4]
    print(f"[INFO] Split into {len(chunks)} vector chunks.")
    return chunks


def _build_vector_store(chunks: list) -> Chroma:
    embeddings    = OllamaEmbeddings(model=EMBED_MODEL)
    BATCH         = 25
    total         = len(chunks)
    vector_store  = None
    skipped       = 0

    print(f"[INFO] Embedding {total} chunks in batches of {BATCH}...")
    for i in range(0, total, BATCH):
        batch = chunks[i:i+BATCH]
        print(f"  Batch {i//BATCH+1}/{-(-total//BATCH)}  ({min(i+BATCH,total)}/{total})", end="\r")
        try:
            if vector_store is None:
                vector_store = Chroma.from_documents(
                    documents=batch, embedding=embeddings,
                    persist_directory=CHROMA_DB_DIR, collection_name=COLLECTION_NAME,
                )
            else:
                vector_store.add_documents(batch)
        except Exception:
            for doc in batch:
                try:
                    if vector_store is None:
                        vector_store = Chroma.from_documents(
                            documents=[doc], embedding=embeddings,
                            persist_directory=CHROMA_DB_DIR, collection_name=COLLECTION_NAME,
                        )
                    else:
                        vector_store.add_documents([doc])
                except Exception:
                    skipped += 1

    print(f"\n[INFO] Embedded {total-skipped}/{total} chunks. Skipped {skipped}.")
    return vector_store


def load_vector_store() -> Chroma:
    embeddings = OllamaEmbeddings(model=EMBED_MODEL)
    return Chroma(
        persist_directory=CHROMA_DB_DIR,
        embedding_function=embeddings,
        collection_name=COLLECTION_NAME,
    )


if __name__ == "__main__":
    ingest()
