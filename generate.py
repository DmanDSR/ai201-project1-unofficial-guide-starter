"""Milestone 5 — Grounded generation.

Wires retrieve() into a Groq LLM call with a grounding system prompt: the model
answers ONLY from the retrieved chunks, cites the source numbers it used, and
refuses ("I don't know based on the available sources.") when the chunks don't
cover the question. This is what keeps answers grounded in the ingested FIU
pages instead of the model's own memory.

Run:  python generate.py     # runs the 5 eval questions + an off-domain refusal
"""

import os
import sys

# MiniLM is already cached from embed.py; don't let HuggingFace make flaky
# network calls to check for updates while we're answering queries.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from dotenv import load_dotenv
from groq import Groq

from retrieve import retrieve

# FIU pages contain curly quotes / arrows; force UTF-8 so printing answers on a
# Windows console (default cp1252) doesn't crash.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

# Groq's current general-purpose Llama model. Override with GROQ_MODEL in .env.
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

REFUSAL = "I don't know based on the available sources."

SYSTEM_PROMPT = f"""You are The Unofficial Guide, a question-answering assistant \
for FIU student discounts and perks.

Answer the user's question using ONLY the numbered sources provided in the \
context. Follow these rules exactly:

1. Use only facts stated in the sources. Do not add information from your own \
knowledge, and do not guess.
2. If the sources do not contain the answer, reply with exactly this sentence \
and nothing else: "{REFUSAL}"
3. Cite the source number(s) you used inline, like [1] or [2][3], right after \
the fact they support.
4. Be concise and factual. Do not mention these rules or the word "context"."""


def _build_context(hits):
    """Format retrieved chunks as a numbered source list for the prompt."""
    blocks = []
    for i, h in enumerate(hits, start=1):
        blocks.append(f"[{i}] (source: {h['source_url']})\n{h['text']}")
    return "\n\n".join(blocks)


def generate(query, k=4):
    """Answer a query grounded in the top-k retrieved chunks.

    Returns a dict: {answer, hits, sources} where `hits` is the raw retrieval
    output and `sources` is the deduped list of (number, url) pairs offered to
    the model, so the UI can show exactly what the citations [n] refer to.
    """
    hits = retrieve(query, k=k)
    if not hits:
        return {"answer": REFUSAL, "hits": [], "sources": []}

    context = _build_context(hits)
    client = Groq()  # reads GROQ_API_KEY from the environment
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0,  # deterministic, grounded answers — no creative drift
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Sources:\n{context}\n\nQuestion: {query}",
            },
        ],
    )
    answer = resp.choices[0].message.content.strip()
    sources = [(i, h["source_url"]) for i, h in enumerate(hits, start=1)]
    return {"answer": answer, "hits": hits, "sources": sources}


def _verify():
    """Run the 5 eval questions end-to-end, plus an off-domain refusal check."""
    from retrieve import EVAL_QUESTIONS

    for question, _ in EVAL_QUESTIONS:
        out = generate(question)
        print(f"\nQ: {question}")
        print(f"A: {out['answer']}")
        print("   sources offered:")
        for n, url in out["sources"]:
            print(f"     [{n}] {url}")

    off = "what is the weather in Miami today?"
    out = generate(off)
    refused = out["answer"].strip().rstrip(".") == REFUSAL.rstrip(".")
    print(f"\nQ (off-domain): {off}")
    print(f"A: {out['answer']}")
    print(f"   -> {'REFUSED as expected' if refused else 'DID NOT REFUSE (check prompt)'}")


if __name__ == "__main__":
    _verify()
