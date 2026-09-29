"""
Vector store service using ChromaDB.
Handles storing and querying document embeddings.
"""
import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List, Optional, Dict
from app.config import get_settings
from app.services.embedding_service import generate_embeddings, generate_single_embedding

settings = get_settings()

# Global ChromaDB client
_chroma_client = None
_collection_cache = {}


def get_chroma_client() -> chromadb.Client:
    """Get or create the ChromaDB persistent client."""
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    return _chroma_client


def get_user_collection(user_id: int) -> chromadb.Collection:
    """Get or create a ChromaDB collection scoped to a specific user."""
    collection_name = f"user_{user_id}_vault"
    if collection_name not in _collection_cache:
        client = get_chroma_client()
        _collection_cache[collection_name] = client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection_cache[collection_name]


def store_document_chunks(
    user_id: int,
    document_id: int,
    chunks: List[dict],
) -> int:
    """
    Store document chunks with their embeddings in ChromaDB.
    Returns the number of chunks stored.
    """
    if not chunks:
        return 0

    collection = get_user_collection(user_id)
    texts = [chunk["text"] for chunk in chunks]
    embeddings = generate_embeddings(texts)

    ids = [f"doc_{document_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = []
    for chunk in chunks:
        meta = chunk.get("metadata", {})
        meta["document_id"] = str(document_id)
        meta["user_id"] = str(user_id)
        metadatas.append(meta)

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas,
    )

    return len(chunks)


def query_similar_chunks(
    user_id: int,
    query_text: str,
    n_results: int = 5,
    document_ids: Optional[List[int]] = None,
) -> List[Dict]:
    """
    Query ChromaDB for the most similar chunks to the query text.
    Optionally filter by specific document IDs.
    Returns a list of dicts with text, metadata, and distance.
    """
    collection = get_user_collection(user_id)
    query_embedding = generate_single_embedding(query_text)

    where_filter = None
    if document_ids:
        str_ids = [str(did) for did in document_ids]
        if len(str_ids) == 1:
            where_filter = {"document_id": str_ids[0]}
        else:
            where_filter = {"document_id": {"$in": str_ids}}

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )

    parsed = []
    if results and results["documents"]:
        for i, doc_text in enumerate(results["documents"][0]):
            parsed.append(
                {
                    "text": doc_text,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0.0,
                }
            )

    return parsed


def delete_document_chunks(user_id: int, document_id: int) -> None:
    """Delete all chunks for a specific document from ChromaDB."""
    collection = get_user_collection(user_id)
    # Get all IDs for this document
    try:
        results = collection.get(
            where={"document_id": str(document_id)},
            include=[],
        )
        if results and results["ids"]:
            collection.delete(ids=results["ids"])
    except Exception:
        # Collection might not exist or be empty
        pass


def semantic_search(
    user_id: int,
    query: str,
    n_results: int = 10,
) -> List[Dict]:
    """
    Perform semantic search across all user documents.
    Returns results sorted by relevance.
    """
    return query_similar_chunks(user_id, query, n_results=n_results)
