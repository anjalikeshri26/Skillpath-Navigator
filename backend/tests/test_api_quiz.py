from datetime import timedelta

from app.core.clock import utcnow
from app.core.database import SessionLocal
from app.models import QuizSession


def _start(client, auth, **body):
    return client.post("/api/quiz/sessions", json={"topic": "Mixed", "difficulty": "Adaptive", "limit": 6, **body}, headers=auth)


def test_session_serves_shuffled_options_without_answers(client, auth):
    data = _start(client, auth).json()
    assert len(data["questions"]) == 6
    assert all(len(q["options"]) == 4 and "answer_index" not in q for q in data["questions"])


def test_submit_with_unanswered_questions_is_accepted(client, auth):
    data = _start(client, auth).json()
    answers = [{"question_id": q["id"], "selected": None} for q in data["questions"]]
    result = client.post(f"/api/quiz/sessions/{data['session_id']}/submit", json={"answers": answers}, headers=auth)
    assert result.status_code == 200
    assert result.json()["skipped"] == 6 and result.json()["score"] == 0


def test_omitting_answers_counts_them_as_skipped(client, auth):
    data = _start(client, auth).json()
    result = client.post(f"/api/quiz/sessions/{data['session_id']}/submit", json={"answers": []}, headers=auth).json()
    assert result["skipped"] == 6


def test_correctness_follows_the_shuffled_positions(client, auth):
    data = _start(client, auth).json()
    answers = [{"question_id": q["id"], "selected": 0} for q in data["questions"]]
    result = client.post(f"/api/quiz/sessions/{data['session_id']}/submit", json={"answers": answers}, headers=auth).json()
    for item in result["details"]:
        assert item["is_correct"] == (item["correct_position"] == 0)
    assert result["correct"] == sum(d["is_correct"] for d in result["details"])


def test_duplicate_answers_are_rejected(client, auth):
    data = _start(client, auth).json()
    qid = data["questions"][0]["id"]
    body = {"answers": [{"question_id": qid, "selected": 0}, {"question_id": qid, "selected": 0}]}
    assert client.post(f"/api/quiz/sessions/{data['session_id']}/submit", json=body, headers=auth).status_code == 422


def test_answers_for_unserved_questions_are_rejected(client, auth):
    data = _start(client, auth).json()
    served = {q["id"] for q in data["questions"]}
    foreign = next(i for i in range(1, 500) if i not in served)
    body = {"answers": [{"question_id": foreign, "selected": 0}]}
    assert client.post(f"/api/quiz/sessions/{data['session_id']}/submit", json=body, headers=auth).status_code == 400


def test_a_session_cannot_be_submitted_twice_or_by_someone_else(client, auth):
    data = _start(client, auth).json()
    url = f"/api/quiz/sessions/{data['session_id']}/submit"
    assert client.post(url, json={"answers": []}, headers=auth).status_code == 200
    assert client.post(url, json={"answers": []}, headers=auth).status_code == 409
    other = client.post("/api/auth/register", json={"name": "Other", "email": "other-quiz@example.com", "password": "Passw0rdOK"})
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"} if other.status_code == 200 else None
    if other_headers:
        assert client.post(url, json={"answers": []}, headers=other_headers).status_code == 404


def test_expired_sessions_are_rejected(client, auth):
    data = _start(client, auth).json()
    with SessionLocal() as db:
        session = db.get(QuizSession, data["session_id"])
        session.expires_at = utcnow() - timedelta(hours=1)
        db.commit()
    assert client.post(f"/api/quiz/sessions/{data['session_id']}/submit", json={"answers": []}, headers=auth).status_code == 410


def test_questions_are_only_used_up_when_a_test_is_submitted(client, auth):
    first = _start(client, auth, topic="SQL", difficulty="Easy", limit=3)
    assert first.status_code == 200
    abandoned = _start(client, auth, topic="SQL", difficulty="Easy", limit=3)
    assert abandoned.status_code == 200  # nothing was consumed by the unsubmitted first test
    client.post(f"/api/quiz/sessions/{first.json()['session_id']}/submit", json={"answers": []}, headers=auth)
    exhausted = _start(client, auth, topic="SQL", difficulty="Easy", limit=3)
    assert exhausted.status_code == 404 and "used up" in exhausted.json()["detail"]


def test_submission_updates_mastery_and_history(client, auth):
    data = _start(client, auth, topic="Python", difficulty="Easy", limit=3).json()
    result = client.post(f"/api/quiz/sessions/{data['session_id']}/submit", json={"answers": []}, headers=auth).json()
    change = result["mastery_changes"][0]
    assert change["topic"] == "Python" and change["after"] < change["before"]
    assert client.get("/api/quiz/history", headers=auth).json()[0]["id"] == data["session_id"]
    assert client.get("/api/quiz/mastery", headers=auth).json()[0]["topic"] == "Python"


def test_three_reports_move_a_question_out_of_circulation(client, auth):
    qid = _start(client, auth).json()["questions"][0]["id"]
    statuses = []
    for i in range(3):
        reg = client.post("/api/auth/register", json={"name": "Reporter", "email": f"reporter{i}-{qid}@example.com", "password": "Passw0rdOK"})
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
        statuses.append(client.post(f"/api/quiz/questions/{qid}/report", json={"reason": "wrong_answer"}, headers=headers).json()["status"])
    assert statuses[-1] == "under_review"


def test_ai_generation_keeps_only_verified_questions(client, auth, fake_ai):
    good = {"prompt": "Which OSI layer is responsible for end-to-end delivery and port numbers?", "options": ["Transport", "Network", "Session", "Physical"], "answer_index": 0, "explanation": "Transport."}
    wrong_key = {"prompt": "Which protocol is connectionless and used by DNS queries by default?", "options": ["TCP", "UDP", "FTP", "SMTP"], "answer_index": 0, "explanation": "UDP."}
    malformed = {"prompt": "Too short", "options": ["a", "b"], "answer_index": 1}
    ai = fake_ai(json_replies=[{"questions": [good, wrong_key, malformed]}, {"answers": [{"id": 0, "answer_index": 0}, {"id": 1, "answer_index": 1}]}])
    response = _start(client, auth, topic="Computer Networks", difficulty="Advanced", limit=3)
    assert len(ai.json_calls) == 2
    served = [q["prompt"] for q in response.json()["questions"]]
    assert good["prompt"] in served and wrong_key["prompt"] not in served
