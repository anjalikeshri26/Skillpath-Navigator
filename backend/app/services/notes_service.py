from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, defer

from ..core.clock import utcnow
from ..core.errors import ServiceError
from ..domain.notes_text import escape_like, excerpt, title_key, word_count
from ..models import Note, User

MAX_NOTES_PER_USER = 500


def _summary(note: Note) -> dict:
    return {"id": note.id, "title": note.title, "excerpt": note.excerpt, "word_count": note.word_count, "source": note.source,
            "subject": note.subject, "pinned": note.pinned, "revision": note.revision,
            "created_at": note.created_at.isoformat(), "updated_at": note.updated_at.isoformat()}


def serialise(note: Note) -> dict:
    return {**_summary(note), "body": note.body}


def _name_taken(title: str) -> ServiceError:
    return ServiceError(409, f"You already have a note called \u201c{title}\u201d. Choose a different name.")


def _owned(db: Session, user: User, note_id: int) -> Note:
    note = db.query(Note).filter_by(id=note_id, user_id=user.id).first()
    if note is None:
        raise ServiceError(404, "Note not found")
    return note


def list_notes(db: Session, user: User, query: str = "", source: str = "", limit: int = 100, offset: int = 0) -> dict:
    q = db.query(Note).options(defer(Note.body)).filter(Note.user_id == user.id)
    if source in ("written", "generated"):
        q = q.filter(Note.source == source)
    if query.strip():
        like = f"%{escape_like(query.strip())}%"
        q = q.filter(or_(Note.title.ilike(like, escape="\\"), Note.body.ilike(like, escape="\\")))
    total = q.count()
    rows = q.order_by(Note.pinned.desc(), Note.updated_at.desc()).offset(max(0, offset)).limit(max(1, min(limit, 200))).all()
    return {"total": total, "items": [_summary(n) for n in rows]}


def get_note(db: Session, user: User, note_id: int) -> dict:
    return serialise(_owned(db, user, note_id))


def create_note(db: Session, user: User, title: str, body: str, source: str, subject: str) -> dict:
    if db.query(func.count(Note.id)).filter(Note.user_id == user.id).scalar() >= MAX_NOTES_PER_USER:
        raise ServiceError(400, f"You have reached the limit of {MAX_NOTES_PER_USER} notes. Delete some to add more.")
    key = title_key(title)
    if db.query(Note.id).filter_by(user_id=user.id, title_key=key).first():
        raise _name_taken(title)
    now = utcnow()
    note = Note(user_id=user.id, title=title, title_key=key, body=body, excerpt=excerpt(body), word_count=word_count(body),
                source=source, subject=subject.strip(), created_at=now, updated_at=now)
    db.add(note)
    try:
        db.commit()
    except IntegrityError:  # another request created the same name between our check and the insert
        db.rollback()
        raise _name_taken(title)
    return serialise(note)


def update_note(db: Session, user: User, note_id: int, title: str, body: str, pinned: bool, revision: int) -> dict:
    note = _owned(db, user, note_id)
    if note.revision != revision:
        raise ServiceError(409, "This note was changed somewhere else, such as another tab. Reload it before saving so nothing is overwritten.")
    key = title_key(title)
    clash = db.query(Note.id).filter(Note.user_id == user.id, Note.title_key == key, Note.id != note.id).first()
    if clash:
        raise _name_taken(title)
    note.title, note.title_key, note.body, note.pinned = title, key, body, pinned
    note.excerpt, note.word_count = excerpt(body), word_count(body)
    note.revision += 1
    note.updated_at = utcnow()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _name_taken(title)
    return serialise(note)


def delete_note(db: Session, user: User, note_id: int) -> None:
    db.delete(_owned(db, user, note_id))
    db.commit()
