"""Tests for stratum.auth.password — ≥5 tests per §3.7."""
import pytest
from stratum.auth.password import hash_password, verify_password, validate_password_strength


def test_hash_verify():
    h = hash_password("Test123456!")
    assert verify_password("Test123456!", h)


def test_password_strength_valid():
    validate_password_strength("Test123456!")  # should not raise


def test_verify_wrong_password():
    h = hash_password("CorrectPass1!")
    assert verify_password("WrongPass1!", h) is False


def test_hash_is_argon2_format():
    h = hash_password("Test123456!")
    assert h.startswith("$argon2")


def test_strength_rejects_short():
    with pytest.raises(ValueError, match="at least 10"):
        validate_password_strength("Ab1!")


def test_strength_rejects_no_digit():
    with pytest.raises(ValueError, match="digit"):
        validate_password_strength("Abcdefghij!")


def test_strength_rejects_no_letter():
    with pytest.raises(ValueError, match="letter"):
        validate_password_strength("1234567890!")


def test_strength_rejects_no_special():
    with pytest.raises(ValueError, match="special"):
        validate_password_strength("Abcdefgh12")
