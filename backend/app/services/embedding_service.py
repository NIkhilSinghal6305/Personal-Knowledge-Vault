"""
Embedding service using Sentence Transformers.
Generates vector embeddings for text chunks.
"""
from typing import List
from sentence_transformers import SentenceTransformer
from app.config import get_settings

settings = get_settings()

# Global model instance (loaded once)
_model = None


def get_embedding_model() -> SentenceTransformer:
    """Lazy-load the embedding model."""
    global _model
    if _model is None:
        print(f"Loading embedding model: {settings.EMBEDDING_MODEL}...")
        _model = SentenceTransformer(settings.EMBEDDING_MODEL)
        print("Embedding model loaded successfully.")
    return _model


def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for a list of text strings.
    Returns a list of embedding vectors.
    """
    if not texts:
        return []
    model = get_embedding_model()
    embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    return embeddings.tolist()


def generate_single_embedding(text: str) -> List[float]:
    """Generate an embedding for a single text string."""
    if not text:
        return []
    model = get_embedding_model()
    embedding = model.encode([text], show_progress_bar=False, convert_to_numpy=True)
    return embedding[0].tolist()
