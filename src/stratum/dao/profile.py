"""DAO for user_profiles table."""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class UserProfile:
    user_id: str
    display_name: Optional[str]
    avatar_url: Optional[str]
    bio: Optional[str]
    location: Optional[str]
    website: Optional[str]
    timezone: str
    locale: str
    created_at: datetime
    updated_at: datetime


class ProfileDAO:
    def __init__(self, db_conn):
        self.conn = db_conn

    _COLS = "user_id, display_name, avatar_url, bio, location, website, timezone, locale, created_at, updated_at"

    def get_profile(self, user_id: str) -> Optional[UserProfile]:
        res = self.conn.execute(f"SELECT {self._COLS} FROM user_profiles WHERE user_id = ?", (user_id,)).fetchone()
        return UserProfile(*res) if res else None

    def create_profile(self, user_id: str, **kwargs) -> UserProfile:
        now = datetime.now(timezone.utc)
        self.conn.execute("""
            INSERT INTO user_profiles (user_id, display_name, bio, location, website, timezone, locale, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, kwargs.get("display_name"), kwargs.get("bio"), kwargs.get("location"),
              kwargs.get("website"), kwargs.get("timezone", "Asia/Shanghai"),
              kwargs.get("locale", "zh-CN"), now, now))
        return self.get_profile(user_id)

    def update_profile(self, user_id: str, **kwargs) -> Optional[UserProfile]:
        profile = self.get_profile(user_id)
        if not profile:
            return None
        now = datetime.now(timezone.utc)
        sets = ["updated_at = ?"]
        params: list = [now]
        for field in ("display_name", "bio", "location", "website", "timezone", "locale", "avatar_url"):
            if field in kwargs:
                sets.append(f"{field} = ?")
                params.append(kwargs[field])
        params.append(user_id)
        self.conn.execute(f"UPDATE user_profiles SET {', '.join(sets)} WHERE user_id = ?", params)
        return self.get_profile(user_id)
