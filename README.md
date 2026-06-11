# The Unofficial Guide — Project 1

A Retrieval-Augmented Generation (RAG) system that answers questions about FIU
student discounts and perks using only knowledge scraped from real FIU web
pages, so every answer is grounded in documents and cites where it came from.

**Pipeline:** Ingestion (`requests` + `beautifulsoup4`) → Chunking (custom
recursive splitter) → Embedding + Vector Store (`all-MiniLM-L6-v2` +
`chromadb`) → Retrieval (top-k + diversity cap) → Generation (Groq +
grounding prompt, Gradio UI).

### Setup (first time only)

All commands are run from the project root in **PowerShell** on Windows.

```powershell
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1
#    (if activation is blocked, run once:
#     Set-ExecutionPolicy -Scope CurrentUser RemoteSigned)

# 2. Install dependencies
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 3. Add your Groq API key
#    Copy the example file, then open .env and paste your key.
#    Get a free key (no credit card) at https://console.groq.com
Copy-Item .env.example .env
```

After copying, `.env` should contain one line: `GROQ_API_KEY=gsk_...your_key...`

### Build the index (first time, or after changing sources)

```powershell
.venv\Scripts\python.exe ingest.py     # scrape the 13 sources -> documents/*.txt + sources.json
.venv\Scripts\python.exe chunk.py       # (optional) chunk + print stats as a sanity check
.venv\Scripts\python.exe embed.py        # build the ChromaDB vector index (downloads MiniLM on first run)
```

### Launch the app

```powershell
.venv\Scripts\python.exe app.py          # then open http://127.0.0.1:7860 in your browser
```

### Stopping the app

The app keeps running until you stop it. To shut it down:

