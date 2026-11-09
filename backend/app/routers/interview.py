from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..ai.groq_client import GroqClient
from ..core.database import get_db
from ..core.deps import current_user, get_ai
from ..models import User
from ..schemas.interview import StartInterviewIn, TurnIn
from ..services import interview_service

router = APIRouter(prefix="/api/interview", tags=["interview"])


@router.post("/sessions")
def start(data: StartInterviewIn, user: User = Depends(current_user), db: Session = Depends(get_db), ai: GroqClient = Depends(get_ai)):
    return interview_service.start(db, ai, user, data.role, data.difficulty, data.use_resume)


@router.post("/sessions/{session_id}/turns")
def turn(session_id: int, data: TurnIn, user: User = Depends(current_user), db: Session = Depends(get_db), ai: GroqClient = Depends(get_ai)):
    return interview_service.next_turn(db, ai, user, session_id, data.text.strip())


@router.post("/sessions/{session_id}/evaluate")
def evaluate(session_id: int, user: User = Depends(current_user), db: Session = Depends(get_db), ai: GroqClient = Depends(get_ai)):
    return interview_service.evaluate(db, ai, user, session_id)


@router.get("/sessions")
def history(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return interview_service.history(db, user)
