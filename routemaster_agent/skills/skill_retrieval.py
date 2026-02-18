"""Skill Retrieval Engine — match page states to relevant skills.

Matches current page context → similar recorded skills → execute or fallback to Gemini.

This is the core of the learned agent transition:
  Page state → skill retrieval → if match: execute skill
                              → if nomatch: Gemini fallback
"""
from typing import Dict, Any, List, Optional, Tuple
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class SkillRetriever:
    """Retrieve and rank skills based on page/task context."""

    def __init__(self, skill_registry_file: str = 'datasets/skill_registry.json'):
        self.registry_file = Path(skill_registry_file)
        self.registry = self._load_registry()
        self.skills_by_context = self._index_by_context()

    def _load_registry(self) -> Dict[str, Any]:
        """Load skill registry from disk."""
        if not self.registry_file.exists():
            logger.warning(f"Skill registry not found: {self.registry_file}")
            return {'skills': [], 'by_context': {}}
        try:
            with open(self.registry_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load registry: {e}")
            return {'skills': [], 'by_context': {}}

    def _index_by_context(self) -> Dict[str, List[Dict[str, Any]]]:
        """Index skills by context for fast lookup."""
        by_context = {}
        for skill in self.registry.get('skills', []):
            context = skill.get('context', 'generic')
            if context not in by_context:
                by_context[context] = []
            by_context[context].append(skill)
        return by_context

    async def retrieve_skills(
        self,
        context: str,
        task: Optional[str] = None,
        confidence_threshold: float = 0.7,
        max_results: int = 3,
    ) -> List[Dict[str, Any]]:
        """Retrieve skills matching context and task.

        Args:
            context: Page context (e.g., 'ntes_schedule', 'booking_search')
            task: Optional task description for rank
- ing
            confidence_threshold: Minimum skill confidence to return
            max_results: Maximum skills to return

        Returns:
            List of ranked skill records
        """
        candidates = []

        # Exact context match
        if context in self.skills_by_context:
            candidates.extend(self.skills_by_context[context])

        # Fallback to generic skills
        if not candidates and 'generic_page' in self.skills_by_context:
            candidates.extend(self.skills_by_context['generic_page'])

        # Rank by confidence + task relevance
        for skill in candidates:
            metrics = skill.get('metrics', {})
            score = metrics.get('success_rate', 0.5)

            # Boost score if task matches
            if task and task.lower() in skill.get('skill_name', '').lower():
                score += 0.2

            skill['_retrieval_score'] = score

        # Filter by threshold and sort
        candidates = [s for s in candidates if s.get('_retrieval_score', 0) >= confidence_threshold]
        candidates.sort(key=lambda s: s.get('_retrieval_score', 0), reverse=True)

        logger.info(f"Retrieved {len(candidates)} skills for context={context}, task={task}")
        return candidates[:max_results]

    async def get_best_skill(
        self, context: str, task: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get the single best-matching skill."""
        results = await self.retrieve_skills(context, task, max_results=1)
        return results[0] if results else None

    def extract_selector_ranking(self) -> List[Dict[str, Any]]:
        """Get selector effectiveness rankings from registry."""
        return self.registry.get('selector_stats', {})

    def get_context_summary(self, context: str) -> Dict[str, Any]:
        """Get summary stats for a context."""
        skills = self.skills_by_context.get(context, [])
        if not skills:
            return {'context': context, 'skill_count': 0}

        avg_success = sum(s.get('metrics', {}).get('success_rate', 0) for s in skills) / len(skills)
        avg_time = sum(s.get('metrics', {}).get('avg_time_ms', 0) for s in skills) / len(skills)

        return {
            'context': context,
            'skill_count': len(skills),
            'avg_success_rate': round(avg_success, 3),
            'avg_time_ms': int(avg_time),
        }


class SkillExecutor:
    """Execute a skill (action sequence) autonomously on a page."""

    def __init__(self, navigator_ai=None):
        """Initialize executor with NavigatorAI for executing actions."""
        self.navigator = navigator_ai

    async def execute_skill(self, skill: Dict[str, Any], page=None) -> Dict[str, Any]:
        """Execute a skill's action sequence on a page.

        Args:
            skill: Skill record from registry
            page: Playwright page object

        Returns:
            {
                'success': bool,
                'steps_executed': int,
                'reason': str,
                'errors': []
            }
        """
        if not self.navigator:
            return {'success': False, 'reason': 'Navigator not available', 'steps_executed': 0, 'errors': []}

        action_sequence = skill.get('action_sequence', [])
        errors = []
        steps_executed = 0

        logger.info(f"Executing skill: {skill.get('skill_name')} ({len(action_sequence)} actions)")

        try:
            for step_idx, action in enumerate(action_sequence):
                action_type = action.get('type')

                try:
                    if action_type == 'input':
                        selector = action.get('selector')
                        value = action.get('value')
                        if selector and value:
                            element = page.locator(selector)
                            await self.navigator.fill_input_and_trigger_event(page, element, value)
                            steps_executed += 1
                        else:
                            errors.append(f"Step {step_idx}: input missing selector or value")

                    elif action_type == 'click':
                        selector = action.get('selector')
                        if selector:
                            await page.click(selector)
                            steps_executed += 1
                        else:
                            errors.append(f"Step {step_idx}: click missing selector")

                    elif action_type == 'select':
                        selector = action.get('selector')
                        value = action.get('value')
                        if selector and value:
                            await self.navigator.handle_dropdown_selection(page, selector, value)
                            steps_executed += 1
                        else:
                            errors.append(f"Step {step_idx}: select missing selector or value")

                    elif action_type == 'scroll':
                        max_scrolls = action.get('max_scrolls', 5)
                        await self.navigator.smart_scroll(page, max_scrolls=max_scrolls)
                        steps_executed += 1

                    elif action_type == 'wait':
                        wait_for = action.get('wait_for')
                        if wait_for:
                            await page.wait_for_selector(wait_for, timeout=5000)
                            steps_executed += 1

                except Exception as e:
                    errors.append(f"Step {step_idx} ({action_type}): {str(e)}")
                    # Continue to next action rather than aborting

        except Exception as e:
            return {
                'success': False,
                'reason': f'Skill execution failed: {str(e)}',
                'steps_executed': steps_executed,
                'errors': errors,
            }

        success = len(errors) == 0
        return {
            'success': success,
            'steps_executed': steps_executed,
            'total_steps': len(action_sequence),
            'reason': 'Skill executed successfully' if success else 'Some steps failed (see errors)',
            'errors': errors,
        }


if __name__ == '__main__':
    import asyncio

    async def test_retrieval():
        retriever = SkillRetriever()
        
        # Test retrieval
        skills = await retriever.retrieve_skills('ntes_schedule', task='train search')
        print(f"Retrieved {len(skills)} skills for ntes_schedule")
        for skill in skills:
            print(f"  - {skill.get('skill_name')} (score: {skill.get('_retrieval_score', 'N/A')})")

        # Context summary
        summary = retriever.get_context_summary('ntes_schedule')
        print(f"\nContext summary: {json.dumps(summary, indent=2)}")

    asyncio.run(test_retrieval())
