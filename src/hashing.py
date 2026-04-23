from __future__ import annotations

import hashlib
import re

_HEX64 = re.compile(r"^[a-fA-F0-9]{64}$")
_NON_DIGIT = re.compile(r"\D")


def is_sha256_hex(value: str | None) -> bool:
    return bool(_HEX64.match(value or ""))


def normalize_email(value: str | None) -> str:
    return (value or "").strip().lower()


def normalize_phone(value: str | None) -> str:
    return _NON_DIGIT.sub("", value or "")


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_email(value: str | None) -> str:
    normalized = normalize_email(value)
    return sha256_hex(normalized) if normalized else ""


def hash_phone(value: str | None) -> str:
    normalized = normalize_phone(value)
    return sha256_hex(normalized) if normalized else ""


def ensure_email_hash(value: str | None) -> str:
    if is_sha256_hex(value):
        return value.lower()
    return hash_email(value)


def ensure_phone_hash(value: str | None) -> str:
    if is_sha256_hex(value):
        return value.lower()
    return hash_phone(value)


def event_id(order_id: str, platform: str) -> str:
    return sha256_hex(f"{order_id}|{platform}")
