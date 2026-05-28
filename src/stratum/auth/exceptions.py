class AuthError(Exception):
    """Base authentication error."""
    pass
class InvalidCredentials(AuthError):
    pass
class TokenExpired(AuthError):
    pass
class InvalidToken(AuthError):
    pass
