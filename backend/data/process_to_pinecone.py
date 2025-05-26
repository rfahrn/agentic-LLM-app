import os
import re
import time
import pdfplumber
import numpy as np
import pandas as pd
from nltk.tokenize import word_tokenize
from tqdm import tqdm
from openai import OpenAI
from pinecone.grpc import PineconeGRPC as Pinecone
from pinecone import ServerlessSpec
# get enviroment variables
from dotenv import load_dotenv
load_dotenv()

# ─── USER CONFIGURATION ────────────────────────────────────────────────────────

OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY  = os.getenv("PINECONE_API_KEY")
PINECONE_ENV      = "gcp-starter" 
PINECONE_INDEX    = "medguides-index"

PDF_DIR           = r"C:\Users\FahRe\Desktop\agentic-LLM-app\backend\data\MedicationGuides_2025_05_19"
CHUNK_SIZE        = 1000
CHUNK_OVERLAP     = 200
BATCH_SIZE        = 10
EMBEDDING_MODEL   = "text-embedding-3-large"
EMBEDDING_DIM     = 3072
RATE_LIMIT_PAUSE  = 1.0

# ─── INIT SERVICES ─────────────────────────────────────────────────────────────

openai_client = OpenAI(api_key=OPENAI_API_KEY)
pinecone = Pinecone(api_key=PINECONE_API_KEY)
spec = ServerlessSpec(cloud="aws", region="us-east-1")

if PINECONE_INDEX not in pinecone.list_indexes().names():
    pinecone.create_index(
        name=PINECONE_INDEX,
        dimension=EMBEDDING_DIM,
        metric="dotproduct",
        spec=spec
    )
index = pinecone.Index(PINECONE_INDEX)
time.sleep(1)

# ─── TABLE FORMATTER ───────────────────────────────────────────────────────────

def format_table_resiliently(table, filename=None, page=None, table_num=None):
    def sanitize(cell):
        return str(cell).replace("\n", " ").strip() if cell else ""

    def log_preview(text):
        if filename and page and table_num:
            #print(f"\n📋 Resilient table preview from '{filename}' p.{page} t.{table_num}:\n")
            #print(text)
            #print("\n" + "─" * 100 + "\n")
            pass

    if not table or len(table) < 1:
        return "(Empty table)"

    max_cols = max(len(row) for row in table)
    padded_table = [row + [""] * (max_cols - len(row)) for row in table]

    if len(padded_table) == 1:
        # Only one row — treat as bullet list
        row = padded_table[0]
        content = "\n".join(f"- {sanitize(cell)}" for cell in row if cell)
        log_preview(content)
        return content

    if max_cols == 1:
        # Single column — render as index + value
        lines = ["Index | Value", "-|-"]
        for i, row in enumerate(padded_table):
            lines.append(f"{i+1} | {sanitize(row[0])}")
        content = "\n".join(lines)
        log_preview(content)
        return content

    # Merge headers if first two rows look like headers
    header_rows = padded_table[:2] if len(padded_table) >= 2 else [padded_table[0]]
    data_rows = padded_table[2:] if len(header_rows) == 2 else padded_table[1:]

    if len(header_rows) == 2:
        headers = [
            f"{sanitize(h1)} ({sanitize(h2)})" if h1 or h2 else f"col_{i}"
            for i, (h1, h2) in enumerate(zip(header_rows[0], header_rows[1]))
        ]
    else:
        headers = [sanitize(h1) if h1 else f"col_{i}" for i, h1 in enumerate(header_rows[0])]

    df = pd.DataFrame(data_rows, columns=headers)

    for col in df.columns:
        df[col] = df[col].map(lambda x: sanitize(x))

    header_line = " | ".join(df.columns)
    sep_line = "-|-".join([""] * len(df.columns))
    body_lines = [
        " | ".join(str(cell) if cell else "" for cell in row)
        for row in df.itertuples(index=False)
    ]

    markdown = "\n".join([header_line, sep_line] + body_lines)
    log_preview(markdown)
    return markdown



# ─── EXTRACT & CHUNK ───────────────────────────────────────────────────────────

