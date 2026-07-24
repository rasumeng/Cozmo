"""
JobManager — lifecycle for Jobs: submit, pause, resume, cancel, retry.

Owns all active/paused/completed jobs. Thread-safe.
Persistence delegated to JobStore (jobs/persistence.py).

Architecture:
  Orchestrator/Continuation → JobManager.submit() → Job
                              JobManager.pause()  → Checkpoint
                              JobManager.resume() → new Job from checkpoint
                              JobManager.cancel()
                              JobManager.retry()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Optional

from .job import Checkpoint, Job, JobStatus

log = logging.getLogger("cozmo.jobs.manager")


class JobManager:
    """Owns job lifecycle. Thread-safe."""

    def __init__(self):
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        ts = datetime.now().strftime("%y%m%d%H%M%S")
        return f"job-{ts}-{self._counter}"

    # ── lifecycle ────────────────────────────────────────────────────────

    def submit(self, task_id: str, strategy: str = "execute",
               max_retries: int = 2, metadata: dict | None = None) -> Job:
        """Create and register a new Job."""
        job = Job(
            id=self._next_id(),
            task_id=task_id,
            status=JobStatus.PENDING,
            strategy=strategy,
            max_retries=max_retries,
            metadata=metadata or {},
        )
        with self._lock:
            self._jobs[job.id] = job
        log.info("job submitted: %s (task=%s, strategy=%s)", job.id, task_id, strategy)
        return job

    def pause(self, job_id: str, checkpoint: Checkpoint | None = None) -> bool:
        """Pause a running job. Captures checkpoint if provided."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status != JobStatus.RUNNING:
                return False
            job.status = JobStatus.PAUSED
            if checkpoint:
                job.checkpoint = checkpoint
        log.info("job paused: %s (step=%s)", job_id,
                 checkpoint.step if checkpoint else "?")
        return True

    def resume(self, job_id: str) -> Job | None:
        """Resume a paused job. Creates a new Job linked via parent_job_id.

        Returns the new Job, or None if the original job can't be resumed.
        """
        with self._lock:
            original = self._jobs.get(job_id)
            if original is None or original.status != JobStatus.PAUSED:
                log.warning("cannot resume %s: status=%s", job_id,
                            original.status if original else "not found")
                return None
            if not original.can_resume:
                log.warning("cannot resume %s: no checkpoint", job_id)
                return None

            new_job = Job(
                id=self._next_id(),
                task_id=original.task_id,
                status=JobStatus.QUEUED,
                strategy=original.strategy,
                checkpoint=original.checkpoint,
                metadata={**original.metadata, "resumed_from": job_id},
            )
            self._jobs[new_job.id] = new_job

        log.info("job resumed: %s → %s (step=%s)", job_id,
                 new_job.id, new_job.checkpoint.step if new_job.checkpoint else "?")
        return new_job

    def cancel(self, job_id: str) -> bool:
        """Cancel a job. Works from any non-terminal status."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.is_done:
                return False
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now().isoformat()
        log.info("job cancelled: %s", job_id)
        return True

    def retry(self, job_id: str) -> Job | None:
        """Retry a failed or errored job. Creates a new Job."""
        with self._lock:
            original = self._jobs.get(job_id)
            if original is None:
                return None
            if original.retry_count >= original.max_retries:
                log.warning("max retries reached for %s (%d/%d)", job_id,
                            original.retry_count, original.max_retries)
                return None

            new_job = Job(
                id=self._next_id(),
                task_id=original.task_id,
                status=JobStatus.QUEUED,
                strategy=original.strategy,
                retry_count=original.retry_count + 1,
                max_retries=original.max_retries,
                metadata={**original.metadata, "retry_of": job_id},
            )
            self._jobs[new_job.id] = new_job

        log.info("job retry: %s → %s (attempt %d/%d)", job_id,
                 new_job.id, new_job.retry_count, new_job.max_retries)
        return new_job

    def start(self, job_id: str) -> bool:
        """Mark a job as running."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status not in (JobStatus.PENDING, JobStatus.QUEUED):
                return False
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now().isoformat()
        return True

    def complete(self, job_id: str, result: str = "", error: str = "") -> bool:
        """Mark a job as done or errored."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False
            job.status = JobStatus.ERROR if error else JobStatus.DONE
            job.result = result
            job.error = error
            job.completed_at = datetime.now().isoformat()
        return True

    # ── queries ──────────────────────────────────────────────────────────

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())

    def list_by_task(self, task_id: str) -> list[Job]:
        with self._lock:
            return [j for j in self._jobs.values() if j.task_id == task_id]

    def active(self) -> list[Job]:
        with self._lock:
            return [j for j in self._jobs.values() if j.is_running]

    def count_by_status(self) -> dict[str, int]:
        with self._lock:
            counts: dict[str, int] = {}
            for j in self._jobs.values():
                counts[j.status.value] = counts.get(j.status.value, 0) + 1
            return counts
