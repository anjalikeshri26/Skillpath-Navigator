from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.rate_limit import SlidingWindowLimiter
from ..core.security import create_access_token, hash_password, verify_password
from ..models import User
from ..schemas.auth import LoginIn, RegisterIn, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])
login_limiter = SlidingWindowLimiter(max_events=5, window_seconds=300)
register_limiter = SlidingWindowLimiter(max_events=10, window_seconds=600)


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _token_response(user: User) -> dict:
    return {"access_token": create_access_token(user.id), "token_type": "bearer", "user": UserOut.model_validate(user)}


@router.post("/register")
def register(data: RegisterIn, request: Request, db: Session = Depends(get_db)):
    ip = _client(request)
    wait = register_limiter.retry_after(ip)
    if wait:
        raise HTTPException(429, "Too many sign-ups from this address. Try again later.", headers={"Retry-After": str(int(wait) + 1)})
    email = data.email.lower()
    if db.query(User.id).filter_by(email=email).first():
        raise HTTPException(409, "That email is already registered")
    user = User(name=data.name, email=email, password_hash=hash_password(data.password), college=data.college,
                branch=data.branch, academic_year=data.academic_year)
    db.add(user)
    db.commit()
    register_limiter.hit(ip)
    return _token_response(user)


@router.post("/login")
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    key = f"{_client(request)}:{data.email.lower()}"
    wait = login_limiter.retry_after(key)
    if wait:
        raise HTTPException(429, "Too many failed attempts. Try again in a few minutes.", headers={"Retry-After": str(int(wait) + 1)})
    user = db.query(User).filter_by(email=data.email.lower()).first()
    if user is None or not verify_password(data.password, user.password_hash):
        login_limiter.hit(key)
        raise HTTPException(401, "Incorrect email or password")
    login_limiter.reset(key)
    return _token_response(user)
