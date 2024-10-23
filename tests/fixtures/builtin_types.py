from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class User(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    belongs_to: UUID | None
