import re
from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_db

bp = Blueprint("auth", __name__)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@bp.before_app_request
def load_user():
    uid = session.get("user_id")
    g.user = get_db().execute("SELECT id,email,name FROM users WHERE id=?", (uid,)).fetchone() if uid else None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            if request.path.startswith("/api/"):
                return jsonify(error="Please log in."), 401
            return redirect(url_for("auth.login_page"))
        return view(*args, **kwargs)
    return wrapped


def _signup(name, email, password):
    name, email, password = (name or "").strip(), (email or "").strip().lower(), password or ""
    if not name or not EMAIL_RE.match(email):
        return None, "Enter your name and a valid email."
    if len(password) < 8:
        return None, "Password must be at least 8 characters."
    conn = get_db()
    if conn.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
        return None, "An account with this email already exists."
    cur = conn.execute("INSERT INTO users(email,name,password_hash,created_at) VALUES(?,?,?,?)",
                       (email, name, generate_password_hash(password), now()))
    conn.commit()
    return cur.lastrowid, None


def _authenticate(email, password):
    row = get_db().execute("SELECT * FROM users WHERE email=?", ((email or "").strip().lower(),)).fetchone()
    if row and check_password_hash(row["password_hash"], password or ""):
        return row["id"], None
    return None, "Invalid email or password."


def _start(uid):
    session.clear()
    session.permanent = True
    session["user_id"] = uid


@bp.route("/login", methods=["GET", "POST"])
def login_page():
    error = None
    if request.method == "POST":
        uid, error = _authenticate(request.form.get("email"), request.form.get("password"))
        if uid:
            _start(uid)
            return redirect(url_for("dashboard.page"))
    return render_template("login.html", error=error)


@bp.route("/signup", methods=["GET", "POST"])
def signup_page():
    error = None
    if request.method == "POST":
        uid, error = _signup(request.form.get("name"), request.form.get("email"), request.form.get("password"))
        if uid:
            _start(uid)
            return redirect(url_for("dashboard.page"))
    return render_template("signup.html", error=error)


@bp.route("/logout", methods=["GET", "POST"])
def logout_page():
    session.clear()
    return redirect(url_for("auth.login_page"))


@bp.post("/api/auth/signup")
def api_signup():
    d = request.get_json(silent=True) or {}
    uid, error = _signup(d.get("name"), d.get("email"), d.get("password"))
    if error:
        return jsonify(error=error), 400
    _start(uid)
    return jsonify(ok=True), 201


@bp.post("/api/auth/login")
def api_login():
    d = request.get_json(silent=True) or {}
    uid, error = _authenticate(d.get("email"), d.get("password"))
    if error:
        return jsonify(error=error), 401
    _start(uid)
    return jsonify(ok=True)


@bp.post("/api/auth/logout")
def api_logout():
    session.clear()
    return jsonify(ok=True)
