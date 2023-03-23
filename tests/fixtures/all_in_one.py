from dataclasses import dataclass
from typing import List

from pydantic import BaseModel


class Class(BaseModel):
    name: str
    methods: List[str]


class DataClass(Class):
    frozen: bool


class Module(BaseModel):
    name: str
    classes: list[Class]


class Environment:
    def __init__(self):
        ...


@dataclass
class BuildInfo:
    os: str
