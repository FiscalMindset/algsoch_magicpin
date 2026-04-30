from pydantic import BaseModel
from typing import Optional
from enum import Enum


class ActionType(str, Enum):
    SEND = "send"
    WAIT = "wait"
    END = "end"


class ComposedMessage(BaseModel):
    body: str
    cta: str  # "open_ended", "binary_yes_no", "none"
    send_as: str  # "vera", "merchant"
    template_id: Optional[str] = None
    suppression_key: str
    rationale: str
