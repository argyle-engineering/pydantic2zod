"""An incomplete Python parser focused around Pydantic declarations."""

import inspect
import logging
from importlib import import_module
from importlib.util import resolve_name
from itertools import chain
from pathlib import Path
from types import ModuleType
from typing import Generic, Literal, NewType, TypeVar, cast

import libcst as cst
import libcst.matchers as m
from networkx import DiGraph, dfs_postorder_nodes
from typing_extensions import Self

from pydantic2zod.model import (
    AnnotatedType,
    AnyType,
    BuiltinType,
    ClassDecl,
    ClassField,
    GenericType,
    Import,
    LiteralType,
    PrimitiveType,
    PydanticField,
    PyDict,
    PyFloat,
    PyInteger,
    PyList,
    PyNone,
    PyString,
    PyType,
    PyValue,
    TupleType,
    UnionType,
    UserDefinedType,
)

_logger = logging.getLogger(__name__)


Imports = NewType("Imports", dict[str, Import])
"""imported_symbol -> from_module

e.g. Request --> scanner_common.http.cassette
"""


def parse(module: ModuleType, ignore_types: set[str]) -> list[ClassDecl]:
    """
    Args:
        ignore_types: fully qualified names of types to ignore when parsing.
            .e.g. `pkg1.module1.MyType` - say when `MyType` is a deeply nested
            complicated type that pydantic2zod is not capable of parsing, we can
            tell the parser to ignore parsing it and instead use `Any` type.
    """
    model_graph = DiGraph()
    pydantic_models = _parse(module, set(), model_graph, ignore_types)
    models_by_name = {c.full_path: c for c in pydantic_models}
    ordered_models = list[str](dfs_postorder_nodes(model_graph))
    return [models_by_name[c] for c in ordered_models if c in models_by_name]


def _parse(
    module: ModuleType,
    parse_only_models: set[str],
    model_graph: DiGraph,
    ignore_types: set[str],
) -> list[ClassDecl]:
    fname = module.__file__ or "SHOULD EXIST"
    _logger.info("Parsing module '%s'", fname)

    classes = list[ClassDecl]()

    parse_module = _ParseModule(module, model_graph, ignore_types, parse_only_models)
    m = cst.parse_module(Path(fname).read_text())
    classes += parse_module.visit(m).classes()

    if depends_on := parse_module.external_models():
        _logger.info("'%s' depends on other pydantic models:", fname)
        for model_path in depends_on:
            _logger.info("    '%s'", model_path)

        for model_path in depends_on:
            m = import_module(".".join(model_path.split(".")[:-1]))
            model_name = model_path.split(".")[-1]
            classes += _parse(m, {model_name}, model_graph, ignore_types)

    return classes


_NodeT = TypeVar("_NodeT", bound=cst.CSTNode)


class _Parse(m.MatcherDecoratableVisitor, Generic[_NodeT]):
    def visit(self, node: _NodeT) -> Self:
        node.visit(self)
        return self


