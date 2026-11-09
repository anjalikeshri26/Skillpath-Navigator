"""Resource catalogue and retrieval."""
import json
from functools import lru_cache

from ..domain.embeddings import TfidfIndex
from ..domain.skills import DATA_DIR, load_taxonomy

_LEVEL_ORDER = ["Beginner", "Intermediate", "Advanced"]


@lru_cache(maxsize=1)
def _resources() -> dict[str, dict]:
    return {r["id"]: r for r in json.loads((DATA_DIR / "resources.json").read_text(encoding="utf-8"))}


@lru_cache(maxsize=1)
def _index() -> TfidfIndex:
    return TfidfIndex({rid: f"{r['title']} {r['summary']} {r['kind']}" for rid, r in _resources().items()})


def _level_bonus(resource_level: str, learner_level: str) -> float:
    try:
        gap = abs(_LEVEL_ORDER.index(resource_level) - _LEVEL_ORDER.index(learner_level))
    except ValueError:
        return 0.0
    return {0: 0.25, 1: 0.1}.get(gap, 0.0)


def recommend_resources(skill_id: str, learner_level: str, hint: str = "", k: int = 2) -> list[dict]:
    """Rank resources for a skill: text relevance to the skill name and hint, plus a bonus for matching level."""
    skill = load_taxonomy().skills[skill_id]
    resources = _resources()
    same_skill = {rid for rid, r in resources.items() if r["skill"] == skill_id}
    allowed = same_skill or None
    hits = dict(_index().search(f"{skill.name} {hint}".strip(), k=len(resources), allowed=allowed))
    pool = same_skill or set(hits)
    ranked = sorted(pool, key=lambda rid: hits.get(rid, 0.0) + _level_bonus(resources[rid]["level"], learner_level), reverse=True)
    return [
        {"title": resources[rid]["title"], "url": resources[rid]["url"], "kind": resources[rid]["kind"], "level": resources[rid]["level"]}
        for rid in ranked[:k]
    ]