def extract_chunks_and_metadata(pdf_path):
    chunks, metas = [], []
    filename = os.path.basename(pdf_path)

    with pdfplumber.open(pdf_path) as pdf:
        for page_i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            tables = page.extract_tables()

            # paragraphs
            paras = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
            for pi, para in enumerate(paras, 1):
                clean = re.sub(r"\s+", " ", para)
                if len(clean.split()) < 30:
                    continue
                chunks.append(clean)
                metas.append({
                    "filename": filename,
                    "page": page_i + 1,
                    "type": "text",
                    "paragraph": pi
                })

            # tables
            for ti, table in enumerate(tables, start=1):
                try:
                    md = format_table_resiliently(table, filename=filename, page=page_i+1, table_num=ti)
                    chunk = f"📊 Table (p.{page_i+1} t.{ti}):\n{md}"
                    chunks.append(chunk)
                    metas.append({
                        "filename": filename,
                        "page": page_i + 1,
                        "type": "table",
                        "table": ti
                    })
                except Exception as e:
                    print(f"⚠️ Skipped bad table on {filename} p.{page_i+1} t.{ti}")
                    print(f"🔍 Table data: {table}")
                    print(f"❌ Error: {e}")

    return chunks, metas

def split_chunk(text, meta):
    words = word_tokenize(text)
    out_chunks, out_metas = [], []
    for i in range(0, len(words), CHUNK_SIZE - CHUNK_OVERLAP):
        chunk = " ".join(words[i:i + CHUNK_SIZE])
        meta_copy = meta.copy()
        meta_copy["split_id"] = i
        out_chunks.append(chunk)
        out_metas.append(meta_copy)
    return out_chunks, out_metas

def normalize_chunks(texts, metas):
    all_chunks, all_metas = [], []
    for text, meta in zip(texts, metas):
        if len(word_tokenize(text)) <= CHUNK_SIZE:
            all_chunks.append(text)
            all_metas.append(meta)
        else:
            chunks, sub_metas = split_chunk(text, meta)
            all_chunks.extend(chunks)
            all_metas.extend(sub_metas)
    return all_chunks, all_metas

# ─── EMBED + UPSERT ───────────────────────────────────────────────────────────

def embed_texts(texts):
    embeddings = []
    for i in tqdm(range(0, len(texts), BATCH_SIZE), desc="Embedding"):
        batch = texts[i:i + BATCH_SIZE]
        try:
            res = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
            batch_embeddings = [record.embedding for record in res.data]
        except Exception as e:
            print(f"⚠️ Embed error: {e}")
            batch_embeddings = [[0.0]*EMBEDDING_DIM] * len(batch)
        embeddings.extend(batch_embeddings)
        time.sleep(RATE_LIMIT_PAUSE)
    return embeddings

def upsert_to_pinecone(vectors, metas, texts):
    items = []
    for i, (vec, meta, text) in enumerate(zip(vectors, metas, texts)):
        vector_id = f"{meta['filename'].replace('.pdf','')}_p{meta.get('page',0)}_{meta.get('type','x')}_{meta.get('paragraph',meta.get('table',0))}_s{meta.get('split_id',0)}"
        clean_meta = {k: v for k, v in meta.items() if k != "text"}
        clean_meta["source_text"] = text  # optionally include short chunks
        items.append((vector_id, vec, clean_meta))

    for i in range(0, len(items), BATCH_SIZE):
        batch = items[i:i + BATCH_SIZE]
        index.upsert(vectors=batch)

# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    all_texts, all_metas = [], []

    pdf_files = [fn for fn in os.listdir(PDF_DIR) if fn.lower().endswith(".pdf")]
    pdf_files = sorted(pdf_files)[:20]  # Take first 20 (sorted for consistency)

    for fn in pdf_files:
        path = os.path.join(PDF_DIR, fn)
        print(f"📄 {fn}")
        c, m = extract_chunks_and_metadata(path)
        all_texts.extend(c)
        all_metas.extend(m)

    print(f"🔎 Extracted {len(all_texts)} raw chunks.")
    final_texts, final_metas = normalize_chunks(all_texts, all_metas)
    print(f"🔗 After splitting: {len(final_texts)} total chunks.")

    vectors = embed_texts(final_texts)
    upsert_to_pinecone(vectors, final_metas, final_texts)

    print("✅ Finished: Embedded and indexed in Pinecone.")
