from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ..domain.notes_text import clean_title


class StudyRequest(BaseModel):
    subject: str = Field(min_length=2, max_length=120)
    depth: Literal["Quick revision", "Standard", "In-depth"] = "Standard"
    focus: str = Field(default="", max_length=200)

    @field_validator("subject")
    @classmethod
    def _needs_letters(cls, value: str) -> str:
        value = clean_title(value)
        if sum(c.isalpha() for c in value) < 2:
            raise ValueError("Enter a subject such as 'Operating system scheduling'")
        return value

    @field_validator("focus")
    @classmethod
    def _tidy_focus(cls, value: str) -> str:
        return clean_title(value)