class _ParseModule(_Parse[cst.Module]):
    def __init__(
        self,
        module: ModuleType,
        model_graph: DiGraph,
        ignore_types: set[str],
        parse_only_models: set[str] | None = None,
    ) -> None:
        """
        Args:
            ignore_types: fully qualified names of types to ignore when parsing:
                'pkg1.module1.MyType'
        """
        super().__init__()

        self._parse_only_models = parse_only_models
        self._ignore_types = ignore_types or set()
        self._model_graph = model_graph
        self._parsing_module = module

        # All classes found in the module.
        self._classes: dict[str, ClassDecl] = {}
        self._pydantic_classes: dict[str, ClassDecl] = {}
        self._class_nodes: dict[str, cst.ClassDef] = {}
        self._alias_nodes: dict[str, cst.AnnAssign] = {}

        self._external_models = set[str]()
        self._imports = Imports({})

    def exec(self) -> Self:
        """A helper for tests."""
        self.visit(cst.parse_module(inspect.getsource(self._parsing_module)))
        return self

    def external_models(self) -> set[str]:
        """A List of pydantic models coming from other Python modules.

        Built-in common types like uuid.UUID are filtered out so that pydantic2zod
        would not try to parse them recursively.
        """
        return self._external_models

    def classes(self) -> list[ClassDecl]:
        return list(self._pydantic_classes.values())

    def visit_ImportFrom(self, node: cst.ImportFrom):
        self._imports |= {
            i.alias or i.name: i for i in _ParseImportFrom().visit(node).imports()
        }

    def visit_ClassDef(self, node: cst.ClassDef):
        cls = _ParseClassDecl().visit(node).class_decl
        cls.full_path = f"{self._parsing_module.__name__}.{cls.name}"
        self._class_nodes[cls.name] = node
        self._classes[cls.name] = cls

    @m.call_if_inside(
        m.AnnAssign(annotation=m.Annotation(annotation=m.Name("TypeAlias")))
    )
    # Only global namespace.
    @m.call_if_not_inside(m.AllOf(m.ClassDef(), m.FunctionDef()))
    def visit_AnnAssign(self, node: cst.AnnAssign):
        target = cst.ensure_type(node.target, cst.Name).value
        # We will parse the alias declaration lazily when one is used within a pydantic
        # model.
        self._alias_nodes[target] = node

    def leave_Module(self, original_node: cst.Module) -> None:
        """Parse the class definitions and resolve imported classes."""
        if self._parse_only_models:
            for m in self._parse_only_models:
                self._recursively_parse_pydantic_model(self._classes[m])
        else:
            self._parse_all_classes()
            for cls in self._pydantic_classes.values():
                self._parse_class_deps(cls)

        for cls in self._pydantic_classes.values():
            for field in cls.fields:
                # MyType(str) --> str
                if isinstance(field.type, UserDefinedType):
                    if user_type := self._classes.get(field.type.name):
                        if next(iter(user_type.base_classes), "") == "str":
                            field.type = BuiltinType(name="str")

                self._resolve_class_field_names(field.type)

                if isinstance(field.type, UserDefinedType):
                    if (
                        field.type.name in self._ignore_types
                        or field.type.name in cls.type_vars
                    ):
                        # Yet to learn know how to parse generic type variables.
                        field.type = AnyType()

    def _recursively_parse_pydantic_model(self, cls: ClassDecl) -> None:
        if not self._is_pydantic_model(cls) or cls.name in self._pydantic_classes:
            return None

        if fully_parsed_cls := self._finish_parsing_class(cls):
            for dep in self._parse_class_deps(fully_parsed_cls):
                self._recursively_parse_pydantic_model(dep)

    def _parse_class_deps(self, cls: ClassDecl) -> list[ClassDecl]:
        local_deps = []
        for dep in self._class_deps(cls):
            if resolved_dep_path := self._is_imported(dep):
                if resolved_dep_path not in [
                    "uuid.UUID",
                    "datetime.datetime",
                    "pydantic.BaseModel",
                    "pydantic.generics.GenericModel",
                ]:
                    self._external_models.add(resolved_dep_path)
                    self._model_graph.add_edge(cls.full_path, resolved_dep_path)

            elif cls_decl := self._classes.get(dep):
                local_deps.append(cls_decl)
                self._model_graph.add_edge(cls.full_path, cls_decl.full_path)
            else:
                _logger.warning(
                    "Can't infer where '%s' is coming from. '%s' depends on it.",
                    dep,
                    cls.name,
                )
        return local_deps

    def _resolve_class_field_names(self, field_type: PyType) -> None:
        """Resolve fully qualified model names in the field type."""
        match field_type:
            case UserDefinedType(name=name):
                if full_qual_name := self._qualname(name):
                    field_type.name = full_qual_name
            case GenericType(type_vars=type_vars):
                for type_var in type_vars:
                    self._resolve_class_field_names(type_var)
            case UnionType(types=types):
                for type_ in types:
                    self._resolve_class_field_names(type_)
            case _:
                ...

    def _qualname(self, type_name: str) -> str | None:
        # Type is local to this module.
        if type_name in self._classes:
            return f"{self._parsing_module.__name__}.{type_name}"

        return self._is_imported(type_name)

    def _is_imported(self, cls_name: str) -> str | None:
        """
        Returns: a full path to the class.
        """
        if cls_name not in self._imports:
            return None

        import_ = self._imports[cls_name]
        abs_module_name = resolve_name(
            import_.from_module, self._parsing_module.__package__
        )
        abs_cls_name = f"{abs_module_name}.{import_.name}"

        return abs_cls_name

    def _class_deps(self, cls: ClassDecl) -> list[str]:
        deps = [
            c
            for c in cls.base_classes
            if self._is_imported(c)
            not in [
                "pydantic.BaseModel",
                "pydantic.generics.GenericModel",
                "typing.Generic",
            ]
        ]
        for f in cls.fields:
            for type_ in _get_user_defined_types(f.type):
                # TODO(povilas): if type_ is type var,
                #                type_ = self._resolve_typevar_bound_to(dep)
                deps.append(type_)
        return deps

    def _parse_all_classes(self) -> None:
        """This case is easier as we traverse classes in a linear order parsing one by
        one."""
        for cls_decl in self._classes.values():
            if self._is_pydantic_model(cls_decl):
                self._finish_parsing_class(cls_decl)

    def _finish_parsing_class(self, cls_decl: ClassDecl) -> ClassDecl | None:
        if cls_decl.full_path in self._ignore_types:
            _logger.info("Ignore parsing '%s'", cls_decl.full_path)
            return None

        cls = _ParseClassDecl().visit(self._class_nodes[cls_decl.name]).class_decl
        cls.full_path = cls_decl.full_path
        self._model_graph.add_node(cls.full_path)
        self._pydantic_classes[cls.name] = cls

        for f in cls.fields:
            f.type = self._resolve_type_aliases(f.type)

        return cls

    def _resolve_type_aliases(self, tp: PyType) -> PyType:
        match tp:
            case UserDefinedType(name=name):
                if node := self._alias_nodes.get(name):
                    assert node.value
                    return _extract_type(node.value)
            case GenericType(type_vars=type_vars):
                for i, type_var in enumerate(type_vars):
                    tp.type_vars[i] = self._resolve_type_aliases(type_var)
            case _:
                ...

        return tp

    def _is_pydantic_model(self, cls: ClassDecl) -> bool:
        for b in cls.base_classes:
            if self._is_imported(b) in [
                "pydantic.BaseModel",
                "pydantic.generics.GenericModel",
            ]:
                return True

        # TODO(povilas): when the base is imported model, it COULD be pydantic model

        for b in cls.base_classes:
            if b in self._classes:
                return self._is_pydantic_model(self._classes[b])

        return False


