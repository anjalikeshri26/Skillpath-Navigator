import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..ai.groq_client import GroqClient
from ..core.database import get_db
from ..core.deps import current_user, get_ai
from ..domain.adaptive import DIFFICULTIES
from ..domain.skills import load_taxonomy
from ..models import Topic, User
from ..schemas.auth import ProfileUpdate, UserOut
from ..services import roadmap_service

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["profile"])


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.patch("/profile", response_model=UserOut)
def update_profile(data: ProfileUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    changes = data.model_dump(exclude_unset=True)
    if "target_role" in changes and changes["target_role"] not in load_taxonomy().roles:
        raise HTTPException(422, "Choose one of the supported target roles")
    plan_changed = any(changes.get(k, getattr(user, k)) != getattr(user, k) for k in ("target_role", "skill_level"))
    for key, value in changes.items():
        setattr(user, key, value)
    db.commit()
    if plan_changed:
        roadmap_service.refresh(db, user)
    return user


@router.get("/meta")
def meta(user: User = Depends(current_user), db: Session = Depends(get_db), ai: GroqClient = Depends(get_ai)):
    topics = db.query(Topic).order_by(Topic.category, Topic.name).all()
    return {
        "roles": list(load_taxonomy().roles),
        "topics": [{"name": t.name, "category": t.category} for t in topics],
        "difficulties": list(DIFFICULTIES),
        "ai": {"configured": ai.configured},
    }
