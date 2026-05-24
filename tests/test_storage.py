"""Unit tests for compass_scraper.storage.sha256_hex.

The MinioStorage class itself isn't covered here — it's a thin wrapper
around a network client and is exercised by the integration runs.
"""

from compass_scraper.storage import sha256_hex


def test_sha256_hex_empty():
    assert sha256_hex(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_sha256_hex_known_string():
    # Known SHA256 of "compass".
    assert sha256_hex(b"compass") == "d1068beeb96a6a79937661d5cc9f290dddaa5730e64b7ab2b238078a1194c614"


def test_sha256_hex_is_deterministic():
    payload = b"<html><body>hello</body></html>"
    assert sha256_hex(payload) == sha256_hex(payload)


def test_sha256_hex_changes_with_content():
    a = sha256_hex(b"<html><body>hello</body></html>")
    b = sha256_hex(b"<html><body>HELLO</body></html>")
    assert a != b, "different content must produce different hashes"
