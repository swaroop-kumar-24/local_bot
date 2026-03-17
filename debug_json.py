"""
debug_json.py - See exactly what JSON records exist and what search returns
Run: python debug_json.py AR67
"""
import sys, json, re, os

JSON_OUTPUT_DIR = "knowledge_base_json"

# Load all JSON files
store = {}
for fname in os.listdir(JSON_OUTPUT_DIR):
    if fname.endswith(".json"):
        with open(os.path.join(JSON_OUTPUT_DIR, fname), encoding="utf-8") as f:
            store[fname] = json.load(f)
        print(f"Loaded: {fname}  ({len(store[fname])} records)")

# Show first record so we know column names
for fname, records in store.items():
    if records:
        print(f"\nColumns in {fname}:")
        print(list(records[0].keys()))
        print("\nFirst record:")
        print(records[0])
        break

# Search
query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "AR67"
print(f"\n── Searching for: '{query}' ──────────────────────────")
tokens = [t.lower() for t in re.findall(r'[A-Za-z0-9]+', query)]

for fname, records in store.items():
    hits = []
    for rec in records:
        vals = [str(v).strip().lower() for v in rec.values()]
        if any(tok in vals or any(tok in v for v in vals) for tok in tokens):
            hits.append(rec)
    print(f"\n{fname}: {len(hits)} hits")
    for h in hits[:5]:
        print(f"  {h}")
