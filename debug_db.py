"""
debug_db.py - Diagnose ChromaDB state
Run: python debug_db.py
"""
import os, chromadb, sys

CHROMA_DB_DIR   = "chroma_db"
COLLECTION_NAME = "local_rag"

# 1. Check folder exists
print(f"\n── Folder check ───────────────────────────────────────")
if os.path.exists(CHROMA_DB_DIR):
    files = []
    for root, dirs, fs in os.walk(CHROMA_DB_DIR):
        for f in fs:
            files.append(os.path.join(root, f))
    print(f"'{CHROMA_DB_DIR}/' EXISTS with {len(files)} files:")
    for f in files[:10]:
        print(f"  {f}")
else:
    print(f"'{CHROMA_DB_DIR}/' does NOT exist — ingest never completed!")
    sys.exit(1)

# 2. List all collections
print(f"\n── Collections in DB ──────────────────────────────────")
client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
cols   = client.list_collections()
print(f"Found {len(cols)} collection(s):")
for c in cols:
    print(f"  - '{c.name}'  ({c.count()} chunks)")

# 3. Try opening our collection
print(f"\n── Checking '{COLLECTION_NAME}' ───────────────────────")
try:
    col   = client.get_collection(COLLECTION_NAME)
    total = col.count()
    print(f"Count: {total}")
    if total > 0:
        sample = col.get(limit=3, include=["documents","metadatas"])
        for i,(d,m) in enumerate(zip(sample["documents"], sample["metadatas"])):
            print(f"\n[{i+1}] {d[:300]}")
            print(f"     {m}")
    else:
        print("Collection exists but is EMPTY.")
except Exception as e:
    print(f"Error: {e}")

# 4. Search for term
term = sys.argv[1] if len(sys.argv) > 1 else "AR67"
print(f"\n── Raw search for '{term}' ─────────────────────────────")
try:
    col   = client.get_or_create_collection(COLLECTION_NAME)
    total = col.count()
    if total == 0:
        print("Nothing to search — collection is empty.")
    else:
        all_docs = col.get(include=["documents","metadatas"])
        hits = [(d,m) for d,m in zip(all_docs["documents"], all_docs["metadatas"])
                if term.lower() in d.lower()]
        print(f"Hits: {len(hits)}")
        for d,m in hits[:5]:
            print(f"\n  >> {d[:400]}")
except Exception as e:
    print(f"Search error: {e}")
