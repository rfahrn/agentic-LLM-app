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


def search_medguides_with_rag(query: str, top_k=8) -> str:
    """
    Embeds a user query, retrieves from Pinecone, and gets a GPT-4o-mini answer.
    Returns a Markdown answer string.
    """
    # Step 1: Embed query
    res = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=query)
    xq = res.data[0].embedding

    # Step 2: Query Pinecone
    response = index.query(vector=xq, top_k=top_k, include_metadata=True)

    # Step 3: Format context
    context_blocks = []
    for match in response['matches']:
        meta = match.get("metadata", {})
        page = meta.get("page", "?")
        filename = meta.get("filename", "unknown.pdf")
        text = meta.get("source_text", "").strip()
        if text:
            context_blocks.append(f"From **{filename}**, page **{page}**:\n{text}")
    context = "\n\n---\n\n".join(context_blocks)

    if not context:
        return "⚠️ Keine passenden Informationen im lokalen PDF-Vektorindex gefunden."

    # Step 4: Prompt GPT
    prompt = f"""You are a helpful medical assistant. Answer the user's question based **only on the context below**.
Use **Markdown** formatting and include lists or tables when appropriate. Do not make up information.

### Context:
{context}

### Question:
{query}

### Answer:"""

    completion = openai_client.chat.completions.create(
        model=GPT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )

    return completion.choices[0].message.content.strip()