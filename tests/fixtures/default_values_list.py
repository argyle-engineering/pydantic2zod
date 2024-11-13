from pydantic import BaseModel, Field


class Class(BaseModel):
    methods: list[str] = []
    dunder_methods: list[str] = Field(default_factory=list)
    created_at: int = 0
