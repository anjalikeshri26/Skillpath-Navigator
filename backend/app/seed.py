"""Load topics and question banks from app/data/questions/*.json. Safe to run repeatedly."""
import json
import logging

from sqlalchemy.orm import Session

from .core.config import settings
from .core.database import Base, SessionLocal, engine
from .core.security import hash_password
from .domain.skills import DATA_DIR
from .models import Topic, User
from .services.question_bank import add_question

log = logging.getLogger(__name__)
DEMO_EMAIL = "demo@skillpath.local"
DEMO_PASSWORD = "DemoPass123"


def seed_content(db: Session) -> int:
    added = 0
    for path in sorted((DATA_DIR / "questions").glob("*.json")):
        bank = json.loads(path.read_text(encoding="utf-8"))
        topic = db.query(Topic).filter_by(name=bank["topic"]).first()
        if topic is None:
            topic = Topic(name=bank["topic"], category=bank["category"], description=bank.get("description", ""),
                          estimated_hours=bank.get("estimated_hours", 10))
            db.add(topic)
            db.flush()
        for q in bank["questions"]:
            if add_question(db, topic, prompt=q["prompt"], options=q["options"], answer_index=q["answer_index"],
                            explanation=q["explanation"], difficulty=q["difficulty"], source="seed"):
                added += 1
    db.commit()
    return added


def seed_demo_user(db: Session) -> None:
    if db.query(User).filter_by(email=DEMO_EMAIL).first():
        return
    db.add(User(name="Demo Student", email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD), college="Demo Institute",
                branch="CSE (AI/ML)", academic_year="3rd Year", skill_level="Intermediate", target_role="AI/ML Engineer"))
    db.commit()


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        added = seed_content(db)
        if added:
            log.info("Seeded %d new questions", added)
        if settings.seed_demo_user and settings.environment != "production":
            seed_demo_user(db)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed()