class _ParseClassDecl(_Parse[cst.ClassDef]):
    def __init__(self) -> None:
        super().__init__()
        self.class_decl = ClassDecl(name="to_be_parsed", base_classes=[])
        self._last_field_nr = 0
        self._depth = 0

    def visit_ClassDef(self, node: cst.ClassDef):
        # Guard against nested classes, e.g.
        #
        #     class Model(BaseModel):
        #         class Config:
        self._depth += 1
        if self._depth > 1:
            return

        base_classes = [
            b.value.value for b in node.bases if isinstance(b.value, cst.Name)
        ]
        self.class_decl = ClassDecl(name=node.name.value, base_classes=base_classes)

    @m.call_if_inside(m.ClassDef(bases=[m.AtLeastN(n=1)]))
    @m.call_if_inside(m.Arg(value=m.Subscript()))
    @m.call_if_inside(m.SubscriptElement())
    def visit_Name(self, node: cst.Name) -> None:
        self.class_decl.type_vars.append(node.value)

    @m.call_if_inside(m.ClassDef())
    @m.call_if_not_inside(m.FunctionDef())
    @m.call_if_inside(m.SimpleStatementLine(body=[m.AtMostN(m.Expr(), n=1)]))
    def visit_SimpleString(self, node: cst.SimpleString):
        comment = node.value.replace('"""', "")

        if not self._last_field_nr:
            self.class_decl.comment = comment
        else:
            self.class_decl.fields[self._last_field_nr - 1].comment = comment

    @m.call_if_inside(m.ClassDef())
    @m.call_if_not_inside(m.FunctionDef())
    def visit_AnnAssign(self, node: cst.AnnAssign):
        self._last_field_nr += 1

        target = cst.ensure_type(node.target, cst.Name).value
        type_ = _extract_type(node.annotation.annotation)
        # ClassVars in pydantic models don't get serialized, hence we skip them.
        if isinstance(type_, UserDefinedType) and type_.name == "ClassVar":
            return

        default_value = _parse_value(node.value) if node.value else None
        self.class_decl.fields.append(
            ClassField(name=target, type=type_, default_value=default_value),
        )


