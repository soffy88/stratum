from typing import Any, Optional
from dataclasses import dataclass
from datetime import date

@dataclass
class Task:
    id: str
    user_id: str
    text: str
    completed: bool
    due_date: Optional[date] = None
    scheduled_date: Optional[date] = None
    tags: Optional[str] = None # CSV tags

def create_task(user_id: str, text: str, due_date: Optional[date] = None, **kwargs: Any) -> Task:
    # Dummy implementation for dao
    return Task(id="t1", user_id=user_id, text=text, completed=False, due_date=due_date)

def get_task(task_id: str) -> Optional[Task]:
    return None

def list_tasks(user_id: str, completed: Optional[bool] = None, due_before: Optional[date] = None, overdue: bool = False, tag: Optional[str] = None, limit: int = 20) -> list[Task]:
    return []

def update_task(task_id: str, **fields: Any) -> Task:
    return Task(id=task_id, user_id="u1", text="Updated", completed=True)

def mark_completed(task_id: str) -> Task:
    return update_task(task_id, completed=True)

def delete_task(task_id: str) -> bool:
    return True
