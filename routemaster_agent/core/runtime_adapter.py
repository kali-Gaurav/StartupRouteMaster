import asyncio
import time
import logging
from pathlib import Path
from typing import Dict, Any

from routemaster_agent.core.reasoning_controller import ReasoningController as CoreReasoningController
from routemaster_agent.skills.skill_retrieval import SkillRetriever, SkillExecutor
from routemaster_agent.ai.gemini_client import GeminiClient

logger = logging.getLogger(__name__)


class RuntimeReasoningAdapter:
    """Adapter that exposes a runtime-friendly ReasoningController API.

    - Provides `initialize()` and `execute_task()` used by scheduler.
    - Applies a timeout guard, basic telemetry, and uses SkillRetriever/Executor.
    """

    def __init__(self, skill_registry_path: str = None, timeout_seconds: int = 15):
        self.skill_registry_path = skill_registry_path or ("datasets/skill_registry.json")
        # choose mock if available
        if not Path(self.skill_registry_path).exists() and Path("datasets/mock_skill_registry.json").exists():
            self.skill_registry_path = "datasets/mock_skill_registry.json"

        # core controller uses a simple skill-first loop
        self.controller = CoreReasoningController(
            skill_retriever=SkillRetriever(skill_registry_file=self.skill_registry_path),
            skill_executor=SkillExecutor(navigator_ai=None),
            gemini_client=GeminiClient(),
            vision_ai=GeminiClient(),
            skill_registry_path=self.skill_registry_path,
        )

        self.timeout_seconds = timeout_seconds

    async def initialize(self):
        # Core controller has no async initialize; keep for compatibility
        return

    async def execute_task(self, task_definition: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task via the core ReasoningController with timeout and telemetry."""
        start = time.monotonic()
        try:
            coro = self.controller.reason_and_act(page=task_definition.get('page'), task=task_definition.get('type'), threshold=task_definition.get('threshold', 0.65))
            result = await asyncio.wait_for(coro, timeout=self.timeout_seconds)
        except asyncio.TimeoutError:
            logger.warning(f"ReasoningController timed out after {self.timeout_seconds}s for task {task_definition.get('id')}")
            # try a best-effort Gemini fallback
            try:
                gem = GeminiClient()
                actions = await gem.propose_actions(task_definition.get('page'), {'task': task_definition.get('type')})
            except Exception:
                actions = []
            result = {'success': False, 'fallback': True, 'reason': 'timeout', 'actions': actions}
        except Exception as e:
            logger.exception(f"Reasoning adapter error: {e}")
            result = {'success': False, 'fallback': False, 'reason': str(e)}

        duration = time.monotonic() - start
        # Telemetry (minimal): source, success, duration
        telemetry = {
            'task_id': task_definition.get('id'),
            'task_type': task_definition.get('type'),
            'duration_s': round(duration, 3),
            'success': result.get('success', False),
            'from_skill': result.get('from_skill'),
            'fallback': result.get('fallback', False),
        }
        logger.info(f"Reasoning execution telemetry: {telemetry}")
        result['_telemetry'] = telemetry
        return result


__all__ = ['RuntimeReasoningAdapter']
