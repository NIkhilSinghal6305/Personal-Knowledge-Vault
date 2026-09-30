import os
import threading
from pathlib import Path

from flask import Blueprint, current_app, g, jsonify, render_template, request

from db import get_db
from routes.auth import login_required, now
from services import embedding_service
from services.ingestion import document_path, ingest_document
from services.vector_store import VectorStoreError, get_store

bp = Blueprint("documents", __name__)
ALLOWED = {"pdf", "docx", "txt"}


def _store():
    return get_store(Path(current_app.config["KB_DIR"]) / "embeddings", g.user["id"])


def _own(doc_id):
    return get_db().execute("SELECT * FROM documents WHERE id=? AND user_id=?", (doc_id, g.user["id"])).fetchone()


def _start_ingest(doc_id):
    cfg = {k: current_app.config[k] for k in ("DATABASE", "KB_DIR", "CHUNK_WORDS", "CHUNK_OVERLAP")}
    if current_app.config["INGEST_SYNC"]:
        ingest_document(cfg, doc_id)
    else:
        threading.Thread(target=ingest_document, args=(cfg, doc_id), daemon=True).start()


@bp.get("/knowledge-base")
@login_required
def kb_page():
    return render_template("knowledge_base.html")


@bp.get("/documents")
@login_required
def documents_page():
    return render_template("documents.html")


@bp.get("/api/documents")
@login_required
def list_documents():
    q = request.args.get("q", "").strip().lower()
    rows = get_db().execute("SELECT * FROM documents WHERE user_id=? ORDER BY id DESC", (g.user["id"],)).fetchall()
    docs = [dict(r) for r in rows if q in r["filename"].lower()]
    return jsonify(documents=docs)


@bp.get("/api/documents/<int:doc_id>")
@login_required
def document_info(doc_id):
    doc = _own(doc_id)
    if doc is None:
        return jsonify(error="Document not found."), 404
    chunks = get_db().execute("SELECT chunk_index,location,text FROM document_chunks WHERE document_id=? ORDER BY chunk_index LIMIT 3",
                              (doc_id,)).fetchall()
    return jsonify(document=dict(doc), preview=[{**dict(c), "text": c["text"][:300]} for c in chunks])


@bp.post("/api/documents/upload")
@login_required
def upload():
    files = request.files.getlist("files")
    if not files:
        return jsonify(error="No files provided."), 400
    conn, results = get_db(), []
    for f in files:
        name = os.path.basename(f.filename or "")
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if ext not in ALLOWED:
            results.append({"filename": name, "error": "Unsupported file type. Use PDF, DOCX or TXT."})
            continue
        cur = conn.execute("INSERT INTO documents(user_id,filename,file_type,status,created_at) VALUES(?,?,?,?,?)",
                           (g.user["id"], name, ext, "queued", now()))
        conn.commit()
        path = document_path(current_app.config["KB_DIR"], g.user["id"], cur.lastrowid, ext)
        path.parent.mkdir(parents=True, exist_ok=True)
        f.save(path)
        _start_ingest(cur.lastrowid)
        results.append({"id": cur.lastrowid, "filename": name})
    return jsonify(results=results), 202


@bp.post("/api/documents/<int:doc_id>/reprocess")
@login_required
def reprocess(doc_id):
    doc = _own(doc_id)
    if doc is None:
        return jsonify(error="Document not found."), 404
    if not document_path(current_app.config["KB_DIR"], g.user["id"], doc_id, doc["file_type"]).exists():
        return jsonify(error="The original file is missing. Upload it again."), 410
    get_db().execute("UPDATE documents SET status='queued', error=NULL WHERE id=?", (doc_id,))
    get_db().commit()
    _start_ingest(doc_id)
    return jsonify(ok=True), 202


@bp.delete("/api/documents/<int:doc_id>")
@login_required
def delete(doc_id):
    doc = _own(doc_id)
    if doc is None:
        return jsonify(error="Document not found."), 404
    _store().delete_document(doc_id)
    document_path(current_app.config["KB_DIR"], g.user["id"], doc_id, doc["file_type"]).unlink(missing_ok=True)
    get_db().execute("DELETE FROM documents WHERE id=?", (doc_id,))
    get_db().commit()
    return jsonify(ok=True)


@bp.get("/api/search")
@login_required
def search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify(error="Enter a search query."), 400
    doc_id = request.args.get("document_id", type=int)
    try:
        hits = _store().search(embedding_service.generate_embedding(q), k=50 if doc_id else 8, min_score=0.15)
    except (embedding_service.EmbeddingError, VectorStoreError) as e:
        return jsonify(error=str(e)), 502
    if doc_id:
        hits = [h for h in hits if h["document_id"] == doc_id][:8]
    return jsonify(results=[{"document_id": h["document_id"], "filename": h["filename"], "location": h["location"],
                             "score": round(h["score"], 3), "text": h["text"][:300]} for h in hits])


@bp.post("/api/documents/rebuild")
@login_required
def rebuild():
    rows = get_db().execute(
        """SELECT c.id AS chunk_id, c.document_id, d.filename, c.text, c.location, c.chunk_index
           FROM document_chunks c JOIN documents d ON d.id=c.document_id
           WHERE c.user_id=? AND d.status='ready' ORDER BY c.id""", (g.user["id"],)).fetchall()
    records = [{"chunk_id": r["chunk_id"], "document_id": r["document_id"], "filename": r["filename"], "text": r["text"],
                "location": r["location"], "metadata": {"chunk_index": r["chunk_index"]}} for r in rows]
    try:
        _store().rebuild_index(records, embedding_service.generate_embeddings([r["text"] for r in records]))
    except (embedding_service.EmbeddingError, VectorStoreError) as e:
        return jsonify(error=str(e)), 502
    return jsonify(ok=True, chunks=len(records))
