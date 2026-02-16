"""
Task Planner AI - Decides what data to collect, when, and how.

High-level planning before execution.
"""

import json
from typing import Dict, Any, List
from datetime import datetime, timedelta

from .gemini_client import GeminiClient


class TaskPlanner:
    def __init__(self):
        self.gemini = GeminiClient()
        self.predefined_tasks = {
            'update_train_schedule': self._plan_schedule_update,
            'collect_live_status': self._plan_live_status,
            'check_seat_availability': self._plan_seat_check,
            'update_all_trains': self._plan_bulk_update,
            'monthly_maintenance': self._plan_monthly_maintenance
        }

    async def plan_task(self, task_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a detailed execution plan for a task.

        Args:
            task_request: Raw task request (e.g., {'type': 'update_train_schedule', 'train_number': '12951'})

        Returns:
            Detailed plan with steps, resources, timeline
        """
        task_type = task_request.get('type')
        if task_type in self.predefined_tasks:
            return await self.predefined_tasks[task_type](task_request)
        else:
            return await self._plan_custom_task(task_request)

    async def _plan_schedule_update(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Plan for updating a train schedule."""
        train_number = request.get('train_number')
        date = request.get('date', 'today')

        plan = {
            'task_id': f"schedule_update_{train_number}_{datetime.utcnow().timestamp()}",
            'type': 'update_train_schedule',
            'priority': 'high',
            'estimated_duration': 120,
            'resources_needed': ['browser', 'ntes_website', 'database'],
            'steps': [
                {
                    'phase': 'navigation',
                    'action': 'navigate_to_ntes',
                    'description': 'Open NTES website and navigate to train schedule section'
                },
                {
                    'phase': 'input',
                    'action': 'enter_train_number',
                    'description': f'Enter train number {train_number}',
                    'parameters': {'train_number': train_number}
                },
                {
                    'phase': 'extraction',
                    'action': 'extract_schedule_table',
                    'description': 'Extract train schedule data from results table'
                },
                {
                    'phase': 'validation',
                    'action': 'validate_schedule_data',
                    'description': 'Validate extracted data for consistency'
                },
                {
                    'phase': 'storage',
                    'action': 'store_to_database',
                    'description': 'Update database with new schedule data'
                }
            ],
            'fallback_strategies': [
                'use_irctc_website',
                'fallback_to_cached_data',
                'manual_verification_required'
            ],
            'success_criteria': [
                'schedule_data_extracted',
                'validation_passed',
                'database_updated'
            ],
            'risk_assessment': {
                'website_down': 'medium',
                'data_unavailable': 'low',
                'extraction_failure': 'medium'
            }
        }

        refined_plan = await self._refine_plan_with_ai(plan, request)
        return refined_plan

    async def _plan_live_status(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Plan for collecting live train status."""
        train_number = request.get('train_number')

        plan = {
            'task_id': f"live_status_{train_number}_{datetime.utcnow().timestamp()}",
            'type': 'collect_live_status',
            'priority': 'urgent',
            'estimated_duration': 60,
            'resources_needed': ['browser', 'ntes_website'],
            'steps': [
                {'phase': 'navigation', 'action': 'navigate_to_live_status'},
                {'phase': 'input', 'action': 'enter_train_number'},
                {'phase': 'extraction', 'action': 'extract_live_data'},
                {'phase': 'validation', 'action': 'validate_live_data'},
                {'phase': 'storage', 'action': 'store_live_status'}
            ],
            'real_time_requirement': True,
            'cache_strategy': 'no_cache'
        }

        return await self._refine_plan_with_ai(plan, request)

    async def _plan_seat_check(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Plan for checking seat availability."""
        plan = {
            'task_id': f"seat_check_{datetime.utcnow().timestamp()}",
            'type': 'check_seat_availability',
            'priority': 'high',
            'estimated_duration': 90,
            'resources_needed': ['browser', 'irctc_website', 'disha_chatbot'],
            'steps': [
                {'phase': 'navigation', 'action': 'navigate_to_booking'},
                {'phase': 'input', 'action': 'enter_journey_details'},
                {'phase': 'extraction', 'action': 'extract_availability'},
                {'phase': 'validation', 'action': 'validate_availability'},
                {'phase': 'storage', 'action': 'store_availability'}
            ]
        }

        return await self._refine_plan_with_ai(plan, request)

    async def _plan_bulk_update(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Plan for updating all trains (monthly maintenance)."""
        plan = {
            'task_id': f"bulk_update_{datetime.utcnow().timestamp()}",
            'type': 'update_all_trains',
            'priority': 'medium',
            'estimated_duration': 3600,
            'resources_needed': ['browser_pool', 'database', 'scheduler'],
            'steps': [
                {'phase': 'planning', 'action': 'get_train_list'},
                {'phase': 'execution', 'action': 'parallel_updates'},
                {'phase': 'consolidation', 'action': 'merge_results'},
                {'phase': 'reporting', 'action': 'generate_report'}
            ],
            'parallel_execution': True,
            'batch_size': 10,
            'retry_policy': {'max_attempts': 3, 'backoff': 'exponential'}
        }

        return plan

    async def _plan_monthly_maintenance(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Plan for monthly system maintenance."""
        plan = {
            'task_id': f"monthly_maint_{datetime.utcnow().timestamp()}",
            'type': 'monthly_maintenance',
            'priority': 'low',
            'scheduled_execution': True,
            'steps': [
                {'phase': 'analysis', 'action': 'analyze_drift'},
                {'phase': 'cleanup', 'action': 'clean_old_data'},
                {'phase': 'optimization', 'action': 'update_selectors'},
                {'phase': 'reporting', 'action': 'generate_monthly_report'}
            ]
        }

        return plan

    async def _plan_custom_task(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Plan for custom/unrecognized tasks using AI."""
        prompt = f"""
Create a detailed execution plan for this custom task:

Task Request: {json.dumps(request)}

Return a JSON plan with:
- task_id
- type
- priority (low/medium/high/urgent)
- estimated_duration (seconds)
- resources_needed
- steps (array of phase, action, description)
- success_criteria
- risk_assessment

Make it realistic for railway data collection.
"""

        ai_plan = await self.gemini.generate(prompt)
        return ai_plan

    async def _refine_plan_with_ai(self, plan: Dict[str, Any], request: Dict[str, Any]) -> Dict[str, Any]:
        """Use Gemini to refine and optimize the plan."""
        prompt = f"""
Refine this task execution plan for railway data collection:

Original Plan: {json.dumps(plan)}

Task Request: {json.dumps(request)}

Consider:
1. Current system capabilities
2. Potential failure points
3. Optimization opportunities
4. Resource constraints

Return refined JSON plan with improvements.
"""

        try:
            refined = await self.gemini.generate(prompt)
            return refined if isinstance(refined, dict) else plan
        except Exception:
            return plan

    def get_available_task_types(self) -> List[str]:
        """Get list of supported task types."""
        return list(self.predefined_tasks.keys())
