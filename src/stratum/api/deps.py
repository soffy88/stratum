from fastapi import Depends
from stratum.common import jwt_auth

class User:
    def __init__(self, user_id: str):
        self.user_id = user_id

async def get_current_user(user_id: str = Depends(jwt_auth)) -> User:
    return User(user_id)
