"""Map-reduce summary engine for DocuSense (provider-aware)."""
import math
import re
import sys
import time
from typing import Callable, Dict, List, Optional

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage

import config
from providers import (
    explain_error,
    get_chat_model,
    get_embeddings,
    missing_key_message,
    provider_ready,
    text_of,
)

NOT_STATED = "Not stated in the document."

SECTIONS = [
    "Context",
    "Objectives",
    "Methodology",
    "Results",
    "Limitations",
    "Suggested Viva Questions",
]

MAP_PROMPT = """You are helping a teacher review a student's project \
documentation. Write brief notes on the text below, using ONLY that text.

RULES:
- Maximum 120 words, as short bullet points.
- Keep concrete facts: goals, methods, tools, datasets, numbers, \
results, problems. Keep exact names of methods, tools and numbers.
- Always keep the main result numbers (scores, accuracy, times).
- Note any goals or limitations ONLY if the text states them.
- If the text compares its method with other methods, say so clearly. \
Do not describe the other methods as part of the project.
- Never add outside knowledge or guess."""

REDUCE_PROMPT = f"""You are helping a teacher review a student's project \
documentation. Using ONLY the NOTES provided, write a structured summary \
with exactly these six headings, in this order, each on its own line \
starting with "## ":

## Context
## Objectives
## Methodology
## Results
## Limitations
## Suggested Viva Questions

RULES:
- Always put a space after every full stop and between words.
- Context, Objectives, Methodology, Results and Limitations: 2 to 4 \
sentences each.
- Context: what the project is and the problem it addresses. Do not \
mention conferences or publication venues.
- Objectives: list only aims the notes actually state. If the notes \
state no aims, write: Not explicitly stated. Then add at most one \
sentence beginning "The document mainly presents".
- Methodology: describe the overall approach in plain language: what \
was built, with which tools or data, and in what steps. Only include \
methods the project itself uses, not methods it is compared with. Skip \
low-level technical details.
- Results: include the main numbers (scores, accuracy, times) from the \
notes.
- Limitations: only weaknesses or problems the notes mention. If none, \
write exactly: {NOT_STATED}
- If the notes do not cover any other section, write exactly: \
{NOT_STATED}
- Suggested Viva Questions: exactly 5 numbered questions about THIS \
project. Each question must mention a specific method, tool, dataset, \
number or result from the notes. Do not ask generic questions such as \
"what are the key findings".
- Never invent facts, numbers or results that are not in the notes."""


class SummaryError(Exception):
    """Raised when a summary cannot be produced."""


# ---------- helpers (tested without a model) ----------

def load_chunks(store: Chroma) -> List[Document]:
    """Read every chunk of the collection, ordered by page."""
    data = store.get(include=["documents", "metadatas"])
    docs = [
        Document(page_content=text, metadata=meta or {})
        for text, meta in zip(data["documents"], data["metadatas"])
    ]
    docs.sort(key=lambda d: int(d.metadata.get("page", 0)))  # stable
    return docs


def group_chunks(chunks: List[Document], max_chars: int) -> List[List[Document]]:
    """Pack consecutive chunks into groups of at most max_chars."""
    groups: List[List[Document]] = []
    current: List[Document] = []
    size = 0
    for chunk in chunks:
        length = len(chunk.page_content)
        if current and size + length > max_chars:
            groups.append(current)
            current, size = [], 0
        current.append(chunk)
        size += length
    if current:
        groups.append(current)
    return groups


def pick_groups(groups: List[List[Document]], max_groups: int) -> List[List[Document]]:
    """If there are too many groups, keep evenly spaced ones."""
    if len(groups) <= max_groups:
        return groups
    if max_groups == 1:
        return [groups[0]]
    step = (len(groups) - 1) / (max_groups - 1)
    indexes = sorted({round(i * step) for i in range(max_groups)})
    return [groups[i] for i in indexes]


def page_range(group: List[Document]) -> str:
    """Return a label like 'pages 2-4' for a group."""
    pages = [int(c.metadata["page"]) for c in group if "page" in c.metadata]
    if not pages:
        return "pages ?"
    low, high = min(pages), max(pages)
    return f"page {low}" if low == high else f"pages {low}-{high}"


def format_group(group: List[Document]) -> str:
    """Label each chunk with its page number."""
    return "\n\n".join(
        f"[Page {c.metadata.get('page', '?')}]\n{c.page_content}" for c in group
    )


def fix_spacing(text: str) -> str:
    """Add the missing space in 'word.Next' (full stop, then a capital).
    Needs two lowercase letters before the full stop, so 'Ph.D' and
    'e.g.' are left alone."""
    return re.sub(r"(?<=[a-z]{2}[.!?])(?=[A-Z][a-z])", " ", text)


def build_groups(
    chunks: List[Document],
    start_chars: int,
    limit_chars: int,
    max_groups: int,
) -> List[List[Document]]:
    """Group chunks so the whole document fits in max_groups if possible.
    Greedy packing can overshoot the cap, so the group size is grown in
    small steps (never beyond limit_chars) until it fits."""
    total_chars = sum(len(c.page_content) for c in chunks)
    group_chars = min(
        limit_chars,
        max(start_chars, math.ceil(total_chars / max_groups)),
    )
    groups = group_chunks(chunks, group_chars)
    while len(groups) > max_groups and group_chars < limit_chars:
        group_chars = min(int(group_chars * 1.1) + 1, limit_chars)
        groups = group_chunks(chunks, group_chars)
    return groups


