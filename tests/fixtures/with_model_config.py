from pydantic import BaseModel, ConfigDict


class Foo(BaseModel):
    pass


class Bar(BaseModel):
    pass


class Model(BaseModel):
    model_config = ConfigDict(title="ModifiedModelName")

    x: str | int
    y: Foo | Bar

    class ArbitraryNestedClass(object):
        pass
