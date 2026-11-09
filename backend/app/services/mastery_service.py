from sqlalchemy.orm import Session

from ..core.clock import utcnow
from ..domain import mastery as model
from ..domain.mastery import MasteryState
from ..models import Topic, TopicMastery


def load_mastery(db: Session, user_id: int) -> dict[str, MasteryState]:
    rows = db.query(TopicMastery, Topic.name).join(Topic, Topic.id == TopicMastery.topic_id).filter(TopicMastery.user_id == user_id).all()
    return {name: MasteryState(row.alpha, row.beta) for row, name in rows}


def apply_answers(db: Session, user_id: int, answers: list[tuple[int, str, str, bool]]) -> list[dict]:
    """Fold graded answers into mastery. `answers` is (topic_id, topic_name, difficulty, is_correct) in order.

    Returns [{topic, before, after}] in 0..1 for the topics that changed. The caller commits.
    """
    now = utcnow()
    rows = {r.topic_id: r for r in db.query(TopicMastery).filter(TopicMastery.user_id == user_id).all()}
    names: dict[int, str] = {}
    before: dict[int, float] = {}
    touched: set[int] = set()
    for topic_id, topic_name, difficulty, is_correct in answers:
        names[topic_id] = topic_name
        row = rows.get(topic_id)
        if row is None:
            row = TopicMastery(user_id=user_id, topic_id=topic_id, alpha=model.PRIOR, beta=model.PRIOR, updated_at=now)
            db.add(row)
            rows[topic_id] = row
        state = MasteryState(row.alpha, row.beta)
        if topic_id not in touched:
            before[topic_id] = state.score
            elapsed = (now - row.updated_at).total_seconds() / 86400
        else:
            elapsed = 0.0
        touched.add(topic_id)
        new_state = model.update(state, correct=is_correct, difficulty=difficulty, days_since_update=elapsed)
        row.alpha, row.beta, row.updated_at = new_state.alpha, new_state.beta, now
    return [
        {"topic": names[t], "before": round(before[t], 3), "after": round(MasteryState(rows[t].alpha, rows[t].beta).score, 3)}
        for t in touched
    ]
