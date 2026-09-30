from flask import Blueprint, current_app, g, jsonify, render_template

from db import get_db
from routes.auth import login_required

bp = Blueprint("dashboard", __name__)


@bp.get("/dashboard")
@login_required
def page():
    return render_template("dashboard.html")


@bp.get("/settings")
@login_required
def settings_page():
    c = current_app.config
    info = {"LLM": f"{c['QWEN_REPO']} / {c['QWEN_FILE']}", "Embedding model": c["EMBEDDING_MODEL"],
            "Chunk size (words)": c["CHUNK_WORDS"], "Chunk overlap": c["CHUNK_OVERLAP"],
            "Top K": c["TOP_K"], "Min similarity": c["MIN_SCORE"], "Context size": c["LLM_CONTEXT"]}
    return render_template("settings.html", info=info)


@bp.get("/api/dashboard/stats")
@login_required
def stats():
    conn, uid = get_db(), g.user["id"]
    one = lambda sql: conn.execute(sql, (uid,)).fetchone()[0]
    return jsonify(documents=one("SELECT COUNT(*) FROM documents WHERE user_id=?"),
                   chunks=one("SELECT COUNT(*) FROM document_chunks WHERE user_id=?"),
                   conversations=one("SELECT COUNT(*) FROM conversations WHERE user_id=?"))
