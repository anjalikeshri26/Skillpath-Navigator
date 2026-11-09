from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..core.clock import utcnow
from ..core.database import Base


class Note(Base):
    """A learner's note, either written by hand or saved from the Study generator.

    `revision` increases on every save and is required on update, so a stale editor (for example a second
    browser tab) cannot silently overwrite newer text. `excerpt` and `word_count` are stored at write time
    so the list view never has to load note bodies.
    """

    __tablename__ = "notes"
    __table_args__ = (UniqueConstraint("user_id", "title_key", name="uq_notes_user_title"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    title_key: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text, default="")
    excerpt: Mapped[str] = mapped_column(String(200), default="")
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(12), default="written")  # written | generated
    subject: Mapped[str] = mapped_column(String(120), default="")
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
