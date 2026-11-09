from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..ai.groq_client import GroqClient
from ..core.config import settings
from ..core.database import get_db
from ..core.deps import get_ai

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health(ai: GroqClient = Depends(get_ai), db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        database = "unavailable"
    return {"status": "ok" if database == "ok" else "degraded", "app": settings.app_name, "database": database,
            "ai": {"provider": "groq", "configured": ai.configured, "model": ai.model if ai.configured else None}}
