"""Grading for shuffled-option quiz sessions."""
from dataclasses import dataclass


@dataclass(frozen=True)
class GradedAnswer:
    question_id: int
    selected_position: int | None
    selected_original_index: int | None
    correct_original_index: int
    is_correct: bool
    skipped: bool


def grade(
    answer_key: dict[int, int],
    option_orders: dict[int, list[int]],
    answers: dict[int, int | None],
) -> list[GradedAnswer]:
    """Grade every question served in the session.

    `option_orders[q][i]` is the original option index shown at position i. Questions with no answer, or
    an out-of-range position, count as skipped and incorrect. Answers for questions that were not served
    are ignored by construction because we iterate over the served questions.
    """
    graded = []
    for question_id, correct_index in answer_key.items():
        order = option_orders[question_id]
        position = answers.get(question_id)
        valid = position is not None and 0 <= position < len(order)
        original = order[position] if valid else None
        graded.append(
            GradedAnswer(
                question_id=question_id,
                selected_position=position if valid else None,
                selected_original_index=original,
                correct_original_index=correct_index,
                is_correct=valid and original == correct_index,
                skipped=not valid,
            )
        )
    return graded
