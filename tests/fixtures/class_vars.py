from typing import ClassVar

from pydantic import BaseModel


class RpcMessage(BaseModel):
    msg_type: str
    __description__: ClassVar[str] = "Base class for all RPC messages"
