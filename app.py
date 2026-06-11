"""Milestone 5 — Query interface (Gradio).

A small web UI over generate(): type a question, get a grounded answer with the
source numbers cited inline, and see the list of source URLs those [n] refer to.

Run:  python app.py          # opens http://127.0.0.1:7860
"""

import gradio as gr

from generate import generate

EXAMPLES = [
    "does FIU have any resources to help students with personal finance?",
    "where can I find the free software provided to students?",
    "what are the FIU One Card benefits?",
    "how does FIU help car owners?",
]

# An animated CSS spinner shown while retrieval + the Groq call are running, so
# it's obvious the app is working and not frozen.
SPINNER = """
<div style="display:flex;align-items:center;gap:12px;color:#555;font-size:15px;">
  <div class="ug-loader"></div>
  Searching the FIU sources and writing a grounded answer&hellip;
</div>
<style>
.ug-loader{
  width:22px;height:22px;border:3px solid #e0e0e0;border-top-color:#1565c0;
  border-radius:50%;animation:ug-spin 0.8s linear infinite;
}
@keyframes ug-spin{to{transform:rotate(360deg);}}
</style>
"""


def answer_question(query):
    """Gradio callback (generator): show a spinner, then stream in the answer.

    Yields (answer_markdown, sources_markdown, status_html). Because this is a
    generator, Gradio renders the first yield (spinner) immediately, then
    replaces it with the final answer once generate() returns.
    """
    query = (query or "").strip()
    if not query:
        yield "Ask a question to get started.", "", ""
        return

    # First yield: clear any previous answer and show the spinner right away.
    yield "", "", SPINNER

    out = generate(query)
    sources_md = "\n".join(
        f"- **[{n}]** [{url}]({url})" for n, url in out["sources"]
    )
    sources_md = f"### Sources\n{sources_md}" if sources_md else ""

    # Final yield: real answer + sources, spinner cleared.
    yield out["answer"], sources_md, ""


with gr.Blocks(title="The Unofficial Guide — FIU Perks") as demo:
    gr.Markdown(
        "# The Unofficial Guide\n"
        "Ask about FIU student discounts and perks. Answers are grounded only in "
        "the ingested FIU pages — the citations `[n]` map to the sources listed below."
    )
    query = gr.Textbox(label="Your question", placeholder="e.g. what are the FIU One Card benefits?")
    ask = gr.Button("Ask", variant="primary")
    status = gr.HTML()          # holds the animated spinner while a query runs
    answer = gr.Markdown(label="Answer")
    sources = gr.Markdown()

    gr.Examples(examples=EXAMPLES, inputs=query)

    ask.click(answer_question, inputs=query, outputs=[answer, sources, status])
    query.submit(answer_question, inputs=query, outputs=[answer, sources, status])


if __name__ == "__main__":
    demo.launch()
