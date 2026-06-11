"""Milestone 4 — Embedding + vector store.

Embeds every chunk from chunk.py with all-MiniLM-L6-v2 and stores the vectors
in a persistent ChromaDB collection. Each vector keeps its source URL as
metadata so retrieval can cite where an answer came from.

The index persists to ./chroma_db, so you only embed once — later runs (and the
query interface in Milestone 5) just open the existing collection.

Run:  python embed.py        # builds/rebuilds the index from documents/
"""

from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

from chunk import chunk_corpus

MODEL_NAME = "all-MiniLM-L6-v2"
CHROMA_DIR = "chroma_db"
COLLECTION = "fiu_perks"

# Loaded lazily so importing this module (e.g. from retrieve.py) is cheap.
_model = None


def get_model():
    """Return the shared embedding model, loading it on first use."""
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def get_client():
    return chromadb.PersistentClient(path=CHROMA_DIR)


def get_collection():
    """Open the existing collection (cosine distance to match normalized vectors)."""
    return get_client().get_or_create_collection(
        name=COLLECTION, metadata={"hnsw:space": "cosine"}
    )


def build_index(size=800, overlap=120):
    """Chunk documents/, embed every chunk, and (re)load them into ChromaDB."""
    records = chunk_corpus(size=size, overlap=overlap)
    if not records:
        raise SystemExit("No chunks found — run `python ingest.py` then `python chunk.py` first.")

    client = get_client()
    # Start clean so re-running doesn't pile up duplicate vectors.
    if COLLECTION in [c.name for c in client.list_collections()]:
        client.delete_collection(COLLECTION)
    collection = client.create_collection(
        name=COLLECTION, metadata={"hnsw:space": "cosine"}
    )

    texts = [r["text"] for r in records]
    ids = [f"{r['source_file']}::{r['chunk_index']}" for r in records]
    metadatas = [
        {
            "source_file": r["source_file"],
            "source_url": r["source_url"],
            "chunk_index": r["chunk_index"],
        }
        for r in records
    ]

    print(f"Embedding {len(texts)} chunks with {MODEL_NAME} ...")
    embeddings = get_model().encode(
        texts, normalize_embeddings=True, show_progress_bar=True
    ).tolist()

    collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
    print(f"Stored {collection.count()} vectors in '{COLLECTION}' "
          f"(persisted to {Path(CHROMA_DIR).resolve()}).")


if __name__ == "__main__":
    build_index()
