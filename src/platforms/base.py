from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol

from ..models import Conversion, SendResult


class PlatformClient(Protocol):
    name: str

    def send(self, conversions: Sequence[Conversion]) -> list[SendResult]: ...


def chunk(items: Sequence, size: int) -> Iterable[Sequence]:
    for i in range(0, len(items), size):
        yield items[i : i + size]
