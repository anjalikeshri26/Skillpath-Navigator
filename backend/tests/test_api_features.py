import io

from docx import Document

from app.ai.groq_client import AINotConfigured

RESUME_LINES = [
    "Asha Rao", "asha@example.com | github.com/asha | linkedin.com/in/asha", "Education", "B.Tech in AI and Machine Learning, 2027",
    "Skills", "Python, SQL, Git", "Projects",
    "- Built a FastAPI service for resume parsing that cut manual review time by 40%",
    "- Developed a Flask dashboard backed by PostgreSQL with 12 REST endpoints",
]


def _docx_bytes(lines=RESUME_LINES):
    doc = Document()
    for line in lines:
        doc.add_paragraph(line)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def test_roadmap_is_built_on_first_request_and_completion_survives_rebuilds(client, auth):
    items = client.get("/api/roadmap", headers=auth).json()["items"]
    assert items and items[0]["position"] == 0 and items[0]["reason"]
    first = items[0]["id"]
    assert client.patch(f"/api/roadmap/{first}", json={"completed": True}, headers=auth).json()["completed"] is True
    rebuilt = client.post("/api/roadmap/rebuild", headers=auth).json()["items"]
    assert next(i for i in rebuilt if i["id"] == first)["completed"] is True


def test_changing_the_target_role_replans(client, auth):
    before = {i["skill_id"] for i in client.get("/api/roadmap", headers=auth).json()["items"]}
    client.patch("/api/profile", json={"target_role": "Cyber Security Analyst"}, headers=auth)
    after = {i["skill_id"] for i in client.get("/api/roadmap", headers=auth).json()["items"]}
    assert "cyber_security" in after and before != after


def test_resume_upload_analysis_and_roadmap_evidence(client, auth):
    response = client.post("/api/resume/analyze", headers=auth, data={"job_description": "Python, SQL and Java required"},
                           files={"file": ("resume.docx", _docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert response.status_code == 200, response.text
    analysis = response.json()["analysis"]
    assert 0 <= analysis["score"] <= 100 and analysis["jd_match"]["missing"] == ["Java"]
    assert client.get("/api/resume/latest", headers=auth).json()["id"] == response.json()["id"]


def test_resume_upload_validates_the_real_file_type(client, auth):
    response = client.post("/api/resume/analyze", headers=auth, files={"file": ("resume.pdf", b"this is not a pdf", "application/pdf")})
    assert response.status_code == 400


def test_resume_can_be_deleted(client, auth):
    rid = client.post("/api/resume/analyze", headers=auth, files={"file": ("r.docx", _docx_bytes(), "application/octet-stream")}).json()["id"]
    assert client.delete(f"/api/resume/{rid}", headers=auth).status_code == 204
    assert client.get("/api/resume/latest", headers=auth).json() is None


def test_dashboard_next_step_starts_with_the_resume(client, auth):
    assert client.get("/api/dashboard", headers=auth).json()["next_step"]["view"] == "resume"


def test_ai_features_explain_when_groq_is_not_configured(client, auth, monkeypatch):
    class Unconfigured:
        configured = False
        model = "none"

        def chat(self, *a, **k):
            raise AINotConfigured("The AI service is not configured. Add GROQ_API_KEY to backend/.env and restart.")

    from app.core.deps import get_ai
    from app.main import app

    app.dependency_overrides[get_ai] = lambda: Unconfigured()
    try:
        response = client.post("/api/assistant", json={"message": "Explain deadlocks"}, headers=auth)
    finally:
        app.dependency_overrides.pop(get_ai, None)
    assert response.status_code == 503 and "GROQ_API_KEY" in response.json()["detail"]


def test_assistant_uses_recent_history(client, auth, fake_ai):
    ai = fake_ai(chat_replies=["A deadlock is a circular wait."])
    body = {"message": "Why?", "history": [{"role": "user", "text": "Explain deadlocks"}, {"role": "assistant", "text": "Sure."}]}
    assert client.post("/api/assistant", json=body, headers=auth).json()["answer"].startswith("A deadlock")
    assert [m["content"] for m in ai.chat_calls[0]][-3:] == ["Explain deadlocks", "Sure.", "Why?"]


def test_interview_flow_with_evaluation(client, auth, fake_ai):
    evaluation = {"scores": {"technical_accuracy": 9, "depth": 3, "communication": "4", "structure": 0}, "overall_readiness": "bogus",
                  "strengths": ["Clear"], "improvements": ["Add detail"], "answer_notes": [{"question": "Q", "feedback": "Fine", "evidence": "I used indexes"}]}
    ai = fake_ai(chat_replies=["Tell me about indexes.", "Good. What about composite indexes?"], json_replies=[evaluation])
    started = client.post("/api/interview/sessions", json={"role": "Data Analyst", "difficulty": "Easy", "use_resume": False}, headers=auth).json()
    sid = started["session_id"]
    assert started["question"] == "Tell me about indexes."
    too_early = client.post(f"/api/interview/sessions/{sid}/evaluate", headers=auth)
    assert too_early.status_code == 400
    turn = client.post(f"/api/interview/sessions/{sid}/turns", json={"text": "An index is a separate sorted structure that lets the database find matching rows quickly instead of scanning the entire table, at the cost of slower writes."}, headers=auth)
    assert turn.json()["response"].startswith("Good")
    result = client.post(f"/api/interview/sessions/{sid}/evaluate", headers=auth).json()
    assert result["scores"] == {"technical_accuracy": 5, "depth": 3, "communication": 4, "structure": 1}
    assert result["overall_readiness"] == "developing"
    assert client.post(f"/api/interview/sessions/{sid}/turns", json={"text": "More"}, headers=auth).status_code == 409


def test_other_users_cannot_read_an_interview_session(client, auth, fake_ai):
    fake_ai(chat_replies=["First question?"])
    sid = client.post("/api/interview/sessions", json={"difficulty": "Easy", "use_resume": False}, headers=auth).json()["session_id"]
    stranger = client.post("/api/auth/register", json={"name": "Stranger", "email": f"s{sid}@example.com", "password": "Passw0rdOK"}).json()
    headers = {"Authorization": f"Bearer {stranger['access_token']}"}
    assert client.post(f"/api/interview/sessions/{sid}/turns", json={"text": "hello"}, headers=headers).status_code == 404
