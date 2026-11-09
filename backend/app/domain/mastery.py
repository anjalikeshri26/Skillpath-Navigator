"""Per-topic mastery estimate.

Each topic keeps a Beta(alpha, beta) belief about the probability that the learner answers a question
on that topic correctly. A correct answer on a hard question is stronger evidence than a correct answer
on an easy one; the reverse holds for mistakes. Old evidence decays towards the prior so the estimate
tracks recent ability instead of lifetime averages.
"""
from dataclasses import dataclass

PRIOR = 1.0  # Beta(1, 1): no opinion until the learner answers something
DAILY_DECAY = 0.985  # evidence half-life of roughly 46 days
_CORRECT_WEIGHT = {"Easy": 0.6, "Medium": 1.0, "Hard": 1.4, "Advanced": 1.8}
_WRONG_WEIGHT = {"Easy": 1.4, "Medium": 1.0, "Hard": 0.6, "Advanced": 0.4}
CONFIDENT_AFTER = 5.0  # weighted answers needed before we call the estimate reliable


@dataclass(frozen=True)
class MasteryState:
    alpha: float = PRIOR
    beta: float = PRIOR

    @property
    def score(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    @property
    def evidence(self) -> float:
        return (self.alpha - PRIOR) + (self.beta - PRIOR)

    @property
    def reliable(self) -> bool:
        return self.evidence >= CONFIDENT_AFTER


def decay(state: MasteryState, days: float) -> MasteryState:
    if days <= 0:
        return state
    factor = DAILY_DECAY ** days
    return MasteryState(PRIOR + (state.alpha - PRIOR) * factor, PRIOR + (state.beta - PRIOR) * factor)


def update(state: MasteryState, *, correct: bool, difficulty: str, days_since_update: float = 0.0) -> MasteryState:
    state = decay(state, days_since_update)
    if correct:
        return MasteryState(state.alpha + _CORRECT_WEIGHT.get(difficulty, 1.0), state.beta)
    return MasteryState(state.alpha, state.beta + _WRONG_WEIGHT.get(difficulty, 1.0))
