"""Evaluation harness for DocuSense (Phase 5).

Modes
  retrieval : does the right text come back for each question? (fast)
  full      : runs the real Q&A engine and grades answers (slow)
  --sweep   : compares chunk sizes on one PDF (fast)
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

from langchain_chroma import Chroma

import config
from ingest import IngestionError, get_embeddings, ingest_pdf, load_pdf
from qa import DocumentQA, QAError

QUESTIONS_PATH = config.BASE_DIR / "eval_questions.json"
Chunk = Tuple[str, int]  # (text, page)
Question = Dict[str, object]


class EvalError(Exception):
    """Raised when an evaluation cannot run."""


# ---------- pure helpers (unit-tested, no Ollama) ----------

def norm(text: object) -> str:
    """Lowercase and collapse all whitespace."""
    return " ".join(str(text).lower().split())


def contains_any(text: object, terms: Sequence[str]) -> bool:
    haystack = norm(text)
    return any(norm(term) in haystack for term in terms)


def evidence_pages(chunks: Sequence[Chunk], terms: Sequence[str]) -> Set[int]:
    """Pages whose text contains any of the evidence terms."""
    return {page for text, page in chunks if contains_any(text, terms)}


def pct(part: int, whole: int) -> str:
    return "n/a" if whole == 0 else f"{part}/{whole} ({round(100 * part / whole)}%)"


def load_questions(path: Path = QUESTIONS_PATH) -> List[Question]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvalError(f"Could not read {path}: {exc}") from exc
    if not isinstance(data, list) or not data:
        raise EvalError("The question file must contain a non-empty list.")

    questions: List[Question] = []
    for number, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise EvalError(f"Question {number} must be an object.")
        text = str(item.get("question", "")).strip()
        kind = item.get("type")
        if not text or kind not in ("answerable", "unanswerable"):
            raise EvalError(
                f"Question {number} needs a 'question' and a type of "
                "'answerable' or 'unanswerable'."
            )
        evidence = [str(t) for t in item.get("evidence", [])]
        if kind == "answerable" and not evidence:
            raise EvalError(f"Question {number} needs 'evidence' terms.")
        terms = [str(t) for t in item.get("answer_contains", evidence)]
        questions.append(
            {
                "question": text,
                "type": kind,
                "evidence": evidence,
                "answer_contains": terms,
            }
        )
    return questions


def split_valid(
    questions: Sequence[Question], chunks: Sequence[Chunk]
) -> Tuple[List[Question], List[Question]]:
    """Separate questions whose evidence text really exists in the
    document from those that do not (bad keyword or odd PDF text)."""
    valid: List[Question] = []
    skipped: List[Question] = []
    for q in questions:
        if q["type"] == "answerable" and not evidence_pages(
            chunks, q["evidence"]  # type: ignore[arg-type]
        ):
            skipped.append(q)
        else:
            valid.append(q)
    return valid, skipped


def grade(
    question: Question, result: Dict[str, object], ev_pages: Set[int]
) -> Dict[str, object]:
    """Grade one answer from DocumentQA.ask()."""
    found = bool(result["found"])
    pages = {int(p) for p in result["pages"]}  # type: ignore[union-attr]
    row: Dict[str, object] = {
        "question": question["question"],
        "type": question["type"],
        "found": found,
        "cited": bool(result["cited"]),
        "answer": str(result["answer"]),
        "unverified": list(result.get("unverified", [])),
    }
    if question["type"] == "unanswerable":
        row["ok"] = not found
        row["source_ok"] = None
    else:
        row["ok"] = found and contains_any(
            row["answer"], question["answer_contains"]  # type: ignore[arg-type]
        )
        row["source_ok"] = bool(pages & ev_pages) if found else None
    return row


def summarize(rows: Sequence[Dict[str, object]]) -> Dict[str, str]:
    ans = [r for r in rows if r["type"] == "answerable"]
    una = [r for r in rows if r["type"] == "unanswerable"]
    found_ans = [r for r in ans if r["found"]]
    cited_ans = [r for r in found_ans if r["cited"]]
    total_seconds = sum(float(r.get("seconds", 0)) for r in rows)
    return {
        "Answer correct (answerable)": pct(sum(bool(r["ok"]) for r in ans), len(ans)),
        "False refusals (answerable)": pct(sum(not r["found"] for r in ans), len(ans)),
        "Correct refusals (unanswerable)": pct(sum(bool(r["ok"]) for r in una), len(una)),
        "Model cited a page": pct(len(cited_ans), len(found_ans)),
        "Shown pages contain the evidence": pct(
            sum(bool(r["source_ok"]) for r in found_ans), len(found_ans)
        ),
        "Answers with unverified numbers": pct(
            sum(bool(r.get("unverified")) for r in found_ans), len(found_ans)
        ),
        "Average seconds per question": (
            f"{total_seconds / len(rows):.0f}" if rows else "n/a"
        ),
    }

# ---------- data access ----------

def open_collection(name: str) -> Tuple[Chroma, List[Chunk]]:
    try:
        store = Chroma(
            collection_name=name,
            embedding_function=get_embeddings(),
            persist_directory=str(config.CHROMA_DIR),
        )
        data = store.get(include=["documents", "metadatas"])
    except Exception as exc:
        raise EvalError(f"Could not open collection '{name}': {exc}") from exc
    chunks = [
        (text, int((meta or {}).get("page", 0)))
        for text, meta in zip(data["documents"], data["metadatas"])
    ]
    if not chunks:
        raise EvalError(f"Collection '{name}' is missing or empty.")
    return store, chunks


# ---------- evaluations ----------

def retrieval_metrics(
    store: Chroma, questions: Sequence[Question], ks: Sequence[int]
) -> Dict[str, object]:
    """For each answerable question: does any of the top-k chunks
    contain the evidence text? Uses embeddings only, so it is fast."""
    answerable = [q for q in questions if q["type"] == "answerable"]
    top = max(ks)
    hits = {k: 0 for k in ks}
    rows: List[Dict[str, object]] = []
    for q in answerable:
        try:
            docs = store.similarity_search(str(q["question"]), k=top)
        except Exception as exc:
            raise EvalError(
                f"Retrieval failed. Is Ollama running? Details: {exc}"
            ) from exc
        row: Dict[str, object] = {"question": q["question"]}
        for k in ks:
            hit = any(
                contains_any(d.page_content, q["evidence"])  # type: ignore[arg-type]
                for d in docs[:k]
            )
            hits[k] += int(hit)
            row[str(k)] = hit
        rows.append(row)
    return {"total": len(answerable), "hits": hits, "rows": rows}


def run_full(
    collection: str, questions: Sequence[Question], chunks: Sequence[Chunk]
) -> List[Dict[str, object]]:
    qa = DocumentQA(collection)
    rows: List[Dict[str, object]] = []
    for number, q in enumerate(questions, start=1):
        qa.history = []  # keep questions independent of each other
        print(f"[{number}/{len(questions)}] {q['question']}", flush=True)
        started = time.time()
        result = qa.ask(str(q["question"]))
        seconds = round(time.time() - started, 1)
        ev = (
            evidence_pages(chunks, q["evidence"])  # type: ignore[arg-type]
            if q["type"] == "answerable"
            else set()
        )
        row = grade(q, result, ev)
        row["seconds"] = seconds
        rows.append(row)
        print(f"    -> {'PASS' if row['ok'] else 'FAIL'} ({seconds}s)", flush=True)
    return rows


# ---------- reports ----------

def settings_block(extra: Optional[Dict[str, object]] = None) -> str:
    items: Dict[str, object] = {
        "Date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "Chat model": config.CHAT_MODEL,
        "Embedding model": config.EMBEDDING_MODEL,
        "Chunk size / overlap": f"{config.CHUNK_SIZE} / {config.CHUNK_OVERLAP}",
        "Retrieval top-k": config.RETRIEVAL_TOP_K,
    }
    items.update(extra or {})
    return "\n".join(f"- **{k}:** {v}" for k, v in items.items())


def skipped_block(skipped: Sequence[Question]) -> str:
    if not skipped:
        return ""
    lines = ["", "## Skipped questions", "", "The evidence text was not found "
             "anywhere in the document, so these were not graded. Fix the "
             "keyword in eval_questions.json.", ""]
    lines += [f"- {q['question']}  (evidence: {q['evidence']})" for q in skipped]
    return "\n".join(lines)


def retrieval_table(result: Dict[str, object], ks: Sequence[int]) -> str:
    hits = result["hits"]
    lines = ["| k | evidence found in top-k chunks |", "|---|---|"]
    lines += [f"| {k} | {pct(hits[k], result['total'])} |" for k in ks]  # type: ignore[index]
    lines += ["", "| Question | " + " | ".join(f"k={k}" for k in ks) + " |",
              "|---|" + "---|" * len(ks)]
    for row in result["rows"]:  # type: ignore[union-attr]
        marks = " | ".join("yes" if row[str(k)] else "NO" for k in ks)
        lines.append(f"| {row['question']} | {marks} |")
    return "\n".join(lines)


def retrieval_report(
    collection: str, questions: Sequence[Question], ks: Sequence[int]
) -> str:
    store, chunks = open_collection(collection)
    valid, skipped = split_valid(questions, chunks)
    result = retrieval_metrics(store, valid, ks)
    return "\n\n".join(
        [
            f"# Retrieval evaluation: {collection}",
            settings_block({"Chunks in collection": len(chunks)}),
            "## Results",
            retrieval_table(result, ks),
            skipped_block(skipped),
        ]
    )


def full_report(collection: str, questions: Sequence[Question]) -> str:
    _, chunks = open_collection(collection)
    valid, skipped = split_valid(questions, chunks)
    rows = run_full(collection, valid, chunks)
    metrics = summarize(rows)
    lines = [
        f"# Full evaluation: {collection}",
        settings_block({"Questions graded": len(rows)}),
        "## Summary",
        "| Metric | Result |\n|---|---|\n"
        + "\n".join(f"| {k} | {v} |" for k, v in metrics.items()),
        "## Per question",
        "| Result | Type | Seconds | Cited | Pages ok | Question |\n"
        "|---|---|---|---|---|---|\n"
        + "\n".join(
            f"| {'PASS' if r['ok'] else 'FAIL'} | {r['type']} | {r['seconds']} "
            f"| {'yes' if r['cited'] else 'no'} "
            f"| {'-' if r['source_ok'] is None else ('yes' if r['source_ok'] else 'NO')} "
            f"| {r['question']} |"
            for r in rows
        ),
        "## Answers (first 300 characters)",
        "\n".join(
            f"- **{r['question']}**  \n  {str(r['answer'])[:300]}" for r in rows
        ),
        skipped_block(skipped),
    ]
    return "\n\n".join(lines)


def sweep_report(
    pdf_path: str, sizes: Sequence[int], questions: Sequence[Question],
    ks: Sequence[int],
) -> str:
    import chromadb

    pages = [(d.page_content, int(d.metadata["page"])) for d in load_pdf(pdf_path)]
    valid, skipped = split_valid(questions, pages)
    client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    original = (config.CHUNK_SIZE, config.CHUNK_OVERLAP)
    table = [
        "| Chunk size | Overlap | Chunks | "
        + " | ".join(f"hit@{k}" for k in ks) + " |",
        "|---|---|---|" + "---|" * len(ks),
    ]
    try:
        for size in sizes:
            config.CHUNK_SIZE = size
            config.CHUNK_OVERLAP = max(0, round(size * 0.15))
            print(f"Chunk size {size}: indexing...", flush=True)
            info = ingest_pdf(pdf_path)
            name = str(info["collection_name"])
            try:
                store, _ = open_collection(name)
                result = retrieval_metrics(store, valid, ks)
            finally:
                client.delete_collection(name)  # temporary collection
            cells = " | ".join(pct(result["hits"][k], result["total"]) for k in ks)  # type: ignore[index]
            table.append(
                f"| {size} | {config.CHUNK_OVERLAP} | {info['chunks']} | {cells} |"
            )
    finally:
        config.CHUNK_SIZE, config.CHUNK_OVERLAP = original

    return "\n\n".join(
        [
            f"# Chunk-size sweep: {Path(pdf_path).name}",
            settings_block(),
            "## Results",
            "\n".join(table),
            skipped_block(skipped),
        ]
    )


# ---------- command line ----------

def save_report(tag: str, text: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = config.DATA_DIR / f"eval_{tag}_{stamp}.md"
    path.write_text(text, encoding="utf-8")
    return path


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate DocuSense.")
    parser.add_argument("collection", nargs="?", help="collection name")
    parser.add_argument("--mode", choices=["retrieval", "full"], default="retrieval")
    parser.add_argument("--ks", type=int, nargs="+", default=[3, 4, 6, 8, 10])
    parser.add_argument("--sweep", metavar="PDF", help="compare chunk sizes")
    parser.add_argument("--sizes", type=int, nargs="+", default=[500, 800, 1000, 1500])
    args = parser.parse_args(argv)
    ks = sorted({k for k in args.ks if k > 0})
    if not ks:
        parser.error("--ks needs at least one positive number")

    try:
        questions = load_questions()
        if args.sweep:
            text, tag = sweep_report(args.sweep, args.sizes, questions, ks), "sweep"
        elif args.collection and args.mode == "full":
            text, tag = full_report(args.collection, questions), "full"
        elif args.collection:
            text, tag = retrieval_report(args.collection, questions, ks), "retrieval"
        else:
            parser.error("give a collection name or use --sweep PDF")
    except (EvalError, IngestionError, QAError) as err:
        print(f"Evaluation failed: {err}")
        return 1

    print("\n" + text + "\n")
    print(f"Saved to {save_report(tag, text)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())