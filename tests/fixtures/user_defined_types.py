from pydantic import BaseModel


class Ulid(str):
    ...


class User(BaseModel):
    id: Ulid
