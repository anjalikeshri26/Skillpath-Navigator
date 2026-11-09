from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.clock import utcnow
from ..core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    college: Mapped[str] = mapped_column(String(180), default="")
    degree: Mapped[str] = mapped_column(String(80), default="B.Tech")
    branch: Mapped[str] = mapped_column(String(100), default="")
    academic_year: Mapped[str] = mapped_column(String(30), default="3rd Year")
    skill_level: Mapped[str] = mapped_column(String(30), default="Beginner")
    target_role: Mapped[str] = mapped_column(String(100), default="Software Engineer")
    target_package: Mapped[str] = mapped_column(String(40), default="")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
