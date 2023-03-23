from pydantic import BaseModel

from .all_in_one import DataClass


class Module(BaseModel):
    name: str
    classes: list[DataClass]
