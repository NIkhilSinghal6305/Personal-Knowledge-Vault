from conftest import signup


def test_pages_require_login(client):
    assert client.get("/dashboard").status_code == 302
    assert client.get("/api/documents").status_code == 401


def test_signup_login_logout(client):
    signup(client)
    assert client.get("/api/dashboard/stats").status_code == 200
    client.post("/api/auth/logout")
    assert client.get("/api/dashboard/stats").status_code == 401
    assert client.post("/api/auth/login", json={"email": "a@example.com", "password": "wrong"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "a@example.com", "password": "password123"}).status_code == 200


def test_duplicate_and_weak_password(client):
    signup(client)
    assert client.post("/api/auth/signup", json={"name": "x", "email": "a@example.com", "password": "password123"}).status_code == 400
    assert client.post("/api/auth/signup", json={"name": "x", "email": "b@example.com", "password": "short"}).status_code == 400


def test_password_is_hashed(app, client):
    signup(client)
    import db
    row = db.connect(app.config["DATABASE"]).execute("SELECT password_hash FROM users").fetchone()
    assert "password123" not in row[0]
