"""Produces valid TypeScript code - `zod` declarations."""

import logging
from typing import Callable

from pydantic2zod.model import (
    AnnotatedType,
    AnyType,
    BuiltinType,
    ClassDecl,
    ClassField,
    GenericType,
    LiteralType,
    PrimitiveType,
    PydanticField,
    PyDict,
    PyFloat,
    PyInteger,
    PyList,
    PyName,
    PyNone,
    PyString,
    PyType,
    PyValue,
    TupleType,
    UnionType,
    UserDefinedType,
)

_logger = logging.getLogger(__name__)


class Codegen:
    """Adjustable zod code generator."""

    def __init__(
        self,
        model_rename_rules: dict[str, str] | None = None,
        modify_models: Callable[[list[ClassDecl]], list[ClassDecl]] | None = None,
        gen_header: Callable[[], str] | None = None,
    ) -> None:
        self._model_rename_rules = model_rename_rules or {}
        self._modify_models = modify_models or (lambda m: m)
        self._gen_header = gen_header or (lambda: "")

    def to_zod(self, pydantic_models: list[ClassDecl]) -> str:
        self._apply_model_rename_rules(pydantic_models)
        models = self._modify_models(pydantic_models)
        _warn_about_duplicate_models(models)

        code = Lines()
        code.add(self._gen_header())

        for cls in models:
            if not cls.name.startswith("_"):
                _class_to_zod(cls, code)
                code.add("")

        return str(code)

    def _apply_model_rename_rules(self, pydantic_models: list[ClassDecl]) -> None:
        for model in pydantic_models:
            if new_name := self._model_rename_rules.get(model.full_path):
                model.name = new_name

            for field in model.fields:
                self._rename_models_in_fields(field.type)

    def _rename_models_in_fields(self, field_type: PyType) -> None:
        match field_type:
            case UserDefinedType(name=type_name):
                if new_name := self._model_rename_rules.get(type_name):
                    field_type.name = new_name
            case GenericType(type_vars=type_vars):
                for type_var in type_vars:
                    self._rename_models_in_fields(type_var)
            case UnionType(types=types):
                for type_ in types:
                    self._rename_models_in_fields(type_)
            case _:
                ...


def _warn_about_duplicate_models(models: list[ClassDecl]) -> None:
    """Warns about duplicate models.

    e.g. if two models have the same name.
    """
    names = [m.name for m in models]
    duplicates = set([n for n in names if names.count(n) > 1])
    if duplicates:
        _logger.warning(
            "Multiple models with the same name: '%s'", ",".join(duplicates)
        )


def _class_to_zod(cls: ClassDecl, code: "Lines") -> None:
    if comment := cls.comment:
        _comment_to_ts(comment, code)

    if cls.base_classes[0] in ["BaseModel", "GenericModel"]:
        constructor = "z.object({"
    else:
        constructor = f"{cls.base_classes[0]}.extend({{"

    code.add(f"export const {cls.name} = {constructor}")

    with code as indent_code:
        for f in cls.fields:
            _class_field_to_zod(f, indent_code)
            code.add(",", inline=True)

    code.add("}).strict();")
    code.add(f"export type {cls.name}Type = z.infer<typeof {cls.name}>;")


def _comment_to_ts(comment: str, code: "Lines") -> None:
    lines = comment.split("\n")
    code.add("/**")
    for ln in lines:
        if ln.startswith("    "):
            # Assume that some comment lines start with an indentation in Python.
            ln = ln[4:]
        comment_ln = (" * " + ln).rstrip()
        code.add(comment_ln)
    code.add(" */")


def _class_field_to_zod(field: ClassField, code: "Lines") -> None:
    if comment := field.comment:
        _comment_to_ts(comment, code)

    code.add(f"{field.name}: ")
    _class_field_type_to_zod(field.type, None, code)

    if default := field.default_value:
        code.add(".default(", inline=True)
        _value_to_zod(default, code)
        code.add(")", inline=True)


