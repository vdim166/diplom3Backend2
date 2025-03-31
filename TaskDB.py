from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
import json
import os
from enum import Enum
from uuid import uuid4

class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"

class Task(BaseModel):
    id: str
    title: str
    description: str
    assigned_to: str
    created_at: datetime
    status: TaskStatus

class TaskCreate(BaseModel):
    title: str
    description: str
    assigned_to: str

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assigned_to: Optional[str] = None
    status: Optional[TaskStatus] = None

class TaskMove(BaseModel):
    new_status: TaskStatus
    new_assignee: Optional[str] = None

class TaskDB:
    def __init__(self, file_path: str = "tasks_db.json"):
        self.file_path = file_path
        self.data: Dict[str, Dict[str, List[Task]]] = {
            "todo": {},
            "in_progress": {},
            "done": {}
        }
        self._load()

    def _load(self):
        if os.path.exists(self.file_path):
            with open(self.file_path, 'r') as f:
                raw_data = json.load(f)
                for status in TaskStatus:
                    self.data[status.value] = {
                        user: [Task(**task) for task in tasks]
                        for user, tasks in raw_data.get(status.value, {}).items()
                    }

    def _save(self):
        with open(self.file_path, 'w') as f:
            save_data = {
                status: {
                    user: [task.dict() for task in tasks]
                    for user, tasks in user_tasks.items()
                }
                for status, user_tasks in self.data.items()
            }
            json.dump(save_data, f, indent=2, default=str)

    def create_task(self, task_data: TaskCreate) -> Task:
        new_task = Task(
            id=str(uuid4()),
            title=task_data.title,
            description=task_data.description,
            assigned_to=task_data.assigned_to,
            created_at=datetime.now(),
            status=TaskStatus.TODO
        )
        
        if new_task.assigned_to not in self.data["todo"]:
            self.data["todo"][new_task.assigned_to] = []
        self.data["todo"][new_task.assigned_to].append(new_task)
        self._save()
        return new_task

    def get_all_tasks(self) -> Dict[str, Dict[str, List[Task]]]:
        return self.data

    def get_user_tasks(self, user: str) -> Dict[str, List[Task]]:
        return {
            status: tasks.get(user, [])
            for status, tasks in self.data.items()
        }

    def update_task(self, task_id: str, update_data: TaskUpdate) -> Optional[Task]:
        for status in TaskStatus:
            for user, tasks in self.data[status.value].items():
                for i, task in enumerate(tasks):
                    if task.id == task_id:
                        # Handle status change
                        if update_data.status and update_data.status != status:
                            return self._move_task(task, status, update_data)
                        
                        # Regular update
                        updated_task = task.copy(update=update_data.dict(exclude_unset=True))
                        self.data[status.value][user][i] = updated_task
                        self._save()
                        return updated_task
        return None

    def _move_task(self, task: Task, old_status: TaskStatus, update_data: TaskUpdate) -> Task:
        # Remove from old status
        self.data[old_status.value][task.assigned_to] = [
            t for t in self.data[old_status.value][task.assigned_to] 
            if t.id != task.id
        ]
        
        # Update task fields
        updated_task = task.copy(update=update_data.dict(exclude_unset=True))
        updated_task.status = update_data.status
        
        # Add to new status
        new_assignee = update_data.assigned_to if update_data.assigned_to else task.assigned_to
        if new_assignee not in self.data[updated_task.status.value]:
            self.data[updated_task.status.value][new_assignee] = []
        self.data[updated_task.status.value][new_assignee].append(updated_task)
        self._save()
        return updated_task

    def delete_task(self, task_id: str) -> bool:
        for status in TaskStatus:
            for user, tasks in self.data[status.value].items():
                for i, task in enumerate(tasks):
                    if task.id == task_id:
                        self.data[status.value][user].pop(i)
                        self._save()
                        return True
        return False