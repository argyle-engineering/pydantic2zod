# pyright: reportPrivateUsage=false

from snapshottest.module import SnapshotTest

from pydantic2zod._compiler import Compiler


def test_renames_models_based_on_given_rules(snapshot: SnapshotTest):
    class MyCompiler(Compiler):
        MODEL_RENAME_RULES = {"tests.fixtures.all_in_one.Class": "BaseClass"}

    out_src = MyCompiler().parse("tests.fixtures.unique_names").to_zod()
    snapshot.assert_match(out_src)


def test_initializes_empty_lists(snapshot: SnapshotTest):
    out_src = Compiler().parse("tests.fixtures.default_values").to_zod()
    snapshot.assert_match(out_src)


def test_generic_field_type_is_any_with_no_typevar_bounds(snapshot: SnapshotTest):
    out_src = Compiler().parse("tests.fixtures.generic_models").to_zod()
    snapshot.assert_match(out_src)
