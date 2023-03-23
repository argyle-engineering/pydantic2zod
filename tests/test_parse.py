# pyright: reportPrivateUsage=false

from importlib import import_module
from pathlib import Path

import libcst as cst
from networkx import DiGraph

from pydantic2zod._model import (
    ClassDecl,
    ClassField,
    GenericType,
    PrimitiveType,
    UnionType,
    UserDefinedType,
)
from pydantic2zod._parser import _ParseModule, parse


def _parse_file(fname: str) -> cst.Module:
    return cst.parse_module(Path(fname).read_text())


def test_recurses_into_imported_modules():
    m = import_module("tests.fixtures.external")

    classes = parse(m)

    assert classes == [
        ClassDecl(
            name="Class",
            fields=[
                ClassField(name="name", type=PrimitiveType(name="str")),
                ClassField(
                    name="methods",
                    type=GenericType(
                        generic="list", type_vars=[PrimitiveType(name="str")]
                    ),
                ),
            ],
            base_classes=["BaseModel"],
        ),
        ClassDecl(
            name="DataClass",
            fields=[ClassField(name="frozen", type=PrimitiveType(name="bool"))],
            base_classes=["Class"],
        ),
        ClassDecl(
            name="Module",
            fields=[
                ClassField(name="name", type=PrimitiveType(name="str")),
                ClassField(
                    name="classes",
                    type=GenericType(
                        generic="list", type_vars=[UserDefinedType(name="DataClass")]
                    ),
                ),
            ],
            base_classes=["BaseModel"],
        ),
    ]


class TestParseModule:
    def test_parses_all_pydantic_models_within_the_same_module(self):
        """
        - parses pydantic models
        - skips non-pydantic classes
        """
        classes = (
            _ParseModule(DiGraph())
            .visit(_parse_file("tests/fixtures/all_in_one.py"))
            .classes()
        )

        assert classes == [
            ClassDecl(
                name="Class",
                base_classes=["BaseModel"],
                fields=[
                    ClassField(name="name", type=PrimitiveType(name="str")),
                    ClassField(
                        name="methods",
                        type=GenericType(
                            generic="list", type_vars=[PrimitiveType(name="str")]
                        ),
                    ),
                ],
            ),
            ClassDecl(
                name="DataClass",
                base_classes=["Class"],
                fields=[
                    ClassField(name="frozen", type=PrimitiveType(name="bool")),
                ],
            ),
            ClassDecl(
                name="Module",
                base_classes=["BaseModel"],
                fields=[
                    ClassField(name="name", type=PrimitiveType(name="str")),
                    ClassField(
                        name="classes",
                        type=GenericType(
                            generic="list", type_vars=[UserDefinedType(name="Class")]
                        ),
                    ),
                ],
            ),
        ]

    def test_parses_only_the_models_explicitly_asked(self):
        classes = (
            _ParseModule(DiGraph(), parse_only_models={"Class"})
            .visit(_parse_file("tests/fixtures/all_in_one.py"))
            .classes()
        )

        assert len(classes) == 1
        assert classes[0].name == "Class"

    def test_parses_only_the_models_explicitly_asked_and_their_dependencies(self):
        classes = (
            _ParseModule(DiGraph(), parse_only_models={"Module"})
            .visit(_parse_file("tests/fixtures/all_in_one.py"))
            .classes()
        )

        assert len(classes) == 2
        assert classes[0].name == "Class"
        assert classes[1].name == "Module"

    def test_detects_external_models(self):
        parse = _ParseModule(DiGraph()).visit(_parse_file("tests/fixtures/external.py"))

        assert parse.external_models() == {"DataClass": ".all_in_one"}
        assert parse.classes() == [
            ClassDecl(
                name="Module",
                base_classes=["BaseModel"],
                fields=[
                    ClassField(name="name", type=PrimitiveType(name="str")),
                    ClassField(
                        name="classes",
                        type=GenericType(
                            generic="list",
                            type_vars=[UserDefinedType(name="DataClass")],
                        ),
                    ),
                ],
            ),
        ]

    def test_supports_explicit_type_alias(self):
        parse = _ParseModule(DiGraph()).visit(
            _parse_file("tests/fixtures/type_alias.py")
        )

        assert parse.classes() == [
            ClassDecl(
                name="Function",
                fields=[ClassField(name="name", type=PrimitiveType(name="str"))],
                base_classes=["BaseModel"],
            ),
            ClassDecl(
                name="LambdaFunc",
                fields=[
                    ClassField(
                        name="args",
                        type=GenericType(
                            generic="list", type_vars=[PrimitiveType(name="str")]
                        ),
                    )
                ],
                base_classes=["BaseModel"],
            ),
            ClassDecl(
                name="EventBus",
                fields=[
                    ClassField(
                        name="handlers",
                        type=UnionType(
                            types=[
                                UserDefinedType(name="Function"),
                                UserDefinedType(name="LambdaFunc"),
                            ]
                        ),
                    )
                ],
                base_classes=["BaseModel"],
            ),
        ]
