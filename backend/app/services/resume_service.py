import io
import zipfile

from sqlalchemy.orm import Session

from ..core.errors import ServiceError
from ..domain.resume_analysis import analyse
from ..domain.skills import load_taxonomy
from ..models import ResumeRecord, User

MAX_BYTES = 8 * 1024 * 1024
MAX_PDF_PAGES = 8
MIN_TEXT_CHARS = 80


def extract_text(filename: str, raw: bytes) -> str:
    """Extract text after checking the file's real type from its leading bytes, not its name or MIME header."""
    name = (filename or "").lower()
    if len(raw) > MAX_BYTES:
        raise ServiceError(413, "File must be smaller than 8 MB")
    try:
        if name.endswith(".pdf") and raw.startswith(b"%PDF"):
            import fitz  # PyMuPDF, imported lazily so the rest of the app works without it

            with fitz.open(stream=raw, filetype="pdf") as doc:
                if doc.needs_pass:
                    raise ServiceError(400, "This PDF is password protected. Remove the password and try again.")
                return "\n".join(page.get_text() for page in list(doc)[:MAX_PDF_PAGES])
        if name.endswith(".docx") and zipfile.is_zipfile(io.BytesIO(raw)):
            from docx import Document

            doc = Document(io.BytesIO(raw))
            parts = [p.text for p in doc.paragraphs]
            for table in doc.tables:
                parts += [" | ".join(cell.text for cell in row.cells) for row in table.rows]
            return "\n".join(parts)
    except ServiceError:
        raise
    except Exception:
        raise ServiceError(400, "Could not read this document. Try exporting it again as a PDF or DOCX.")
    raise ServiceError(400, "Upload a valid PDF or DOCX file")


def analyse_and_store(db: Session, user: User, filename: str, raw: bytes, job_description: str | None) -> ResumeRecord:
    text = extract_text(filename, raw)
    if len(text.strip()) < MIN_TEXT_CHARS:
        raise ServiceError(400, "No readable text found. If this is a scanned PDF, run OCR on it first.")
    analysis = analyse(text, user.target_role, load_taxonomy(), (job_description or "")[:6000] or None)
    record = ResumeRecord(user_id=user.id, filename=(filename or "resume")[:255], extracted_text=text[:50000], analysis=analysis)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
