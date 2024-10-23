from typing import Annotated

from pydantic import BaseModel, Field


class Employee(BaseModel):
    age: Annotated[int, Field(ge=18, le=67)]
    level: Annotated[int, Field(1, gt=0, lt=6)]
    salary: Annotated[float, Field(gt=1000, lt=10000)]
