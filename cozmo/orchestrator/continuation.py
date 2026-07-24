"""
Continuation — load Task + Job, resume execution from checkpoint.

Handles "keep going", "continue", and retry flows.
Loads persisted state, builds EngineContext from last checkpoint.
"""

from __future__ import annotations

import logging
from typing import Optional

from ..jobs.job import Checkpoint, Job, JobStatus
from ..jobs.manager import JobManager
from ..jobs.persistence import JobStore
from ..orchestrator.task_types import ExecutionPlan, IntentType, Task, TaskStatus
from ..runtime.engine import Engine, EngineContext

log = logging.getLogger("cozmo.continuation")


class ContinuationHandler:
    """Handles task continuation, retry, and resume flows."""

    def __init__(self, job_manager: Optional[JobManager] = None,
                 job_store: Optional[JobStore] = None):
        self.job_manager = job_manager or JobManager()
        self.job_store = job_store or JobStore()

    def continue_task(self, task: Task) -> Optional[Job]:
        """Continue a task: create a new Job from the last checkpoint.

        Returns the new Job, or None if the task can't be continued.
        """
        if not task.can_continue():
            log.warning("task %s cannot continue (status=%s)", task.id, task.status)
            return None

        last_job_id = task.execution_history.last_job_id
        if not last_job_id:
            log.warning("task %s has no execution history", task.id)
            return None

        last_job = self._load_job(last_job_id)
        if last_job is None:
            return None

        if last_job.can_resume:
            new_job = self.job_manager.resume(last_job_id)
        else:
            new_job = self.job_manager.submit(
                task_id=task.id,
                strategy=last_job.strategy,
                metadata={"continuation": True, "previous_job": last_job_id},
            )

        if new_job:
            task.execution_history.add(
                job_id=new_job.id,
                reason="continuation",
                parent_job_id=last_job_id,
            )
            task.status = TaskStatus.EXECUTING
            log.info("task continued: %s → job %s", task.id, new_job.id)

        return new_job

    def retry_job(self, job_id: str, task: Optional[Task] = None) -> Optional[Job]:
        """Retry a failed job. Optionally update task execution history."""
        new_job = self.job_manager.retry(job_id)
        if new_job and task:
            task.execution_history.add(
                job_id=new_job.id,
                reason="retry",
                parent_job_id=job_id,
            )
        return new_job

    def build_engine_context(self, job: Job, plan: Optional[ExecutionPlan] = None) -> EngineContext:
        """Build an EngineContext from a Job (and optional ExecutionPlan)."""
        messages = []
        if plan and plan.system_prompt:
            from langchain_core.messages import SystemMessage
            messages.append(SystemMessage(content=plan.system_prompt))

        if job.checkpoint and job.checkpoint.messages:
            messages = list(job.checkpoint.messages)

        return EngineContext(
            job_id=job.id,
            task_id=job.task_id,
            system_prompt=plan.system_prompt if plan else "",
            messages=messages,
            tools=plan.tools if plan else [],
            max_steps=plan.max_steps if plan else 10,
            temperature=plan.temperature if plan else 0.6,
            checkpoint_interval=3,
            checkpoint=job.checkpoint,
            metadata={"strategy": job.strategy},
        )

    def _load_job(self, job_id: str) -> Optional[Job]:
        """Try memory first, then disk."""
        job = self.job_manager.get(job_id)
        if job:
            return job
        return self.job_store.load(job_id)
