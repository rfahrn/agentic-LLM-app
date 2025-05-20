import os
import re
import pdfplumber
import pandas as pd
from nltk.tokenize import sent_tokenize
import numpy as np
import openai
import faiss
import time
from tqdm import tqdm
from nltk.tokenize import sent_tokenize, word_tokenize

openai.api_key = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIM = 3072  # this is correct for "text-embedding-3-large"

# ----------------------------- #
#       TABLE FORMATTER        #
# ----------------------------- #
def format_table_as_markdown(table):
    df = pd.DataFrame(table[1:], columns=table[0])
    for col in df.columns:
        df[col] = df[col].map(lambda x: str(x).replace('\n', ' ').strip() if pd.notnull(x) else "")
    
    lines = []
    headers = " | ".join(map(str, df.columns))
    lines.append(headers)
    lines.append("-" * len(headers))

    for _, row in df.iterrows():
        lines.append(" | ".join(map(str, row)))
    return "\n".join(lines)

# ----------------------------- #
#   TEXT + TABLE PER PAGE       #
# ----------------------------- #
def extract_sections_and_tables(pdf_path):
    chunks = []
    metadata = []
    filename = os.path.basename(pdf_path)

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            tables = page.extract_tables()

            # SECTION SPLIT: based on ALL-CAPS or numbered headers
            sections = re.split(r'\n(?=[A-Z\d][A-Z\d\s\-\(\)\.]{5,})', text)
            for section in sections:
                cleaned = re.sub(r'\s+', ' ', section.strip())
                if len(cleaned) > 50:
                    chunks.append(cleaned)
                    metadata.append({
                        "file": filename,
                        "page": page_num + 1,
                        "type": "text",
                        "section": None  # optionally extract heading from section[:50]
                    })

            # TABLES: standalone chunks
            for table in tables:
                try:
                    table_text = format_table_as_markdown(table)
                    chunks.append(f"📊 Table (Page {page_num+1}):\n{table_text}")
                    metadata.append({
                        "file": filename,
                        "page": page_num + 1,
                        "type": "table",
                        "section": None
                    })
                except Exception as e:
                    print(f"⚠️ Skipped malformed table on page {page_num+1}: {e}")

    return chunks, metadata

# ----------------------------- #
#         CHUNK CLEANER         #
# ----------------------------- #
def chunk_long_text(text, meta, max_tokens=700, overlap=100):
    words = word_tokenize(text)
    chunks = []
    metas = []

    i = 0
    while i < len(words):
        chunk_words = words[i:i+max_tokens]
        chunk_text = " ".join(chunk_words)
        chunks.append(chunk_text)
        metas.append(meta)
        i += max_tokens - overlap
    return chunks, metas

def clean_and_split_chunks(raw_chunks, raw_metadata):
    all_chunks = []
    all_meta = []

    for chunk, meta in zip(raw_chunks, raw_metadata):
        if len(word_tokenize(chunk)) <= 700:
            all_chunks.append(chunk)
            all_meta.append(meta)
        else:
            sub_chunks, sub_metas = chunk_long_text(chunk, meta)
            all_chunks.extend(sub_chunks)
            all_meta.extend(sub_metas)

    return all_chunks, all_meta


# ----------------------------- #
#       EMBEDDING GENERATOR     #
# ----------------------------- #
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
        time.sleep(1)  # stay below rate limit
    return np.array(embeddings).astype("float32")

# ----------------------------- #
#            MAIN               #
# ----------------------------- #
def process_pdf_folder(pdf_dir):
    all_chunks = []
    all_meta = []

    for filename in os.listdir(pdf_dir):
        if filename.lower().endswith(".pdf"):
            pdf_path = os.path.join(pdf_dir, filename)
            print(f"📄 Processing: {filename}")
            chunks, metas = extract_sections_and_tables(pdf_path)
            sub_chunks, sub_metas = clean_and_split_chunks(chunks, metas)
            all_chunks.extend(sub_chunks)
            all_meta.extend(sub_metas)

    return all_chunks, all_meta


if __name__ == "__main__":
    PDF_DIR = r"C:\Users\FahRe\Desktop\agentic-LLM-app\backend\data\MedicationGuides_2025_05_19"
    print(f"📁 Loading PDFs from: {PDF_DIR}")
    chunks, metadata = process_pdf_folder(PDF_DIR)
    print(f"🔎 Total chunks: {len(chunks)}")
    embeddings = get_openai_embeddings(chunks)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)
    print(f"✅ FAISS index created with {index.ntotal} entries.")
    import pickle
    with open(r"C:\Users\FahRe\Desktop\agentic-LLM-app\backend\data\faiss_metadata.pkl", "wb") as f:
        pickle.dump(metadata, f)
    with open(r"C:\Users\FahRe\Desktop\agentic-LLM-app\backend\data\faiss_embeddings.pkl", "wb") as f:
        pickle.dump(embeddings, f)
    with open(r"C:\Users\FahRe\Desktop\agentic-LLM-app\backend\data\faiss_chunks.pkl", "wb") as f:
        pickle.dump(chunks, f)

    faiss.write_index(index, r"C:\Users\FahRe\Desktop\agentic-LLM-app\backend\data\faiss_index.idx")
        #index, model, _ = create_faiss_index(chunks)
    #search_query(index, model, metadata, query="What is the dosage for ABILIFY®  (aripiprazole) Tablets on patients with Schizophrenia ?")

