import numpy as np

from services.vector_store import VectorStore


def rec(cid, doc, name):
    return {"chunk_id": cid, "document_id": doc, "filename": name, "text": name, "location": None, "metadata": {}}


def test_add_search_delete_persist(tmp_path):
    s = VectorStore(tmp_path)
    s.add_documents([rec(1, 1, "a"), rec(2, 2, "b")], np.array([[1, 0], [0, 1]], dtype=np.float32))
    top = s.search(np.array([1, 0], dtype=np.float32), k=1)
    assert top[0]["filename"] == "a" and top[0]["score"] > 0.99
    assert len(VectorStore(tmp_path)) == 2  # persisted
    s.delete_document(1)
    assert [r["filename"] for r in s.search(np.array([1, 0], dtype=np.float32), k=5)] == ["b"]
    s.rebuild_index([rec(3, 3, "c")], np.array([[1, 0]], dtype=np.float32))
    assert len(s) == 1


def test_min_score_filters(tmp_path):
    s = VectorStore(tmp_path)
    s.add_documents([rec(1, 1, "a")], np.array([[0, 1]], dtype=np.float32))
    assert s.search(np.array([1, 0], dtype=np.float32), min_score=0.5) == []
