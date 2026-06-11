"""Milestone 3 — Chunking.

Splits each ingested document into overlapping chunks for embedding.
Uses a recursive splitter: it tries to break on the largest natural boundary
first (blank line -> line -> sentence -> space -> character), so a chunk stays
on a coherent thought instead of cutting mid-word. Then adjacent pieces are
merged into windows of up to `size` characters, carrying `overlap` characters
from the end of one chunk into the start of the next so a fact that straddles a
boundary isn't lost.

Defaults (from planning.md): size=800, overlap=120.

Run:  python chunk.py        # chunks everything in documents/ and prints stats
"""

import json
from pathlib import Path

DOCS_DIR = Path("documents")
SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


def _split_recursive(text, size, separators):
    """Break text into atomic pieces, each <= size, honoring the separator order."""
    if len(text) <= size:
        return [text]

    # No separators left: hard-split on character count as a last resort.
    if not separators:
        return [text[i:i + size] for i in range(0, len(text), size)]

    sep, rest = separators[0], separators[1:]
    if sep == "":
        return [text[i:i + size] for i in range(0, len(text), size)]
    if sep not in text:
        return _split_recursive(text, size, rest)

    pieces = []
    for part in text.split(sep):
        if not part:
            continue
        if len(part) <= size:
            pieces.append(part)
        else:
            pieces.extend(_split_recursive(part, size, rest))  # recurse smaller
    return pieces


def chunk_text(text, size=800, overlap=120):
    """Return a list of overlapping chunks, each at most `size` characters."""
    text = (text or "").strip()
    if not text:
        return []

    pieces = _split_recursive(text, size, SEPARATORS)

    chunks = []
    current = ""
    for piece in pieces:
        candidate = piece if not current else f"{current} {piece}"
        if len(candidate) <= size:
            current = candidate
            continue

        # Adding this piece would overflow -> close out the current chunk.
        if current:
            chunks.append(current)
            tail = current[-overlap:] if overlap > 0 else ""
            current = f"{tail} {piece}" if tail else piece
            if len(current) > size:        # tail+piece too big -> drop the overlap
                current = piece
        else:
            current = piece                # single oversized piece (already <= size)

    if current:
        chunks.append(current)
    return chunks


def chunk_corpus(size=800, overlap=120):
    """Chunk every .txt in documents/, tagging each chunk with its source URL."""
    sources_path = DOCS_DIR / "sources.json"
    url_by_file = {}
    if sources_path.exists():
        for entry in json.loads(sources_path.read_text(encoding="utf-8")):
            url_by_file[entry["filename"]] = entry["url"]

    records = []
    for txt_path in sorted(DOCS_DIR.glob("*.txt")):
        text = txt_path.read_text(encoding="utf-8")
        for i, chunk in enumerate(chunk_text(text, size, overlap)):
            records.append({
                "source_file": txt_path.name,
                "source_url": url_by_file.get(txt_path.name, "unknown"),
                "chunk_index": i,
                "text": chunk,
            })
    return records


def _report(records, size):
    """Print stats and confirm the chunking constraints hold."""
    if not records:
        print("No chunks produced — documents/ has no readable .txt files yet.")
        print("Run `python ingest.py` on a machine with internet access first.")
        return

    lengths = [len(r["text"]) for r in records]
    files = {r["source_file"] for r in records}
    print(f"Documents chunked : {len(files)}")
    print(f"Total chunks      : {len(records)}")
    print(f"Chunk length      : min {min(lengths)}, avg {sum(lengths)//len(lengths)}, max {max(lengths)}")
    print(f"All chunks <= {size}: {all(n <= size for n in lengths)}")


if __name__ == "__main__":
    SIZE, OVERLAP = 800, 120
    records = chunk_corpus(SIZE, OVERLAP)
    _report(records, SIZE)
