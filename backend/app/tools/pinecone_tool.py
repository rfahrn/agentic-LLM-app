# pinecone_tool.py

import os
from dotenv import load_dotenv
from openai import OpenAI
from pinecone.grpc import PineconeGRPC as Pinecone
from pinecone import ServerlessSpec
import streamlit as st
# Load environment variables (for API keys)
load_dotenv()

# Configuration
OPENAI_API_KEY = st.secrets.OPENAI.OPENAI_API_KEY
PINECONE_API_KEY = st.secrets.PINECONE.PINECONE_API_KEY
PINECONE_INDEX = "medguides-index"
EMBEDDING_MODEL = "text-embedding-3-large"
GPT_MODEL = "gpt-4o-mini"

# Initialize clients
openai_client = OpenAI(api_key=OPENAI_API_KEY)
pinecone = Pinecone(api_key=PINECONE_API_KEY)
index = pinecone.Index(PINECONE_INDEX)


# ─── Embed Query ─────────────────────────────────────────────────────
def embed_query(query: str):
    res = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=query)
    return res.data[0].embedding


# ─── Context Retrieval ───────────────────────────────────────────────
def retrieve_context(query: str, top_k=8):
    xq = embed_query(query)
    response = index.query(vector=xq, top_k=top_k, include_metadata=True)

    context_blocks = []
    sources = []
    scores = []

    for match in response['matches']:
        meta = match.get("metadata", {})
        text = meta.get("source_text", "").strip()
        if not text:
            continue

        filename = meta.get("filename", "unknown.pdf")
        page = meta.get("page", "?")
        score = round(match.get("score", 0), 2)
        scores.append(score)
        short_filename = filename.split('_TABLET_')[0].replace('_', ' ').title()
        context_blocks.append(f"From **{short_filename}**, page **{page}**:\n{text}")
        sources.append({
            "filename": filename,
            "page": page,
            "score": score,
            "preview": text[:250] + ("..." if len(text) > 250 else "")
        })
    sources = sorted(sources, key=lambda x: x['score'], reverse=True)[:5]

    context = "\n\n---\n\n".join(context_blocks)
    avg_score = round(sum(scores) / len(scores), 2) if scores else 0

    return context, sources, avg_score


# ─── RAG Workflow with GPT + Markdown Answer ─────────────────────────
def search_medguides_with_rag(query: str, top_k=8) -> str:
    context, sources, avg_score = retrieve_context(query, top_k=top_k)

    if not context:
        return "⚠️ Keine passenden Informationen im lokalen PDF-Vektorindex gefunden."

    prompt = f"""Du bist ein pharmazeutischer Assistent. Beantworte die folgende Frage **ausschließlich basierend auf dem untenstehenden Kontext**.
            Antworte in **Markdown**, gegliedert in eine **Zusammenfassung**, eine **Detailanalyse** (Text oder Tabelle), und schließe mit **Quellenangaben** ab. Wenn Tabellen im Kontext enthalten sind, stelle sie als Markdown-Tabelle dar. Zitiere die Quelle jeder Information als (Quelle: DATEI.pdf, S. X).

            ### Kontext:
            {context}

            ### Frage:
            {query}

            ### Antwort:"""

    res = openai_client.chat.completions.create(
        model=GPT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    answer = res.choices[0].message.content.strip()

    citation_block = "\n".join([
        f"- **{s['filename']}**, Seite {s['page']} – Relevanz-Score: `{s['score']}`"
        for s in sources
    ])

    final_md = f"""{answer}

---

### 📊 Quellen & Relevanzbewertung
**Durchschnittlicher Übereinstimmungswert:** `{avg_score}`  
{citation_block}
"""
    return final_md