"""Python program model.

Once the source code is parsed we use this in-mem model to manipulate it
programmatically: e.g. generate TypeScript code, etc.
"""
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class PyType:
    ...


@dataclass
class PyValue:
    ...


@dataclass
class Import:
    from_module: str
    "pkg.module1"

    name: str
    "ClassName"

    alias: str | None = None
    """`import module.Class as OtherClass`"""


@dataclass
class ClassField:
    name: str
    type: PyType
    default_value: PyValue | None = None
    comment: str | None = None


@dataclass
class ClassDecl:
    name: str
    full_path: str = ""
    """pkg1.module.ClassName"""
    fields: list[ClassField] = field(default_factory=lambda: [])
    base_classes: list[str] = field(default_factory=lambda: [])
    comment: str | None = None


@dataclass
class PyString(PyValue):
    value: str


@dataclass
class PyNone(PyValue):
    """A placeholder for `None` value."""

    def __repr__(self) -> str:
        return "PyNone"


@dataclass
class PyName(PyValue):
    """A symbolic reference to a variable, class, function, etc."""

    value: str


@dataclass
class PyDict(PyValue):
    """Represents an empty dict for now."""

    ...


@dataclass
class PyList(PyValue):
    """Represents an empty list for now."""

    ...


@dataclass
class BuiltinType(PyType):
    name: Literal[
        "str",
        "bytes",
        "int",
        "float",
        "bool",
        "None",
        "list",
        "dict",
    ]


@dataclass
class PrimitiveType(BuiltinType):
    name: Literal["str", "bytes", "int", "float", "bool", "None"]


@dataclass
class UserDefinedType(PyType):
    name: str


@dataclass
class GenericType(PyType):
    generic: str
    type_vars: list[PyType]


@dataclass
class LiteralType(PyType):
    value: str


@dataclass
class UnionType(PyType):
    types: list[PyType]


@dataclass
class TupleType(PyType):
    types: list[PyType]
