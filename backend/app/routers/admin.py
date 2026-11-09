from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.deps import admin_user
from ..models import Question, QuestionReport, QuizSession, Topic, User
from ..schemas.admin import QuestionStatusIn

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/overview")
def overview(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    by_status = dict(db.query(Question.status, func.count(Question.id)).group_by(Question.status).all())
    by_source = dict(db.query(Question.source, func.count(Question.id)).group_by(Question.source).all())
    return {"users": db.query(User).count(), "topics": db.query(Topic).count(), "questions": by_status, "question_sources": by_source,
            "tests_submitted": db.query(QuizSession).filter(QuizSession.submitted_at.is_not(None)).count(),
            "open_reports": db.query(QuestionReport).count()}


@router.get("/questions")
def questions(status: str | None = None, source: str | None = None, limit: int = 100, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    query = db.query(Question)
    if status:
        query = query.filter(Question.status == status)
    if source:
        query = query.filter(Question.source == source)
    rows = query.order_by(Question.id.desc()).limit(max(1, min(limit, 500))).all()
    return [{"id": q.id, "topic": q.topic.name, "difficulty": q.difficulty, "prompt": q.prompt, "options": q.options,
             "answer_index": q.answer_index, "status": q.status, "source": q.source, "model": q.model,
             "answered": q.times_answered, "percent_correct": round(100 * q.times_correct / q.times_answered, 1) if q.times_answered else None,
             "reports": db.query(func.count(QuestionReport.id)).filter(QuestionReport.question_id == q.id).scalar()} for q in rows]


@router.patch("/questions/{question_id}")
def set_status(question_id: int, data: QuestionStatusIn, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(404, "Question not found")
    question.status = data.status
    db.commit()
    return {"id": question.id, "status": question.status}
