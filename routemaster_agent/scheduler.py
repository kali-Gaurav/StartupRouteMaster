"""
Autonomous Scheduler - Handles scheduled execution of tasks.

Supports cron-like scheduling for monthly updates, daily maintenance, etc.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from typing import Dict, Any, Optional
import asyncio

from .ai.planner import TaskPlanner
from routemaster_agent.core.runtime_adapter import RuntimeReasoningAdapter
from .ai.agent_state_manager import agent_state_manager, AgentState


class AutonomousScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.planner = TaskPlanner()
        # Use the core ReasoningController via the runtime adapter so skills drive execution
        self.controller = RuntimeReasoningAdapter()
        self.scheduled_jobs = {}

    async def initialize(self):
        """Initialize scheduler and reasoning controller."""
        await self.controller.initialize()
        self._setup_default_schedules()

    def _setup_default_schedules(self):
        """Setup default scheduled tasks."""
        self.schedule_monthly_update()
        self.schedule_daily_reliability()
        self.schedule_hourly_live_checks()
        self.schedule_weekly_maintenance()

    def schedule_monthly_update(self):
        """Schedule monthly bulk train updates."""
        job = self.scheduler.add_job(
            self._execute_monthly_update,
            CronTrigger(day=1, hour=2, minute=0),
            id='monthly_train_update',
            name='Monthly Train Schedule Update',
            replace_existing=True
        )
        self.scheduled_jobs['monthly_train_update'] = job

    def schedule_daily_reliability(self):
        """Schedule daily reliability computation."""
        job = self.scheduler.add_job(
            self._execute_daily_reliability,
            CronTrigger(hour=3, minute=0),
            id='daily_reliability',
            name='Daily Reliability Computation',
            replace_existing=True
        )
        self.scheduled_jobs['daily_reliability'] = job

    def schedule_hourly_live_checks(self):
        """Schedule hourly live status checks."""
        job = self.scheduler.add_job(
            self._execute_hourly_live_checks,
            CronTrigger(minute=0),
            id='hourly_live_checks',
            name='Hourly Live Status Checks',
            replace_existing=True
        )
        self.scheduled_jobs['hourly_live_checks'] = job

    def schedule_weekly_maintenance(self):
        """Schedule weekly maintenance."""
        job = self.scheduler.add_job(
            self._execute_weekly_maintenance,
            CronTrigger(day_of_week=6, hour=4, minute=0),
            id='weekly_maintenance',
            name='Weekly System Maintenance',
            replace_existing=True
        )
        self.scheduled_jobs['weekly_maintenance'] = job

    async def _execute_monthly_update(self):
        """Execute monthly train update task."""
        if not agent_state_manager.can_accept_commands():
            print("Agent busy, skipping monthly update")
            return

        task_def = {
            'id': f"monthly_update_{datetime.utcnow().timestamp()}",
            'type': 'update_all_trains',
            'parameters': {},
            'priority': 'medium'
        }

        agent_state_manager.transition_to(AgentState.PLANNING, task_id=task_def['id'])
        try:
            result = await self.controller.execute_task(task_def)
            print(f"Monthly update completed: {result}")
        except Exception as e:
            print(f"Monthly update failed: {e}")
            agent_state_manager.transition_to(AgentState.ERROR_RECOVERY)

    async def _execute_daily_reliability(self):
        """Execute daily reliability computation."""
        print("Executing daily reliability computation")

    async def _execute_hourly_live_checks(self):
        """Execute hourly live status checks for active trains."""
        active_trains = self._get_active_trains()

        for train_no in active_trains[:5]:
            task_def = {
                'id': f"live_check_{train_no}_{datetime.utcnow().timestamp()}",
                'type': 'collect_live_status',
                'parameters': {'train_number': train_no},
                'priority': 'high'
            }

            try:
                result = await self.controller.execute_task(task_def)
                print(f"Live check for {train_no}: {result}")
                await asyncio.sleep(10)
            except Exception as e:
                print(f"Live check failed for {train_no}: {e}")

    async def _execute_weekly_maintenance(self):
        """Execute weekly maintenance tasks."""
        task_def = {
            'id': f"weekly_maint_{datetime.utcnow().timestamp()}",
            'type': 'monthly_maintenance',
            'parameters': {},
            'priority': 'low'
        }

        try:
            result = await self.controller.execute_task(task_def)
            print(f"Weekly maintenance completed: {result}")
        except Exception as e:
            print(f"Weekly maintenance failed: {e}")

    def _get_active_trains(self) -> list:
        """Get list of trains that need live monitoring."""
        return ['12951', '12952', '11603', '12425']

    def add_custom_schedule(self, task_type: str, cron_expression: str, parameters: Dict[str, Any] = None):
        """Add a custom scheduled task."""
        job_id = f"custom_{task_type}_{datetime.utcnow().timestamp()}"

        job = self.scheduler.add_job(
            self._execute_custom_task,
            CronTrigger.from_crontab(cron_expression),
            id=job_id,
            name=f"Custom {task_type}",
            args=[task_type, parameters or {}],
            replace_existing=True
        )

        self.scheduled_jobs[job_id] = job
        return job_id

    async def _execute_custom_task(self, task_type: str, parameters: Dict[str, Any]):
        """Execute a custom scheduled task."""
        task_def = {
            'id': f"custom_{task_type}_{datetime.utcnow().timestamp()}",
            'type': task_type,
            'parameters': parameters,
            'priority': 'medium'
        }

        try:
            result = await self.controller.execute_task(task_def)
            print(f"Custom task {task_type} completed: {result}")
        except Exception as e:
            print(f"Custom task {task_type} failed: {e}")

    def start(self):
        """Start the scheduler."""
        self.scheduler.start()
        print("Autonomous scheduler started")

    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
        print("Autonomous scheduler stopped")

    def get_scheduled_jobs(self) -> Dict[str, Any]:
        """Get information about scheduled jobs."""
        jobs_info = {}
        for job_id, job in self.scheduled_jobs.items():
            jobs_info[job_id] = {
                'name': job.name,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            }
        return jobs_info

    def pause_job(self, job_id: str):
        """Pause a scheduled job."""
        if job_id in self.scheduled_jobs:
            self.scheduled_jobs[job_id].pause()

    def resume_job(self, job_id: str):
        """Resume a paused job."""
        if job_id in self.scheduled_jobs:
            self.scheduled_jobs[job_id].resume()

    def remove_job(self, job_id: str):
        """Remove a scheduled job."""
        if job_id in self.scheduled_jobs:
            self.scheduler.remove_job(job_id)
            del self.scheduled_jobs[job_id]
