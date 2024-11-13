from pydantic import BaseModel, Field


class Class(BaseModel):
    some_dict: dict[str, int] = {}
    some_other_dict: dict[str, int] = Field(default_factory=dict)
    created_at: int = 0
