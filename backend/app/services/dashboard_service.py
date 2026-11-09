from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.clock import utcnow
from ..domain import adaptive
from ..models import QuizSession, ResumeRecord, User
from . import mastery_service, roadmap_service


def _next_step(db: Session, user: User, attempts: int, mastery: dict, items: list) -> dict:
    if not db.query(ResumeRecord.id).filter_by(user_id=user.id).first():
        return {"view": "resume", "title": "Upload your resume",
                "detail": "Your roadmap uses it to see which skills you can already show evidence for."}
    if attempts == 0:
        return {"view": "tests", "title": "Take your first test",
                "detail": "A short adaptive test sets your starting mastery so the roadmap can prioritise correctly."}
    weak = sorted(((t, s) for t, s in mastery.items() if s.evidence >= 2 and s.score < 0.6), key=lambda kv: kv[1].score)
    if weak:
        topic, state = weak[0]
        return {"view": "tests", "topic": topic, "title": f"Practise {topic}",
                "detail": f"Mastery is about {round(state.score * 100)}%. A {adaptive.recommend_difficulty(state)} test is the right next step."}
    open_items = [i for i in items if not i.completed]
    if open_items:
        return {"view": "roadmap", "title": f"Continue with {open_items[0].topic}", "detail": open_items[0].reason}
    return {"view": "interview", "title": "Practise an interview",
            "detail": "Your plan is complete. A mock interview is a good way to test it."}


def build(db: Session, user: User) -> dict:
    items = roadmap_service.get_items(db, user)
    mastery = mastery_service.load_mastery(db, user.id)
    attempts = (db.query(QuizSession).filter(QuizSession.user_id == user.id, QuizSession.submitted_at.is_not(None))
                .order_by(QuizSession.submitted_at.desc()).all())
    recent_scores = [a.score for a in attempts[:10]]
    now = utcnow()
    active_days = {a.submitted_at.date() for a in attempts if (now - a.submitted_at).days < 14}
    return {
        "stats": {
            "tests_taken": len(attempts),
            "recent_average": round(sum(recent_scores) / len(recent_scores), 1) if recent_scores else None,
            "questions_answered": sum(a.total for a in attempts),
            "active_days_14": len(active_days),
            **roadmap_service.summary(items),
        },
        "mastery": [{"topic": t, "mastery": round(s.score, 3), "reliable": s.reliable, "recommended_difficulty": adaptive.recommend_difficulty(s)}
                    for t, s in sorted(mastery.items(), key=lambda kv: kv[1].score)],
        "recent_attempts": [{"id": a.id, "topic": a.topic_label, "difficulty": a.difficulty_label, "score": a.score,
                             "correct": a.correct, "total": a.total, "date": a.submitted_at.isoformat()} for a in attempts[:5]],
        "roadmap_preview": [roadmap_service.serialise(i) for i in items if not i.completed][:4],
        "next_step": _next_step(db, user, len(attempts), mastery, items),
    }
