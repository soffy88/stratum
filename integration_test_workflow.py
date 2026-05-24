import asyncio
import os
import shutil
from datetime import datetime, UTC, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from omodul.weekly_review_workflow import (
    weekly_review_workflow,
    WeeklyReviewConfig,
    WeeklyReviewInput,
    ActivityItem,
    compute_fingerprint_for
)

# Mock service layer DAOs
class MockSubstrateDao:
    def list_since(self, user_id, days):
        return [{"id": "s1", "title": "Report", "created_at": datetime.now(UTC).isoformat()}]

class MockAgentRunDao:
    def list_since(self, user_id, days):
        return [{"id": "r1", "agent_name": "Companion", "started_at": datetime.now(UTC).isoformat()}]

async def test_integration():
    user_id = "demo"
    days = 7
    
    substrate_dao = MockSubstrateDao()
    agent_run_dao = MockAgentRunDao()

    substrates = substrate_dao.list_since(user_id, days=days)
    agent_runs = agent_run_dao.list_since(user_id, days=days)

    activities = [
        ActivityItem(activity_id=s["id"], activity_type="substrate", title=s["title"],
                     timestamp_utc=s["created_at"])
        for s in substrates
    ] + [
        ActivityItem(activity_id=r["id"], activity_type="agent_run", title=r["agent_name"],
                     timestamp_utc=r["started_at"])
        for r in agent_runs
    ]

    config = WeeklyReviewConfig(time_window_days=7)
    input_data = WeeklyReviewInput(
        activities=activities,
        window_start_utc=datetime.now(UTC) - timedelta(days=7),
        window_end_utc=datetime.now(UTC),
    )

    output_dir = Path.home() / ".stratum" / "reports" / "demo" / "weekly_test"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Patch ProviderRegistry to avoid real API calls
    with patch("obase.provider_registry.ProviderRegistry.get_caller") as mock_get_caller:
        mock_get_caller.return_value = MagicMock(return_value={"content": "Integrated summary"})
        
        result = weekly_review_workflow(config, input_data, output_dir)
        
        print(f"status: {result['status']}")
        print(f"fingerprint: {result['fingerprint']}")
        print(f"report_path: {result['report_path']}")
        print(f"cost_usd: {result['cost_usd']}")
        print(f"trail steps: {len(result['decision_trail']['steps'])}")
        
        assert result['status'] == 'completed'
        assert len(result['fingerprint']) == 64
        assert Path(result['report_path']).exists()

if __name__ == "__main__":
    asyncio.run(test_integration())
