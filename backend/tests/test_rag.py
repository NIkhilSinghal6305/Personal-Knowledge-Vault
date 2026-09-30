from io import BytesIO

from services.rag_service import NOT_FOUND

DOC = b"Database normalization is the process of organizing data in a relational database to reduce redundancy."


def ingest(client):
    client.post("/api/documents/upload", data={"files": (BytesIO(DOC), "DBMS_Notes.txt")}, content_type="multipart/form-data")


def test_kb_answer_has_real_sources(app, user):
    ingest(user)
    d = user.post("/api/chat", json={"message": "Explain database normalization", "mode": "knowledge_base"}).get_json()
    assert d["answer"] == "FAKE ANSWER" and d["label"] == "Knowledge Base Answer"
    assert [s["filename"] for s in d["sources"]] == ["DBMS_Notes.txt"]
    assert "redundancy" in app.llm_calls[-1][-1]["content"]  # retrieved chunk was sent to the model


def test_kb_not_found_skips_llm(app, user):
    ingest(user)
    d = user.post("/api/chat", json={"message": "quantum chromodynamics gluons", "mode": "knowledge_base"}).get_json()
    assert d["answer"] == NOT_FOUND and d["sources"] == [] and app.llm_calls == []


def test_general_mode_has_no_sources(user):
    d = user.post("/api/chat", json={"message": "What is Python?", "mode": "general"}).get_json()
    assert d["label"] == "General AI Answer" and d["sources"] == []


def test_conversations_and_pdf(user):
    ingest(user)
    d = user.post("/api/chat", json={"message": "Explain database normalization"}).get_json()
    convs = user.get("/api/conversations").get_json()["conversations"]
    assert convs[0]["id"] == d["conversation_id"]
    msgs = user.get(f"/api/conversations/{d['conversation_id']}").get_json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    pdf = user.get(f"/api/messages/{d['message_id']}/pdf")
    assert pdf.status_code == 200 and pdf.data.startswith(b"%PDF")


def test_invalid_input(user):
    assert user.post("/api/chat", json={"message": ""}).status_code == 400
    assert user.post("/api/chat", json={"message": "hi", "mode": "bogus"}).status_code == 400
