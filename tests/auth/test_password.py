import pytest
from stratum.auth.password import hash_password, verify_password, validate_password_strength

def test_hash_verify():
    pwd = "TestPassword123!"
    h = hash_password(pwd)
    assert verify_password(pwd, h) is True
    assert verify_password("wrong", h) is False

def test_password_strength():
    validate_password_strength("StrongPass1!") # Should not raise
    with pytest.raises(ValueError, match="at least 10 characters"):
        validate_password_strength("Short1!")
    with pytest.raises(ValueError, match="at least one digit"):
        validate_password_strength("NoDigitsSpec!")
    with pytest.raises(ValueError, match="at least one letter"):
        validate_password_strength("1234567890!")
    with pytest.raises(ValueError, match="at least one special character"):
        validate_password_strength("NoSpecial123")
