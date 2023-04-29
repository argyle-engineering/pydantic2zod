from typing import Generic, TypeVar

from pydantic.generics import GenericModel

AddrT = TypeVar("AddrT")
"""Different countries have different address format."""


class User(GenericModel, Generic[AddrT]):
    name: str
    address: AddrT
