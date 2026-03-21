"""Scheduler engine — asyncio loop, tick, directory scanning, workflow execution."""

from __future__ import annotations

import asyncio
import logging
import signal
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from croniter import croniter  # type: ignore[import-untyped]

from binex.scheduler.models import ScheduledWorkflow, SchedulerState
from binex.scheduler.state import record_run, record_skip, save_state

logger = logging.getLogger(__name__)

_RESCAN_INTERVAL = 60  # seconds
_DEFAULT_POLL = 60  # seconds


def scan_directory(directory: Path) -> list[ScheduledWorkflow]:
    """Recursively scan directory for workflow files with a schedule field."""
    results: list[ScheduledWorkflow] = []
    for pattern in ("**/*.yaml", "**/*.yml"):
        for path in directory.rglob(pattern.split("/", 1)[1]):
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
            except Exception:
                logger.warning("Skipping unreadable file: %s", path)
                continue
            if not isinstance(data, dict):
                continue
            schedule = data.get("schedule")
            if not schedule or not isinstance(schedule, str):
                continue
            if not croniter.is_valid(schedule):
                logger.warning("Invalid cron in %s: %r", path, schedule)
                continue
            name = data.get("name", path.stem)
            next_run = datetime.fromtimestamp(
                croniter(schedule, datetime.now(UTC)).get_next(), tz=UTC,
            )
            results.append(ScheduledWorkflow(
                name=name, path=str(path), schedule=schedule, next_run=next_run,
            ))
    return results


class SchedulerEngine:
    """Core scheduler — asyncio loop that ticks, executes due workflows, rescans."""

    def __init__(
        self,
        workflows: list[ScheduledWorkflow],
        state: SchedulerState,
        state_path: Path | None = None,
        scan_dir: Path | None = None,
    ) -> None:
        self.workflows = list(workflows)
        self.state = state
        self._state_path = state_path
        self._scan_dir = scan_dir
        self._running_tasks: dict[str, asyncio.Task[Any]] = {}
        self._shutdown = False
        self._last_rescan = time.monotonic()

    async def run_loop(self) -> None:
        """Main scheduler loop — tick, sleep, repeat."""
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGINT, self._request_shutdown)
        loop.add_signal_handler(signal.SIGTERM, self._request_shutdown)

        logger.info("Scheduler started with %d workflow(s)", len(self.workflows))
        for wf in self.workflows:
            logger.info("  %s [%s] next: %s", wf.name, wf.schedule, wf.next_run)

        try:
            while not self._shutdown:
                await self._tick()
                self._cleanup_finished_tasks()
                await self._maybe_rescan()
                sleep_secs = min(self._seconds_to_next_run(), _DEFAULT_POLL)
                sleep_secs = max(sleep_secs, 1)
                await asyncio.sleep(sleep_secs)
        finally:
            await self._wait_for_running()
            if self._state_path:
                save_state(self.state, self._state_path)

    async def _tick(self) -> None:
        """Check each workflow and execute or skip if due."""
        now = datetime.now(UTC)
        for wf in self.workflows:
            if wf.next_run > now:
                continue
            if wf.name in self._running_tasks:
                logger.warning("Skipping %s — previous run still in progress", wf.name)
                record_skip(self.state, wf.name, "previous_still_running")
                wf.advance_next_run()
                continue
            await self._execute_workflow(wf)

    async def _execute_workflow(self, wf: ScheduledWorkflow) -> None:
        """Launch workflow execution as a background task."""
        logger.info("Executing workflow: %s", wf.name)
        task = asyncio.create_task(self._run_workflow(wf))
        self._running_tasks[wf.name] = task
        wf.advance_next_run()

    async def _run_workflow(self, wf: ScheduledWorkflow) -> None:
        """Actually run the workflow and record result."""
        start = time.monotonic()
        run_id = f"sched-{wf.name}-{int(time.time())}"
        try:
            from binex.cli import get_stores
            from binex.runtime.orchestrator import Orchestrator
            from binex.workflow_spec.loader import load_workflow

            spec = load_workflow(wf.path)
            execution_store, artifact_store = get_stores()
            # Use the standard orchestrator to run the workflow
            orchestrator = Orchestrator(
                artifact_store=artifact_store,
                execution_store=execution_store,
                interactive=False,
            )
            result = await orchestrator.run_workflow(spec)
            duration = time.monotonic() - start
            cost = getattr(result, "total_cost", None)
            raw_status = getattr(result, "status", "completed")
            status = "completed" if raw_status == "completed" else "failed"
            record_run(self.state, wf.name, run_id, status, duration, cost)
            logger.info("Workflow %s %s in %.1fs", wf.name, status, duration)
        except Exception as exc:
            duration = time.monotonic() - start
            record_run(self.state, wf.name, run_id, "failed", duration)
            logger.error("Workflow %s failed: %s", wf.name, exc)

    def _cleanup_finished_tasks(self) -> None:
        """Remove completed tasks from the running set."""
        finished = [name for name, task in self._running_tasks.items() if task.done()]
        for name in finished:
            del self._running_tasks[name]

    async def _maybe_rescan(self) -> None:
        """Re-scan directory for new workflows if enough time has passed."""
        if not self._scan_dir:
            return
        if time.monotonic() - self._last_rescan < _RESCAN_INTERVAL:
            return
        self._last_rescan = time.monotonic()
        new_workflows = scan_directory(self._scan_dir)
        existing_paths = {wf.path for wf in self.workflows}
        for wf in new_workflows:
            if wf.path not in existing_paths:
                self.workflows.append(wf)
                logger.info("Discovered new workflow: %s [%s]", wf.name, wf.schedule)

    def _seconds_to_next_run(self) -> float:
        """Return seconds until the next workflow is due."""
        if not self.workflows:
            return _DEFAULT_POLL
        now = datetime.now(UTC)
        min_delta = min((wf.next_run - now).total_seconds() for wf in self.workflows)
        return max(min_delta, 0)

    def _request_shutdown(self) -> None:
        """Signal the engine to stop after current tick."""
        logger.info("Shutdown requested — finishing in-progress workflows...")
        self._shutdown = True

    async def _wait_for_running(self) -> None:
        """Wait for all currently running workflow tasks to complete."""
        if self._running_tasks:
            logger.info("Waiting for %d running workflow(s)...", len(self._running_tasks))
            await asyncio.gather(*self._running_tasks.values(), return_exceptions=True)


__all__ = ["SchedulerEngine", "scan_directory"]