class _ParseImportFrom(_Parse[cst.ImportFrom]):
    def __init__(self) -> None:
        super().__init__()
        self._from = list[str]()
        self._imports = list[Import]()
        self._relative = 0

    def imports(self) -> list[Import]:
        for imp in self._imports:
            imp.from_module = "." * self._relative + ".".join(self._from)
        return self._imports

    def visit_ImportFrom(self, node: cst.ImportFrom):
        self._relative = len(list(node.relative))

    @m.call_if_not_inside(m.ImportAlias())
    def visit_Name(self, node: cst.Name):
        self._from.append(node.value)

    def visit_ImportAlias(self, node: cst.ImportAlias) -> None:
        import_name = cst.ensure_type(node.name, cst.Name).value
        import_ = Import(from_module="", name=import_name)
        if node.asname:
            if isinstance(node.asname.name, cst.Name):
                import_.alias = node.asname.name.value
            else:
                _logger.warning(
                    "Don't know how to parse this import alias: '%s'", node.asname
                )

        self._imports.append(import_)


def _extract_type(node: cst.BaseExpression) -> PyType:
    match node:
        case cst.Name(value=type_name):
            return _primitive_or_user_defined_type(type_name)
        case cst.Subscript():
            return _parse_generic_type(node)
        case cst.BinaryOperation():
            return _extract_union(node)
        case _:
            raise AssertionError(
                f"Unexpected node in type definition: '{node.__class__}'"
            )


def _get_user_defined_types(tp: PyType) -> list[str]:
    match tp:
        case UserDefinedType(name=name):
            return [name]
        case UnionType(types=types):
            return list(chain(*[_get_user_defined_types(t) for t in types]))
        case LiteralType(type=type_):
            return _get_user_defined_types(type_)
        case GenericType(type_vars=args):
            return list(chain(*[_get_user_defined_types(a) for a in args]))
        case _:
            return []


def _parse_generic_type(
    node: cst.Subscript,
) -> (
    GenericType | LiteralType | UnionType | TupleType | UserDefinedType | AnnotatedType
):
    """Try to parse a generic type.
    Fall back to `UserDefinedType` when don't know how.
    """
    generic_type = cst.ensure_type(node.value, cst.Name).value
    match generic_type:
        case "Literal":
            return _parse_literal(node)
        case "list" | "List":
            return GenericType(generic="list", type_vars=_parse_types_list(node))
        case "dict" | "Dict":
            return GenericType(generic="dict", type_vars=_parse_types_list(node))
        case "Union":
            return UnionType(types=_parse_types_list(node))
        case "Optional":
            return UnionType(
                types=[*_parse_types_list(node), PrimitiveType(name="None")]
            )
        case "tuple" | "Tuple":
            return TupleType(types=_parse_types_list(node))
        case "Annotated":
            return _parse_annotated(node)
        case other:
            _logger.warning("Generic type not supported: '%s'", other)
            return UserDefinedType(name=other)


def _parse_literal(node: cst.Subscript) -> LiteralType | UnionType:
    assert cst.ensure_type(node.value, cst.Name).value == "Literal"

    literal_values = []
    for elem in node.slice:
        value = cst.ensure_type(
            cst.ensure_type(elem.slice, cst.Index).value, cst.SimpleString
        ).value.replace('"', "")
        literal_values.append(value)

    if len(literal_values) == 1:
        return LiteralType(value=literal_values[0])
    else:
        return UnionType(types=[LiteralType(value=v) for v in literal_values])


