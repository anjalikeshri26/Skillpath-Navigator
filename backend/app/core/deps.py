from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from ..ai.groq_client import GroqClient
from ..models import User
from .config import settings
from .database import get_db
from .security import decode_access_token

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    try:
        user_id = decode_access_token(token)
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(401, "Your session has expired. Please sign in again.")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(401, "Your session has expired. Please sign in again.")
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, "Administrator access required")
    return user


@lru_cache(maxsize=1)
def _groq_client() -> GroqClient:
    return GroqClient(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        fast_model=settings.groq_fast_model,
        base_url=settings.groq_base_url,
        timeout=settings.ai_timeout_seconds,
        max_retries=settings.ai_max_retries,
    )


def get_ai() -> GroqClient:
    """FastAPI dependency; tests override it with a fake client."""
    return _groq_client()
