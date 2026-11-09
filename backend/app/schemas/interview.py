from pydantic import BaseModel, Field


class StartInterviewIn(BaseModel):
    role: str = Field(default="", max_length=100)
    difficulty: str = Field(default="Medium", pattern="^(Easy|Medium|Hard|Advanced)$")
    use_resume: bool = True


class TurnIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
