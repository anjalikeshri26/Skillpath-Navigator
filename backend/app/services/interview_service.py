from sqlalchemy.orm import Session

from ..ai import prompts
from ..ai.groq_client import GroqClient
from ..core.errors import ServiceError
from ..domain.resume_analysis import split_sections
from ..models import InterviewSession, InterviewTurn, ResumeRecord, User

MAX_TURNS = 24
READINESS = {"not_ready", "developing", "interview_ready"}
DIMENSIONS = ("technical_accuracy", "depth", "communication", "structure")


def resume_context(db: Session, user_id: int) -> str | None:
    """A short, factual summary of the latest resume used to ground questions in the candidate's own work."""
    latest = db.query(ResumeRecord).filter_by(user_id=user_id).order_by(ResumeRecord.created_at.desc()).first()
    if latest is None:
        return None
    skills = [s["name"] for s in latest.analysis.get("skills", [])][:8]
    project_lines = [ln.strip("-*\u2022 ").strip() for ln in split_sections(latest.extracted_text).get("projects", "").splitlines() if len(ln.split()) >= 5][:3]
    parts = []
    if skills:
        parts.append("skills: " + ", ".join(skills))
    if project_lines:
        parts.append("projects: " + " | ".join(l[:160] for l in project_lines))
    return "; ".join(parts)[:700] or None


def _owned(db: Session, user: User, session_id: int) -> InterviewSession:
    session = db.get(InterviewSession, session_id)
    if session is None or session.user_id != user.id:
        raise ServiceError(404, "Interview session not found")
    return session


def _transcript(session: InterviewSession) -> list[dict]:
    return [{"speaker": t.speaker, "text": t.text} for t in session.turns]


def start(db: Session, ai: GroqClient, user: User, role: str, difficulty: str, use_resume: bool) -> dict:
    role = role.strip() or user.target_role
    context = resume_context(db, user.id) if use_resume else None
    reply = ai.chat(prompts.interview_opening(role, difficulty, context), fast=True, max_tokens=600, temperature=0.7)
    session = InterviewSession(user_id=user.id, role=role, difficulty=difficulty, resume_grounded=bool(context))
    session.turns.append(InterviewTurn(idx=0, speaker="interviewer", text=reply.text))
    db.add(session)
    db.commit()
    return {"session_id": session.id, "role": role, "resume_grounded": session.resume_grounded, "question": reply.text}


def next_turn(db: Session, ai: GroqClient, user: User, session_id: int, text: str) -> dict:
    session = _owned(db, user, session_id)
    if session.evaluation is not None:
        raise ServiceError(409, "This interview has already been evaluated")
    if len(session.turns) >= MAX_TURNS:
        raise ServiceError(409, "This interview has reached its length limit. Request the evaluation.")
    context = resume_context(db, user.id) if session.resume_grounded else None
    transcript = _transcript(session) + [{"speaker": "candidate", "text": text}]
    reply = ai.chat(prompts.interview_followup(session.role, session.difficulty, transcript, context),
                    fast=True, max_tokens=600, temperature=0.7)
    # Persist only after the AI call succeeds so a failed call can be retried without a duplicate answer.
    base = len(session.turns)
    session.turns.append(InterviewTurn(idx=base, speaker="candidate", text=text))
    session.turns.append(InterviewTurn(idx=base + 1, speaker="interviewer", text=reply.text))
    db.commit()
    return {"response": reply.text, "turns": len(session.turns)}


def _clean_evaluation(raw) -> dict:
    if not isinstance(raw, dict):
        raise ServiceError(502, "The evaluation came back in an unexpected format. Please try again.")
    scores_in = raw.get("scores") if isinstance(raw.get("scores"), dict) else {}
    scores = {}
    for key in DIMENSIONS:
        try:
            scores[key] = max(1, min(5, int(round(float(scores_in.get(key, 1))))))
        except (TypeError, ValueError):
            scores[key] = 1
    readiness = raw.get("overall_readiness") if raw.get("overall_readiness") in READINESS else "developing"

    def strings(value, limit):
        return [str(v).strip()[:300] for v in value if str(v).strip()][:limit] if isinstance(value, list) else []

    notes = []
    for n in raw.get("answer_notes", [])[:8] if isinstance(raw.get("answer_notes"), list) else []:
        if isinstance(n, dict) and n.get("feedback"):
            notes.append({"question": str(n.get("question", ""))[:300], "feedback": str(n["feedback"])[:500], "evidence": str(n.get("evidence", ""))[:300]})
    return {"scores": scores, "average": round(sum(scores.values()) / len(scores), 1), "overall_readiness": readiness,
            "strengths": strings(raw.get("strengths"), 5), "improvements": strings(raw.get("improvements"), 5), "answer_notes": notes}


def evaluate(db: Session, ai: GroqClient, user: User, session_id: int) -> dict:
    session = _owned(db, user, session_id)
    if session.evaluation is not None:
        return session.evaluation
    candidate_words = sum(len(t.text.split()) for t in session.turns if t.speaker == "candidate")
    if candidate_words < 15:
        raise ServiceError(400, "Answer at least one question properly before asking for an evaluation.")
    raw = ai.chat_json(prompts.interview_evaluation(session.role, session.difficulty, _transcript(session)), max_tokens=3000)
    session.evaluation = _clean_evaluation(raw)
    db.commit()
    return session.evaluation


def history(db: Session, user: User, limit: int = 10) -> list[dict]:
    rows = db.query(InterviewSession).filter_by(user_id=user.id).order_by(InterviewSession.started_at.desc()).limit(limit).all()
    return [{"id": s.id, "role": s.role, "difficulty": s.difficulty, "started_at": s.started_at.isoformat(),
             "turns": len(s.turns), "average": (s.evaluation or {}).get("average"),
             "readiness": (s.evaluation or {}).get("overall_readiness")} for s in rows]
