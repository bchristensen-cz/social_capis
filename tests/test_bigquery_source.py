from __future__ import annotations

from datetime import UTC, datetime

from src.bigquery_source import EVENT_NAME, _row_to_conversion, rows_to_jsonl_bytes
from src.hashing import sha256_hex
from src.models import Conversion


def test_row_to_conversion_maps_user_schema_and_hashes_raw():
    row = {
        "event_time": datetime(2026, 4, 23, 18, 30, tzinfo=UTC),
        "transaction_id": "BRINK-001",
        "transaction_value": 24.75,
        "currency": "USD",
        "email": "Jane@Example.com",
        "phone_raw": "18015550100",
    }

    c = _row_to_conversion(row)

    assert isinstance(c, Conversion)
    assert c.event_name == EVENT_NAME == "Purchase"
    assert c.order_id == "BRINK-001"
    assert c.value == 24.75
    assert c.currency == "USD"
    assert c.email_hash == sha256_hex("jane@example.com")
    assert c.phone_hash == sha256_hex("18015550100")
    assert c.event_time.tzinfo is not None


def test_row_to_conversion_drops_garbage_phone():
    row = {
        "event_time": datetime(2026, 4, 23, 18, 30, tzinfo=UTC),
        "transaction_id": "BRINK-002",
        "transaction_value": 10.0,
        "currency": "USD",
        "email": "a@b.com",
        "phone_raw": "1abc",
    }

    c = _row_to_conversion(row)
    assert c.phone_hash == ""
    assert c.email_hash == sha256_hex("a@b.com")


def test_row_to_conversion_naive_datetime_gets_utc():
    naive = datetime(2026, 4, 23, 18, 30)
    row = {
        "event_time": naive,
        "transaction_id": "X",
        "transaction_value": 1.0,
        "currency": "USD",
        "email": "a@b.com",
        "phone_raw": "18015550100",
    }
    c = _row_to_conversion(row)
    assert c.event_time.tzinfo is not None


def test_rows_to_jsonl_bytes_empty():
    assert rows_to_jsonl_bytes([]) == b""


def test_rows_to_jsonl_bytes_round_trip(sample_conversion):
    import json

    data = rows_to_jsonl_bytes([sample_conversion])
    text = data.decode()
    line = text.strip()
    parsed = json.loads(line)
    assert parsed["order_id"] == sample_conversion.order_id
    assert parsed["email_hash"] == sample_conversion.email_hash
    assert parsed["event_name"] == sample_conversion.event_name
