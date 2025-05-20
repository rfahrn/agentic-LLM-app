import os
import re
import pdfplumber
import pickle
import numpy as np
import pandas as pd
import openai
import faiss
import time
from tqdm import tqdm
from nltk.tokenize import word_tokenize

# CONFIG
openai.api_key = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIM = 3072
INDEX_PATH = "your_path/faiss_index.idx"
METADATA_PATH = "your_path/faiss_metadata.pkl"
CHUNKS_PATH = "your_path/faiss_chunks.pkl"
EMBEDDINGS_PATH = "your_path/faiss_embeddings.pkl"

# Replace 'your_path' with the actual shared directory like:
# C:/Users/FahRe/Desktop/agentic-LLM-app/backend/data/

# ----------- UTILITIES (reuse your logic) ------------ #

def format_table_as_markdown(table):
    df = pd.DataFrame(table[1:], columns=table[0])
    for col in df.columns:
        df[col] = df[col].map(lambda x: str(x).replace('\n', ' ').strip() if pd.notnull(x) else "")
    lines = [" | ".join(df.columns), "-" * len(" | ".join(df.columns))]
    for _, row in df.iterrows():
        lines.append(" | ".join(map(str, row)))
    return "\n".join(lines)

def extract_sections_and_tables(pdf_path):
    chunks, metadata = [], []
    filename = os.path.basename(pdf_path)
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            tables = page.extract_tables()
            sections = re.split(r'\n(?=[A-Z\d][A-Z\d\s\-\(\)\.]{5,})', text)
            for section in sections:
                cleaned = re.sub(r'\s+', ' ', section.strip())
                if len(cleaned) > 50:
                    chunks.append(cleaned)
                    metadata.append({"file": filename, "page": page_num + 1, "type": "text"})
            for table in tables:
                try:
                    table_text = format_table_as_markdown(table)
                    chunks.append(f"📊 Table (Page {page_num+1}):\n{table_text}")
                    metadata.append({"file": filename, "page": page_num + 1, "type": "table"})
                except:
                    pass
    return chunks, metadata

def chunk_long_text(text, meta, max_tokens=700, overlap=100):
    words = word_tokenize(text)
    chunks, metas = [], []
    i = 0
    while i < len(words):
        chunk_words = words[i:i+max_tokens]
        chunks.append(" ".join(chunk_words))
        metas.append(meta)
        i += max_tokens - overlap
    return chunks, metas

def clean_and_split_chunks(raw_chunks, raw_metadata):
    all_chunks, all_meta = [], []
    for chunk, meta in zip(raw_chunks, raw_metadata):
        if len(word_tokenize(chunk)) <= 700:
            all_chunks.append(chunk)
            all_meta.append(meta)
        else:
            sub_chunks, sub_metas = chunk_long_text(chunk, meta)
            all_chunks.extend(sub_chunks)
            all_meta.extend(sub_metas)
    return all_chunks, all_meta

def get_openai_embeddings(texts, model=EMBEDDING_MODEL):
    embeddings = []
    batch_size = 10
    for i in tqdm(range(0, len(texts), batch_size), desc="🔗 Embedding"):
        batch = texts[i:i+batch_size]
        try:
            response = openai.embeddings.create(input=batch, model=model)
            batch_embeddings = [r.embedding for r in response.data]
            embeddings.extend(batch_embeddings)
        except Exception as e:
            print(f"⚠️ Embedding batch failed: {e}")
            embeddings.extend([[0.0] * EMBEDDING_DIM] * len(batch))
        time.sleep(1)
    return np.array(embeddings).astype("float32")

# ------------- MAIN FUNCTION ---------------- #

def add_new_pdf(pdf_path):
    print(f"📥 Loading PDF: {pdf_path}")
    raw_chunks, raw_metadata = extract_sections_and_tables(pdf_path)
    chunks, metadata = clean_and_split_chunks(raw_chunks, raw_metadata)
    print(f"🔍 New Chunks: {len(chunks)}")

    # Step 1: Embed new chunks
    new_embeddings = get_openai_embeddings(chunks)

    # Step 2: Load existing FAISS index
    index = faiss.read_index(INDEX_PATH)
    index.add(new_embeddings)
    faiss.write_index(index, INDEX_PATH)
    print(f"✅ Added {len(new_embeddings)} embeddings to FAISS index.")

    # Step 3: Append metadata and chunks to existing pickles
    with open(METADATA_PATH, "rb") as f: old_metadata = pickle.load(f)
    with open(CHUNKS_PATH, "rb") as f: old_chunks = pickle.load(f)
    with open(EMBEDDINGS_PATH, "rb") as f: old_embeds = pickle.load(f)

    updated_metadata = old_metadata + metadata
    updated_chunks = old_chunks + chunks
    updated_embeds = np.vstack([old_embeds, new_embeddings])

    with open(METADATA_PATH, "wb") as f: pickle.dump(updated_metadata, f)
    with open(CHUNKS_PATH, "wb") as f: pickle.dump(updated_chunks, f)
    with open(EMBEDDINGS_PATH, "wb") as f: pickle.dump(updated_embeds, f)

    print("📦 Metadata, chunks, and embeddings updated.")

# ------------------ RUN --------------------- #
if __name__ == "__main__":
    PDF_PATH = r"your_path/new_pdf_file.pdf"  # 👈 Replace with new file
    add_new_pdf(PDF_PATH)
