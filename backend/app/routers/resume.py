import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.deps import current_user
from ..models import ResumeRecord, User
from ..services import resume_service, roadmap_service

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/resume", tags=["resume"])


def _out(record: ResumeRecord) -> dict:
    return {"id": record.id, "filename": record.filename, "created_at": record.created_at.isoformat(), "analysis": record.analysis}


@router.post("/analyze")
def analyze(file: UploadFile = File(...), job_description: str = Form(default=""), user: User = Depends(current_user), db: Session = Depends(get_db)):
    raw = file.file.read(resume_service.MAX_BYTES + 1)
    record = resume_service.analyse_and_store(db, user, file.filename or "", raw, job_description)
    try:
        roadmap_service.refresh(db, user)  # resume evidence feeds the roadmap
    except Exception:
        log.exception("Roadmap refresh failed after resume analysis")
    return _out(record)


@router.get("/latest")
def latest(user: User = Depends(current_user), db: Session = Depends(get_db)):
    record = db.query(ResumeRecord).filter_by(user_id=user.id).order_by(ResumeRecord.created_at.desc()).first()
    return _out(record) if record else None


@router.delete("/{resume_id}", status_code=204)
def delete(resume_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    record = db.query(ResumeRecord).filter_by(id=resume_id, user_id=user.id).first()
    if record is None:
        raise HTTPException(404, "Resume not found")
    db.delete(record)
    db.commit()
    roadmap_service.refresh(db, user)
