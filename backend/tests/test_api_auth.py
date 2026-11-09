import uuid


def _register(client, **overrides):
    body = {"name": "Asha Rao", "email": f"{uuid.uuid4().hex[:8]}@example.com", "password": "Passw0rdOK", **overrides}
    return client.post("/api/auth/register", json=body)


def test_register_then_login_and_fetch_profile(client):
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    assert _register(client, email=email).status_code == 200
    login = client.post("/api/auth/login", json={"email": email, "password": "Passw0rdOK"})
    assert login.status_code == 200
    me = client.get("/api/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert me.json()["email"] == email


def test_password_policy_is_enforced(client):
    assert _register(client, password="short1").status_code == 422
    assert _register(client, password="onlyletters").status_code == 422
    assert _register(client, password="12345678").status_code == 422


def test_duplicate_email_is_rejected(client):
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    assert _register(client, email=email).status_code == 200
    assert _register(client, email=email).status_code == 409


def test_login_is_rate_limited_after_repeated_failures(client):
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    _register(client, email=email)
    codes = [client.post("/api/auth/login", json={"email": email, "password": "wrong-pass1"}).status_code for _ in range(6)]
    assert codes[:5] == [401] * 5 and codes[5] == 429


def test_protected_routes_require_a_valid_token(client):
    assert client.get("/api/dashboard").status_code == 401
    assert client.get("/api/me", headers={"Authorization": "Bearer not-a-token"}).status_code == 401


def test_admin_routes_reject_normal_users(client, auth):
    assert client.get("/api/admin/overview", headers=auth).status_code == 403


def test_profile_rejects_unknown_roles(client, auth):
    assert client.patch("/api/profile", json={"target_role": "Wizard"}, headers=auth).status_code == 422
    ok = client.patch("/api/profile", json={"target_role": "Data Analyst", "skill_level": "Intermediate"}, headers=auth)
    assert ok.status_code == 200 and ok.json()["target_role"] == "Data Analyst"
