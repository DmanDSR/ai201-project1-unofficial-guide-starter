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
    (5, "https://news.fiu.edu/2020/fiu-offers-interactive,-digital-financial-literacy-platform-and-financial-wellness-coaches-to-university-community"),
    # The canonical discounts page is JavaScript-rendered (only a short intro is
    # in the HTML), so we also pull the Panther Perks newsroom page, which lists
    # the actual alumni deals. Both are fetched and concatenated into one doc.
    (6, ["https://fiualumni.com/resources/discounts/",
         "https://fiualumni.com/stay-connected/alumni-news/newsroom/index.php/tag/panther-perks/"]),
    (7, "https://transfer.fiu.edu/connect4success/one-card-benefits/"),
    (8, "https://gallo8gym.com/blog/gyms-with-student-discounts-miami"),
    (9, "https://hr.fiu.edu/employees-affiliates/benefits/perks-services/"),
    (10, "https://fiusports.com/news/2024/2/21/general-ticket-smarter-and-fiu-miami-entertainment-guide.aspx"),
    (11, "https://onecard.fiu.edu/card-perks/employee-perks/"),
    (12, "https://libanswers.fiu.edu/faq/18206"),
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
        # A source may be one URL or a list of URLs to merge into one document.
        urls = [url] if isinstance(url, str) else list(url)
        canonical = urls[0]
        filename = f"{doc_id:02d}_{slug_from_url(canonical)}.txt"
        out_path = DOCS_DIR / filename

        parts = []
        for u in urls:
            try:
                resp = requests.get(u, headers=HEADERS, timeout=20)
                resp.raise_for_status()
                parts.append(clean_html(resp.text))
            except Exception as exc:  # noqa: BLE001 - report and keep going
                print(f"[FAILED] #{doc_id:2}  {u}\n         {exc}")

        text = "\n\n".join(p for p in parts if p)
        if text:
            out_path.write_text(text, encoding="utf-8")
        status = "ok" if len(text) >= 200 else ("thin" if text else "FAILED")
        print(f"[{status:4}] #{doc_id:2}  {len(text):6} chars  -> {filename}")

        manifest.append({
            "id": doc_id,
            "filename": filename,
            "url": canonical,
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
