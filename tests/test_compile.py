import pydantic
import pytest
from snapshottest.module import SnapshotTest

from pydantic2zod._compiler import Compiler


def test_renames_models_based_on_given_rules(snapshot: SnapshotTest):
    class MyCompiler(Compiler):
        MODEL_RENAME_RULES = {"tests.fixtures.all_in_one.Class": "BaseClass"}

    out_src = MyCompiler().parse("tests.fixtures.unique_names").to_zod()
    snapshot.assert_match(out_src)


def test_initializes_empty_lists(snapshot: SnapshotTest):
    out_src = Compiler().parse("tests.fixtures.default_values_list").to_zod()
    snapshot.assert_match(out_src)


def test_initializes_empty_dicts(snapshot: SnapshotTest):
    out_src = Compiler().parse("tests.fixtures.default_values_dict").to_zod()
    snapshot.assert_match(out_src)


def test_generic_field_type_is_any_with_no_typevar_bounds(snapshot: SnapshotTest):
    out_src = Compiler().parse("tests.fixtures.generic_models").to_zod()
    snapshot.assert_match(out_src)


def test_with_pydantic_model_config(snapshot: SnapshotTest):
    out_src = Compiler().parse("tests.fixtures.with_model_config").to_zod()
    snapshot.assert_match(out_src)


def test_user_defined_types_inheriting_from_str(snapshot: SnapshotTest):
    out_src = Compiler().parse("tests.fixtures.user_defined_types").to_zod()
    snapshot.assert_match(out_src)


def test_class_variables_are_skipped(snapshot: SnapshotTest):
    out_src = Compiler().parse("tests.fixtures.class_vars").to_zod()
    snapshot.assert_match(out_src)


def test_builtin_types(snapshot: SnapshotTest):
    out_src = Compiler().parse("tests.fixtures.builtin_types").to_zod()
    snapshot.assert_match(out_src)


@pytest.mark.skipif(
    not pydantic.VERSION.startswith("2"), reason="Only works with pydantic v2"
)
def test_annotated_fields(snapshot: SnapshotTest):
    out_src = Compiler().parse("tests.fixtures.annotated_fields").to_zod()
    snapshot.assert_match(out_src)
