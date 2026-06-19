from stratum.db import get_conn


class ArxivSubscriptionStore:
    def __init__(self, subscription_id: str):
        self.subscription_id = subscription_id

    def get_processed_ids(self) -> set[str]:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT arxiv_id FROM arxiv_processed_papers WHERE subscription_id = ?",
                (self.subscription_id,),
            ).fetchall()
        return {r[0] for r in rows}

    def mark_processed(self, arxiv_ids: str | list[str]) -> None:
        ids = [arxiv_ids] if isinstance(arxiv_ids, str) else arxiv_ids
        with get_conn() as conn:
            for arxiv_id in ids:
                conn.execute(
                    "INSERT INTO arxiv_processed_papers (subscription_id, arxiv_id) "
                    "VALUES (?, ?) ON CONFLICT DO NOTHING",
                    (self.subscription_id, arxiv_id),
                )
