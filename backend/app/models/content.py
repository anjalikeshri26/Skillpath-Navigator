from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.clock import utcnow
from ..core.database import Base


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    category: Mapped[str] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(Text, default="")
    estimated_hours: Mapped[int] = mapped_column(Integer, default=10)


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), index=True)
    prompt: Mapped[str] = mapped_column(Text)
    prompt_key: Mapped[str] = mapped_column(String(64), unique=True)  # hash of the normalised prompt
    options: Mapped[list] = mapped_column(JSON)
    answer_index: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[str] = mapped_column(Text, default="")
    difficulty: Mapped[str] = mapped_column(String(20), default="Easy", index=True)
    source: Mapped[str] = mapped_column(String(20), default="seed")  # seed | ai
    model: Mapped[str] = mapped_column(String(80), default="")  # model that wrote an AI question
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)  # active | under_review | retired
    times_answered: Mapped[int] = mapped_column(Integer, default=0)
    times_correct: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    topic: Mapped[Topic] = relationship(lazy="joined")


class QuestionReport(Base):
    """A learner flagging a question as wrong or unclear. One report per user per question."""

    __tablename__ = "question_reports"
    __table_args__ = (UniqueConstraint("user_id", "question_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    reason: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
