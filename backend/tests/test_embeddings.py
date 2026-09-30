import numpy as np

from services import embedding_service


def test_embeddings_are_normalised(app):
    v = embedding_service.generate_embeddings(["hello world", "database normalization"])
    assert v.shape == (2, 512) and v.dtype == np.float32
    assert np.allclose(np.linalg.norm(v, axis=1), 1.0)
    assert embedding_service.generate_embedding("hello").shape == (512,)
    assert embedding_service.generate_embeddings([]).shape[0] == 0
