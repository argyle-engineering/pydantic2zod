from pydantic import BaseModel


class Foo(BaseModel):
    pass


class Bar(BaseModel):
    pass


class Model(BaseModel):
    x: str | int
    y: Foo | Bar

    class Config:
        smart_union = True
