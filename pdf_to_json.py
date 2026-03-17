"""
pdf_to_json.py
--------------
Converts PDF tables (Excel exports) into a clean JSON file.
Run: python pdf_to_json.py
Produces: knowledge_base_json/<filename>.json
"""

import os
import json
import pdfplumber

KNOWLEDGE_BASE_DIR = "knowledge_base"
JSON_OUTPUT_DIR    = "knowledge_base_json"


def pdf_table_to_json(filepath: str) -> list:
    """Extract all tables from a PDF and return as list of dicts (one per row)."""
    rows = []
    with pdfplumber.open(filepath) as pdf:
        headers = None
        for page_num, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for table in tables:
                if not table:
                    continue

                # First page / first table with content = headers
                if headers is None:
                    headers = [str(h).strip() if h else f"Col{i}"
                               for i, h in enumerate(table[0])]
                    data_rows = table[1:]
                else:
                    # Subsequent pages: check if first row looks like a header repeat
                    first_row = [str(c).strip() if c else "" for c in table[0]]
                    if first_row == headers:
                        data_rows = table[1:]
                    else:
                        data_rows = table   # no repeated header on this page

                for row in data_rows:
                    if not any(cell for cell in row):
                        continue  # skip empty rows
                    record = {}
                    for h, v in zip(headers, row):
                        record[h] = str(v).strip() if v else ""
                    rows.append(record)

    return rows


def convert_all():
    os.makedirs(JSON_OUTPUT_DIR, exist_ok=True)
    pdf_files = [f for f in os.listdir(KNOWLEDGE_BASE_DIR) if f.lower().endswith(".pdf")]

    if not pdf_files:
        print("[WARN] No PDF files found in knowledge_base/")
        return

    for filename in pdf_files:
        filepath = os.path.join(KNOWLEDGE_BASE_DIR, filename)
        print(f"[...] Converting: {filename}")
        try:
            rows = pdf_table_to_json(filepath)
            out_name = os.path.splitext(filename)[0] + ".json"
            out_path = os.path.join(JSON_OUTPUT_DIR, out_name)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(rows, f, indent=2, ensure_ascii=False)
            print(f"[OK]  {len(rows)} rows → {out_path}")

            # Print first row so you can verify column names
            if rows:
                print(f"      Columns: {list(rows[0].keys())}")
                print(f"      Sample:  {rows[0]}")
        except Exception as e:
            print(f"[ERROR] {filename}: {e}")


if __name__ == "__main__":
    convert_all()
