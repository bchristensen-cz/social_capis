from src.hashing import (
    ensure_email_hash,
    ensure_phone_hash,
    event_id,
    hash_email,
    hash_phone,
    is_sha256_hex,
    normalize_email,
    normalize_phone,
    sha256_hex,
)


def test_normalize_email_lowercases_and_trims():
    assert normalize_email("  Foo@Bar.Com ") == "foo@bar.com"
    assert normalize_email(None) == ""


def test_normalize_phone_digits_only():
    assert normalize_phone("+1 (555) 123-4567") == "15551234567"
    assert normalize_phone(None) == ""


def test_sha256_hex_known_vector():
    assert sha256_hex("abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_hash_email_matches_normalized():
    assert hash_email("Foo@Bar.com") == sha256_hex("foo@bar.com")


def test_hash_phone_matches_normalized():
    assert hash_phone("+1-555-1234") == sha256_hex("15551234")


def test_is_sha256_hex_validates_format():
    assert is_sha256_hex(sha256_hex("x"))
    assert not is_sha256_hex("")
    assert not is_sha256_hex("NOTHEX")
    assert not is_sha256_hex("a" * 63)


def test_ensure_email_hash_passes_through_prehashed():
    h = sha256_hex("foo@bar.com")
    assert ensure_email_hash(h) == h
    assert ensure_email_hash(h.upper()) == h


def test_ensure_email_hash_hashes_raw():
    assert ensure_email_hash("Foo@Bar.com") == sha256_hex("foo@bar.com")


def test_ensure_phone_hash_passes_through_prehashed():
    h = sha256_hex("15551234567")
    assert ensure_phone_hash(h) == h


def test_ensure_phone_hash_hashes_raw():
    assert ensure_phone_hash("+1 555-123-4567") == sha256_hex("15551234567")


def test_event_id_is_platform_scoped():
    a = event_id("A123", "tiktok")
    b = event_id("A123", "meta")
    c = event_id("A123", "tiktok")
    assert a != b
    assert a == c
    assert is_sha256_hex(a)
