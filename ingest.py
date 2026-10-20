"""PDF ingestion pipeline for DocuSense (provider-aware)."""
import re
import sys
import uuid
from pathlib import Path
from typing import Dict, List

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

import config
from providers import (
    explain_error,
    missing_key_message,
    provider_ready,
)
from providers import get_embeddings as build_embeddings


class IngestionError(Exception):
    """Raised when a PDF cannot be ingested."""


def clean_text(text: str) -> str:
    """Normalize whitespace while keeping paragraph breaks."""
    text = re.sub(r"[ \t]+", " ", text)
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def load_pdf(pdf_path: str) -> List[Document]:
    """Read a PDF page by page, keeping 1-based page numbers."""
    path = Path(pdf_path)
    if not path.exists() or not path.is_file():
        raise IngestionError(f"PDF file not found: {path}")
    if path.suffix.lower() != ".pdf":
        raise IngestionError("The file must be a PDF.")

    try:
        reader = PdfReader(str(path))
        pages = [
            (index + 1, page.extract_text() or "")
            for index, page in enumerate(reader.pages)
        ]
    except Exception as exc:
        raise IngestionError(
            f"Could not read the PDF. It may be damaged: {exc}"
        ) from exc

    documents: List[Document] = []
    for page_number, raw_text in pages:
        text = clean_text(raw_text)
        if not text:
            continue
        documents.append(
            Document(
                page_content=text,
                metadata={"source": path.name, "page": page_number},
            )
        )

    if not documents:
        raise IngestionError(
            "No extractable text was found. The PDF may be empty or "
            "scanned. OCR is not implemented."
        )
    return documents


def split_documents(documents: List[Document]) -> List[Document]:
    """Split pages into overlapping chunks, keeping metadata."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    if not chunks:
        raise IngestionError("Text splitting produced no chunks.")
    return chunks


def get_embeddings():
    """Embedding model for the active provider."""
    if not provider_ready():
        raise IngestionError(missing_key_message())
    try:
        return build_embeddings()
    except Exception as exc:
        raise IngestionError(
            explain_error(exc, "Could not start the embedding model.")
        ) from exc


def make_collection_name(pdf_name: str, doc_id: str) -> str:
    """Build a valid, unique Chroma collection name."""
    stem = re.sub(r"[^a-zA-Z0-9]+", "_", Path(pdf_name).stem).strip("_")
    return f"doc_{stem[:30]}_{doc_id}"


def ingest_pdf(pdf_path: str) -> Dict[str, object]:
    """Run the full pipeline: load, clean, split, embed, store."""
    documents = load_pdf(pdf_path)
    chunks = split_documents(documents)

    doc_id = uuid.uuid4().hex[:8]
    collection_name = make_collection_name(Path(pdf_path).name, doc_id)

    try:
        store = Chroma.from_documents(
            documents=chunks,
            embedding=get_embeddings(),
            collection_name=collection_name,
            persist_directory=str(config.CHROMA_DIR),
        )
        vector_count = store._collection.count()
    except IngestionError:
        raise
    except Exception as exc:
        raise IngestionError(
            explain_error(exc, "Embedding or storage failed.")
        ) from exc

    return {
        "document_id": doc_id,
        "collection_name": collection_name,
        "pages": len(documents),
        "chunks": len(chunks),
        "vectors": vector_count,
        "provider": config.PROVIDER,
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python ingest.py data/sample.pdf")
        sys.exit(1)
    try:
        result = ingest_pdf(sys.argv[1])
    except IngestionError as err:
        print(f"Ingestion failed: {err}")
        sys.exit(1)

    print("Ingestion complete")
    for key, value in result.items():
        print(f"  {key}: {value}")