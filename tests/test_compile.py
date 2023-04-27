# pyright: reportPrivateUsage=false
from importlib import import_module

from snapshottest.module import SnapshotTest

from pydantic2zod._compiler import Compiler
from pydantic2zod._parser import parse


def test_renames_models_based_on_given_rules(snapshot: SnapshotTest):
    class MyCompiler(Compiler):
        MODEL_NAME_RULES = {"tests.fixtures.all_in_one.Class": "BaseClass"}

    m = import_module("tests.fixtures.unique_names")
    classes = parse(m)

    out_src = MyCompiler().compile(classes)
    snapshot.assert_match(out_src)
