from __future__ import annotations

import hashlib
import re

import phonenumbers
from phonenumbers import NumberParseException

_HEX64 = re.compile(r"^[a-fA-F0-9]{64}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

DEFAULT_PHONE_REGION = "US"


def is_sha256_hex(value: str | None) -> bool:
    return bool(_HEX64.match(value or ""))


def normalize_email(value: str | None) -> str:
    return (value or "").strip().lower()


def is_valid_email(value: str | None) -> bool:
    return bool(_EMAIL.match(normalize_email(value)))


def normalize_phone(value: str | None, default_region: str = DEFAULT_PHONE_REGION) -> str:
    """Parse with libphonenumber, validate, and return E.164 digits (no '+').

    Returns empty string when the input is missing or not a valid number. This
    lets callers safely hash only real phone numbers and drop the field for
    garbage inputs.
    """
    raw = (value or "").strip()
    if not raw:
        return ""
    try:
        parsed = phonenumbers.parse(raw, default_region)
    except NumberParseException:
        return ""
    if not phonenumbers.is_valid_number(parsed):
        return ""
    e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    return e164.lstrip("+")


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_email(value: str | None) -> str:
    if not is_valid_email(value):
        return ""
    return sha256_hex(normalize_email(value))


def hash_phone(value: str | None, default_region: str = DEFAULT_PHONE_REGION) -> str:
    normalized = normalize_phone(value, default_region)
    return sha256_hex(normalized) if normalized else ""


def ensure_email_hash(value: str | None) -> str:
    if is_sha256_hex(value):
        return value.lower()
    return hash_email(value)


def ensure_phone_hash(
    value: str | None, default_region: str = DEFAULT_PHONE_REGION
) -> str:
    if is_sha256_hex(value):
        return value.lower()
    return hash_phone(value, default_region)


def event_id(order_id: str, platform: str) -> str:
    return sha256_hex(f"{order_id}|{platform}")
