from pydantic import BaseModel

from .all_in_one import Class as Cls


class Module(BaseModel):
    name: str
    classes: list[Cls]
