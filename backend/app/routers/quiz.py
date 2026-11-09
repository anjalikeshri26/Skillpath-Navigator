import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..ai.groq_client import GroqClient
from ..core.database import get_db
from ..core.deps import current_user, get_ai
from ..models import User
from ..schemas.quiz import ReportIn, StartSessionIn, SubmitIn
from ..services import quiz_service, roadmap_service

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/quiz", tags=["quiz"])


@router.post("/sessions")
def start(data: StartSessionIn, user: User = Depends(current_user), db: Session = Depends(get_db), ai: GroqClient = Depends(get_ai)):
    return quiz_service.start_session(db, ai, user, data.topic, data.difficulty, data.limit)


@router.post("/sessions/{session_id}/submit")
def submit(session_id: int, data: SubmitIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    result = quiz_service.submit_session(db, user, session_id, {a.question_id: a.selected for a in data.answers})
    try:
        roadmap_service.refresh(db, user)  # mastery changed, so the plan may too
    except Exception:
        log.exception("Roadmap refresh failed after quiz submission")
    return result


@router.get("/history")
def history(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return quiz_service.history(db, user)


@router.get("/mastery")
def mastery(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return quiz_service.mastery_overview(db, user)


@router.post("/questions/{question_id}/report")
def report(question_id: int, data: ReportIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return quiz_service.report_question(db, user, question_id, data.reason)
