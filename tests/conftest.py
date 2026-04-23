from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.hashing import sha256_hex
from src.models import Conversion


@pytest.fixture
def sample_conversion() -> Conversion:
    return Conversion(
        event_time=datetime(2026, 4, 22, 14, 7, 0, tzinfo=UTC),
        event_name="Purchase",
        email_hash=sha256_hex("foo@bar.com"),
        phone_hash=sha256_hex("15551234567"),
        value=42.50,
        currency="USD",
        order_id="A00123456",
    )


@pytest.fixture
def sample_conversions(sample_conversion) -> list[Conversion]:
    return [
        sample_conversion,
        Conversion(
            event_time=datetime(2026, 4, 22, 15, 30, 0, tzinfo=UTC),
            event_name="Purchase",
            email_hash=sha256_hex("baz@qux.com"),
            phone_hash=sha256_hex("15550000000"),
            value=99.99,
            currency="USD",
            order_id="A00123457",
        ),
    ]
