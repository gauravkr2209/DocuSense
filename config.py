"""Central configuration for DocuSense.

Choose the model provider with the DOCUSENSE_PROVIDER environment variable:
  gemini -> Google Gemini API (free tier, needs an API key). Default.
  ollama -> Ollama on this computer (fully local, slower on a CPU).
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CHROMA_DIR = BASE_DIR / "chroma_db"

PROVIDER = os.environ.get("DOCUSENSE_PROVIDER", "gemini").strip().lower()
if PROVIDER not in ("gemini", "ollama"):
    raise ValueError(
        f"DOCUSENSE_PROVIDER must be 'gemini' or 'ollama', not '{PROVIDER}'."
    )

# Demo mode for the public version: uploads are switched off.
DEMO_MODE = os.environ.get("DOCUSENSE_DEMO", "0") == "1"

# Ollama (local)
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_CHAT_MODEL = "llama3.2:3b"
OLLAMA_EMBEDDING_MODEL = "nomic-embed-text"

# Gemini (hosted). Chat models are tried in this order. If one is busy or
# over its free-tier quota, the next one answers. Override the whole list
# with GEMINI_CHAT_MODELS="model-a,model-b" (comma-separated).
DEFAULT_GEMINI_CHAT_MODELS = [
    "gemini-3.1-flash-lite",   # 500 requests/day
    "gemini-3.5-flash-lite",   # 500 requests/day
    "gemini-3.6-flash",        # 20 requests/day, last resort
    "gemini-3.8-flash",        # 20 requests/day, last resort
]
_custom = os.environ.get("GEMINI_CHAT_MODELS", "")
GEMINI_CHAT_MODELS = [m.strip() for m in _custom.split(",") if m.strip()] or DEFAULT_GEMINI_CHAT_MODELS
GEMINI_CHAT_MODEL = GEMINI_CHAT_MODELS[0]

# Embeddings stay fixed: documents indexed with one embedding model
# cannot be searched with another.
GEMINI_EMBEDDING_MODEL = os.environ.get("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")

# Active names, used by the rest of the code and the evaluation reports.
if PROVIDER == "gemini":
    CHAT_MODEL, EMBEDDING_MODEL = GEMINI_CHAT_MODEL, GEMINI_EMBEDDING_MODEL
else:
    CHAT_MODEL, EMBEDDING_MODEL = OLLAMA_CHAT_MODEL, OLLAMA_EMBEDDING_MODEL

# Text splitting
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150

# Q&A retrieval
RETRIEVAL_TOP_K = 6

# Summary settings
SUMMARY_GROUP_CHARS = 4000       # starting size of each chunk group
SUMMARY_MAX_GROUP_CHARS = 6000   # hard limit so a group fits the context
SUMMARY_MAX_GROUPS = 10          # cap on model calls in the map step
SUMMARY_NUM_CTX = 4096           # context window (Ollama only)

DATA_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)