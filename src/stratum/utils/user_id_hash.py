import hashlib


def hash_user_id(user_id: str) -> str:
    """Hash raw user_id (ULID from JWT sub) to 16-char hex.

    Used in: substrates.user_id column write/read, InboxConfig.user_id_hash, feeds.py.
    Must match oskill InboxConfig.user_id_hash format (SPEC v0.7 §6.1).
    """
    return hashlib.sha256(user_id.encode()).hexdigest()[:16]