- **Click into the terminal** where `app.py` is running and press **Ctrl + C**
  (press it twice if the first doesn't take). The prompt returns when it has
  stopped, and http://127.0.0.1:7860 will no longer load.
- If the terminal is gone but the port is still busy, find and end the process
  from a new PowerShell window:
  ```powershell
  Get-Process python | Stop-Process            # ends all python processes, or:
  (Get-NetTCPConnection -LocalPort 7860).OwningProcess | Stop-Process   # just the app on port 7860
  ```

Closing the browser tab does **not** stop the app — the server keeps running in
the terminal until you Ctrl + C it.

### (Optional) Verify the pipeline from the command line

```powershell
.venv\Scripts\python.exe retrieve.py     # top-k retrieval over the 5 eval questions
.venv\Scripts\python.exe generate.py     # full end-to-end: grounded answers + off-domain refusal
```

> **Notes:** an internet connection is required for `ingest.py` and the first
> `embed.py` (model download); after that everything runs locally except the
> Groq API call. Once the index is built in `chroma_db/`, you only need to run
> `app.py` on later sessions — you don't have to re-ingest or re-embed.

---

## Domain

The domain I chose is **FIU student discounts and perks** — discounts,
financial help, the food pantry, One Card benefits, gym deals, commuter/car
perks, free software, and more. This knowledge is valuable because it directly
helps students save money and take advantage of everything FIU offers, but it
is genuinely hard to find through official channels: the information is
scattered across many different FIU pages, some of them years old and never
taken down, and a lot of it is barely advertised — if at all. It's the kind of
thing that feels like a secret the university doesn't go out of its way to tell
you about, and pulling it into one place a student can just *ask* is exactly
what this project fixes.

---

## Document Sources

I collected 13 sources covering different subtopics within the domain (general
money-saving tips, financial wellness, food security, discount aggregators,
alumni perks, the One Card, gyms, HR perks, athletics/entertainment, free
software, and commuter perks).

| # | Source | Type | URL or file path |
|---|--------|------|-----------------|
| 1 | FIU Online Story Hub | Web page | https://fiuonline.fiu.edu/about-us/story-hub/student/5-life-hacks-to-save-money-as-a-college-student.php |
| 2 | FIU Online Story Hub | Web page | https://fiuonline.fiu.edu/about-us/story-hub/student/10-ways-to-slay-your-next-semester-online.php |
| 3 | FIU Student Food Pantry (DASA) | Web page | https://dasa.fiu.edu/all-departments/student-food-pantry/ |
| 4 | Unidays | Web page (discount aggregator) | https://www.myunidays.com/US/en-US |
| 5 | FIU News — iGrad financial wellness partnership | News article | https://news.fiu.edu/2020/fiu-offers-interactive,-digital-financial-literacy-platform-and-financial-wellness-coaches-to-university-community |
| 6 | FIU Alumni discounts + Panther Perks newsroom | Web page (multi-URL) | https://fiualumni.com/resources/discounts/ (merged with the Panther Perks newsroom deals page) |
| 7 | Connect4Success — One Card Benefits | Web page | https://transfer.fiu.edu/connect4success/one-card-benefits/ |
| 8 | Gallo 8 Gym blog | Blog post | https://gallo8gym.com/blog/gyms-with-student-discounts-miami |
| 9 | FIU Human Resources — Perks & Services | Web page | https://hr.fiu.edu/employees-affiliates/benefits/perks-services/ |
| 10 | FIU Sports — Ticket Smarter / entertainment guide | News article | https://fiusports.com/news/2024/2/21/general-ticket-smarter-and-fiu-miami-entertainment-guide.aspx |
| 11 | FIU One Card — Employee perks | Web page | https://onecard.fiu.edu/card-perks/employee-perks/ |
| 12 | FIU Libraries LibAnswers FAQ — free software | FAQ page | https://libanswers.fiu.edu/faq/18206 |
| 13 | PantherNOW — commuter perks | News article | https://panthernow.com/2023/04/10/commuters-here-are-some-fiu-perks-you-should-know-about/ |

**Two sources were swapped for scrapable equivalents** because the originals
were JavaScript-only and returned empty HTML: the original iGrad page (#5)
became the `news.fiu.edu` partnership article, and the original Software
Resources page (#12) became the LibAnswers FAQ. Source #6 is multi-URL — the
canonical alumni discounts page is JS-thin, so I merged it with the Panther
Perks newsroom deals page to capture real discount content.

---

## Chunking Strategy

**Chunk size:** 800 characters

**Overlap:** 120 characters (~15%)

**Why these choices fit your documents:**
My sources are web pages of FIU perks — mostly short, list-style, factual items
(a gym discount, the food pantry hours, a single One Card benefit). Each perk is
a small, self-contained fact, so I want chunks small enough that one chunk stays
on a single topic; if several unrelated perks get averaged into one embedding,
retrieval gets fuzzy. 800 characters (~150 words) is big enough to keep one perk
together with its conditions (who qualifies, how to redeem) but small enough to
stay "sharp." I used a **recursive splitter** that breaks on the largest natural
boundary first (blank line → line → sentence → space → character), so a chunk
ends on a coherent thought instead of mid-word — which matters for pages that
vary a lot in length and format. Overlap is 120 characters to catch facts that
straddle a boundary without duplicating large amounts of text; a 300-character
overlap on an 800-character chunk would duplicate over a third of every chunk
and crowd my top-k=4 retrieval with near-identical neighbors.

**Preprocessing before chunking:** `ingest.py` strips HTML boilerplate
(`nav`, `footer`, `script`, `style`, menus) so chunks contain real content, not
menu/footer junk, and writes clean `.txt` files plus a `sources.json` mapping
each file to its source URL.

**Final chunk count:** 236 chunks across 13 documents (all ≤ 800 characters,
overlap verified).

---

## Embedding Model

**Model used:** `all-MiniLM-L6-v2` via the `sentence-transformers` library,
with vectors stored in a persistent ChromaDB collection using cosine distance.
I chose it because it is small, fast, runs locally for free, and is accurate
enough for short factual perk text.

**Production tradeoff reflection:**
If I were deploying this for real FIU students and cost wasn't a constraint, I'd
switch to a hosted API embedding model and weigh these tradeoffs:

- **Multilingual support:** FIU's student body is heavily Spanish-speaking, so
  I'd pick a model trained on Spanish + English so a question asked in Spanish
  still retrieves the right English perk. MiniLM is English-only and would miss
  those.
- **Domain accuracy:** I'd choose a model that handles short, entity-heavy text
  well (program names like "Panther Perks," "iGrad," "One Card"), since accuracy
  on these specific names matters more here than understanding long passages.
- **Context length:** my chunks are only ~800 characters, so a long-context
  model would be wasted spend — medium context is plenty.
- **Latency:** since this is a live, interactive Q&A tool, I'd accept slightly
  higher per-call cost for a low-latency hosted endpoint so students aren't left
  waiting.

---

## Grounded Generation

Generation runs through Groq (`llama-3.3-70b-versatile`) at `temperature=0` in
`generate.py`. Grounding is enforced by **both** the system prompt and how the
context is structured.

**System prompt grounding instruction:** the model is told it may use *only*
the numbered sources provided, with these exact rules:

1. Use only facts stated in the sources — no outside knowledge, no guessing.
2. If the sources don't contain the answer, reply with exactly:
   `"I don't know based on the available sources."`
3. Cite the source number(s) used inline, like `[1]` or `[2][3]`, right after
   the fact they support.
4. Be concise and factual.

**Structural choices that reinforce grounding:**
- The retrieved chunks are formatted as an explicitly **numbered source list**,
  each block prefixed with `[n] (source: <URL>)`, so the model has a stable
  handle to cite and the citation can be mapped back to a real URL.
- `temperature=0` keeps answers deterministic and prevents creative drift away
  from the supplied text.
- A **per-source diversity cap (max 2 chunks per source)** in retrieval keeps a
  single dominant source from filling all 4 slots, so the model sees a more
  representative context.

**How source attribution is surfaced in the response:** the model cites source
numbers inline (`[n]`), and `generate()` returns the `(number → URL)` mapping
alongside the answer. The Gradio UI renders the answer with those inline
citations and a **Sources** section listing each number as a clickable URL, so a
user can click straight through to the FIU page a fact came from. When the
sources don't cover the question, the system returns the refusal sentence
instead of inventing an answer.

---

## Evaluation Report

I ran all 5 test questions from `planning.md` end-to-end through `generate.py`
(retrieval → Groq grounded generation), plus an off-domain question.

| # | Question | Expected answer | System response (summarized) | Retrieval quality | Response accuracy |
|---|----------|-----------------|------------------------------|-------------------|-------------------|
| 1 | Does FIU have resources to help with personal finance? | FIU partnered with iGrad for financial wellness tools | "Yes — FIU offers a digital financial literacy platform and financial wellness coaches through a partnership with iGrad `[1]`." | Relevant (#5 retrieved) | Accurate |
| 2 | Where can I find the free software for students? | Free software via FIU credentials (Office, eLabs); see Libraries FAQ | "Through eLabs @FIU and FIU's free software resources `[2]`." | Relevant (#12 retrieved) | Accurate |
| 3 | What discounts are there for alumni? | FIU's Panther Perks program lists alumni discounts (source #6) | "I don't know based on the available sources." | Off-target (#6 missed — landed at rank 5) | Correctly refused rather than hallucinating (see Failure Case) |
| 4 | What are the FIU One Card benefits? | Home games, library privileges, WRC access, etc. | "Free entry to home athletic games `[1]`, library borrowing/database privileges `[3]`, plus dining/retail perks `[2]`." | Relevant (#7 retrieved) | Accurate |
| 5 | How does FIU help car owners? | Free inflation station and free jump-start help | "Free inflation stations around campus and free jump-start help `[3]`, plus parking/transportation perks `[1]`." | Relevant (#13 retrieved, via diversity cap) | Accurate |

**Off-domain control:** "What is the weather in Miami today?" → the system
returned `"I don't know based on the available sources."` instead of
hallucinating, confirming the grounding holds on out-of-scope questions.

**Summary:** 4/5 questions retrieved their expected source and produced an
accurate, cited answer. Q3 is a documented retrieval miss where the system
correctly refused rather than fabricating an answer.

---

## Failure Case Analysis

**Question that failed:** "What discounts are there for alumni?" (Q3, expected
source #6 — the FIU alumni / Panther Perks discounts page).

**What the system returned:** `"I don't know based on the available sources."`
The retrieved chunks came from general discount aggregators (Unidays #4, the
money-saving tips page #1, the Gallo 8 gym page #8) — none of which mention
*alumni* discounts — so the model correctly judged that the context didn't
answer the question and refused.

**Root cause (tied to a specific pipeline stage):** this is an
**embedding/retrieval** failure, not a generation failure. There are two layers
to it. First, the canonical alumni discounts page is JavaScript-rendered, so
only a short intro was scrapable (partly mitigated by merging in the Panther
Perks newsroom page). The deeper problem is that `all-MiniLM-L6-v2` treats
"student discounts" and "alumni discounts" as nearly identical, so broad
discount aggregators outrank the dedicated alumni page. Source #6 lands at
**rank 5 — just outside the top-4** — so it never reaches the generator, and
with grounding enforced, the model refuses instead of guessing.

**What you would change to fix it:** the cheapest fix is tightening the
per-source diversity cap to 1, which pushes #6 into the top-4 — but that weakens
depth on narrow questions that legitimately need two chunks from one source, so
I kept the cap at 2 and documented this tradeoff instead. The more robust fix is
the production embedding model discussed above: a model with better accuracy on
short, entity-heavy domain text would distinguish "alumni" from "student"
discounts and rank the dedicated page higher. Re-scraping the alumni page with a
headless browser (so the full JS-rendered discount list is captured) would also
give retrieval more distinctive alumni-specific text to match on.

---

## Spec Reflection

**One way the spec helped you during implementation:**
Writing the Evaluation Plan in `planning.md` *before* coding — five specific,
checkable questions each mapped to an expected source number — turned
"does retrieval work?" into a concrete pass/fail test. That mapping became the
literal `EVAL_QUESTIONS` table in `retrieve.py` and the harness in
`generate.py`, so I could measure 4/5 instead of eyeballing results. It's also
what surfaced the Q3 alumni problem early and precisely (rank 5, just outside
top-4) rather than as a vague sense that "alumni questions seem off."

**One way your implementation diverged from the spec, and why:**
The spec's Retrieval Approach was just "all-MiniLM-L6-v2, top-k = 4." During
implementation I discovered that one source (the HR perks directory) is ~70% of
the index and would fill every top-4 slot, burying smaller, more specific
sources. So I added a **per-source diversity cap (max 2 chunks per source)** to
`retrieve()` that wasn't in the original plan — this is what fixed Q5 (car
owners). I updated the plan's reasoning to reflect the change, as the spec
instructed.

---

## AI Usage

**Instance 1 — Ingestion & chunking (Milestone 3)**

- *What I gave the AI:* my Documents table (the 13 URLs) and my Chunking Strategy
  section (size = 800, overlap = 120, recursive splitter), plus `requirements.txt`.
- *What it produced:* `ingest.py` (fetches each URL, strips nav/footer/script
  boilerplate, writes clean `.txt` + `sources.json`) and `chunk.py` with a
  `chunk_text(text, size=800, overlap=120)` recursive splitter.
- *What I changed or overrode:* when two pages (iGrad #5, software #12) returned
  empty because they were JavaScript-only, I directed the AI to swap them for
  server-rendered equivalents (`news.fiu.edu` and `libanswers.fiu.edu`) and to
  support a multi-URL source so #6 could merge the alumni page with the Panther
  Perks newsroom page.

**Instance 2 — Grounded generation & interface (Milestone 5)**

- *What I gave the AI:* my Grounded Generation requirements (answer only from
  retrieved chunks, refuse with a fixed sentence otherwise, cite source URLs) and
  the retrieval output format from Milestone 4.
- *What it produced:* `generate.py` — a Groq call wrapped in a grounding system
  prompt that numbers the sources, enforces the refusal sentence, and cites
  `[n]` inline — plus a Gradio UI (`app.py`) and an end-to-end verification
  harness.
- *What I changed or overrode:* I chose **Gradio** over Streamlit for the
  interface, set `temperature=0` for deterministic grounded answers, and had the
  citations surfaced as clickable source URLs mapped from the inline `[n]`
  markers rather than the model free-typing URLs (which it could get wrong). I
  also kept the diversity cap at 2 after seeing it caused Q3 to refuse, choosing
  to document that as a failure case rather than over-tune retrieval.
