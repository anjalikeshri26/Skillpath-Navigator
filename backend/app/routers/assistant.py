from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..ai.groq_client import GroqClient
from ..core.database import get_db
from ..core.deps import current_user, get_ai
from ..models import User
from ..schemas.assistant import AssistantIn
from ..services import tutor_service

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


@router.post("")
def ask(data: AssistantIn, user: User = Depends(current_user), db: Session = Depends(get_db), ai: GroqClient = Depends(get_ai)):
    history = [{"role": t.role, "text": t.text} for t in data.history]
    return {"answer": tutor_service.answer(db, ai, user, data.message, history)}
