from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True, slots=True)
class Conversion:
    event_time: datetime
    event_name: str
    email_hash: str
    phone_hash: str
    value: float
    currency: str
    order_id: str

    def epoch_seconds(self) -> int:
        return int(self.event_time.timestamp())


Status = Literal["ok", "error"]


@dataclass(frozen=True, slots=True)
class SendResult:
    platform: str
    order_id: str
    event_id: str
    status: Status
    http_code: int | None = None
    error: str | None = None
