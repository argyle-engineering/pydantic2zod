from typing import TypeAlias

from pydantic import BaseModel


class Function(BaseModel):
    name: str


class LambdaFunc(BaseModel):
    args: list[str]


EventHandler: TypeAlias = Function | LambdaFunc


class EventBus(BaseModel):
    handlers: EventHandler
