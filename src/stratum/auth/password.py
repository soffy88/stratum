from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import re

ph = PasswordHasher()

def hash_password(password: str) -> str:
    return ph.hash(password)

def verify_password(password: str, hash: str) -> bool:
    try:
        return ph.verify(hash, password)
    except VerifyMismatchError:
        return False

def validate_password_strength(password: str):
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters long")
    if not re.search("[0-9]", password):
        raise ValueError("Password must contain at least one digit")
    if not re.search("[a-zA-Z]", password):
        raise ValueError("Password must contain at least one letter")
    if not re.search("[^a-zA-Z0-9]", password):
        raise ValueError("Password must contain at least one special character")
