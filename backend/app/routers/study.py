from fastapi import APIRouter, Depends, HTTPException

from ..ai.groq_client import GroqClient
from ..core.deps import current_user, get_ai
from ..core.rate_limit import SlidingWindowLimiter
from ..models import User
from ..schemas.study import StudyRequest
from ..services import study_service

router = APIRouter(prefix="/api/study", tags=["study"])
# Long generations are the most expensive thing the API does, so each learner gets a modest budget.
limiter = SlidingWindowLimiter(max_events=8, window_seconds=600)


@router.post("/generate")
def generate(data: StudyRequest, user: User = Depends(current_user), ai: GroqClient = Depends(get_ai)):
    key = str(user.id)
    wait = limiter.retry_after(key)
    if wait:
        raise HTTPException(429, f"You have generated several sets of notes recently. Try again in about {int(wait // 60) + 1} minute(s).",
                            headers={"Retry-After": str(int(wait) + 1)})
    limiter.hit(key)
    return study_service.generate(ai, user, data.subject, data.depth, data.focus)
