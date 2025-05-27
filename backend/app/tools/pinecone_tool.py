# pinecone_tool.py

import os
from dotenv import load_dotenv
from openai import OpenAI
from pinecone.grpc import PineconeGRPC as Pinecone
from pinecone import ServerlessSpec
import streamlit as st
import base64
from io import BytesIO
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
# ─── Extract Follow-Up Questions ──────────────────────────────────────
import re

def extract_follow_up_questions(answer: str) -> list:
    pattern = r"(?:\*\*|\#\#\#?)?\s*(?:Frage|Follow[-\s]?up)?[:\-]?\s*(.*?\?)"
    matches = re.findall(pattern, answer, re.IGNORECASE)
    return [q.strip() for q in matches if len(q.strip()) > 10]

# ─── Get PDF Page as Base64 Image ────────────────────────────────────

def get_pdf_page_as_base64_image(filename: str, page_num: int):
    import fitz 
    try:
        page_num = int(float(page_num)) - 1  # fitz is 0-indexed
        fixed_dir = r"C:\Users\FahRe\Desktop\agentic-LLM-app\backend\data\MedicationGuides_2025_05_19_FIXED"
        pdf_path = os.path.join(fixed_dir, filename)

        doc = fitz.open(pdf_path)
        if page_num < 0 or page_num >= len(doc):
            return f"⚠️ Seite {page_num+1} existiert nicht (PDF hat {len(doc)} Seiten)."

        page = doc[page_num]
        pix = page.get_pixmap(dpi=150)
        buffered = BytesIO(pix.tobytes("png"))
        img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return f"<img src='data:image/png;base64,{img_base64}' width='700'/>"

    except Exception as e:
        return f"⚠️ Fehler beim Generieren der Seitenvorschau ({filename}, S. {page_num+1}): {e}"

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
# ─── Answer Follow-Up Question ───────────────────────────────────────

def answer_follow_up_question(follow_up: str, top_k=4):
    context, sources, _ = retrieve_context(follow_up, top_k=top_k)

    if not context:
        return f"- **{follow_up}**\n  ⚠️ Keine Informationen gefunden.", None

    prompt = f"""
    Du bist ein pharmazeutischer Assistent. Beantworte die folgende **Zusatzfrage** **nur basierend auf dem untenstehenden Kontext**.

    Gib eine **kurze Antwort** mit Seitenangabe. Keine ausführliche Analyse.

    Kontext:
    {context}

    Zusatzfrage:
    {follow_up}

    Format:
    - **Kurzantwort**: {{Antwort}}
    - **Gefundene Stelle**: (Quelle: DATEI.pdf, S. X)
    """

    try:
        res = openai_client.chat.completions.create(
            model=GPT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        response_text = res.choices[0].message.content.strip()
        return f"- **{follow_up}**\n  {response_text}", sources
    except Exception as e:
        return f"- **{follow_up}**\n  ⚠️ Fehler: {e}", None



# ─── RAG Workflow with GPT + Markdown Answer ─────────────────────────
def search_medguides_with_rag(query: str, top_k=8, include_followups=True) -> str:
    context, sources, avg_score = retrieve_context(query, top_k=top_k)

    if not context:
        return "⚠️ Keine passenden Informationen im lokalen PDF-Vektorindex gefunden."

    prompt = f"""
    Du bist ein pharmazeutischer Assistent. Deine Aufgabe ist es, die folgende Frage **ausschließlich basierend auf dem untenstehenden Kontext** zu beantworten.

    Arbeite strukturiert nach folgendem Ablauf:

    ---

    ### 1. **Frageprüfung und Optimierung**

    - Überprüfe die Frage auf:
    - Unklarheiten oder fehlende Präzision
    - Rechtschreib- oder Grammatikfehler
    - Allgemeinheit oder undeutliche Begriffe

    - Wenn nötig:
    - **Formuliere die Frage neu**
    - **Korrigiere Schreibfehler**
    - Gib an:
        - **Ursprüngliche Frage**
        - **Überarbeitete Frage**
        - **Kurze Begründung**, warum die Umformulierung vorgenommen wurde (z. B. zu allgemein, missverständlich, nicht fachlich genug etc.)

    - Formuliere **bis zu drei sinnvolle Folgefragen**, die sich logisch aus dem Thema ergeben könnten.

    ---

    ### 2. **Antwort (im Format Markdown)**

    #### 🟢 Zusammenfassung  
    Gib einen klaren Überblick über die zentrale Erkenntnis.

    #### 🧪 Detailanalyse  
    Geh fachlich in die Tiefe. Falls Tabellen im Kontext vorhanden sind, stelle sie als **Markdown-Tabelle** dar.

    #### 📚 Quellenangaben  
    Zitiere jede verwendete Information im Format:  
    `(Quelle: DATEI.pdf, S. X)`

    ---

    ### 3. **Behandlung der Folgefragen** (sofern möglich)

    - Gehe auf die zuvor genannten Folgefragen kurz ein.
    - Falls eine fundierte Antwort möglich ist, **nenne nur die relevante Textstelle oder Seitenangabe**, ohne vollständige Analyse.
    - Falls keine ausreichende Information vorhanden ist, sage dies deutlich.

    ---

    Wenn der Kontext **nicht ausreicht**, um die Hauptfrage zu beantworten, erkläre dies und **vermeide Spekulationen**.

    ---

    ### Kontext:
    {context}

    ### Ursprüngliche Frage:
    {query}

    ---

    ### Antwort:
    """

    res = openai_client.chat.completions.create(
        model=GPT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    answer = res.choices[0].message.content.strip()
    # Extract follow-up questions
    follow_up_md = ""
    follow_up_sources = []

    if include_followups:
        follow_ups = extract_follow_up_questions(answer)
        if follow_ups:
            follow_up_md += "\n\n---\n\n### 🔄 Folgefragen (Hinweisantworten)\n"
            for i, fq in enumerate(follow_ups[:3], 1):
                fq_answer, fq_sources = answer_follow_up_question(fq)
                follow_up_md += f"\n**{i}.** {fq_answer}\n"
                if fq_sources:
                    follow_up_sources.extend(fq_sources)
    citation_block = "\n".join([
        f"- **{s['filename']}**, Seite {s['page']} – Relevanz-Score: `{s['score']}`"
        for s in sources
    ])
    # Combine all sources for citation block
    all_sources = sources + follow_up_sources
    unique_sources = {(s['filename'], s['page']): s for s in all_sources}.values()
    citation_block = "\n".join([
        f"- **{s['filename']}**, Seite {s['page']} – Relevanz-Score: `{s['score']}`"
        for s in sorted(unique_sources, key=lambda x: x['score'], reverse=True)
    ])


    final_md = f"""{answer}
    {follow_up_md}
---

### 📊 Quellen & Relevanzbewertung
**Durchschnittlicher Übereinstimmungswert:** `{avg_score}`  
{citation_block}
"""
    return final_md, sources