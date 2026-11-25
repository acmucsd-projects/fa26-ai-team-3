from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

PERSIST_DIR = "data/chroma"
COLLECTION = "medlineplus_glossary"
MODEL_NAME = "all-MiniLM-L6-v2"

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _embedding_function():
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=MODEL_NAME
    )


def build_index(docs: list[str]) -> None:
    if not docs:
        raise ValueError("Cannot index an empty list.")

    client = chromadb.PersistentClient(
        path=str(PROJECT_ROOT / PERSIST_DIR)
    )

    existing = client.list_collections()
    names = {
        item if isinstance(item, str) else item.name
        for item in existing
    }

    if COLLECTION in names:
        client.delete_collection(name=COLLECTION)

    collection = client.create_collection(
        name=COLLECTION,
        embedding_function=_embedding_function()
    )

    collection.add(
        ids=[f"glossary-{i}" for i in range(len(docs))],
        documents=docs
    )


def retrieve(query: str, k: int = 3) -> list[str]:
    if not query.strip():
        raise ValueError("Query cannot be empty.")
    if k < 1:
        raise ValueError("k must be positive.")

    client = chromadb.PersistentClient(
        path=str(PROJECT_ROOT / PERSIST_DIR)
    )

    collection = client.get_collection(
        name=COLLECTION,
        embedding_function=_embedding_function()
    )

    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(k, collection.count()),
        include=["documents"]
    )

    return results["documents"][0] or []

