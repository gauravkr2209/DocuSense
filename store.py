"""Document registry and summary cache for DocuSense (Phase 4)."""
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import config

REGISTRY_PATH = config.DATA_DIR / "registry.json"
UPLOAD_DIR = config.DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

Record = Dict[str, object]


def file_sha256(data: bytes) -> str:
    """Fingerprint of a file, used to detect duplicate uploads."""
    return hashlib.sha256(data).hexdigest()


def safe_filename(name: str) -> str:
    """Make an uploaded file name safe to store on disk."""
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(Path(name).name).stem)
    stem = stem.strip("._")
    return f"{stem[:60] or 'document'}.pdf"


def load_registry(path: Path = REGISTRY_PATH) -> List[Record]:
    """Read the list of ingested documents. A damaged file is set
    aside as .bad and an empty list is returned."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    try:
        path.replace(path.with_suffix(".bad"))
    except OSError:
        pass
    return []


def save_registry(records: List[Record], path: Path = REGISTRY_PATH) -> None:
    """Write the registry safely (temp file, then replace)."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(records, indent=2), encoding="utf-8")
    tmp.replace(path)


def add_record(record: Record, path: Path = REGISTRY_PATH) -> Record:
    records = load_registry(path)
    records.append(record)
    save_registry(records, path)
    return record


def find_by_hash(file_hash: str, path: Path = REGISTRY_PATH) -> Optional[Record]:
    for record in load_registry(path):
        if record.get("file_hash") == file_hash:
            return record
    return None


def get_record(collection: str, path: Path = REGISTRY_PATH) -> Optional[Record]:
    for record in load_registry(path):
        if record.get("collection_name") == collection:
            return record
    return None


def make_record(
    student_name: str,
    project_title: str,
    source_file: str,
    file_hash: str,
    result: Dict[str, object],
    provider: Optional[str] = None,
) -> Record:
    """Build a registry entry from an ingest_pdf() result. The provider
    records which model indexed the document, because embeddings from
    different providers cannot be mixed."""
    return {
        "collection_name": result["collection_name"],
        "document_id": result["document_id"],
        "student_name": student_name.strip(),
        "project_title": project_title.strip(),
        "source_file": source_file,
        "file_hash": file_hash,
        "pages": result["pages"],
        "chunks": result["chunks"],
        "provider": provider or str(result.get("provider", "ollama")),
        "created": datetime.now().isoformat(timespec="seconds"),
    }

def label(record: Record) -> str:
    """Text shown in the document picker."""
    student = record.get("student_name") or "Unknown student"
    title = record.get("project_title") or record.get("collection_name")
    return f"{student} - {title}"


def import_existing(
    path: Path = REGISTRY_PATH, chroma_dir: Path = config.CHROMA_DIR
) -> int:
    """Register collections created before the app existed
    (your Phase 1 test runs). Returns how many were added."""
    import chromadb

    client = chromadb.PersistentClient(path=str(chroma_dir))
    names = [getattr(c, "name", c) for c in client.list_collections()]
    known = {r.get("collection_name") for r in load_registry(path)}
    added = 0
    for name in names:
        if name in known:
            continue
        add_record(
            {
                "collection_name": name,
                "document_id": str(name).rsplit("_", 1)[-1],
                "student_name": "",
                "project_title": str(name),
                "source_file": "(imported)",
                "file_hash": "",
                "pages": None,
                "chunks": None,
                "created": datetime.now().isoformat(timespec="seconds"),
            },
            path,
        )
        added += 1
    return added


def summary_path(collection: str, data_dir: Optional[Path] = None) -> Path:
    """Same file name the command-line summarize.py already uses."""
    return (data_dir or config.DATA_DIR) / f"summary_{collection}.md"


def load_summary(collection: str, data_dir: Optional[Path] = None) -> Optional[str]:
    path = summary_path(collection, data_dir)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def save_summary(
    collection: str, markdown: str, data_dir: Optional[Path] = None
) -> Path:
    path = summary_path(collection, data_dir)
    path.write_text(markdown, encoding="utf-8")
    return path