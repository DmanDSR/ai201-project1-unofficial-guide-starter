"""Milestone 4 — Retrieval.

Embeds a user query with the SAME model used to build the index, then asks
ChromaDB for the top-k most similar chunks. Returns each chunk's text and its
source URL so Milestone 5 can ground its answer and cite sources.

Run:  python retrieve.py      # runs the 5 evaluation questions and prints hits
"""

import os
import sys

# The MiniLM model is cached after the first embed.py run, so don't let the
# HuggingFace client make flaky network calls to check for updates at query time.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from embed import get_collection, get_model

# FIU pages contain curly quotes / arrows; force UTF-8 so printing them on a
# Windows console (default cp1252) doesn't crash.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Maps each evaluation question to the source # we expect it to retrieve
# (from the Evaluation Plan table in planning.md). Used only for verification.
EVAL_QUESTIONS = [
    ("does FIU have any resources to help students with personal finance?", 5),
    ("where can I find the free software provided to students?", 12),
    ("what discounts are there for alumni?", 6),
    ("what are the FIU One Card benefits?", 7),
    ("how does FIU help car owners?", 13),
]


def retrieve(query, k=4, max_per_source=2):
    """Return the top-k chunks for a query as a list of dicts.

    To keep results diverse, no single source document contributes more than
    `max_per_source` chunks. (One of our sources — the HR perks directory — is
    ~70% of the index, so without this cap it can fill every slot and bury
    smaller, more specific sources.) We over-fetch candidates, then take the
    most similar ones that respect the cap.
    """
    query_embedding = get_model().encode(
        [query], normalize_embeddings=True
    ).tolist()
    res = get_collection().query(
        query_embeddings=query_embedding, n_results=max(k * 5, 20)
    )

    hits = []
    per_source = {}
    for doc, meta, dist in zip(
        res["documents"][0], res["metadatas"][0], res["distances"][0]
    ):
        src = meta["source_file"]
        if per_source.get(src, 0) >= max_per_source:
            continue
        per_source[src] = per_source.get(src, 0) + 1
        hits.append({
            "text": doc,
            "source_file": src,
            "source_url": meta["source_url"],
            "similarity": round(1 - dist, 3),   # cosine distance -> similarity
        })
        if len(hits) >= k:
            break
    return hits


def _verify():
    """Run each eval question and report whether its expected source was retrieved."""
    passed = 0
    for question, expected_src in EVAL_QUESTIONS:
        hits = retrieve(question, k=4)
        # source_file starts with the zero-padded source id, e.g. "05_..."
        retrieved_ids = [int(h["source_file"].split("_")[0]) for h in hits]
        ok = expected_src in retrieved_ids
        passed += ok
        print(f"\nQ: {question}")
        print(f"   expected source #{expected_src} | retrieved {retrieved_ids} "
              f"-> {'PASS' if ok else 'MISS'}")
        for h in hits:
            print(f"     [{h['similarity']:.3f}] {h['source_file']}  "
                  f"{h['text'][:80].strip()}...")
    print(f"\n{passed}/{len(EVAL_QUESTIONS)} questions retrieved their expected source.")


if __name__ == "__main__":
    _verify()
