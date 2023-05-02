# pyright: reportPrivateUsage=false

from importlib import import_module

import pytest
from networkx import DiGraph

from pydantic2zod._model import (
    AnyType,
    ClassDecl,
    ClassField,
    GenericType,
    PrimitiveType,
    UnionType,
    UserDefinedType,
)
from pydantic2zod._parser import _ParseModule, parse


def test_recurses_into_imported_modules():
    m = import_module("tests.fixtures.external")

    classes = parse(m, set())

    assert classes == [
        ClassDecl(
            name="Class",
            full_path="tests.fixtures.all_in_one.Class",
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
            full_path="tests.fixtures.all_in_one.DataClass",
            fields=[ClassField(name="frozen", type=PrimitiveType(name="bool"))],
            base_classes=["Class"],
        ),
        ClassDecl(
            name="Module",
            full_path="tests.fixtures.external.Module",
            fields=[
                ClassField(name="name", type=PrimitiveType(name="str")),
                ClassField(
                    name="classes",
                    type=GenericType(
                        generic="list",
                        type_vars=[
                            UserDefinedType(name="tests.fixtures.all_in_one.DataClass")
                        ],
                    ),
                ),
            ],
            base_classes=["BaseModel"],
        ),
    ]


class TestParseModule:
    def test_parses_all_pydantic_models_within_same_module(self):
        """
        - parses pydantic models
        - skips non-pydantic classes
        """
        classes = (
            _ParseModule(import_module("tests.fixtures.all_in_one"), DiGraph(), set())
            .exec()
            .classes()
        )

        assert classes == [
            ClassDecl(
                name="Class",
                full_path="tests.fixtures.all_in_one.Class",
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
                full_path="tests.fixtures.all_in_one.DataClass",
                base_classes=["Class"],
                fields=[
                    ClassField(name="frozen", type=PrimitiveType(name="bool")),
                ],
            ),
            ClassDecl(
                name="Module",
                full_path="tests.fixtures.all_in_one.Module",
                base_classes=["BaseModel"],
                fields=[
                    ClassField(name="name", type=PrimitiveType(name="str")),
                    ClassField(
                        name="classes",
                        type=GenericType(
                            generic="list",
                            type_vars=[
                                UserDefinedType(name="tests.fixtures.all_in_one.Class")
                            ],
                        ),
                    ),
                ],
            ),
        ]

    def test_parses_only_the_models_explicitly_asked(self):
        classes = (
            _ParseModule(
                import_module("tests.fixtures.all_in_one"),
                DiGraph(),
                set(),
                parse_only_models={"Class"},
            )
            .exec()
            .classes()
        )

        assert set(c.name for c in classes) == {"Class"}

    def test_parses_only_the_models_explicitly_asked_and_their_dependencies(self):
        classes = (
            _ParseModule(
                import_module("tests.fixtures.all_in_one"),
                DiGraph(),
                set(),
                parse_only_models={"Module"},
            )
            .exec()
            .classes()
        )

        assert set(c.name for c in classes) == {"Class", "Module"}

    def test_detects_external_models(self):
        parse = _ParseModule(
            import_module("tests.fixtures.external"), DiGraph(), set()
        ).exec()

        assert parse.external_models() == {"tests.fixtures.all_in_one.DataClass"}
        assert parse.classes() == [
            ClassDecl(
                name="Module",
                full_path="tests.fixtures.external.Module",
                base_classes=["BaseModel"],
                fields=[
                    ClassField(name="name", type=PrimitiveType(name="str")),
                    ClassField(
                        name="classes",
                        type=GenericType(
                            generic="list",
                            type_vars=[
                                UserDefinedType(
                                    name="tests.fixtures.all_in_one.DataClass"
                                )
                            ],
                        ),
                    ),
                ],
            ),
        ]

    def test_supports_explicit_type_alias(self):
        parse = _ParseModule(
            import_module("tests.fixtures.type_alias"), DiGraph(), set()
        ).exec()

        assert parse.classes() == [
            ClassDecl(
                name="Function",
                full_path="tests.fixtures.type_alias.Function",
                fields=[ClassField(name="name", type=PrimitiveType(name="str"))],
                base_classes=["BaseModel"],
            ),
            ClassDecl(
                name="LambdaFunc",
                full_path="tests.fixtures.type_alias.LambdaFunc",
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
                full_path="tests.fixtures.type_alias.EventBus",
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

    def test_supports_builtin_types(self):
        parse = _ParseModule(
            import_module("tests.fixtures.builtin_types"), DiGraph(), set()
        ).exec()

        assert parse.classes() == [
            ClassDecl(
                name="User",
                full_path="tests.fixtures.builtin_types.User",
                fields=[
                    ClassField(name="id", type=UserDefinedType(name="uuid.UUID")),
                    ClassField(name="name", type=PrimitiveType(name="str")),
                    ClassField(
                        name="belongs_to",
                        type=UnionType(
                            types=[
                                UserDefinedType(name="uuid.UUID"),
                                PrimitiveType(name="None"),
                            ]
                        ),
                    ),
                ],
                base_classes=["BaseModel"],
            )
        ]
        # built-in types are not considered external models
        assert parse.external_models() == set()

    def test_resolves_import_aliases(self):
        parse = _ParseModule(
            import_module("tests.fixtures.import_alias"), DiGraph(), set()
        ).exec()

        assert parse.classes() == [
            ClassDecl(
                name="Module",
                full_path="tests.fixtures.import_alias.Module",
                fields=[
                    ClassField(name="name", type=PrimitiveType(name="str")),
                    ClassField(
                        name="classes",
                        type=GenericType(
                            generic="list",
                            type_vars=[
                                UserDefinedType(name="tests.fixtures.all_in_one.Class")
                            ],
                        ),
                    ),
                ],
                base_classes=["BaseModel"],
            )
        ]
        # built-in types are not considered external models
        assert parse.external_models() == set(["tests.fixtures.all_in_one.Class"])

    class TestIgnoreModels:
        def test_basic(self):
            """Class fields with ignored types become `AnyType`"""
            parse = _ParseModule(
                import_module("tests.fixtures.ignore_parsing"),
                DiGraph(),
                {"tests.fixtures.ignore_parsing.Config"},
            ).exec()

            assert parse.classes() == [
                ClassDecl(
                    name="App",
                    full_path="tests.fixtures.ignore_parsing.App",
                    fields=[
                        ClassField(name="version", type=PrimitiveType(name="str")),
                        ClassField(name="config", type=AnyType()),
                    ],
                    base_classes=["BaseModel"],
                ),
            ]

        @pytest.mark.xfail(
            reason="Some cases implemented yet: ignored base class, ignored type is "
            "generic type variable: list[IgnoredT]"
        )
        def test_with_generics(self):
            parse = _ParseModule(
                import_module("tests.fixtures.all_in_one"),
                DiGraph(),
                {"tests.fixtures.all_in_one.Class"},
            ).exec()

            assert parse.classes() == [
                ClassDecl(
                    name="DataClass",
                    full_path="tests.fixtures.all_in_one.DataClass",
                    fields=[ClassField(name="frozen", type=PrimitiveType(name="bool"))],
                    base_classes=["Class"],
                ),
                ClassDecl(
                    name="Module",
                    full_path="tests.fixtures.all_in_one.Module",
                    fields=[
                        ClassField(name="name", type=PrimitiveType(name="str")),
                        ClassField(
                            name="classes",
                            type=GenericType(
                                generic="list",
                                type_vars=[
                                    UserDefinedType(
                                        name="tests.fixtures.all_in_one.Class"
                                    )
                                ],
                            ),
                        ),
                    ],
                    base_classes=["BaseModel"],
                ),
            ]
