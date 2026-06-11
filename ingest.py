"""Milestone 3 — Document ingestion.

Fetches each web source listed in planning.md, strips the HTML boilerplate
(nav, footer, scripts, etc.), and saves clean plain text into documents/.
Also writes documents/sources.json mapping each .txt file to its source URL,
which Milestone 4 uses to attach source attribution metadata in ChromaDB.

Run:  python ingest.py
"""

import json
import re
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

# The 13 sources from planning.md (id -> URL). Keep this in sync with the
# Documents table so every chunk can be traced back to where it came from.
SOURCES = [
    (1, "https://fiuonline.fiu.edu/about-us/story-hub/student/5-life-hacks-to-save-money-as-a-college-student.php"),
    (2, "https://fiuonline.fiu.edu/about-us/story-hub/student/10-ways-to-slay-your-next-semester-online.php"),
    (3, "https://dasa.fiu.edu/all-departments/student-food-pantry/"),
    (4, "https://www.myunidays.com/US/en-US"),
    (5, "https://fiu.igrad.com/"),
    (6, "https://fiualumni.com/resources/discounts/"),
    (7, "https://transfer.fiu.edu/connect4success/one-card-benefits/"),
    (8, "https://gallo8gym.com/blog/gyms-with-student-discounts-miami"),
    (9, "https://hr.fiu.edu/employees-affiliates/benefits/perks-services/"),
    (10, "https://fiusports.com/news/2024/2/21/general-ticket-smarter-and-fiu-miami-entertainment-guide.aspx"),
    (11, "https://onecard.fiu.edu/card-perks/employee-perks/"),
    (12, "https://fiuonline.my.site.com/canvas/s/article/Software-Resources"),
    (13, "https://panthernow.com/2023/04/10/commuters-here-are-some-fiu-perks-you-should-know-about/"),
]

# Pretend to be a real browser so sites don't reject the request outright.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

DOCS_DIR = Path("documents")
# Tags that hold layout/navigation noise rather than real content.
BOILERPLATE_TAGS = ["script", "style", "noscript", "nav", "header", "footer",
                    "aside", "form", "button", "svg", "iframe"]


def slug_from_url(url: str) -> str:
    """Build a short, filesystem-safe name from a URL's path."""
    path = urlparse(url).path.strip("/")
    last = path.split("/")[-1] if path else urlparse(url).netloc
    last = re.sub(r"\.(php|aspx|html?)$", "", last)      # drop file extensions
    last = re.sub(r"[^a-zA-Z0-9]+", "-", last).strip("-").lower()
    return (last or "page")[:50]


def clean_html(html: str) -> str:
    """Strip boilerplate and return readable plain text."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(BOILERPLATE_TAGS):
        tag.decompose()

    # Prefer the main content region if the page marks one.
    container = soup.find("main") or soup.find("article") or soup.body or soup

    text = container.get_text(separator="\n")
    # Collapse runs of spaces, drop blank lines, and de-duplicate blank gaps.
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


def main() -> None:
    DOCS_DIR.mkdir(exist_ok=True)
    manifest = []

    for doc_id, url in SOURCES:
        filename = f"{doc_id:02d}_{slug_from_url(url)}.txt"
        out_path = DOCS_DIR / filename
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            text = clean_html(resp.text)
            out_path.write_text(text, encoding="utf-8")
            status = "ok" if len(text) >= 200 else "thin"
            print(f"[{status:4}] #{doc_id:2}  {len(text):6} chars  -> {filename}")
        except Exception as exc:  # noqa: BLE001 - report and keep going
            text = ""
            status = "FAILED"
            print(f"[{status}] #{doc_id:2}  {url}\n         {exc}")

        manifest.append({
            "id": doc_id,
            "filename": filename,
            "url": url,
            "status": status,
            "chars": len(text),
        })

    (DOCS_DIR / "sources.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    ok = sum(1 for m in manifest if m["status"] == "ok")
    print(f"\n{ok}/{len(SOURCES)} sources fetched cleanly. "
          f"Manifest written to {DOCS_DIR / 'sources.json'}.")
    thin_or_failed = [m for m in manifest if m["status"] != "ok"]
    if thin_or_failed:
        print("Review these (may need manual copy-paste into their .txt):")
        for m in thin_or_failed:
            print(f"  #{m['id']:2} [{m['status']}] {m['url']}")


if __name__ == "__main__":
    main()
