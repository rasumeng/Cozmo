"""Background task queue for async operations.

Tasks are persisted to disk so they survive restarts.
"""
import json
import threading
import logging
from datetime import datetime
from pathlib import Path
from enum import Enum

log = logging.getLogger("cozmo.taskqueue")

TASKS_DIR = Path.home() / ".cozmo" / "tasks"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task:
    def __init__(self, id: str, description: str, prompt: str,
                 agent_type: str = "general", status: TaskStatus = TaskStatus.PENDING,
                 created: str = "", result: str = "", error: str = ""):
        self.id = id
        self.description = description
        self.prompt = prompt
        self.agent_type = agent_type
        self.status = status
        self.created = created or datetime.now().isoformat()
        self.result = result
        self.error = error

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "prompt": self.prompt,
            "agent_type": self.agent_type,
            "status": self.status.value,
            "created": self.created,
            "result": self.result,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        return cls(
            id=d["id"],
            description=d.get("description", ""),
            prompt=d.get("prompt", ""),
            agent_type=d.get("agent_type", "general"),
            status=TaskStatus(d.get("status", "pending")),
            created=d.get("created", ""),
            result=d.get("result", ""),
            error=d.get("error", ""),
        )


class TaskQueue:
    def __init__(self):
        TASKS_DIR.mkdir(parents=True, exist_ok=True)
        self._tasks: dict[str, Task] = {}
        self._running: dict[str, threading.Thread] = {}
        self._load()

    def _load(self):
        """Load pending/running tasks from disk."""
        for f in TASKS_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                task = Task.from_dict(data)
                if task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                    task.status = TaskStatus.PENDING  # re-queue running tasks
                self._tasks[task.id] = task
            except Exception as e:
                log.warning("Failed to load task %s: %s", f.name, e)

    def _save(self, task: Task):
        """Persist task to disk."""
        path = TASKS_DIR / f"{task.id}.json"
        path.write_text(json.dumps(task.to_dict(), indent=2), encoding="utf-8")

    def add(self, description: str, prompt: str, agent_type: str = "general") -> Task:
        """Add a new task to the queue."""
        import uuid
        task = Task(
            id=str(uuid.uuid4())[:8],
            description=description,
            prompt=prompt,
            agent_type=agent_type,
        )
        self._tasks[task.id] = task
        self._save(task)
        return task

    def get(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        tasks.sort(key=lambda t: t.created, reverse=True)
        return tasks

    def cancel(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task:
            return False
        if task.status == TaskStatus.RUNNING:
            # Can't kill thread, but mark as cancelled
            task.status = TaskStatus.CANCELLED
        elif task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CANCELLED
        self._save(task)
        return True

    def run_task(self, task: Task, runtime_factory):
        """Run a task in a background thread.

        runtime_factory: callable() -> CozmoRuntime
        """
        if task.status == TaskStatus.RUNNING:
            return

        task.status = TaskStatus.RUNNING
        self._save(task)

        def _worker():
            try:
                runtime = runtime_factory()
                result = runtime.run(task.prompt)
                task.result = result
                task.status = TaskStatus.COMPLETED
            except Exception as e:
                task.error = str(e)
                task.status = TaskStatus.FAILED
            self._save(task)

        t = threading.Thread(target=_worker, daemon=True)
        self._running[task.id] = t
        t.start()

    def cleanup(self, max_completed: int = 50):
        """Remove old completed tasks from disk."""
        completed = self.list_tasks(TaskStatus.COMPLETED)
        for task in completed[max_completed:]:
            path = TASKS_DIR / f"{task.id}.json"
            if path.exists():
                path.unlink()
            del self._tasks[task.id]
