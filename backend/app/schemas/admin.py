from typing import Literal

from pydantic import BaseModel


class QuestionStatusIn(BaseModel):
    status: Literal["active", "under_review", "retired"]
