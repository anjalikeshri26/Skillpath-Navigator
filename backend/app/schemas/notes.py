from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ..domain.notes_text import clean_title

MAX_BODY = 100_000


class _TitleMixin(BaseModel):
    title: str = Field(min_length=1, max_length=120)

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str) -> str:
        value = clean_title(value)
        if not value:
            raise ValueError("Give the note a name")
        return value


class NoteCreate(_TitleMixin):
    body: str = Field(default="", max_length=MAX_BODY)
    source: Literal["written", "generated"] = "written"
    subject: str = Field(default="", max_length=120)


class NoteUpdate(_TitleMixin):
    body: str = Field(max_length=MAX_BODY)
    pinned: bool = False
    revision: int = Field(ge=1)  # the revision the editor last loaded
