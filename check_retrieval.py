"""Quick retrieval check against a stored collection."""
import sys

from langchain_chroma import Chroma

import config
from ingest import get_embeddings

collection_name, query = sys.argv[1], sys.argv[2]

store = Chroma(
    collection_name=collection_name,
    embedding_function=get_embeddings(),
    persist_directory=str(config.CHROMA_DIR),
)

for doc in store.similarity_search(query, k=config.RETRIEVAL_TOP_K):
    print(f"--- page {doc.metadata['page']} ---")
    print(doc.page_content[:300], "\n")