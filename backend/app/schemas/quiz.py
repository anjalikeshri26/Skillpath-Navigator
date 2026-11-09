from typing import Literal

from pydantic import BaseModel, Field, model_validator


class StartSessionIn(BaseModel):
    topic: str = "Mixed"
    difficulty: str = "Adaptive"  # Adaptive, or one of Easy / Medium / Hard / Advanced
    limit: int = Field(default=8, ge=3, le=20)


class AnswerIn(BaseModel):
    question_id: int
    selected: int | None = Field(default=None, ge=0, le=3)  # position shown to the learner; null = skipped


class SubmitIn(BaseModel):
    answers: list[AnswerIn] = Field(max_length=20)

    @model_validator(mode="after")
    def _unique_questions(self):
        ids = [a.question_id for a in self.answers]
        if len(ids) != len(set(ids)):
            raise ValueError("Each question may only be answered once")
        return self


class ReportIn(BaseModel):
    reason: Literal["wrong_answer", "unclear", "duplicate", "off_topic"]
