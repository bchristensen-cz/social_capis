from src.hashing import (
    ensure_email_hash,
    ensure_phone_hash,
    event_id,
    hash_email,
    hash_phone,
    is_sha256_hex,
    is_valid_email,
    normalize_email,
    normalize_phone,
    sha256_hex,
)


def test_normalize_email_lowercases_and_trims():
    assert normalize_email("  Foo@Bar.Com ") == "foo@bar.com"
    assert normalize_email(None) == ""


def test_is_valid_email_true_false():
    assert is_valid_email("Foo@Bar.com")
    assert not is_valid_email("notanemail")
    assert not is_valid_email("")
    assert not is_valid_email(None)


def test_normalize_phone_formats_valid_us():
    assert normalize_phone("+1 (801) 555-0100") == "18015550100"
    assert normalize_phone("801-555-0100") == "18015550100"
    assert normalize_phone("18015550100") == "18015550100"


def test_normalize_phone_drops_invalid():
    assert normalize_phone("555-123-4567") == ""  # 555 is a fictional area code
    assert normalize_phone("+1-555-1234") == ""   # too short
    assert normalize_phone("garbage") == ""
    assert normalize_phone("") == ""
    assert normalize_phone(None) == ""


def test_sha256_hex_known_vector():
    assert sha256_hex("abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_hash_email_matches_normalized():
    assert hash_email("Foo@Bar.com") == sha256_hex("foo@bar.com")


def test_hash_email_empty_for_invalid():
    assert hash_email("notanemail") == ""
    assert hash_email(None) == ""


def test_hash_phone_matches_normalized():
    assert hash_phone("+1 801-555-0100") == sha256_hex("18015550100")


def test_hash_phone_empty_for_invalid():
    assert hash_phone("555-123-4567") == ""  # fictional area code
    assert hash_phone("+1-555-1234") == ""   # too short
    assert hash_phone("garbage") == ""


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
    h = sha256_hex("18015550100")
    assert ensure_phone_hash(h) == h


def test_ensure_phone_hash_hashes_raw():
    assert ensure_phone_hash("+1 801-555-0100") == sha256_hex("18015550100")


def test_ensure_phone_hash_empty_for_garbage():
    assert ensure_phone_hash("+1-555-1234") == ""
    assert ensure_phone_hash("1abc") == ""
    assert ensure_phone_hash("555-123-4567") == ""


def test_event_id_is_platform_scoped():
    a = event_id("A123", "tiktok")
    b = event_id("A123", "meta")
    c = event_id("A123", "tiktok")
    assert a != b
    assert a == c
    assert is_sha256_hex(a)
