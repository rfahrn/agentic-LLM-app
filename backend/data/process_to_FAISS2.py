import os
import re
import time
import pickle
import pdfplumber
import numpy as np
import pandas as pd
import faiss
import openai
from nltk.tokenize import word_tokenize
from tqdm import tqdm

# ─── USER CONFIGURATION ────────────────────────────────────────────────────────

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PDF_DIR        = r"C:\Users\FahRe\Desktop\agentic-LLM-app\backend\data\MedicationGuides_2025_05_19"
OUTPUT_DIR     = r"C:\Users\FahRe\Desktop\agentic-LLM-app\backend\data\faiss_new"
EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIM   = 3072
MAX_TOKENS      = 1000
OVERLAP_TOKENS  = 200
BATCH_SIZE      = 10
OPENAI_RATE_PAUSE = 1.0  # seconds between batches

# ─── SETUP ─────────────────────────────────────────────────────────────────────
openai.api_key = OPENAI_API_KEY
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─── TABLE FORMATTER ───────────────────────────────────────────────────────────
def format_table_as_markdown(table):
    df = pd.DataFrame(table[1:], columns=table[0])
    # flatten newlines
    df = df.applymap(lambda x: str(x).replace("\n", " ").strip() if pd.notnull(x) else "")
    headers = " | ".join(df.columns)
    sep     = "-|-".join(["" for _ in df.columns])
    lines   = [headers, sep]
    for row in df.itertuples(index=False):
        lines.append(" | ".join(map(str, row)))
    return "\n".join(lines)

# ─── EXTRACTION ────────────────────────────────────────────────────────────────
def extract_chunks_and_metadata(pdf_path):
    """
    Returns:
      chunks   : list[str]
      metadata : list[dict]  (same length as chunks)
    """
    chunks , metas = [], []
    filename = os.path.basename(pdf_path)

    with pdfplumber.open(pdf_path) as pdf:
        for page_i, page in enumerate(pdf.pages):
            text   = page.extract_text() or ""
            tables = page.extract_tables()

            # split into paragraphs by 2+ newlines
            paras = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
            for pi, para in enumerate(paras, start=1):
                clean = re.sub(r"\s+", " ", para)
                if len(clean) < 50:
                    continue
                chunks.append(clean)
                metas.append({
                    "source_pdf": filename,
                    "pdf_path":   pdf_path,
                    "page":       page_i + 1,
                    "paragraph":  pi,
                    "type":       "text"
                })

            # each table
            for ti, table in enumerate(tables, start=1):
                try:
                    md = format_table_as_markdown(table)
                    chunk = f"📊 Table (p.{page_i+1} t.{ti}):\n{md}"
                    chunks.append(chunk)
                    metas.append({
                        "source_pdf": filename,
                        "pdf_path":   pdf_path,
                        "page":       page_i + 1,
                        "table":      ti,
                        "type":       "table"
                    })
                except Exception as e:
                    print(f"⚠️ Skipped bad table on {filename} p.{page_i+1}: {e}")
    return chunks, metas

# ─── CHUNK SPLITTING ───────────────────────────────────────────────────────────
def split_long_chunk(text, meta, max_tokens=MAX_TOKENS, overlap=OVERLAP_TOKENS):
    words = word_tokenize(text)
    out_chunks, out_metas = [], []
    i = 0
    while i < len(words):
        window = words[i : i + max_tokens]
        txt    = " ".join(window)
        out_chunks.append(txt)
        out_metas.append(meta.copy())
        i += max_tokens - overlap
    return out_chunks, out_metas

def normalize_chunks(raw_chunks, raw_metas):
    final_chunks, final_metas = [], []
    for txt, md in zip(raw_chunks, raw_metas):
        if len(word_tokenize(txt)) <= MAX_TOKENS:
            final_chunks.append(txt)
            final_metas.append(md)
        else:
            sc, sm = split_long_chunk(txt, md)
            final_chunks.extend(sc)
            final_metas.extend(sm)
    return final_chunks, final_metas

# ─── EMBEDDING ─────────────────────────────────────────────────────────────────
def embed_texts(texts, model=EMBEDDING_MODEL):
    all_embeds = []
    for i in tqdm(range(0, len(texts), BATCH_SIZE), desc="Embedding"):
        batch = texts[i : i + BATCH_SIZE]
        try:
            resp = openai.embeddings.create(model=model, input=batch)
            embeds = [d.embedding for d in resp.data]
        except Exception as e:
            print(f"⚠️ Embed error: {e}")
            embeds = [[0.0]*EMBEDDING_DIM]*len(batch)
        all_embeds.extend(embeds)
        time.sleep(OPENAI_RATE_PAUSE)
    return np.array(all_embeds, dtype="float32")

# ─── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # 1) extract + split
    raw_chunks, raw_meta = [], []
    for fn in os.listdir(PDF_DIR):
        if fn.lower().endswith(".pdf"):
            path = os.path.join(PDF_DIR, fn)
            print(f"📄 {fn}")
            c, m = extract_chunks_and_metadata(path)
            raw_chunks += c
            raw_meta   += m

    print(f"🔎 Extracted {len(raw_chunks)} raw chunks.")
    chunks, metas = normalize_chunks(raw_chunks, raw_meta)
    print(f"🔗 After splitting, {len(chunks)} total chunks.")

    # 2) embed
    embeddings = embed_texts(chunks)
    print(f"🧮 Embeddings shape: {embeddings.shape}")

    # 3) build FAISS
    dim   = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)
    print(f"✅ FAISS index built with {index.ntotal} vectors.")

    # 4) persist all artifacts
    with open(os.path.join(OUTPUT_DIR, "faiss_chunks.pkl"),   "wb") as f: pickle.dump(chunks, f)
    with open(os.path.join(OUTPUT_DIR, "faiss_metadata.pkl"), "wb") as f: pickle.dump(metas, f)
    # save embeddings in numpy format for easy loading/analysis:
    np.save(os.path.join(OUTPUT_DIR, "faiss_embeddings.npy"), embeddings)
    faiss.write_index(index, os.path.join(OUTPUT_DIR, "faiss_index.idx"))

    print(f"🎉 Wrote all files to {OUTPUT_DIR}")