def _parse_annotated(node: cst.Subscript) -> AnnotatedType:
    assert cst.ensure_type(node.value, cst.Name).value == "Annotated"
    args = list(node.slice)
    if len(args) != 2:
        _logger.warning("Annotated type should have exactly two arguments")
        return AnnotatedType(type_=AnyType(), metadata=None)

    type_ = _extract_type(cst.ensure_type(args[0].slice, cst.Index).value)
    metadata = _parse_field_constraints(cst.ensure_type(args[1].slice, cst.Index).value)
    return AnnotatedType(type_=type_, metadata=metadata)


def _parse_types_list(node: cst.Subscript) -> list[PyType]:
    types = list[PyType]()
    for element in node.slice:
        type_var_node = cst.ensure_type(element.slice, cst.Index).value
        match type_var_node:
            case cst.Name(value=type_var):
                types.append(_primitive_or_user_defined_type(type_var))
            case other:
                types.append(_extract_type(other))
    return types


def _primitive_or_user_defined_type(
    type_name: str,
) -> PrimitiveType | UserDefinedType | BuiltinType:
    match type_name:
        case "str" | "bytes" | "bool" | "int" | "float" | "None":
            return PrimitiveType(name=type_name)
        case "dict" | "Dict" | "list" | "List":
            return BuiltinType(name=cast(Literal["dict", "list"], type_name.lower()))
        case _:
            return UserDefinedType(name=type_name)


def _extract_union(node: cst.BinaryOperation) -> UnionType:
    cst.ensure_type(node.operator, cst.BitOr)
    all_types = []

    left = _extract_type(node.left)
    match left:
        case UnionType(types=types):
            all_types += types
        case single_type:
            all_types.append(single_type)

    right = _extract_type(node.right)
    match right:
        case UnionType(types=types):
            all_types += types
        case single_type:
            all_types.append(single_type)

    return UnionType(types=all_types)


def _parse_value(node: cst.BaseExpression) -> PyValue:
    match node:
        case cst.SimpleString(value=value):
            return PyString(value=value.replace('"', ""))
        case cst.Name(value="None"):
            return PyNone()
        case cst.Dict():
            return PyDict()
        case cst.List():
            return PyList()
        case cst.Integer(value=value):
            return PyInteger(value=value)
        case cst.Float(value=value):
            return PyFloat(value=value)
        case cst.Call():
            if empty_list := _parse_value_from_call(node):
                return empty_list
            else:
                _logger.warning("Unsupported value type: '%s'", node)
                return PyNone()
        case other:
            _logger.warning("Unsupported value type: '%s'", other)
            return PyNone()


def _parse_value_from_call(node: cst.Call) -> PyValue | None:
    if m.matches(
        node,
        m.Call(
            func=m.Name("Field"),
            args=[m.Arg(value=m.Name("list"), keyword=m.Name("default_factory"))],
        ),
    ):
        return PyList()
    if m.matches(
        node,
        m.Call(
            func=m.Name("Field"),
            args=[m.Arg(value=m.Name("dict"), keyword=m.Name("default_factory"))],
        ),
    ):
        return PyDict()
    return None


def _parse_field_constraints(node: cst.BaseExpression) -> PydanticField | None:
    if not m.matches(
        node,
        m.Call(func=m.Name("Field")),
    ):
        return None
    node = cst.ensure_type(node, cst.Call)

    field_decl = PydanticField()

    for arg in node.args:
        if not (arg_name := arg.keyword):
            continue

        arg_value = _parse_value(arg.value)
        match arg_name.value:
            case "gt":
                field_decl.gt = arg_value
            case "ge":
                field_decl.ge = arg_value
            case "lt":
                field_decl.lt = arg_value
            case "le":
                field_decl.le = arg_value
            case _:
                ...

    return field_decl
