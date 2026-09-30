import logging
import threading

import numpy as np

from config import Config

logger = logging.getLogger(__name__)
_model = None
_lock = threading.Lock()


class EmbeddingError(Exception):
    pass


def _get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                try:
                    from sentence_transformers import SentenceTransformer

                    _model = SentenceTransformer(Config.EMBEDDING_MODEL)
                except Exception:
                    logger.exception("Failed to load embedding model")
                    raise EmbeddingError("Could not load the embedding model. Check your internet connection and try again.")
    return _model


def generate_embeddings(texts: list[str]) -> np.ndarray:
    """Return an (n, d) float32 array of L2-normalised embeddings."""
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    model = _get_model()
    try:
        vecs = model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True)
        return np.asarray(vecs, dtype=np.float32)
    except Exception:
        logger.exception("Embedding failed")
        raise EmbeddingError("Could not generate embeddings for this text.")


def generate_embedding(text: str) -> np.ndarray:
    return generate_embeddings([text])[0]
