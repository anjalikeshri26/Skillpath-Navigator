"""Difficulty selection and session planning from mastery."""
from .mastery import MasteryState

DIFFICULTIES = ("Easy", "Medium", "Hard", "Advanced")
_THRESHOLDS = ((0.40, "Easy"), (0.62, "Medium"), (0.82, "Hard"))


def recommend_difficulty(state: MasteryState | None) -> str:
    """Pick the level at which the learner is most likely to be challenged but not overwhelmed."""
    if state is None or state.evidence < 1:
        return "Easy"
    for limit, level in _THRESHOLDS:
        if state.score < limit:
            return level
    return "Advanced"


def neighbours(difficulty: str) -> list[str]:
    """Fallback order when the bank is short at a level: closest levels first."""
    i = DIFFICULTIES.index(difficulty)
    order = sorted(range(len(DIFFICULTIES)), key=lambda j: (abs(j - i), j))
    return [DIFFICULTIES[j] for j in order if j != i]


def plan_session(
    topics: list[str], mastery: dict[str, MasteryState], limit: int, difficulty: str | None = None
) -> list[tuple[str, str]]:
    """Return `limit` (topic, difficulty) slots.

    Weaker topics receive more slots (weight = 1.2 - mastery, with unknown topics treated as 0.5). If the
    learner chose a fixed difficulty it is used for every slot; otherwise each slot uses the recommended
    difficulty for that topic.
    """
    if not topics or limit <= 0:
        return []
    weights = {t: max(0.2, 1.2 - (mastery[t].score if t in mastery else 0.5)) for t in topics}
    total = sum(weights.values())
    quota = {t: limit * w / total for t, w in weights.items()}
    slots = {t: int(q) for t, q in quota.items()}
    leftovers = sorted(topics, key=lambda t: quota[t] - slots[t], reverse=True)
    for t in leftovers[: limit - sum(slots.values())]:
        slots[t] += 1
    plan: list[tuple[str, str]] = []
    for t in topics:
        level = difficulty or recommend_difficulty(mastery.get(t))
        plan.extend([(t, level)] * slots[t])
    return plan
