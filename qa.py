"""Grounded Q&A engine for DocuSense (Phase 2, hardened)."""
import re
import sys
from typing import Callable, Dict, List, Optional, Tuple

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

import config
from ingest import get_embeddings

NOT_FOUND = "I could not find that in the document."
MAX_HISTORY_TURNS = 3
POSSIBLE_SOURCE_PAGES = 2

SYSTEM_PROMPT = f"""You are DocuSense, an assistant that helps teachers \
review a student's project documentation.

RULES:
1. Answer ONLY using the CONTEXT provided below. Never use outside \
knowledge.
2. If the context does not contain the answer, reply with exactly: \
{NOT_FOUND}
3. Be concise and factual. Do not invent numbers, names or results. \
Copy numbers exactly as written in the context.
4. You MUST end every answer with the page numbers you used, in this \
form: (page 4) or (pages 4, 7). Use the [Page N] labels from the \
context. Never start your answer with a [Page N] label. Do not write \
any other comment about page numbers or citations.
5. Use the CHAT HISTORY only to understand follow-up questions, never \
as a source of facts."""

# "(page 8)", "(pages 4, 7)", "[Page 3]", "(Page 2 and 5)"
_CITATION = re.compile(
    r"\s*[\(\[]\s*pages?\s*\d+(?:\s*(?:,|and|&|-|\u2013)\s*\d+)*\s*[\)\]]",
    flags=re.IGNORECASE,
)
# Comments about citations, e.g. "(No page numbers used, as ...)"
_META_NOTE = re.compile(
    r"\s*\(\s*(?:no\s+page|page\s+numbers?)[^)]*\)", flags=re.IGNORECASE
)
# A standalone number: not part of a word (P100) or a longer number.
_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?!\w)")


class QAError(Exception):
    """Raised when the Q&A engine cannot answer."""


def format_context(chunks: List[Document]) -> str:
    """Label each chunk with its page number for the prompt."""
    parts = [
        f"[Page {c.metadata.get('page', '?')}]\n{c.page_content}"
        for c in chunks
    ]
    return "\n\n---\n\n".join(parts)


def format_history(history: List[Tuple[str, str]]) -> str:
    """Turn (question, answer) pairs into plain text."""
    if not history:
        return "(none)"
    return "\n".join(f"Teacher: {q}\nAssistant: {a}" for q, a in history)


def trim_history(
    history: List[Tuple[str, str]], max_turns: int = MAX_HISTORY_TURNS
) -> List[Tuple[str, str]]:
    """Keep only the most recent turns to save memory and time."""
    return history[-max_turns:]


def is_not_found(answer: str) -> bool:
    """Detect the fallback reply, ignoring case and final period."""
    return NOT_FOUND.lower().rstrip(".") in answer.lower()


def extract_cited_pages(answer: str) -> List[int]:
    """Pull page numbers the model cited, e.g. [Page 3], (page 4)
    or (pages 4, 7)."""
    pages = set()
    for match in re.finditer(
        r"pages?\s*((?:\d+\s*(?:,|and|&|-)?\s*)+)", answer, flags=re.IGNORECASE
    ):
        pages.update(int(n) for n in re.findall(r"\d+", match.group(1)))
    return sorted(pages)


def strip_page_labels(answer: str) -> str:
    """Remove a leading [Page N] label the model sometimes copies."""
    return re.sub(r"^\s*\[Page \d+\]\s*", "", answer).strip()


def strip_citations(answer: str) -> str:
    """Remove the model's own page citations and comments about them.
    Sources are shown by the app from verified pages instead."""
    text = _CITATION.sub("", answer)
    text = _META_NOTE.sub("", text)
    text = re.sub(r"[ \t]+([.,;:!?])", r"\1", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return strip_page_labels(text.strip())


def _normalize_numbers(text: str) -> str:
    """Remove thousands separators: 4,500,000 -> 4500000."""
    return re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)


def find_unverified_numbers(
    answer: str, context: str, question: str = ""
) -> List[str]:
    """Numbers in the answer that do not appear in the retrieved text.

    Single digits are ignored (too noisy), as are numbers that the
    teacher's own question contained. Call this on an answer whose
    page citations were already stripped."""
    ctx = _normalize_numbers(context)
    asked = set(_NUMBER.findall(_normalize_numbers(question)))
    missing: List[str] = []
    for number in _NUMBER.findall(_normalize_numbers(answer)):
        if len(number) < 2 or number in asked or number in missing:
            continue
        if not re.search(r"(?<![\d.])" + re.escape(number) + r"(?!\d)", ctx):
            missing.append(number)
    return missing


