"""Builds a personalised study plan from role requirements, prerequisites, mastery and resume evidence."""
from dataclasses import dataclass

from .mastery import MasteryState
from .skills import Taxonomy

MASTERED_AT = 0.80  # reliable mastery at or above this removes a skill from the plan
PREREQ_PULL_IN_BELOW = 0.60  # a weak prerequisite is added even if the role does not list it


@dataclass(frozen=True)
class PlanItem:
    skill_id: str
    name: str
    topic: str | None
    position: int
    priority: str
    priority_score: float
    reason: str
    estimated_hours: int
    prerequisites: tuple[str, ...]


def _gap(skill_id: str, topic: str | None, mastery: dict[str, MasteryState], resume_skills: dict[str, str]) -> tuple[float, str]:
    """Return (gap in 0..1, human-readable evidence). Larger gap means more study needed."""
    state = mastery.get(topic) if topic else None
    if state is not None and state.evidence >= 1:
        pct = round(state.score * 100)
        note = f"Quiz mastery is about {pct}%"
        note += " from your recent answers" if state.reliable else " (few answers so far, treat as a rough estimate)"
        return 1.0 - state.score, note
    evidence = resume_skills.get(skill_id)
    if evidence == "demonstrated":
        return 0.35, "Shown in your resume projects or experience, but not yet checked by a quiz"
    if evidence == "listed":
        return 0.55, "Listed on your resume without supporting projects, and not yet checked by a quiz"
    return 0.70, "Not on your resume and not yet checked by a quiz"


def build_plan(
    role: str,
    level: str,
    taxonomy: Taxonomy,
    mastery: dict[str, MasteryState],
    resume_skills: dict[str, str] | None = None,
) -> list[PlanItem]:
    resume_skills = resume_skills or {}
    requirements = taxonomy.requirements(role)
    factor = taxonomy.level_factor.get(level, 1.0)

    gaps: dict[str, tuple[float, str]] = {}
    for sid in requirements:
        gaps[sid] = _gap(sid, taxonomy.skills[sid].topic, mastery, resume_skills)

    # Pull in weak prerequisites transitively so the plan is learnable in order.
    pulled: dict[str, str] = {}
    queue = list(requirements)
    while queue:
        sid = queue.pop()
        for pre in taxonomy.skills[sid].prerequisites:
            if pre in gaps or pre in pulled:
                continue
            gap, note = _gap(pre, taxonomy.skills[pre].topic, mastery, resume_skills)
            if 1.0 - gap < PREREQ_PULL_IN_BELOW:
                gaps[pre] = (gap, note)
                pulled[pre] = sid
                queue.append(pre)

    selected = {}
    for sid, (gap, note) in gaps.items():
        topic = taxonomy.skills[sid].topic
        state = mastery.get(topic) if topic else None
        if state is not None and state.reliable and state.score >= MASTERED_AT:
            continue
        weight = requirements.get(sid)
        score = round((weight if weight else 1.5) * gap, 3)  # prerequisites get a mid weight
        selected[sid] = (score, gap, note)

    # Topological order (prerequisites first); among available skills, highest priority score first.
    ordered: list[str] = []
    remaining = set(selected)
    while remaining:
        ready = [s for s in remaining if all(p not in remaining for p in taxonomy.skills[s].prerequisites)]
        if not ready:  # defensive: a cycle in the data should not hang the planner
            ready = list(remaining)
        ready.sort(key=lambda s: (-selected[s][0], s))
        ordered.append(ready[0])
        remaining.discard(ready[0])

    max_score = max((v[0] for v in selected.values()), default=1.0) or 1.0
    items = []
    for position, sid in enumerate(ordered):
        score, gap, note = selected[sid]
        skill = taxonomy.skills[sid]
        ratio = score / max_score
        priority = "High" if ratio >= 0.66 else "Medium" if ratio >= 0.33 else "Low"
        if sid in pulled:
            reason = f"Prerequisite for {taxonomy.skills[pulled[sid]].name}. {note}."
        else:
            reason = f"Weight {requirements[sid]} of 3 for {role}. {note}."
        hours = max(2, round(skill.hours * (0.4 + 0.6 * gap) * factor))
        items.append(PlanItem(sid, skill.name, skill.topic, position, priority, round(score, 2), reason, hours,
                              tuple(taxonomy.skills[p].name for p in skill.prerequisites)))
    return items
