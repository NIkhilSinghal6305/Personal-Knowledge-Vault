"""Persistent NumPy vector store (cosine similarity via dot product on normalised vectors), one per user."""
import json
import logging
import threading
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


class VectorStoreError(Exception):
    pass


class VectorStore:
    def __init__(self, directory):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.vectors = np.zeros((0, 0), dtype=np.float32)
        self.records: list[dict] = []
        self._load()

    def _load(self) -> None:
        vec_path, rec_path = self.dir / "vectors.npy", self.dir / "records.json"
        if vec_path.exists() and rec_path.exists():
            try:
                self.vectors = np.load(vec_path)
                self.records = json.loads(rec_path.read_text(encoding="utf-8"))
            except Exception:
                logger.exception("Corrupt vector store; starting empty")
                self.vectors, self.records = np.zeros((0, 0), dtype=np.float32), []

    def _save(self) -> None:
        tmp_v, tmp_r = self.dir / "vectors.tmp", self.dir / "records.tmp"
        with open(tmp_v, "wb") as f:
            np.save(f, self.vectors)
        tmp_r.write_text(json.dumps(self.records), encoding="utf-8")
        tmp_v.replace(self.dir / "vectors.npy")
        tmp_r.replace(self.dir / "records.json")

    def __len__(self) -> int:
        return len(self.records)

    def add_documents(self, records: list[dict], embeddings: np.ndarray) -> None:
        """records: dicts with chunk_id, document_id, filename, text, location, metadata."""
        if len(records) != len(embeddings):
            raise VectorStoreError("Records and embeddings do not match.")
        if not records:
            return
        with self._lock:
            if self.vectors.size and self.vectors.shape[1] != embeddings.shape[1]:
                raise VectorStoreError("Embedding size changed. Rebuild the index from Settings.")
            self.vectors = embeddings.astype(np.float32) if not self.vectors.size else np.vstack([self.vectors, embeddings])
            self.records.extend(records)
            self._save()

    def search(self, query_vec: np.ndarray, k: int = 4, min_score: float = 0.0) -> list[dict]:
        with self._lock:
            if not self.records:
                return []
            try:
                scores = self.vectors @ np.asarray(query_vec, dtype=np.float32)
            except ValueError:
                raise VectorStoreError("Index and query embeddings are incompatible. Rebuild the index from Settings.")
            order = np.argsort(-scores)[:k]
            return [{**self.records[i], "score": float(scores[i])} for i in order if scores[i] >= min_score]

    def delete_document(self, document_id: int) -> None:
        with self._lock:
            keep = [i for i, r in enumerate(self.records) if r["document_id"] != document_id]
            if len(keep) == len(self.records):
                return
            self.records = [self.records[i] for i in keep]
            self.vectors = self.vectors[keep] if keep else np.zeros((0, 0), dtype=np.float32)
            self._save()

    def rebuild_index(self, records: list[dict], embeddings: np.ndarray) -> None:
        with self._lock:
            self.records = list(records)
            self.vectors = embeddings.astype(np.float32) if records else np.zeros((0, 0), dtype=np.float32)
            self._save()


_stores: dict[str, VectorStore] = {}
_stores_lock = threading.Lock()


def get_store(base_dir, user_id: int) -> VectorStore:
    path = Path(base_dir) / str(user_id)
    key = str(path)
    with _stores_lock:
        if key not in _stores:
            _stores[key] = VectorStore(path)
        return _stores[key]