def top_pages(chunks: List[Document], n: int = POSSIBLE_SOURCE_PAGES) -> List[int]:
    """Pages of the best-matching chunks, in relevance order."""
    ordered: List[int] = []
    for chunk in chunks:
        if "page" in chunk.metadata:
            page = int(chunk.metadata["page"])
            if page not in ordered:
                ordered.append(page)
    return ordered[:n]


class DocumentQA:
    """Answers questions from ONE document's Chroma collection."""

    def __init__(self, collection_name: str) -> None:
        self.collection_name = collection_name
        self.history: List[Tuple[str, str]] = []

        try:
            self.store = Chroma(
                collection_name=collection_name,
                embedding_function=get_embeddings(),
                persist_directory=str(config.CHROMA_DIR),
            )
            count = self.store._collection.count()
        except Exception as exc:
            raise QAError(f"Could not open the document store: {exc}") from exc

        if count == 0:
            raise QAError(
                f"Collection '{collection_name}' is missing or empty. "
                "Check the name or ingest the PDF again."
            )

        if config.CHAT_PROVIDER != "ollama":
            raise QAError(f"Unsupported chat provider: {config.CHAT_PROVIDER}")
        self.llm = ChatOllama(
            model=config.CHAT_MODEL,
            base_url=config.OLLAMA_BASE_URL,
            temperature=0,
        )

    def _retrieve(self, question: str) -> List[Document]:
        """Find the most relevant chunks. For follow-ups, include the
        previous question so words like 'it' still retrieve well."""
        query = question
        if self.history:
            query = f"{self.history[-1][0]} {question}"
        try:
            return self.store.similarity_search(
                query, k=config.RETRIEVAL_TOP_K
            )
        except Exception as exc:
            raise QAError(
                "Retrieval failed. Is Ollama running and is "
                f"'{config.EMBEDDING_MODEL}' pulled? Details: {exc}"
            ) from exc

    def ask(
        self,
        question: str,
        on_stage: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, object]:
        """Return {'answer', 'pages', 'found', 'cited', 'unverified'}.

        on_stage is called with "search" before retrieval and "write"
        before the model answers, so an interface can show progress.

        cited=True      -> pages are ones the model named AND that were
                           really retrieved.
        cited=False     -> pages are only the best-matching retrieved pages.
        unverified      -> numbers in the answer that are not in the
                           retrieved text (check them in the document).
        """
        notify = on_stage or (lambda stage: None)
        question = question.strip()
        if not question:
            raise QAError("Please enter a question.")

        notify("search")
        chunks = self._retrieve(question)
        user_prompt = (
            f"CONTEXT:\n{format_context(chunks)}\n\n"
            f"CHAT HISTORY:\n{format_history(self.history)}\n\n"
            f"QUESTION: {question}"
        )

        notify("write")
        try:
            reply = self.llm.invoke(
                [
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=user_prompt),
                ]
            )
        except Exception as exc:
            raise QAError(
                "The chat model failed. Is Ollama running and is "
                f"'{config.CHAT_MODEL}' pulled? Details: {exc}"
            ) from exc

        raw = str(reply.content).strip()
        found = not is_not_found(raw)
        cited = False
        unverified: List[str] = []
        if not found:
            answer = NOT_FOUND
            pages: List[int] = []
        else:
            retrieved = {
                int(c.metadata["page"])
                for c in chunks
                if "page" in c.metadata
            }
            model_pages = [
                p for p in extract_cited_pages(raw) if p in retrieved
            ]
            answer = strip_citations(raw) or raw
            unverified = find_unverified_numbers(
                answer,
                "\n".join(c.page_content for c in chunks),
                question,
            )
            if model_pages:
                pages, cited = model_pages, True
            else:
                pages = top_pages(chunks)

        self.history = trim_history(self.history + [(question, answer)])
        return {
            "answer": answer,
            "pages": pages,
            "found": found,
            "cited": cited,
            "unverified": unverified,
        }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python qa.py <collection_name>")
        sys.exit(1)

    try:
        qa = DocumentQA(sys.argv[1])
    except QAError as err:
        print(f"Error: {err}")
        sys.exit(1)

    print("Ask questions about the document. Type 'exit' to quit.\n")
    while True:
        try:
            q = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in {"exit", "quit"}:
            break
        try:
            result = qa.ask(q)
        except QAError as err:
            print(f"Error: {err}\n")
            continue
        print(f"\nDocuSense: {result['answer']}")
        if result["pages"]:
            label = "Sources" if result["cited"] else "Possible sources"
            print(f"{label}: pages {', '.join(map(str, result['pages']))}")
        if result["unverified"]:
            print(
                "WARNING: not found in the retrieved text, check the "
                f"document: {', '.join(result['unverified'])}"
            )
        print()