def _match_section(line: str) -> Optional[str]:
    """Return the section name if the line is a section heading."""
    cleaned = re.sub(r"[#*:_]", "", line).strip().lower()
    for name in SECTIONS:
        if cleaned == name.lower():
            return name
    if cleaned in {"viva questions", "suggested viva question"}:
        return SECTIONS[-1]
    return None


def parse_sections(text: str) -> Dict[str, str]:
    """Split model output into the six sections.
    Missing or empty sections become NOT_STATED."""
    found: Dict[str, List[str]] = {}
    current: Optional[str] = None
    for line in text.splitlines():
        name = _match_section(line)
        if name:
            current = name
            found.setdefault(name, [])
        elif current:
            found[current].append(line)
    return {
        name: fix_spacing("\n".join(found.get(name, [])).strip())
        or NOT_STATED
        for name in SECTIONS
    }


def render_summary(sections: Dict[str, str], title: str = "") -> str:
    """Build the final Markdown document."""
    parts = [f"# {title}"] if title else []
    parts += [f"## {name}\n{sections[name]}" for name in SECTIONS]
    return "\n\n".join(parts)


# ---------- engine ----------

def summarize_collection(
    collection_name: str,
    title: str = "",
    progress: Optional[Callable[[str], None]] = None,
) -> Dict[str, object]:
    """Summarize one document's collection.

    Returns {'markdown', 'sections', 'groups_used', 'groups_total',
    'seconds'}."""
    say = progress or (lambda message: None)
    started = time.time()

    if not provider_ready():
        raise SummaryError(missing_key_message())

    try:
        store = Chroma(
            collection_name=collection_name,
            embedding_function=get_embeddings(),
            persist_directory=str(config.CHROMA_DIR),
        )
        chunks = load_chunks(store)
    except Exception as exc:
        raise SummaryError(
            explain_error(exc, "Could not open the document store.")
        ) from exc

    if not chunks:
        raise SummaryError(
            f"Collection '{collection_name}' is missing or empty. "
            "Check the name or ingest the PDF again."
        )

    all_groups = build_groups(
        chunks,
        config.SUMMARY_GROUP_CHARS,
        config.SUMMARY_MAX_GROUP_CHARS,
        config.SUMMARY_MAX_GROUPS,
    )
    groups = pick_groups(all_groups, config.SUMMARY_MAX_GROUPS)

    try:
        llm = get_chat_model(max_output_tokens=350, num_ctx=config.SUMMARY_NUM_CTX)
        final_llm = get_chat_model(max_output_tokens=900, num_ctx=config.SUMMARY_NUM_CTX)
    except Exception as exc:
        raise SummaryError(
            explain_error(exc, "Could not start the chat model.")
        ) from exc

    def call(model, system: str, human: str) -> str:
        try:
            reply = model.invoke(
                [SystemMessage(content=system), HumanMessage(content=human)]
            )
        except Exception as exc:
            raise SummaryError(
                explain_error(exc, "The chat model failed.")
            ) from exc
        text = text_of(reply)
        if not text:
            raise SummaryError("The model returned an empty reply.")
        return text

    # Map step: short notes for each group.
    notes: List[str] = []
    for number, group in enumerate(groups, start=1):
        label = page_range(group)
        if len(groups) == 1:
            notes.append(f"({label})\n{format_group(group)}")
            break
        say(f"Reading part {number} of {len(groups)} ({label})...")
        result = call(llm, MAP_PROMPT, f"TEXT ({label}):\n{format_group(group)}")
        notes.append(f"Notes ({label}):\n{result}")

    # Reduce step: one structured summary.
    say("Writing the final summary...")
    final = call(
        final_llm,
        REDUCE_PROMPT,
        "NOTES:\n\n" + "\n\n".join(notes),
    )

    sections = parse_sections(final)
    if all(value == NOT_STATED for value in sections.values()):
        raise SummaryError(
            "The model did not follow the summary format. Try again."
        )

    return {
        "markdown": render_summary(sections, title),
        "sections": sections,
        "groups_used": len(groups),
        "groups_total": len(all_groups),
        "seconds": round(time.time() - started),
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python summarize.py <collection_name>")
        sys.exit(1)

    name = sys.argv[1]
    try:
        out = summarize_collection(name, title=name, progress=print)
    except SummaryError as err:
        print(f"Summary failed: {err}")
        sys.exit(1)

    print("\n" + out["markdown"] + "\n")
    if out["groups_used"] < out["groups_total"]:
        print(
            f"Note: long document. Summarized {out['groups_used']} of "
            f"{out['groups_total']} parts (evenly spaced)."
        )
    path = config.DATA_DIR / f"summary_{name}.md"
    path.write_text(str(out["markdown"]), encoding="utf-8")
    print(f"Saved to {path}  (took {out['seconds']} seconds)")