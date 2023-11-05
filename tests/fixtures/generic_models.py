from typing import Generic, TypeVar

from pydantic import BaseModel

AddrT = TypeVar("AddrT")
"""Different countries have different address format."""


class User(BaseModel, Generic[AddrT]):
    name: str
    address: AddrT
