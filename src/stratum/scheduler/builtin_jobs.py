from datetime import datetime, UTC, timedelta
from pathlib import Path
from typing import Any

from omodul.weekly_review_workflow import (
    weekly_review_workflow,
    WeeklyReviewConfig,
    WeeklyReviewInput,
    compute_fingerprint_for,
    ActivityItem
)

def _collect_activities(user_id: str, days: int) -> list[ActivityItem]:
    # Placeholder: in real impl, query DAO
    return [
        ActivityItem(activity_id="sub-1", activity_type="substrate", title="Market Report", timestamp_utc=datetime.now(UTC).isoformat())
    ]

def _run_review(kind: str):
    """调 omodul.weekly_review_workflow."""
    days = 7 if kind == "weekly" else 30
    user_id = "default" # Should come from config
    
    activities = _collect_activities(user_id, days)
    
    config = WeeklyReviewConfig(time_window_days=days, title_prefix=f"{'周' if kind=='weekly' else '月'}回顾")
    input_data = WeeklyReviewInput(
        activities=activities,
        window_start_utc=datetime.now(UTC) - timedelta(days=days),
        window_end_utc=datetime.now(UTC),
    )
    
    fp = compute_fingerprint_for(config, input_data)
    # Service layer constructs output_dir
    output_dir = Path.home() / ".stratum" / "reports" / user_id / kind / fp[:12]
    
    return weekly_review_workflow(config, input_data, output_dir)

WEEKLY_REVIEW_JOB = {
    "name": "weekly_review",
    "cron": "0 9 * * 0",   # 周日 9 点
    "callable": lambda: _run_review("weekly"),
    "enabled": False,
    "timezone": "Asia/Shanghai",
}

MONTHLY_REVIEW_JOB = {
    "name": "monthly_review",
    "cron": "0 9 1 * *",   # 月 1 号 9 点
    "callable": lambda: _run_review("monthly"),
    "enabled": False,
    "timezone": "Asia/Shanghai",
}
