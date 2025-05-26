import os
import time
from dotenv import load_dotenv
from openai import OpenAI
from pinecone.grpc import PineconeGRPC as Pinecone
from pinecone import ServerlessSpec

# ─── LOAD ENV VARS ────────────────────────────────────────────────────────────
load_dotenv()

OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY  = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX    = "medguides-index"
EMBEDDING_MODEL   = "text-embedding-3-large"
GPT_MODEL         = "gpt-4o-mini"  # or use "gpt-4o-mini" for faster + cheaper

# ─── INIT CLIENTS ─────────────────────────────────────────────────────────────
openai_client = OpenAI(api_key=OPENAI_API_KEY)
pinecone = Pinecone(api_key=PINECONE_API_KEY)
index = pinecone.Index(PINECONE_INDEX)

# ─── EMBEDDING ────────────────────────────────────────────────────────────────
def embed_query(query: str):
    res = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=query)
    return res.data[0].embedding

# ─── QUERY + CONTEXT RETRIEVAL ────────────────────────────────────────────────
def retrieve_context(query: str, top_k=8):
    xq = embed_query(query)
    res = index.query(vector=xq, top_k=top_k, include_metadata=True)

    context_chunks = []
    source_info = []

    for match in res['matches']:
        meta = match['metadata']
        text = meta.get("source_text", "").strip()
        if not text:
            continue

        filename = meta.get("filename", "unknown.pdf")
        page = meta.get("page", "?")
        kind = meta.get("type", "text")
        score = match.get("score", 0)

        source_info.append({
            "filename": filename,
            "page": page,
            "type": kind,
            "score": round(score, 2),
            "preview": text[:300] + ("..." if len(text) > 300 else "")
        })

        context_chunks.append(f"From **{filename}**, page **{page}**:\n{text}")

    return "\n\n---\n\n".join(context_chunks), source_info

# ─── GPT-4o RAG CALL ──────────────────────────────────────────────────────────
def answer_with_rag(query: str, context: str):
    prompt = f"""You are a helpful assistant answering medical queries based only on the provided context.
    Please answer in **Markdown** and include lists or tables when appropriate.
    If the answer is not in the context, say "I don’t know."

    ### Context
    {context}

    ### Question
    {query}

    ### Answer
    """

    res = openai_client.chat.completions.create(
        model=GPT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    return res.choices[0].message.content.strip()

# ─── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    while True:
        query = input("\n💬 Ask a question (or type 'exit'): ").strip()
        if query.lower() in {"exit", "quit"}:
            break

        print("\n🔍 Retrieving context from Pinecone...")
        context, sources = retrieve_context(query)

        print("\n📄 Top context sources:")
        for i, s in enumerate(sources, 1):
            print(f"\n#{i}: {s['filename']} (p.{s['page']}) [{s['type']}] — score: {s['score']}")
            print(f"> {s['preview']}")

        print("\n🤖 Asking GPT-4o...")
        answer = answer_with_rag(query, context)

        print("\n🧠 Answer (Markdown):\n")
        print(answer)
        print("\n" + "=" * 120)