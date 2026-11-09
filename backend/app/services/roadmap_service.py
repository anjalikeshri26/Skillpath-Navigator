from sqlalchemy.orm import Session

from ..domain.roadmap_planner import build_plan
from ..domain.skills import load_taxonomy
from ..models import ResumeRecord, RoadmapItem, User
from . import mastery_service
from .catalog import recommend_resources


def resume_evidence(db: Session, user_id: int) -> dict[str, str]:
    latest = db.query(ResumeRecord).filter_by(user_id=user_id).order_by(ResumeRecord.created_at.desc()).first()
    if latest is None:
        return {}
    return {s["id"]: s["evidence"] for s in latest.analysis.get("skills", [])}


def refresh(db: Session, user: User) -> list[RoadmapItem]:
    """Recompute the plan from current mastery and resume evidence.

    Completion flags are preserved. Items the learner already finished stay visible even if the planner no
    longer wants them; unfinished items that dropped out of the plan (for example because the topic is now
    mastered) are removed.
    """
    taxonomy = load_taxonomy()
    plan = build_plan(user.target_role, user.skill_level, taxonomy,
                      mastery_service.load_mastery(db, user.id), resume_evidence(db, user.id))
    existing = {item.skill_id: item for item in db.query(RoadmapItem).filter_by(user_id=user.id)}
    for p in plan:
        item = existing.pop(p.skill_id, None)
        if item is None:
            item = RoadmapItem(user_id=user.id, skill_id=p.skill_id, completed=False)
            db.add(item)
        item.topic, item.position, item.priority = p.name, p.position, p.priority
        item.priority_score, item.reason, item.estimated_hours = p.priority_score, p.reason, p.estimated_hours
        item.prerequisites = list(p.prerequisites)
        item.resources = recommend_resources(p.skill_id, user.skill_level)
    tail = len(plan)
    for leftover in existing.values():
        if leftover.completed:
            leftover.position = tail
            tail += 1
        else:
            db.delete(leftover)
    db.commit()
    return get_items(db, user, build_if_empty=False)


def get_items(db: Session, user: User, build_if_empty: bool = True) -> list[RoadmapItem]:
    items = db.query(RoadmapItem).filter_by(user_id=user.id).order_by(RoadmapItem.position).all()
    if not items and build_if_empty:
        return refresh(db, user)
    return items


def serialise(item: RoadmapItem) -> dict:
    return {"id": item.id, "skill_id": item.skill_id, "topic": item.topic, "position": item.position, "priority": item.priority,
            "priority_score": item.priority_score, "reason": item.reason, "estimated_hours": item.estimated_hours,
            "prerequisites": item.prerequisites, "resources": item.resources, "completed": item.completed}


def summary(items: list[RoadmapItem]) -> dict:
    return {"total": len(items), "completed": sum(i.completed for i in items),
            "hours_remaining": sum(i.estimated_hours for i in items if not i.completed)}
