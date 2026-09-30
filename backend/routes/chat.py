import json
from io import BytesIO
from pathlib import Path

from flask import Blueprint, current_app, g, jsonify, render_template, request, send_file

from db import get_db
from routes.auth import login_required, now
from services import rag_service
from services.embedding_service import EmbeddingError
from services.llm_service import LLMError
from services.pdf_export import build_answer_pdf
from services.vector_store import VectorStoreError, get_store

bp = Blueprint("chat", __name__)


@bp.get("/chat")
@login_required
def chat_page():
    return render_template("chat.html", conversation_id=request.args.get("c", type=int))


@bp.post("/api/chat")
@login_required
def chat():
    data = request.get_json(silent=True) or {}
    message, mode = (data.get("message") or "").strip(), data.get("mode", "knowledge_base")
    if not message:
        return jsonify(error="Please enter a question."), 400
    if len(message) > 4000:
        return jsonify(error="Question is too long (max 4000 characters)."), 400
    if mode not in rag_service.LABELS:
        return jsonify(error="Unknown mode."), 400
    conn, uid = get_db(), g.user["id"]
    conv_id, history = data.get("conversation_id"), []
    if conv_id:
        if not conn.execute("SELECT 1 FROM conversations WHERE id=? AND user_id=?", (conv_id, uid)).fetchone():
            return jsonify(error="Conversation not found."), 404
        rows = conn.execute("SELECT role,content FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT 6", (conv_id,)).fetchall()
        history = [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
    store = get_store(Path(current_app.config["KB_DIR"]) / "embeddings", uid)
    try:
        result = rag_service.answer_question(message, mode, store=store, history=history)
    except (EmbeddingError, VectorStoreError, LLMError) as e:
        return jsonify(error=str(e)), 502
    if not conv_id:
        conv_id = conn.execute("INSERT INTO conversations(user_id,title,created_at) VALUES(?,?,?)", (uid, message[:80], now())).lastrowid
    conn.execute("INSERT INTO messages(conversation_id,role,content,mode,created_at) VALUES(?,?,?,?,?)", (conv_id, "user", message, mode, now()))
    mid = conn.execute("INSERT INTO messages(conversation_id,role,content,mode,sources,created_at) VALUES(?,?,?,?,?,?)",
                       (conv_id, "assistant", result["answer"], mode, json.dumps(result["sources"]), now())).lastrowid
    conn.commit()
    return jsonify(conversation_id=conv_id, message_id=mid, **result)


@bp.get("/api/conversations")
@login_required
def conversations():
    rows = get_db().execute("SELECT id,title,created_at FROM conversations WHERE user_id=? ORDER BY id DESC", (g.user["id"],)).fetchall()
    return jsonify(conversations=[dict(r) for r in rows])


@bp.get("/api/conversations/<int:conv_id>")
@login_required
def conversation(conv_id):
    conn = get_db()
    conv = conn.execute("SELECT id,title,created_at FROM conversations WHERE id=? AND user_id=?", (conv_id, g.user["id"])).fetchone()
    if conv is None:
        return jsonify(error="Conversation not found."), 404
    msgs = conn.execute("SELECT id,role,content,mode,sources,created_at FROM messages WHERE conversation_id=? ORDER BY id", (conv_id,)).fetchall()
    out = [{**dict(m), "sources": json.loads(m["sources"] or "[]"), "label": rag_service.LABELS.get(m["mode"])} for m in msgs]
    return jsonify(conversation=dict(conv), messages=out)


@bp.get("/api/messages/<int:msg_id>/pdf")
@login_required
def export_pdf(msg_id):
    conn = get_db()
    msg = conn.execute("""SELECT m.* FROM messages m JOIN conversations c ON c.id=m.conversation_id
                          WHERE m.id=? AND c.user_id=? AND m.role='assistant'""", (msg_id, g.user["id"])).fetchone()
    if msg is None:
        return jsonify(error="Answer not found."), 404
    q = conn.execute("SELECT content FROM messages WHERE conversation_id=? AND id<? AND role='user' ORDER BY id DESC LIMIT 1",
                     (msg["conversation_id"], msg_id)).fetchone()
    pdf = build_answer_pdf(q["content"] if q else "", msg["content"], json.loads(msg["sources"] or "[]"),
                           rag_service.LABELS.get(msg["mode"], "Answer"))
    return send_file(BytesIO(pdf), mimetype="application/pdf", as_attachment=True, download_name="knowledge-vault-answer.pdf")
