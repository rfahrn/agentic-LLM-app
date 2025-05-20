import pickle
import numpy as np
import chromadb
from chromadb.config import Settings

# Load FAISS-based files
with open("faiss_chunks.pkl", "rb") as f:
    chunks = pickle.load(f)

with open("faiss_metadata.pkl", "rb") as f:
    metadata = pickle.load(f)

with open("faiss_embeddings.pkl", "rb") as f:
    embeddings = pickle.load(f)

# Sanity check
assert len(chunks) == len(metadata) == len(embeddings)

# Setup ChromaDB client
chroma_client = chromadb.Client(Settings(
    persist_directory="chroma_db",  # Where it stores data
    anonymized_telemetry=False
))

# Create (or get) collection
collection = chroma_client.get_or_create_collection(name="med_guides")

# Prepare document IDs (must be unique strings)
ids = [f"{meta['file']}_{i}" for i, meta in enumerate(metadata)]

# Add all data to Chroma
collection.add(
    documents=chunks,
    embeddings=embeddings.tolist(),  # Chroma expects lists, not np.array
    metadatas=metadata,
    ids=ids
)

print(f"✅ Successfully migrated {len(chunks)} documents to Chroma!")

# query example
#results = collection.query(
#    query_texts=["What is the dosage for ibuprofen?"],
#    n_results=5
#)

#for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
#    print(f"📄 Match: {doc}\n🧾 Metadata: {meta}\n")