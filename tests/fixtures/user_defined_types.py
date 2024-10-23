from pydantic import BaseModel, ConfigDict


class Ulid(str): ...


class User(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    id: Ulid
