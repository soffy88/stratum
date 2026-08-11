import os
from pathlib import Path
from datetime import datetime, UTC, timedelta
from typing import Any

# 3O 平台包仅部署于容器 /opt/platform；缺失时返回 status='failed' 而非 ImportError。
try:
    from omodul.weekly_review_workflow import (
        weekly_review_workflow,
        WeeklyReviewConfig,
        WeeklyReviewInput,
        ActivityItem,
        compute_fingerprint_for,
    )

    _HAS_WEEKLY_REVIEW = True
except ImportError:  # pragma: no cover — 平台包仅部署于容器
    _HAS_WEEKLY_REVIEW = False
    weekly_review_workflow = None
    WeeklyReviewConfig = None
    WeeklyReviewInput = None
    ActivityItem = None
    compute_fingerprint_for = None


async def run_weekly_review(user_id: str, days: int = 7) -> dict[str, Any]:
    if not _HAS_WEEKLY_REVIEW:
        return {
            "status": "failed",
            "error": "omodul platform package unavailable (no /opt/platform)",
        }
    # Placeholder: in real impl, collect activities from multiple DAOs
    activities = [
        ActivityItem(activity_id="1", activity_type="test", title="Test Activity", timestamp_utc=datetime.now(UTC).isoformat())
    ]
    
    config = WeeklyReviewConfig(time_window_days=days)
    input_data = WeeklyReviewInput(
        activities=activities,
        window_start_utc=datetime.now(UTC) - timedelta(days=days),
        window_end_utc=datetime.now(UTC),
    )
    
    fp = compute_fingerprint_for(config, input_data)
    # Service layer constructs output_dir with user_id
    output_dir = Path.home() / ".stratum" / "reports" / user_id / "weekly" / fp[:12]
    
    return weekly_review_workflow(config, input_data, output_dir)