def _value_to_zod(pyval: PyValue, code: "Lines") -> None:
    match pyval:
        case PyString(value=value):
            code.add(f'"{value}"', inline=True)
        case PyInteger(value=value) | PyFloat(value=value):
            code.add(value, inline=True)
        case PyNone():
            code.add("null", inline=True)
        case PyName(value=name):
            code.add(name, inline=True)
        case PyDict():
            code.add("{}", inline=True)
        case PyList():
            code.add("[]", inline=True)
        case other:
            raise AssertionError(f"Unsupported value type: '{other}'")


def _class_field_type_to_zod(
    field_type: PyType, type_constraints: PydanticField | None, code: "Lines"
) -> None:
    match field_type:
        case BuiltinType(name=type_name) | PrimitiveType(name=type_name):
            match type_name:
                case "str":
                    code.add("z.string()", inline=True)

                case "int" | "float":
                    code.add("z.number()", inline=True)
                    if type_name == "int":
                        code.add(".int()", inline=True)
                    if type_constraints:
                        if type_constraints.gt is not None:
                            code.add(".gt(", inline=True)
                            _value_to_zod(type_constraints.gt, code)
                            code.add(")", inline=True)
                        if type_constraints.ge is not None:
                            code.add(".gte(", inline=True)
                            _value_to_zod(type_constraints.ge, code)
                            code.add(")", inline=True)
                        if type_constraints.lt is not None:
                            code.add(".lt(", inline=True)
                            _value_to_zod(type_constraints.lt, code)
                            code.add(")", inline=True)
                        if type_constraints.le is not None:
                            code.add(".lte(", inline=True)
                            _value_to_zod(type_constraints.le, code)
                            code.add(")", inline=True)

                case "None":
                    code.add("z.null()", inline=True)
                case "bool":
                    code.add("z.boolean()", inline=True)
                case "dict":
                    code.add("z.record(z.any())", inline=True)
                case "list":
                    code.add("z.array(z.any())", inline=True)
                case other:
                    raise AssertionError(f"Unsupported field type: '{other}'")

        case LiteralType(value=value):
            code.add(f'z.literal("{value}")', inline=True)

        case UnionType(types=types) | TupleType(types=types):
            zod_obj = "union" if isinstance(field_type, UnionType) else "tuple"
            code.add(f"z.{zod_obj}([", inline=True)
            with code as indent_code:
                code.add("")
                for i, tp in enumerate(types):
                    _class_field_type_to_zod(tp, type_constraints, indent_code)
                    code.add(",", inline=True)
                    if i < len(types) - 1:
                        code.add("")
            code.add("])")

        case GenericType(generic=generic, type_vars=type_vars):
            match generic:
                case "dict":
                    code.add("z.record(", inline=True)
                case "list":
                    code.add("z.array(", inline=True)
                case "tuple":
                    code.add("z.tuple(", inline=True)
                case other:
                    raise AssertionError(f"Unsupported generic type: '{other}'")

            for i, tv in enumerate(type_vars):
                _class_field_type_to_zod(tv, type_constraints, code)
                if i < len(type_vars) - 1:
                    code.add(", ", inline=True)
            code.add(")", inline=True)

        case UserDefinedType(name=type_name):
            if type_name == "uuid.UUID":
                code.add("z.string().uuid()", inline=True)
            elif type_name == "datetime.datetime":
                code.add("z.string().datetime()", inline=True)
            else:
                type_name = type_name.split(".")[-1]
                code.add(type_name, inline=True)

        case AnyType():
            code.add("z.any()", inline=True)

        case AnnotatedType(type_=type_, metadata=metadata):
            _class_field_type_to_zod(type_, metadata, code)

        case other:
            raise AssertionError(f"Unsupported field type: '{other}'")


class Lines:
    """A helper to deal with indentation."""

    def __init__(self) -> None:
        self._lines: list[str] = []
        self._indent = 0

    def __enter__(self) -> "Lines":
        self._indent += 2
        return self

    def __exit__(self, exception_type, exception_value, traceback) -> None:
        self._indent -= 2
        self._inline = False

    def add(self, text: str, inline: bool = False) -> None:
        if inline:
            self._lines[-1] += text
        else:
            self._lines.append(" " * self._indent + text)

    def __str__(self) -> str:
        return "\n".join(self._lines)
