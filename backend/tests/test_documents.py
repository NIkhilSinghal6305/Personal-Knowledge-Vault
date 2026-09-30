from io import BytesIO

from conftest import signup
from services.chunker import chunk_text
from services.document_processor import clean_text


def upload(client, name, data):
    return client.post("/api/documents/upload", data={"files": (BytesIO(data), name)}, content_type="multipart/form-data")


def test_chunking_overlap():
    chunks = chunk_text(" ".join(str(i) for i in range(100)), size=40, overlap=10)
    assert len(chunks) == 3 and chunks[1].split()[0] == "30"


def test_clean_text():
    assert clean_text("a  b\n\n\n\nc\x00") == "a b\n\nc"


def test_upload_lists_and_deletes(user):
    r = upload(user, "notes.txt", b"Normalization organizes data in a relational database.")
    assert r.status_code == 202
    doc = user.get("/api/documents").get_json()["documents"][0]
    assert doc["status"] == "ready" and doc["num_chunks"] == 1
    assert user.post(f"/api/documents/{doc['id']}/reprocess").status_code == 202
    assert user.delete(f"/api/documents/{doc['id']}").status_code == 200
    assert user.get("/api/documents").get_json()["documents"] == []


def test_bad_uploads(user):
    assert upload(user, "x.exe", b"abc").get_json()["results"][0]["error"]
    upload(user, "empty.txt", b"   ")
    upload(user, "bad.pdf", b"not a pdf")
    upload(user, "bad.docx", b"not a docx")
    docs = user.get("/api/documents").get_json()["documents"]
    assert len(docs) == 3 and all(d["status"] == "failed" and d["error"] for d in docs)


def test_users_are_isolated(app):
    a, b = app.test_client(), app.test_client()
    signup(a, "a@example.com"); signup(b, "b@example.com")
    upload(a, "secret.txt", b"Top secret database normalization notes.")
    doc_id = a.get("/api/documents").get_json()["documents"][0]["id"]
    assert b.get("/api/documents").get_json()["documents"] == []
    assert b.delete(f"/api/documents/{doc_id}").status_code == 404
    assert b.get("/api/search?q=normalization").get_json()["results"] == []
