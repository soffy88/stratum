# src/stratum/services/channel_subscription_store.py
from stratum.db import get_conn

class SubscriptionStore:
    """实现 oservi channel_watcher 的 subscription 注入点接口。"""

    def __init__(self, subscription_id: str):
        self.subscription_id = subscription_id

    def get_processed_ids(self, channel_url: str) -> set[str]:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT video_id FROM channel_processed_videos WHERE subscription_id = ?",
                (self.subscription_id,)
            ).fetchall()
        return {r[0] for r in rows}

    def mark_processed(self, channel_url: str, video_ids: str | list[str]) -> None:
        if isinstance(video_ids, str):
            ids = [video_ids]
        else:
            ids = video_ids
        with get_conn() as conn:
            for video_id in ids:
                conn.execute(
                    "INSERT INTO channel_processed_videos (subscription_id, video_id) "
                    "VALUES (?, ?) ON CONFLICT DO NOTHING",
                    (self.subscription_id, video_id)
                )
