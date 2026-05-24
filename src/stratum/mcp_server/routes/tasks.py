from typing import Any
from stratum.dao import task_dao

async def list_tasks(user_id: str, completed: bool | None = None) -> list[dict[str, Any]]:
    tasks = task_dao.list_tasks(user_id=user_id, completed=completed)
    return [t.__dict__ for t in tasks]

async def mark_task_completed(task_id: str) -> dict[str, Any]:
    task = task_dao.mark_completed(task_id)
    return task.__dict__
