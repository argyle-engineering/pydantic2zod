from pydantic import BaseModel


class Config(BaseModel):
    dark_mode: bool


class App(BaseModel):
    version: str
    config: Config
