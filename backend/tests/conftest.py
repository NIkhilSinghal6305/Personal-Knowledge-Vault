import hashlib
import re
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from services import embedding_service, llm_service  # noqa: E402


class FakeModel:
    """Deterministic bag-of-words hashing embedder so tests need no model download."""

    def encode(self, texts, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True):
        out = np.zeros((len(texts), 512), dtype=np.float32)
        for i, t in enumerate(texts):
            for w in re.findall(r"[a-z]+", t.lower()):
                out[i, int(hashlib.md5(w.encode()).hexdigest(), 16) % 512] += 1
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        norms[norms == 0] = 1
        return out / norms


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(embedding_service, "_model", FakeModel())
    calls = []

    def fake_generate(messages, **kw):
        calls.append(messages)
        return "FAKE ANSWER"

    monkeypatch.setattr(llm_service, "generate", fake_generate)
    a = create_app({"TESTING": True, "DATABASE": str(tmp_path / "t.db"), "KB_DIR": tmp_path / "kb",
                    "INGEST_SYNC": True, "SECRET_KEY": "test"})
    a.llm_calls = calls
    return a


@pytest.fixture
def client(app):
    return app.test_client()


def signup(client, email="a@example.com"):
    r = client.post("/api/auth/signup", json={"name": "Ada", "email": email, "password": "password123"})
    assert r.status_code == 201
    return client


@pytest.fixture
def user(client):
    return signup(client)
