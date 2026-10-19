"""Central configuration for DocuSense."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CHROMA_DIR = BASE_DIR / "chroma_db"

# Provider and model choices live here so they can be swapped later.
EMBEDDING_PROVIDER = "ollama"
CHAT_PROVIDER = "ollama"
OLLAMA_BASE_URL = "http://localhost:11434"
EMBEDDING_MODEL = "nomic-embed-text"
CHAT_MODEL = "llama3.2:3b"

# Text splitting
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150

# Used in the Q&A phase
RETRIEVAL_TOP_K = 6

DATA_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

# Summary settings (sized for a 3B model on CPU)
SUMMARY_GROUP_CHARS = 4000    # target size of each chunk group
SUMMARY_MAX_GROUP_CHARS = 6000  # hard limit so a group fits the context
SUMMARY_MAX_GROUPS = 10        # cap on model calls in the map step
SUMMARY_NUM_CTX = 4096        # context window for summary calls