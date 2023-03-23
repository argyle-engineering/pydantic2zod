from pydantic import BaseModel


class User(BaseModel):
    id: int
    name: str
    email: str


class Address(BaseModel):
    street: str
    city: str
    state: str
    zip: str


class Product(BaseModel):
    id: int
    name: str
    description: str | None
    price: float
    is_available: bool
    is_available: bool


class Order(BaseModel):
    id: int
    user: User
    items: list[Product]
    address: Address
