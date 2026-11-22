from wbr_studio.security import decrypt_secret, encrypt_secret, hash_password, verify_password
from wbr_studio.settings import reset_settings


def test_password_roundtrip():
    stored = hash_password("password123")
    assert verify_password("password123", stored)
    assert not verify_password("password124", stored)
    assert stored != "password123"


def test_fernet_roundtrip_is_not_plaintext():
    reset_settings()
    secret = "sk-live-DO-NOT-LEAK-8f3a2c91"
    first = encrypt_secret(secret)
    second = encrypt_secret(secret)
    assert first != second
    assert secret not in first
    assert decrypt_secret(first) == secret
    assert decrypt_secret(second) == secret
