import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

YEARS = Literal["1st Year", "2nd Year", "3rd Year", "4th Year", "Graduate", "Other"]
LEVELS = Literal["Beginner", "Intermediate", "Advanced"]


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    college: str = Field(default="", max_length=180)
    branch: str = Field(default="", max_length=100)
    academic_year: YEARS = "3rd Year"

    @field_validator("name", "college", "branch")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("password")
    @classmethod
    def _password_policy(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes")  # bcrypt's hard limit
        if not (re.search(r"[A-Za-z]", value) and re.search(r"\d", value)):
            raise ValueError("Password must contain at least one letter and one number")
        return value


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class ProfileUpdate(BaseModel):
    college: str | None = Field(default=None, max_length=180)
    branch: str | None = Field(default=None, max_length=100)
    academic_year: YEARS | None = None
    skill_level: LEVELS | None = None
    target_role: str | None = Field(default=None, max_length=100)
    target_package: str | None = Field(default=None, max_length=40)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    college: str
    degree: str
    branch: str
    academic_year: str
    skill_level: str
    target_role: str
    target_package: str
    is_admin: bool
