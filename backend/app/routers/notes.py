from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.deps import current_user
from ..models import User
from ..schemas.notes import NoteCreate, NoteUpdate
from ..services import notes_service

router = APIRouter(prefix="/api/notes", tags=["notes"])


@router.get("")
def list_notes(q: str = Query(default="", max_length=100), source: str = "", limit: int = 100, offset: int = 0,
               user: User = Depends(current_user), db: Session = Depends(get_db)):
    return notes_service.list_notes(db, user, q, source, limit, offset)


@router.post("", status_code=201)
def create(data: NoteCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return notes_service.create_note(db, user, data.title, data.body, data.source, data.subject)


@router.get("/{note_id}")
def read(note_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return notes_service.get_note(db, user, note_id)


@router.put("/{note_id}")
def update(note_id: int, data: NoteUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return notes_service.update_note(db, user, note_id, data.title, data.body, data.pinned, data.revision)


@router.delete("/{note_id}", status_code=204)
def delete(note_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    notes_service.delete_note(db, user, note_id)
