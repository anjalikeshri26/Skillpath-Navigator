import hashlib

from sqlalchemy import exists
from sqlalchemy.orm import Session

from ..domain.text import normalise
from ..models import Question, QuestionSeen, Topic


def prompt_key(prompt: str) -> str:
    return hashlib.sha256(normalise(prompt).encode("utf-8")).hexdigest()


def add_question(db: Session, topic: Topic, *, prompt: str, options: list[str], answer_index: int,
                 explanation: str, difficulty: str, source: str, model: str = "") -> Question | None:
    """Insert a question unless an identical normalised prompt exists. Returns None for duplicates."""
    key = prompt_key(prompt)
    if db.query(Question.id).filter(Question.prompt_key == key).first():
        return None
    question = Question(topic_id=topic.id, prompt=prompt.strip(), prompt_key=key, options=options, answer_index=answer_index,
                        explanation=explanation.strip(), difficulty=difficulty, source=source, model=model)
    db.add(question)
    db.flush()
    return question


def available_questions(db: Session, user_id: int, topic_name: str, difficulty: str, exclude_ids: set[int]) -> list[Question]:
    """Active questions at this topic and level that the learner has not already completed."""
    seen = exists().where(QuestionSeen.user_id == user_id, QuestionSeen.question_id == Question.id)
    query = (
        db.query(Question).join(Topic, Topic.id == Question.topic_id)
        .filter(Topic.name == topic_name, Question.difficulty == difficulty, Question.status == "active", ~seen)
    )
    if exclude_ids:
        query = query.filter(~Question.id.in_(list(exclude_ids)))
    return query.all()
