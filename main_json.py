"""
main_json.py
------------
Pure JSON lookup RAG. No vector store, no embeddings, no condense step.
Uses the same search logic as debug_json.py — proven to find records correctly.

Setup:
    1. Place .xlsx / .csv in knowledge_base/
    2. python ingest.py
    3. python main_json.py
"""

import os, sys, json, re
from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

# ─── Config ──────────────────────────────────────────────────────────────────

CHAT_MODEL  = "qwen2.5:7b"
JSON_DIR    = "knowledge_base_json"
MAX_RESULTS = 10
MAX_HISTORY = 5
DEBUG       = True    # set False to hide raw context printout

# ─── Prompt ──────────────────────────────────────────────────────────────────

QA_PROMPT = """You are a data reporting assistant. Your only job is to read the RECORDS below and present them.

TASK:
- The user asked about: {question}
- The matching records are listed below under RECORDS.
- Present each record as a clean, readable summary listing every field and its value.
- Do not skip any fields. Do not add anything not in the records.
- Do not say "I cannot find" or "not in the records" — the records ARE the answer.
# - Format each record like this:
#     Field Name: value
#     Field Name: value
    ...

RECORDS:
{records}

CONVERSATION HISTORY (only to understand pronouns like "it", "that"):
{history}

Now present the records above as the answer to: {question}

ANSWER:"""

# ─── Pronoun detection ───────────────────────────────────────────────────────

PRONOUNS = {"it", "its", "this", "that", "these", "those", "they", "their",
            "them", "he", "she", "his", "her", "the same", "aforementioned"}

def is_followup(query: str) -> bool:
    """Return True if the query contains pronouns or lacks a searchable entity."""
    tokens = set(re.findall(r'[A-Za-z0-9]+', query.lower()))
    return bool(tokens & PRONOUNS) or len(tokens) <= 3


def extract_last_entity(history: list) -> str:
    """
    Pull the most recent searchable code/entity from conversation history.
    Looks for patterns like AR76, IN2024, patent codes, proper nouns etc.
    """
    if not history:
        return ""
    # Walk history newest-first
    for human, assistant in reversed(history):
        # Find codes like AR76, IN2024CH, alphanumeric IDs
        codes = re.findall(r'\b[A-Z]{1,4}\d{2,}\w*\b', human + " " + assistant)
        if codes:
            return codes[0]
        # Fallback: any capitalised word that might be a name/entity
        words = re.findall(r'\b[A-Z][a-z]{2,}\b', human)
        if words:
            return words[0]
    return ""


def enrich_query(query: str, history: list) -> str:
    """
    If the query is a follow-up (has pronouns / no clear entity),
    prepend the last known entity so search can find the right record.
    """
    if not is_followup(query):
        return query
    entity = extract_last_entity(history)
    if entity:
        enriched = f"{entity} {query}"
        print(f"  [follow-up detected — searching as: '{enriched}']")
        return enriched
    return query


# ─── Load JSON ────────────────────────────────────────────────────────────────

_store: dict = {}

def load():
    if not os.path.exists(JSON_DIR):
        print(f"[ERROR] '{JSON_DIR}/' not found. Run: python ingest.py")
        sys.exit(1)
    files = [f for f in os.listdir(JSON_DIR) if f.endswith(".json")]
    if not files:
        print(f"[ERROR] No JSON files in '{JSON_DIR}/'. Run: python ingest.py")
        sys.exit(1)
    for fname in files:
        path = os.path.join(JSON_DIR, fname)
        with open(path, encoding="utf-8") as f:
            records = json.load(f)
        _store[fname] = records
        cols = list(records[0].keys()) if records else []
        print(f"[OK] {fname}  —  {len(records)} records")
        print(f"     Columns: {cols}\n")

# ─── Search (same logic as debug_json.py) ────────────────────────────────────

def search(query: str) -> list:
    """
    Exact-only matching — no substring scoring.
    A record only matches if a query token EXACTLY equals a full field value.
    This prevents AR76 from matching AR764, AR765, etc.

    Scoring:
      +100  full query string exactly equals a field value  (e.g. "AR76" == "AR76")
      +10   a query token exactly equals a field value
      ZERO  for substring matches (AR76 inside AR764 = no match)
    """
    tokens      = [t.lower() for t in re.findall(r'[A-Za-z0-9]+', query) if len(t) >= 2]
    query_lower = query.strip().lower()

    scored = []
    for fname, records in _store.items():
        for rec in records:
            # Exact field values only — strip and lowercase each
            field_vals = [str(v).strip().lower() for v in rec.values() if str(v).strip()]
            score      = 0

            # Full query matches a field value exactly
            if query_lower in field_vals:
                score += 100

            # Each token matches a field value exactly
            for tok in tokens:
                if tok in field_vals:
                    score += 10

            if score > 0:
                scored.append((score, fname, rec))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:MAX_RESULTS]


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

# ─── Chat ─────────────────────────────────────────────────────────────────────

def chat():
    total = sum(len(v) for v in _store.values())
    print("="*60)
    print(f"  JSON RAG  |  {CHAT_MODEL}  |  {total} records")
    print(f"  DEBUG={'ON' if DEBUG else 'OFF'}  |  'clear' = reset  |  'exit' = quit")
    print("="*60 + "\n")

    llm      = OllamaLLM(model=CHAT_MODEL)
    qa_chain = PromptTemplate.from_template(QA_PROMPT) | llm | StrOutputParser()
    history  = []

    while True:
        try:
            query = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!"); break

        if not query:             continue
        if query.lower() in ("exit","quit","q"): print("Goodbye!"); break
        if query.lower() == "clear":
            history.clear(); print("[INFO] Memory cleared.\n"); continue
        if query.lower() == "history":
            print(fmt_history(history) + "\n"); continue

        # Enrich query with history context if it's a follow-up
        search_query = enrich_query(query, history)
        hits    = search(search_query)
        records = fmt_records(hits)
        print(f"  [{len(hits)} record(s) found from {JSON_DIR}/]")

        # Show exactly what the LLM will receive
        if DEBUG:
            print("\n── DEBUG: records sent to LLM ──────────────────────")
            print(records[:1000] + ("..." if len(records) > 1000 else ""))
            print("────────────────────────────────────────────────────\n")

        # Answer via LLM
        print("Agent: ", end="", flush=True)
        answer = qa_chain.invoke({
            "records":  records,
            "history":  fmt_history(history),
            "question": query,
        })
        print(answer)

        history.append((query, answer))
        if len(history) > MAX_HISTORY:
            history = history[-MAX_HISTORY:]
        print()


if __name__ == "__main__":
    load()
    chat()
