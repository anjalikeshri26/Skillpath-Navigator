from pydantic import BaseModel


class RoadmapUpdate(BaseModel):
    completed: bool
