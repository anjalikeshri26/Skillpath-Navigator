from datetime import timedelta

import bcrypt
import jwt

from .clock import utcnow
from .config import settings, signing_key

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("ascii"))
    except ValueError:
        return False


def create_access_token(user_id: int) -> str:
    now = utcnow()
    payload = {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=settings.access_token_expire_minutes)}
    return jwt.encode(payload, signing_key(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> int:
    """Return the user id, or raise jwt.PyJWTError / ValueError for any invalid token."""
    payload = jwt.decode(token, signing_key(), algorithms=[ALGORITHM], options={"require": ["exp", "sub"]})
    return int(payload["sub"])
