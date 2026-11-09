import uuid

from app.ai.groq_client import ChatResult


def _create(client, auth, title="Binary trees", body="# Trees\n\nA tree has nodes.", **extra):
    return client.post("/api/notes", json={"title": title, "body": body, **extra}, headers=auth)


def test_create_list_and_open_a_note(client, auth):
    created = _create(client, auth)
    assert created.status_code == 201 and created.json()["revision"] == 1 and created.json()["word_count"] == 5
    listing = client.get("/api/notes", headers=auth).json()
    assert listing["total"] == 1 and "body" not in listing["items"][0] and listing["items"][0]["excerpt"].startswith("Trees")
    assert client.get(f"/api/notes/{created.json()['id']}", headers=auth).json()["body"].startswith("# Trees")


def test_note_names_are_unique_per_user_ignoring_case(client, auth):
    assert _create(client, auth, title="Graphs").status_code == 201
    clash = _create(client, auth, title="  graphs ")
    assert clash.status_code == 409 and "already have a note" in clash.json()["detail"]


def test_two_users_can_use_the_same_name_and_cannot_read_each_other(client, auth):
    note = _create(client, auth, title="Shared name").json()
    other = client.post("/api/auth/register", json={"name": "Other", "email": f"{uuid.uuid4().hex[:8]}@example.com", "password": "Passw0rdOK"}).json()
    headers = {"Authorization": f"Bearer {other['access_token']}"}
    assert _create(client, headers, title="Shared name").status_code == 201
    assert client.get(f"/api/notes/{note['id']}", headers=headers).status_code == 404
    assert client.delete(f"/api/notes/{note['id']}", headers=headers).status_code == 404


def test_blank_titles_are_rejected(client, auth):
    assert _create(client, auth, title="   ").status_code == 422


def test_update_requires_the_current_revision(client, auth):
    note = _create(client, auth, title="Stale test").json()
    body = {"title": "Stale test", "body": "new text", "pinned": False, "revision": note["revision"]}
    first = client.put(f"/api/notes/{note['id']}", json=body, headers=auth)
    assert first.status_code == 200 and first.json()["revision"] == 2
    stale = client.put(f"/api/notes/{note['id']}", json={**body, "body": "from an old tab"}, headers=auth)
    assert stale.status_code == 409 and "another tab" in stale.json()["detail"]
    assert client.get(f"/api/notes/{note['id']}", headers=auth).json()["body"] == "new text"


def test_renaming_to_an_existing_name_is_refused(client, auth):
    _create(client, auth, title="Alpha")
    beta = _create(client, auth, title="Beta").json()
    response = client.put(f"/api/notes/{beta['id']}", json={"title": "ALPHA", "body": "", "pinned": False, "revision": 1}, headers=auth)
    assert response.status_code == 409


def test_search_filters_pinning_and_order(client, auth):
    _create(client, auth, title="Recursion", body="base case and call stack")
    pinned = _create(client, auth, title="SQL joins", body="inner and outer joins", source="generated", subject="SQL").json()
    client.put(f"/api/notes/{pinned['id']}", json={"title": "SQL joins", "body": "inner and outer joins", "pinned": True, "revision": 1}, headers=auth)
    assert [n["title"] for n in client.get("/api/notes", headers=auth).json()["items"]][0] == "SQL joins"
    assert [n["title"] for n in client.get("/api/notes?q=call%20stack", headers=auth).json()["items"]] == ["Recursion"]
    assert [n["title"] for n in client.get("/api/notes?source=generated", headers=auth).json()["items"]] == ["SQL joins"]


def test_percent_signs_in_search_are_literal(client, auth):
    _create(client, auth, title="Discounts", body="a 50% rule")
    _create(client, auth, title="Other", body="no symbols here")
    found = client.get("/api/notes?q=50%25", headers=auth).json()["items"]
    assert [n["title"] for n in found] == ["Discounts"]


def test_delete_removes_the_note(client, auth):
    note = _create(client, auth, title="Temp").json()
    assert client.delete(f"/api/notes/{note['id']}", headers=auth).status_code == 204
    assert client.get(f"/api/notes/{note['id']}", headers=auth).status_code == 404


def test_study_generation_returns_a_draft_and_stores_nothing(client, auth, fake_ai):
    text = "```markdown\n# Deadlocks\n\n" + "## Overview\nA deadlock is a state where processes wait on each other forever. " * 12 + "\n```"
    ai = fake_ai(chat_replies=[text])
    response = client.post("/api/study/generate", json={"subject": "Operating system deadlocks", "depth": "Quick revision", "focus": "Banker's algorithm"}, headers=auth)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["markdown"].startswith("# Deadlocks") and not data["markdown"].rstrip().endswith("```") and data["title"] == "Operating system deadlocks: study notes"
    assert "Banker" in ai.chat_calls[0][1]["content"] and "Quick revision".lower() in ai.chat_calls[0][1]["content"]
    assert client.get("/api/notes", headers=auth).json()["total"] == 0


def test_study_flags_truncated_output(client, auth, fake_ai):
    class Truncating:
        configured, model, fast_model = True, "fake", "fake"

        def chat(self, messages, **kwargs):
            return ChatResult("# T\n\n" + "word " * 120, "fake", finish_reason="length")

    from app.core.deps import get_ai
    from app.main import app
    app.dependency_overrides[get_ai] = lambda: Truncating()
    try:
        data = client.post("/api/study/generate", json={"subject": "Topic here"}, headers=auth).json()
    finally:
        app.dependency_overrides.pop(get_ai, None)
    assert data["truncated"] is True and "length limit" in data["markdown"]


def test_study_rejects_tiny_model_output_and_bad_subjects(client, auth, fake_ai):
    fake_ai(chat_replies=["Sorry."])
    assert client.post("/api/study/generate", json={"subject": "Paging"}, headers=auth).status_code == 502
    assert client.post("/api/study/generate", json={"subject": "12"}, headers=auth).status_code == 422
    assert client.post("/api/study/generate", json={"subject": "Paging", "depth": "Huge"}, headers=auth).status_code == 422


def test_study_is_rate_limited_per_user(client, auth, fake_ai):
    fake_ai(chat_replies=["# T\n\n" + "word " * 120] * 8)
    codes = [client.post("/api/study/generate", json={"subject": "Caching"}, headers=auth).status_code for _ in range(9)]
    assert codes[:8] == [200] * 8 and codes[8] == 429
